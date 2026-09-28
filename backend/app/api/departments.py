from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from ..core.deps import get_current_user, get_db, require_permission
from ..core.response import EnvelopeRoute
from ..schemas import DepartmentIn
from ..services import system as sys_svc

router = APIRouter(prefix="/departments", tags=["部门管理"], route_class=EnvelopeRoute)


@router.get("")
def list_departments(db: Session = Depends(get_db), _=Depends(get_current_user)):
    return sys_svc.list_departments(db)


@router.post("")
def create_department(
    data: DepartmentIn,
    request: Request,
    db: Session = Depends(get_db),
    user=Depends(require_permission("department:manage")),
):
    return sys_svc.create_department(db, data, user, request)


@router.put("/{dept_id}")
def update_department(
    dept_id: int,
    data: DepartmentIn,
    request: Request,
    db: Session = Depends(get_db),
    user=Depends(require_permission("department:manage")),
):
    return sys_svc.update_department(db, dept_id, data, user, request)


@router.delete("/{dept_id}")
def delete_department(
    dept_id: int,
    request: Request,
    db: Session = Depends(get_db),
    user=Depends(require_permission("department:manage")),
):
    sys_svc.delete_department(db, dept_id, user, request)
    return None
