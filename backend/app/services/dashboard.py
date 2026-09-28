"""首页 / 统计分析：全部是 SQL 聚合，不建统计表。"""

from datetime import timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..core.constants import ACTIVE_ASSIGNMENT_STATUS, ASSET_STATUS, APPLICATION_STATUS
from ..core.database import now
from ..models import Asset, AssetApplication, AssetAssignment, AssetCategory, Department, User


def _group_count(db: Session, stmt) -> dict:
    return {k: v for k, v in db.execute(stmt).all()}


def overview(db: Session) -> dict:
    status_cnt = _group_count(db, select(Asset.status, func.count()).group_by(Asset.status))
    deadline = now() + timedelta(days=30)
    return {
        "total_assets": sum(status_cnt.values()),
        "in_stock": status_cnt.get("IN_STOCK", 0),
        "borrowed": status_cnt.get("BORROWED", 0),
        "pending_repair": status_cnt.get("PENDING_REPAIR", 0),
        "repairing": status_cnt.get("REPAIRING", 0),
        "pending_scrap": status_cnt.get("PENDING_SCRAP", 0),
        "scrapped": status_cnt.get("SCRAPPED", 0),
        "pending_applications": db.scalar(
            select(func.count()).select_from(AssetApplication).where(AssetApplication.status == "PENDING")
        )
        or 0,
        "expiring_30_days": db.scalar(
            select(func.count())
            .select_from(AssetAssignment)
            .where(
                AssetAssignment.status.in_(ACTIVE_ASSIGNMENT_STATUS),
                AssetAssignment.expected_return_time >= now(),
                AssetAssignment.expected_return_time <= deadline,
            )
        )
        or 0,
        "overdue_assignments": db.scalar(
            select(func.count()).select_from(AssetAssignment).where(AssetAssignment.status == "OVERDUE")
        )
        or 0,
    }


def asset_status(db: Session) -> list[dict]:
    cnt = _group_count(db, select(Asset.status, func.count()).group_by(Asset.status))
    return [{"status": k, "name": name, "count": cnt.get(k, 0)} for k, name in ASSET_STATUS.items()]


def asset_category(db: Session) -> list[dict]:
    rows = db.execute(
        select(AssetCategory.category_name, func.count(Asset.id))
        .join(Asset, Asset.category_id == AssetCategory.id)
        .group_by(AssetCategory.category_name)
        .order_by(func.count(Asset.id).desc())
    ).all()
    return [{"name": name, "count": count} for name, count in rows]


def department(db: Session) -> list[dict]:
    rows = db.execute(
        select(Department.department_name, func.count(AssetAssignment.id))
        .join(User, User.department_id == Department.id)
        .join(AssetAssignment, AssetAssignment.user_id == User.id)
        .where(AssetAssignment.status.in_(ACTIVE_ASSIGNMENT_STATUS))
        .group_by(Department.department_name)
        .order_by(func.count(AssetAssignment.id).desc())
    ).all()
    return [{"name": name, "count": count} for name, count in rows]


def expiry(db: Session, days: int = 30) -> list[dict]:
    """未来 N 天到期的领用（不含已逾期，逾期单独统计）。"""
    deadline = now() + timedelta(days=days)
    rows = db.execute(
        select(AssetAssignment.expected_return_time)
        .where(
            AssetAssignment.status.in_(ACTIVE_ASSIGNMENT_STATUS),
            AssetAssignment.expected_return_time >= now(),
            AssetAssignment.expected_return_time <= deadline,
        )
        .order_by(AssetAssignment.expected_return_time)
    ).scalars().all()
    buckets: dict[str, int] = {}
    for t in rows:
        key = t.strftime("%Y-%m-%d")
        buckets[key] = buckets.get(key, 0) + 1
    return [{"date": k, "count": v} for k, v in list(buckets.items())[:30]]


def borrow_trend(db: Session, months: int = 6) -> list[dict]:
    start = now() - timedelta(days=30 * months)
    rows = db.scalars(select(AssetAssignment.assign_time).where(AssetAssignment.assign_time >= start)).all()
    buckets: dict[str, int] = {}
    for t in rows:
        key = t.strftime("%Y-%m")
        buckets[key] = buckets.get(key, 0) + 1
    keys = sorted(buckets)
    return [{"month": k, "count": buckets[k]} for k in keys]


def application_stats(db: Session) -> list[dict]:
    cnt = _group_count(db, select(AssetApplication.status, func.count()).group_by(AssetApplication.status))
    return [{"status": k, "name": name, "count": cnt.get(k, 0)} for k, name in APPLICATION_STATUS.items()]
