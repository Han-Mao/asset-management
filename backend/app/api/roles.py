from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from ..core.deps import get_current_user, get_db, require_permission
from ..core.response import EnvelopeRoute
from ..schemas import RoleIn, RoleUpdate
from ..services import system as sys_svc

router = APIRouter(prefix="/roles", tags=["角色权限"], route_class=EnvelopeRoute)


@router.get("")
def list_roles(db: Session = Depends(get_db), _=Depends(get_current_user)):
    return sys_svc.list_roles(db)


@router.get("/permissions")
def list_permissions(db: Session = Depends(get_db), _=Depends(require_permission("role:read"))):
    return sys_svc.list_permissions(db)


@router.post("")
def create_role(
    data: RoleIn,
    request: Request,
    db: Session = Depends(get_db),
    user=Depends(require_permission("role:update")),
):
    return sys_svc.create_role(db, data, user, request)


@router.put("/{role_id}")
def update_role(
    role_id: int,
    data: RoleUpdate,
    request: Request,
    db: Session = Depends(get_db),
    user=Depends(require_permission("role:update")),
):
    return sys_svc.update_role(db, role_id, data, user, request)


@router.delete("/{role_id}")
def delete_role(
    role_id: int,
    request: Request,
    db: Session = Depends(get_db),
    user=Depends(require_permission("role:update")),
):
    sys_svc.delete_role(db, role_id, user, request)
    return None
