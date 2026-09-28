"""维修管理：报修 → 接单 → 完成 / 取消，资产状态跟着走。"""

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from ..core.constants import ACTIVE_ASSIGNMENT_STATUS, REPAIR_STATUS
from ..core.database import now
from ..core.errors import BizError
from ..models import Asset, AssetAssignment, AssetRepair, User
from . import notification as notif
from .asset import viewer_is_admin
from .common import change_asset_status, gen_no, write_log


def _row(db: Session, r: AssetRepair) -> dict:
    asset = db.get(Asset, r.asset_id)
    reporter = db.get(User, r.reporter_id)
    return {
        "id": r.id,
        "repair_no": r.repair_no,
        "asset_id": r.asset_id,
        "asset_code": asset.asset_code if asset else None,
        "asset_name": asset.asset_name if asset else None,
        "reporter_id": r.reporter_id,
        "reporter_name": reporter.real_name if reporter else None,
        "fault_description": r.fault_description,
        "repair_company": r.repair_company,
        "repair_cost": r.repair_cost,
        "start_time": r.start_time,
        "end_time": r.end_time,
        "repair_result": r.repair_result,
        "status": r.status,
        "status_name": REPAIR_STATUS.get(r.status, r.status),
        "created_at": r.created_at,
    }


def get_repair(db: Session, repair_id: int) -> dict:
    r = db.get(AssetRepair, repair_id)
    if r is None:
        raise BizError("维修记录不存在", 40401)
    return _row(db, r)


def list_repairs(db: Session, page, status: str | None = None, keyword: str | None = None, reporter_id: int | None = None) -> dict:
    cond = []
    if status:
        cond.append(AssetRepair.status == status)
    if reporter_id:
        cond.append(AssetRepair.reporter_id == reporter_id)
    if keyword:
        like = f"%{keyword}%"
        cond.append(
            or_(
                AssetRepair.repair_no.like(like),
                AssetRepair.asset_id.in_(select(Asset.id).where(Asset.asset_name.like(like) | Asset.asset_code.like(like))),
            )
        )
    total = db.scalar(select(func.count()).select_from(AssetRepair).where(*cond)) or 0
    rows = db.scalars(
        select(AssetRepair).where(*cond).order_by(AssetRepair.created_at.desc()).offset(page.offset).limit(page.page_size)
    ).all()
    return page.wrap([_row(db, r) for r in rows], total)


def _has_active_assignment(db: Session, asset_id: int, user_id: int | None = None) -> bool:
    cond = [AssetAssignment.asset_id == asset_id, AssetAssignment.status.in_(ACTIVE_ASSIGNMENT_STATUS)]
    if user_id is not None:
        cond.append(AssetAssignment.user_id == user_id)
    return bool(db.scalar(select(func.count()).select_from(AssetAssignment).where(*cond)))


def create_repair(db: Session, data, user, request=None) -> dict:
    asset = db.get(Asset, data.asset_id)
    if asset is None:
        raise BizError("资产不存在", 40401)
    if asset.status == "SCRAPPED":
        raise BizError("已报废资产不能报修")
    if asset.status in ("PENDING_REPAIR", "REPAIRING"):
        raise BizError("该资产已在维修流程中")
    # 普通用户只能报修自己当前领用的设备；管理员代报修不受限
    if not viewer_is_admin(db, user) and not _has_active_assignment(db, asset.id, user.id):
        raise BizError("只能报修自己当前领用的设备", 40301)

    r = AssetRepair(
        repair_no=gen_no("RP"),
        asset_id=asset.id,
        reporter_id=user.id,
        fault_description=data.fault_description,
        repair_company=data.repair_company,
        status="PENDING",
    )
    change_asset_status(asset, "PENDING_REPAIR")
    db.add(r)
    db.flush()
    notif.send_to_role(
        db,
        ["ADMIN"],
        title="新的维修申请",
        content=f"{user.real_name} 报修 {asset.asset_name}（{asset.asset_code}）：{data.fault_description}",
        notification_type="REPAIR_PENDING",
        related_type="REPAIR",
        related_id=r.id,
    )
    write_log(db, user.id, "REPAIR_CREATE", "REPAIR", r.id, f"提交维修 {r.repair_no}", request)
    db.commit()
    return _row(db, r)


def update_repair(db: Session, repair_id: int, data, operator=None, request=None) -> dict:
    r = db.get(AssetRepair, repair_id)
    if r is None:
        raise BizError("维修记录不存在", 40401)
    for k, v in data.model_dump(exclude_unset=True).items():
        setattr(r, k, v)
    write_log(db, operator.id if operator else None, "REPAIR_UPDATE", "REPAIR", r.id, f"更新维修 {r.repair_no}", request)
    db.commit()
    return _row(db, r)


def start_repair(db: Session, repair_id: int, operator, request=None) -> dict:
    r = db.get(AssetRepair, repair_id)
    if r is None:
        raise BizError("维修记录不存在", 40401)
    if r.status != "PENDING":
        raise BizError(f"该维修单已是「{REPAIR_STATUS.get(r.status, r.status)}」，不能接单")
    asset = db.get(Asset, r.asset_id)
    r.status = "REPAIRING"
    r.start_time = now()
    if asset:
        change_asset_status(asset, "REPAIRING")
    notif.send(
        db,
        receiver_id=r.reporter_id,
        title="维修已接单",
        content=f"{asset.asset_name if asset else ''} 已进入维修中，维修单号 {r.repair_no}",
        notification_type="REPAIR_STARTED",
        related_type="REPAIR",
        related_id=r.id,
    )
    write_log(db, operator.id if operator else None, "REPAIR_START", "REPAIR", r.id, f"维修接单 {r.repair_no}", request)
    db.commit()
    return _row(db, r)


def complete_repair(db: Session, repair_id: int, data, operator, request=None) -> dict:
    r = db.get(AssetRepair, repair_id)
    if r is None:
        raise BizError("维修记录不存在", 40401)
    if r.status != "REPAIRING":
        raise BizError("只有「维修中」的维修单可以完成")
    asset = db.get(Asset, r.asset_id)
    r.status = "COMPLETED"
    r.end_time = now()
    for k, v in data.model_dump(exclude_unset=True).items():
        setattr(r, k, v)
    if asset:
        # 还在原用户手上 → 回到「已领用」；否则回库
        change_asset_status(asset, "BORROWED" if _has_active_assignment(db, asset.id) else "IN_STOCK")
    notif.send(
        db,
        receiver_id=r.reporter_id,
        title="维修已完成",
        content=f"您的设备维修已完成：{r.repair_result or '设备已修复'}",
        notification_type="REPAIR_COMPLETED",
        related_type="REPAIR",
        related_id=r.id,
    )
    write_log(db, operator.id if operator else None, "REPAIR_COMPLETE", "REPAIR", r.id, f"维修完成 {r.repair_no}", request)
    db.commit()
    return _row(db, r)


def cancel_repair(db: Session, repair_id: int, operator, request=None) -> dict:
    r = db.get(AssetRepair, repair_id)
    if r is None:
        raise BizError("维修记录不存在", 40401)
    if r.status not in ("PENDING", "REPAIRING"):
        raise BizError("该维修单已结束，不能取消")
    asset = db.get(Asset, r.asset_id)
    r.status = "CANCELLED"
    r.end_time = now()
    if asset and asset.status in ("PENDING_REPAIR", "REPAIRING"):
        change_asset_status(asset, "BORROWED" if _has_active_assignment(db, asset.id) else "IN_STOCK")
    write_log(db, operator.id if operator else None, "REPAIR_CANCEL", "REPAIR", r.id, f"取消维修 {r.repair_no}", request)
    db.commit()
    return _row(db, r)
