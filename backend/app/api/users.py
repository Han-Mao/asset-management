from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from ..core.deps import Page, get_db, require_permission
from ..core.response import EnvelopeRoute
from ..schemas import PasswordIn, StatusIn, UserCreate, UserUpdate
from ..services import system as sys_svc

router = APIRouter(prefix="/users", tags=["用户管理"], route_class=EnvelopeRoute)


@router.get("")
def list_users(
    keyword: str | None = None,
    department_id: int | None = None,
    status: int | None = None,
    page: Page = Depends(),
    db: Session = Depends(get_db),
    _=Depends(require_permission("user:read")),
):
    return sys_svc.list_users(db, keyword, department_id, status, page)


@router.post("")
def create_user(
    data: UserCreate,
    request: Request,
    db: Session = Depends(get_db),
    user=Depends(require_permission("user:create")),
):
    return sys_svc.create_user(db, data, user, request)


@router.get("/{user_id}")
def get_user(user_id: int, db: Session = Depends(get_db), _=Depends(require_permission("user:read"))):
    return sys_svc.get_user(db, user_id)


@router.put("/{user_id}")
def update_user(
    user_id: int,
    data: UserUpdate,
    request: Request,
    db: Session = Depends(get_db),
    user=Depends(require_permission("user:update")),
):
    return sys_svc.update_user(db, user_id, data, user, request)


@router.delete("/{user_id}")
def delete_user(
    user_id: int,
    request: Request,
    db: Session = Depends(get_db),
    user=Depends(require_permission("user:delete")),
):
    sys_svc.delete_user(db, user_id, user, request)
    return None


@router.patch("/{user_id}/status")
def set_status(
    user_id: int,
    data: StatusIn,
    request: Request,
    db: Session = Depends(get_db),
    user=Depends(require_permission("user:update")),
):
    sys_svc.set_status(db, user_id, data.status, user, request)
    return None


@router.post("/{user_id}/reset-password")
def reset_password(
    user_id: int,
    data: PasswordIn,
    request: Request,
    db: Session = Depends(get_db),
    user=Depends(require_permission("user:update")),
):
    sys_svc.reset_password(db, user_id, data.password, user, request)
    return None
