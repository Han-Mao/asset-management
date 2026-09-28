from io import BytesIO

from sqlalchemy import and_, func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, aliased

from ..core.config import settings
from ..core.constants import ACTIVE_ASSIGNMENT_STATUS, ASSET_STATUS
from ..core.database import now
from ..core.errors import BizError
from ..models import (
    Asset,
    AssetApplication,
    AssetAssignment,
    AssetCategory,
    AssetRepair,
    OperationLog,
    User,
)
from .common import change_asset_status, next_asset_code, write_log


def viewer_is_admin(db: Session, user) -> bool:
    from .system import user_roles

    return "ADMIN" in user_roles(db, user.id)


def get_accessible_asset(db: Session, asset_id: int, viewer=None) -> Asset:
    """资产访问权限的唯一入口：详情/生命周期/二维码都用它，别各写一套判断。

    管理员看全部；普通用户只能看「在库资产」和「自己当前领用的资产」。
    """
    asset = db.get(Asset, asset_id)
    if asset is None:
        raise BizError("资产不存在", 40401)
    if viewer is None or viewer_is_admin(db, viewer):
        return asset
    if asset.status == "IN_STOCK":
        return asset
    if current_assignment_map(db, [asset.id]).get(asset.id, {}).get("borrower_id") == viewer.id:
        return asset
    raise BizError("无权查看该资产", 40301)


def current_assignment_map(db: Session, asset_ids: list[int]) -> dict[int, dict]:
    """一次查出这批资产当前的领用人/应归还时间，避免 N+1。"""
    if not asset_ids:
        return {}
    rows = db.execute(
        select(AssetAssignment, User.real_name)
        .join(User, User.id == AssetAssignment.user_id)
        .where(
            AssetAssignment.asset_id.in_(asset_ids),
            AssetAssignment.status.in_(ACTIVE_ASSIGNMENT_STATUS),
        )
    ).all()
    return {
        a.asset_id: {
            "assignment_id": a.id,
            "borrower_id": a.user_id,
            "borrower_name": name,
            "assign_time": a.assign_time,
            "expected_return_time": a.expected_return_time,
            "assignment_status": a.status,
            "days_left": (a.expected_return_time - now()).days,
        }
        for a, name in rows
    }


def _row(asset: Asset, category_name: str | None, cur: dict | None) -> dict:
    return {
        "id": asset.id,
        "asset_code": asset.asset_code,
        "asset_name": asset.asset_name,
        "category_id": asset.category_id,
        "category_name": category_name,
        "brand": asset.brand,
        "model": asset.model,
        "serial_number": asset.serial_number,
        "purchase_date": asset.purchase_date,
        "purchase_price": asset.purchase_price,
        "warranty_expire_date": asset.warranty_expire_date,
        "status": asset.status,
        "status_name": ASSET_STATUS.get(asset.status, asset.status),
        "location": asset.location,
        "supplier": asset.supplier,
        "remark": asset.remark,
        "created_at": asset.created_at,
        **(cur or {"borrower_id": None, "borrower_name": None, "expected_return_time": None, "days_left": None}),
    }


def build_query(
    db: Session,
    keyword: str | None = None,
    category_id: int | None = None,
    status: str | None = None,
    borrower_id: int | None = None,
    borrow_start=None,
    borrow_end=None,
    return_start=None,
    return_end=None,
    viewer=None,
    only_available: bool = False,
):
    cur = aliased(AssetAssignment)
    stmt = (
        select(Asset, AssetCategory.category_name, cur, User.real_name)
        .join(AssetCategory, AssetCategory.id == Asset.category_id)
        .outerjoin(
            cur,
            and_(cur.asset_id == Asset.id, cur.status.in_(ACTIVE_ASSIGNMENT_STATUS)),
        )
        .outerjoin(User, User.id == cur.user_id)
    )
    if keyword:
        like = f"%{keyword}%"
        stmt = stmt.where(
            or_(Asset.asset_code.like(like), Asset.asset_name.like(like), Asset.serial_number.like(like))
        )
    if category_id:
        stmt = stmt.where(Asset.category_id == category_id)
    if status:
        stmt = stmt.where(Asset.status == status)
    if borrower_id:
        stmt = stmt.where(cur.user_id == borrower_id)
    if borrow_start:
        stmt = stmt.where(cur.assign_time >= borrow_start)
    if borrow_end:
        stmt = stmt.where(cur.assign_time <= borrow_end)
    if return_start:
        stmt = stmt.where(cur.expected_return_time >= return_start)
    if return_end:
        stmt = stmt.where(cur.expected_return_time <= return_end)
    if only_available:
        stmt = stmt.where(Asset.status == "IN_STOCK")
    if viewer is not None and not viewer_is_admin(db, viewer):
        # 普通用户：可申请资产 + 自己的资产
        stmt = stmt.where(or_(Asset.status == "IN_STOCK", cur.user_id == viewer.id))
    return stmt


def list_assets(db: Session, page, viewer=None, **filters) -> dict:
    stmt = build_query(db, viewer=viewer, **filters)
    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    rows = db.execute(stmt.order_by(Asset.id.desc()).offset(page.offset).limit(page.page_size)).all()
    items = [
        _row(
            a,
            cname,
            {
                "assignment_id": ca.id,
                "borrower_id": ca.user_id,
                "borrower_name": uname,
                "assign_time": ca.assign_time,
                "expected_return_time": ca.expected_return_time,
                "assignment_status": ca.status,
                "days_left": (ca.expected_return_time - now()).days,
            }
            if ca
            else None,
        )
        for a, cname, ca, uname in rows
    ]
    return page.wrap(items, total)


def get_asset(db: Session, asset_id: int, viewer=None) -> dict:
    asset = get_accessible_asset(db, asset_id, viewer)
    cname = db.scalar(select(AssetCategory.category_name).where(AssetCategory.id == asset.category_id))
    return _row(asset, cname, current_assignment_map(db, [asset.id]).get(asset.id))


def create_asset(db: Session, data, operator=None, request=None) -> dict:
    if not db.get(AssetCategory, data.category_id):
        raise BizError("资产类型不存在")
    payload = data.model_dump(exclude={"asset_code"})
    # ponytail: 编号用 max(code)+1，并发下会撞号 —— 靠唯一索引 + 最多 5 次重试兜底。
    # 要严格不重不跳号就换 PostgreSQL Sequence（SQLite 不支持，本地跑不了）。
    for attempt in range(5):
        code = data.asset_code or next_asset_code(db)
        if db.scalar(select(func.count()).select_from(Asset).where(Asset.asset_code == code)):
            raise BizError(f"资产编号 {code} 已存在")
        asset = Asset(asset_code=code, status="IN_STOCK", **payload)
        db.add(asset)
        try:
            db.flush()
            break
        except IntegrityError:
            db.rollback()
            if data.asset_code or attempt == 4:
                raise BizError(f"资产编号 {code} 冲突，请重试") from None
    write_log(db, operator.id if operator else None, "ASSET_CREATE", "ASSET", asset.id, f"新增资产 {asset.asset_code}", request)
    db.commit()
    return get_asset(db, asset.id, viewer=operator)


def update_asset(db: Session, asset_id: int, data, operator=None, request=None) -> dict:
    asset = db.get(Asset, asset_id)
    if asset is None:
        raise BizError("资产不存在", 40401)
    if asset.status == "SCRAPPED":
        raise BizError("已报废资产不可编辑")
    payload = data.model_dump(exclude_unset=True)
    if payload.get("category_id") and not db.get(AssetCategory, payload["category_id"]):
        raise BizError("资产类型不存在")
    for k, v in payload.items():
        setattr(asset, k, v)
    write_log(db, operator.id if operator else None, "ASSET_UPDATE", "ASSET", asset.id, f"修改资产 {asset.asset_code}", request)
    db.commit()
    return get_asset(db, asset.id, viewer=operator)


def delete_asset(db: Session, asset_id: int, operator=None, request=None) -> None:
    """只能删「在库且从未产生任何业务记录」的资产；有历史的请走报废。"""
    asset = db.get(Asset, asset_id)
    if asset is None:
        raise BizError("资产不存在", 40401)
    if asset.status != "IN_STOCK":
        raise BizError("只有「在库」资产可以删除，已产生记录的资产请走报废流程")
    for model in (AssetApplication, AssetAssignment, AssetRepair):
        if db.scalar(select(func.count()).select_from(model).where(model.asset_id == asset_id)):
            raise BizError("该资产已有申请/领用/维修记录，不能删除，请走报废流程")
    code = asset.asset_code
    db.delete(asset)
    write_log(db, operator.id if operator else None, "ASSET_DELETE", "ASSET", asset_id, f"删除资产 {code}", request)
    db.commit()


def mark_pending_scrap(db: Session, asset_id: int, operator=None, request=None) -> dict:
    """第一步：在库/已领用 → 待报废"""
    asset = db.get(Asset, asset_id)
    if asset is None:
        raise BizError("资产不存在", 40401)
    change_asset_status(asset, "PENDING_SCRAP")
    write_log(db, operator.id if operator else None, "ASSET_PENDING_SCRAP", "ASSET", asset.id, f"提交待报废 {asset.asset_code}", request)
    db.commit()
    return get_asset(db, asset.id, viewer=operator)


def scrap_asset(db: Session, asset_id: int, operator=None, request=None) -> dict:
    """第二步：待报废 → 已报废（必须两步，避免一次调用直接报废）"""
    asset = db.get(Asset, asset_id)
    if asset is None:
        raise BizError("资产不存在", 40401)
    if asset.status != "PENDING_SCRAP":
        raise BizError(f"资产当前为「{ASSET_STATUS.get(asset.status, asset.status)}」，只有「待报废」资产才能确认报废")
    change_asset_status(asset, "SCRAPPED")
    write_log(db, operator.id if operator else None, "ASSET_SCRAP", "ASSET", asset.id, f"确认报废 {asset.asset_code}", request)
    db.commit()
    return get_asset(db, asset.id, viewer=operator)


def qrcode_png(db: Session, asset_id: int, viewer=None) -> bytes:
    import qrcode

    asset = get_accessible_asset(db, asset_id, viewer)
    # 二维码只存详情页 URL，扫码后服务端重新查最新数据（前端是 hash 路由）
    # 未登录扫码会先跳登录页再回详情，不额外开放匿名接口
    url = f"{settings.frontend_url}/#/assets/{asset.id}"
    img = qrcode.make(url)
    buf = BytesIO()
    img.save(buf, "PNG")
    return buf.getvalue()


def lifecycle(db: Session, asset_id: int, viewer=None) -> list[dict]:
    """生命周期不单独建表，由 asset + application + assignment + repair + log 组合出来。"""
    asset = get_accessible_asset(db, asset_id, viewer)
    events = [
        {
            "time": asset.created_at,
            "type": "ASSET_CREATED",
            "title": "资产入库",
            "description": f"{asset.asset_name}（{asset.asset_code}）登记入库",
        }
    ]
    for a in db.scalars(select(AssetApplication).where(AssetApplication.asset_id == asset_id)):
        applicant = db.get(User, a.applicant_id)
        events.append(
            {
                "time": a.apply_time,
                "type": "APPLICATION_SUBMITTED",
                "title": "提交领用申请",
                "description": f"{applicant.real_name if applicant else ''}申请：{a.reason}（{a.application_no}）",
            }
        )
        if a.approval_time:
            events.append(
                {
                    "time": a.approval_time,
                    "type": f"APPLICATION_{a.status}",
                    "title": "领用审批通过" if a.status == "APPROVED" else "领用审批驳回",
                    "description": a.approval_remark or "",
                }
            )
    for s in db.scalars(select(AssetAssignment).where(AssetAssignment.asset_id == asset_id)):
        user = db.get(User, s.user_id)
        events.append(
            {
                "time": s.assign_time,
                "type": "ASSIGNED",
                "title": "设备领用出库",
                "description": f"{user.real_name if user else ''} 领用，应归还 {s.expected_return_time:%Y-%m-%d}",
            }
        )
        if s.actual_return_time:
            events.append(
                {
                    "time": s.actual_return_time,
                    "type": "RETURNED",
                    "title": "设备归还",
                    "description": s.remark or "已归还入库",
                }
            )
    for r in db.scalars(select(AssetRepair).where(AssetRepair.asset_id == asset_id)):
        events.append(
            {
                "time": r.created_at,
                "type": "REPAIR_CREATED",
                "title": "提交维修",
                "description": r.fault_description,
            }
        )
        if r.end_time:
            events.append(
                {
                    "time": r.end_time,
                    "type": "REPAIR_COMPLETED",
                    "title": "维修完成",
                    "description": r.repair_result or "",
                }
            )
    for log in db.scalars(
        select(OperationLog).where(OperationLog.target_type == "ASSET", OperationLog.target_id == asset_id)
    ):
        events.append(
            {
                "time": log.created_at,
                "type": f"LOG_{log.operation_type}",
                "title": log.operation_type,
                "description": log.operation_content or "",
            }
        )
    return sorted(events, key=lambda e: e["time"] or now())


def status_options() -> list[dict]:
    return [{"status": k, "name": v} for k, v in ASSET_STATUS.items()]
