"""领用记录：资产的历史领用关系 + 归还。"""

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from ..core.constants import ACTIVE_ASSIGNMENT_STATUS
from ..core.database import now
from ..core.errors import BizError
from ..models import Asset, AssetAssignment, User
from . import notification as notif
from .common import change_asset_status, write_log
from .system import user_roles


def _row(db: Session, s: AssetAssignment) -> dict:
    asset = db.get(Asset, s.asset_id)
    user = db.get(User, s.user_id)
    return {
        "id": s.id,
        "asset_id": s.asset_id,
        "asset_code": asset.asset_code if asset else None,
        "asset_name": asset.asset_name if asset else None,
        "user_id": s.user_id,
        "user_name": user.real_name if user else None,
        "application_id": s.application_id,
        "assign_time": s.assign_time,
        "expected_return_time": s.expected_return_time,
        "actual_return_time": s.actual_return_time,
        "status": s.status,
        "remark": s.remark,
        "days_left": (s.expected_return_time - now()).days if s.status in ACTIVE_ASSIGNMENT_STATUS else None,
    }


def get_assignment(db: Session, assignment_id: int) -> dict:
    s = db.get(AssetAssignment, assignment_id)
    if s is None:
        raise BizError("领用记录不存在", 40401)
    return _row(db, s)


def list_assignments(
    db: Session, page, status: str | None = None, keyword: str | None = None, user_id: int | None = None
) -> dict:
    cond = []
    if status:
        cond.append(AssetAssignment.status == status)
    if user_id:
        cond.append(AssetAssignment.user_id == user_id)
    if keyword:
        like = f"%{keyword}%"
        cond.append(
            or_(
                AssetAssignment.asset_id.in_(select(Asset.id).where(Asset.asset_name.like(like) | Asset.asset_code.like(like))),
                AssetAssignment.user_id.in_(select(User.id).where(User.real_name.like(like))),
            )
        )
    total = db.scalar(select(func.count()).select_from(AssetAssignment).where(*cond)) or 0
    rows = db.scalars(
        select(AssetAssignment)
        .where(*cond)
        .order_by(AssetAssignment.status.asc(), AssetAssignment.expected_return_time.asc())
        .offset(page.offset)
        .limit(page.page_size)
    ).all()
    return page.wrap([_row(db, s) for s in rows], total)


def return_asset(db: Session, assignment_id: int, data, operator, request=None) -> dict:
    s = db.execute(
        select(AssetAssignment).where(AssetAssignment.id == assignment_id).with_for_update()
    ).scalar_one_or_none()
    if s is None:
        raise BizError("领用记录不存在", 40401)
    if s.status not in ACTIVE_ASSIGNMENT_STATUS:
        raise BizError("该设备已归还，不能重复归还")
    if operator.id != s.user_id and "ADMIN" not in user_roles(db, operator.id):
        raise BizError("只能归还自己的设备", 40301)

    asset = db.execute(select(Asset).where(Asset.id == s.asset_id).with_for_update()).scalar_one_or_none()
    s.status = "RETURNED"
    s.actual_return_time = now()
    s.remark = data.remark or s.remark
    if asset is not None and asset.status == "BORROWED":
        # 归还时发现故障 → 直接进待维修，而不是回在库
        change_asset_status(asset, "PENDING_REPAIR" if data.to_repair else "IN_STOCK")
    write_log(db, operator.id, "ASSIGNMENT_RETURN", "ASSET", s.asset_id, f"归还设备（领用记录 {s.id}）", request)
    if asset is not None:
        notif.send_to_role(
            db,
            ["ADMIN"],
            title="设备已归还",
            content=f"{asset.asset_name}（{asset.asset_code}）已归还入库"
            + (f"，备注：{data.remark}" if data.remark else ""),
            notification_type="ASSET_RETURNED",
            related_type="ASSIGNMENT",
            related_id=s.id,
        )
    db.commit()
    return _row(db, s)


def my_assignments(db: Session, page, user_id: int, status: str | None = None) -> dict:
    return list_assignments(db, page, status=status, user_id=user_id)


def overdue_status_sync(db: Session) -> int:
    """过了应归还时间仍是 ACTIVE 的领用记录刷成 OVERDUE；资产状态保持 BORROWED。"""
    rows = db.scalars(
        select(AssetAssignment).where(
            AssetAssignment.status == "ACTIVE",
            AssetAssignment.expected_return_time < now(),
        )
    ).all()
    for s in rows:
        s.status = "OVERDUE"
    db.commit()
    return len(rows)
