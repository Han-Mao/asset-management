from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..core.deps import Page, get_db, require_permission
from ..core.errors import BizError
from ..core.response import EnvelopeRoute
from ..models import OperationLog, User
from ..schemas import LogOut

router = APIRouter(prefix="/operation-logs", tags=["操作日志"], route_class=EnvelopeRoute)


@router.get("")
def list_logs(
    operation_type: str | None = None,
    target_type: str | None = None,
    operator_id: int | None = None,
    page: Page = Depends(),
    db: Session = Depends(get_db),
    _=Depends(require_permission("log:read")),
):
    cond = []
    if operation_type:
        cond.append(OperationLog.operation_type == operation_type)
    if target_type:
        cond.append(OperationLog.target_type == target_type)
    if operator_id:
        cond.append(OperationLog.operator_id == operator_id)
    total = db.scalar(select(func.count()).select_from(OperationLog).where(*cond)) or 0
    rows = db.execute(
        select(OperationLog, User.real_name)
        .outerjoin(User, User.id == OperationLog.operator_id)
        .where(*cond)
        .order_by(OperationLog.created_at.desc())
        .offset(page.offset)
        .limit(page.page_size)
    ).all()
    items = []
    for log, name in rows:
        item = LogOut.model_validate(log)
        item.operator_name = name
        items.append(item)
    return page.wrap(items, total)


@router.get("/{log_id}")
def get_log(log_id: int, db: Session = Depends(get_db), _=Depends(require_permission("log:read"))):
    log = db.get(OperationLog, log_id)
    if log is None:
        raise BizError("日志不存在", 40401)
    item = LogOut.model_validate(log)
    item.operator_name = db.scalar(select(User.real_name).where(User.id == log.operator_id))
    return item
