from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from ..core.deps import Page, get_current_user, get_db, require_permission
from ..core.response import EnvelopeRoute
from ..schemas import RepairCreate, RepairUpdate
from ..services import repair as repair_svc
from ..services.asset import viewer_is_admin

router = APIRouter(prefix="/repairs", tags=["维修管理"], route_class=EnvelopeRoute)


@router.post("")
def create_repair(
    data: RepairCreate,
    request: Request,
    db: Session = Depends(get_db),
    user=Depends(require_permission("repair:create")),
):
    return repair_svc.create_repair(db, data, user, request)


@router.get("")
def list_repairs(
    status: str | None = None,
    keyword: str | None = None,
    mine: bool = False,
    page: Page = Depends(),
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    # 管理员看全部，普通用户只能看自己报修的（mine=true 或非管理员）
    reporter_id = user.id if (mine or not viewer_is_admin(db, user)) else None
    return repair_svc.list_repairs(db, page, status=status, keyword=keyword, reporter_id=reporter_id)


@router.get("/{repair_id}")
def get_repair(repair_id: int, db: Session = Depends(get_db), user=Depends(get_current_user)):
    return repair_svc.get_repair(db, repair_id)


@router.put("/{repair_id}")
def update_repair(
    repair_id: int,
    data: RepairUpdate,
    request: Request,
    db: Session = Depends(get_db),
    user=Depends(require_permission("repair:handle")),
):
    return repair_svc.update_repair(db, repair_id, data, user, request)


@router.post("/{repair_id}/start")
def start_repair(
    repair_id: int,
    request: Request,
    db: Session = Depends(get_db),
    user=Depends(require_permission("repair:handle")),
):
    return repair_svc.start_repair(db, repair_id, user, request)


@router.post("/{repair_id}/complete")
def complete_repair(
    repair_id: int,
    data: RepairUpdate,
    request: Request,
    db: Session = Depends(get_db),
    user=Depends(require_permission("repair:handle")),
):
    return repair_svc.complete_repair(db, repair_id, data, user, request)


@router.post("/{repair_id}/cancel")
def cancel_repair(
    repair_id: int,
    request: Request,
    db: Session = Depends(get_db),
    user=Depends(require_permission("repair:handle")),
):
    return repair_svc.cancel_repair(db, repair_id, user, request)
