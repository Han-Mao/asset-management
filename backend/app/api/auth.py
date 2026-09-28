from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from ..core.deps import get_current_user, get_db, user_permissions
from ..core.response import EnvelopeRoute
from ..schemas import LoginIn
from ..services import auth as auth_svc
from ..services import notification as notif
from ..services.common import write_log
from ..services.system import user_roles

router = APIRouter(prefix="/auth", tags=["认证"], route_class=EnvelopeRoute)


@router.post("/login")
def login(data: LoginIn, request: Request, db: Session = Depends(get_db)):
    user, token = auth_svc.login(db, data.username, data.password, request)
    return {
        "access_token": token,
        "token_type": "bearer",
        "user": {
            "id": user.id,
            "username": user.username,
            "real_name": user.real_name,
            "roles": user_roles(db, user.id),
            "permissions": sorted(user_permissions(db, user)),
        },
    }


@router.post("/logout")
def logout(user=Depends(get_current_user), db: Session = Depends(get_db), request: Request = None):
    write_log(db, user.id, "LOGOUT", "USER", user.id, f"{user.real_name} 退出登录", request)
    db.commit()
    return None


@router.get("/me")
def me(user=Depends(get_current_user), db: Session = Depends(get_db)):
    return {
        "id": user.id,
        "username": user.username,
        "real_name": user.real_name,
        "email": user.email,
        "phone": user.phone,
        "department_id": user.department_id,
        "roles": user_roles(db, user.id),
        "permissions": sorted(user_permissions(db, user)),
        "unread_count": notif.unread_count(db, user.id),
    }
