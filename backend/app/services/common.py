"""跨 Service 复用的小工具：编号生成、状态流转校验、操作日志。"""

from uuid import uuid4

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..core.constants import ASSET_STATUS, ASSET_TRANSITIONS
from ..core.database import now
from ..core.errors import BizError
from ..models import Asset, OperationLog


def gen_no(prefix: str) -> str:
    """AP20260928A3F1 这种：日期 + 随机后缀，无查询、无并发冲突。"""
    return f"{prefix}{now().strftime('%Y%m%d')}{uuid4().hex[:4].upper()}"


def next_asset_code(db: Session) -> str:
    prefix = f"IT-{now().year}-"
    last = db.scalar(select(func.max(Asset.asset_code)).where(Asset.asset_code.like(prefix + "%")))
    n = int(last.rsplit("-", 1)[1]) + 1 if last else 1
    return f"{prefix}{n:06d}"


def change_asset_status(asset: Asset, target: str) -> None:
    """业务状态机：只有允许的流转才放行，前端传什么都改不动资产状态。"""
    if target == asset.status:
        return
    if target not in ASSET_TRANSITIONS.get(asset.status, set()):
        raise BizError(
            f"资产当前为「{ASSET_STATUS.get(asset.status, asset.status)}」，"
            f"不能变更为「{ASSET_STATUS.get(target, target)}」"
        )
    asset.status = target


def write_log(
    db: Session,
    operator_id: int | None,
    operation_type: str,
    target_type: str | None = None,
    target_id: int | None = None,
    content: str | None = None,
    request=None,
) -> None:
    ip = ua = None
    if request is not None:
        fwd = request.headers.get("x-forwarded-for")
        ip = fwd.split(",")[0].strip() if fwd else (request.client.host if request.client else None)
        ua = request.headers.get("user-agent")
    db.add(
        OperationLog(
            operator_id=operator_id,
            operation_type=operation_type,
            target_type=target_type,
            target_id=target_id,
            operation_content=content,
            ip_address=ip,
            user_agent=ua,
        )
    )
