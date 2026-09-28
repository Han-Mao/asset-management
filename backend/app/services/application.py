"""领用申请 + 审批。审批是整个系统最关键的事务。"""

from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..core.constants import APPLICATION_STATUS, ASSET_STATUS
from ..core.database import now
from ..core.errors import BizError
from ..models import Asset, AssetApplication, AssetAssignment, Department, User
from . import notification as notif
from .common import change_asset_status, gen_no, write_log


def _row(db: Session, a: AssetApplication) -> dict:
    applicant = db.get(User, a.applicant_id)
    asset = db.get(Asset, a.asset_id)
    approver = db.get(User, a.approver_id) if a.approver_id else None
    dept = db.scalar(select(Department.department_name).where(Department.id == applicant.department_id)) if applicant else None
    return {
        "id": a.id,
        "application_no": a.application_no,
        "applicant_id": a.applicant_id,
        "applicant_name": applicant.real_name if applicant else None,
        "department_name": dept,
        "asset_id": a.asset_id,
        "asset_code": asset.asset_code if asset else None,
        "asset_name": asset.asset_name if asset else None,
        "reason": a.reason,
        "apply_time": a.apply_time,
        "expected_return_time": a.expected_return_time,
        "status": a.status,
        "status_name": APPLICATION_STATUS.get(a.status, a.status),
        "approver_id": a.approver_id,
        "approver_name": approver.real_name if approver else None,
        "approval_time": a.approval_time,
        "approval_remark": a.approval_remark,
    }


def get_application(db: Session, application_id: int) -> dict:
    a = db.get(AssetApplication, application_id)
    if a is None:
        raise BizError("申请不存在", 40401)
    return _row(db, a)


def list_applications(db: Session, page, status: str | None = None, keyword: str | None = None, applicant_id: int | None = None) -> dict:
    cond = []
    if status:
        cond.append(AssetApplication.status == status)
    if applicant_id:
        cond.append(AssetApplication.applicant_id == applicant_id)
    if keyword:
        like = f"%{keyword}%"
        sub = select(User.id).where(User.real_name.like(like))
        sub_asset = select(Asset.id).where(or_(Asset.asset_name.like(like), Asset.asset_code.like(like)))
        cond.append(
            or_(
                AssetApplication.application_no.like(like),
                AssetApplication.applicant_id.in_(sub),
                AssetApplication.asset_id.in_(sub_asset),
            )
        )
    total = db.scalar(select(func.count()).select_from(AssetApplication).where(*cond)) or 0
    rows = db.scalars(
        select(AssetApplication)
        .where(*cond)
        .order_by(AssetApplication.apply_time.desc())
        .offset(page.offset)
        .limit(page.page_size)
    ).all()
    return page.wrap([_row(db, a) for a in rows], total)


def create_application(db: Session, data, user, request=None) -> dict:
    asset = db.get(Asset, data.asset_id)
    if asset is None:
        raise BizError("资产不存在", 40401)
    if asset.status != "IN_STOCK":
        raise BizError(f"该资产当前为「{ASSET_STATUS.get(asset.status, asset.status)}」，不可申请领用")
    if data.expected_return_time <= now():
        raise BizError("预计归还时间必须晚于当前时间")
    dup = db.scalar(
        select(func.count())
        .select_from(AssetApplication)
        .where(
            AssetApplication.applicant_id == user.id,
            AssetApplication.asset_id == asset.id,
            AssetApplication.status == "PENDING",
        )
    )
    if dup:
        raise BizError("您已提交过该资产的申请，请等待审批")

    app = AssetApplication(
        application_no=gen_no("AP"),
        applicant_id=user.id,
        asset_id=asset.id,
        reason=data.reason,
        expected_return_time=data.expected_return_time,
        status="PENDING",
    )
    db.add(app)
    db.flush()
    notif.send_to_role(
        db,
        ["ADMIN"],
        title="新的领用申请待审批",
        content=f"{user.real_name} 申请领用 {asset.asset_name}（{asset.asset_code}），理由：{data.reason}",
        notification_type="APPLICATION_PENDING",
        related_type="APPLICATION",
        related_id=app.id,
    )
    write_log(db, user.id, "APPLICATION_CREATE", "APPLICATION", app.id, f"提交领用申请 {app.application_no}", request)
    db.commit()
    return _row(db, app)


def cancel_application(db: Session, application_id: int, user, request=None) -> dict:
    a = db.get(AssetApplication, application_id)
    if a is None:
        raise BizError("申请不存在", 40401)
    if a.applicant_id != user.id:
        raise BizError("只能取消自己的申请", 40301)
    if a.status != "PENDING":
        raise BizError("该申请已处理，不能取消")
    a.status = "CANCELLED"
    write_log(db, user.id, "APPLICATION_CANCEL", "APPLICATION", a.id, f"取消申请 {a.application_no}", request)
    db.commit()
    return _row(db, a)


def _do_approve(db: Session, application_id: int, approver, remark: str | None, request=None, approved: bool = True) -> dict:
    # ① 锁申请 ② 锁资产 ③ 校验状态 ④ 同事务改申请/资产/建档/发信/日志
    a = db.execute(
        select(AssetApplication).where(AssetApplication.id == application_id).with_for_update()
    ).scalar_one_or_none()
    if a is None:
        raise BizError("申请不存在", 40401)
    if a.status != "PENDING":
        raise BizError(f"该申请已是「{APPLICATION_STATUS.get(a.status, a.status)}」状态，不能重复审批")

    if not approved:
        a.status = "REJECTED"
        a.approver_id = approver.id
        a.approval_time = now()
        a.approval_remark = remark
        notif.send(
            db,
            receiver_id=a.applicant_id,
            title="领用申请被驳回",
            content=f"您申请的 {a.application_no} 已被驳回。{('原因：' + remark) if remark else ''}",
            notification_type="APPLICATION_REJECTED",
            related_type="APPLICATION",
            related_id=a.id,
        )
        write_log(db, approver.id, "APPLICATION_REJECT", "APPLICATION", a.id, f"驳回申请 {a.application_no}", request)
        db.commit()
        return _row(db, a)

    asset = db.execute(select(Asset).where(Asset.id == a.asset_id).with_for_update()).scalar_one_or_none()
    if asset is None:
        raise BizError("资产不存在", 40401)
    if asset.status != "IN_STOCK":
        raise BizError(f"资产当前为「{ASSET_STATUS.get(asset.status, asset.status)}」，不可领用")

    a.status = "APPROVED"
    a.approver_id = approver.id
    a.approval_time = now()
    a.approval_remark = remark
    change_asset_status(asset, "BORROWED")

    assignment = AssetAssignment(
        asset_id=asset.id,
        user_id=a.applicant_id,
        application_id=a.id,
        expected_return_time=a.expected_return_time,
        status="ACTIVE",
    )
    db.add(assignment)
    db.flush()

    notif.send(
        db,
        receiver_id=a.applicant_id,
        title="领用申请已通过",
        content=f"您申请的 {asset.asset_name}（{asset.asset_code}）已审批通过，请在 {a.expected_return_time:%Y-%m-%d} 前归还。",
        notification_type="APPLICATION_APPROVED",
        related_type="APPLICATION",
        related_id=a.id,
    )
    write_log(db, approver.id, "APPLICATION_APPROVE", "APPLICATION", a.id, f"审批通过 {a.application_no}", request)

    try:
        db.commit()
    except IntegrityError:
        # 数据库唯一索引 uq_active_asset_assignment 兜底：同一资产不能被重复领用
        db.rollback()
        raise BizError("该资产已被其他人领用，请刷新后重试") from None
    return _row(db, a)


def approve_application(db: Session, application_id: int, approver, remark: str | None, request=None) -> dict:
    return _do_approve(db, application_id, approver, remark, request, approved=True)


def reject_application(db: Session, application_id: int, approver, remark: str | None, request=None) -> dict:
    return _do_approve(db, application_id, approver, remark, request, approved=False)


def batch_approve(db: Session, application_ids: list[int], approver, remark: str | None, request=None) -> dict:
    """批量审批：逐条独立事务，一条失败不影响其他，返回成功/失败明细。"""
    ok, failed = [], []
    for aid in application_ids:
        try:
            approve_application(db, aid, approver, remark, request)
            ok.append(aid)
        except BizError as exc:
            failed.append({"id": aid, "message": exc.message})
    return {"success": ok, "failed": failed}
