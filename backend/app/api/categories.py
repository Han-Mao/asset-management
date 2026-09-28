from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from ..core.deps import get_current_user, get_db, require_permission
from ..core.response import EnvelopeRoute
from ..schemas import CategoryIn
from ..services import system as sys_svc

router = APIRouter(prefix="/asset-categories", tags=["资产分类"], route_class=EnvelopeRoute)


@router.get("")
def list_categories(db: Session = Depends(get_db), _=Depends(get_current_user)):
    return sys_svc.list_categories(db)


@router.post("")
def create_category(
    data: CategoryIn,
    request: Request,
    db: Session = Depends(get_db),
    user=Depends(require_permission("category:manage")),
):
    return sys_svc.create_category(db, data, user, request)


@router.put("/{category_id}")
def update_category(
    category_id: int,
    data: CategoryIn,
    request: Request,
    db: Session = Depends(get_db),
    user=Depends(require_permission("category:manage")),
):
    return sys_svc.update_category(db, category_id, data, user, request)


@router.delete("/{category_id}")
def delete_category(
    category_id: int,
    request: Request,
    db: Session = Depends(get_db),
    user=Depends(require_permission("category:manage")),
):
    sys_svc.delete_category(db, category_id, user, request)
    return None
