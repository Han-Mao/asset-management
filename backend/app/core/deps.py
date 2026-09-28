from collections.abc import Iterator

from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.orm import Session

from .database import SessionLocal
from .security import parse_token

bearer = HTTPBearer(auto_error=False)


def get_db() -> Iterator[Session]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_current_user(
    cred: HTTPAuthorizationCredentials | None = Depends(bearer),
    db: Session = Depends(get_db),
):
    from ..models import User

    if cred is None:
        raise HTTPException(401, "未登录或登录已过期")
    user_id = parse_token(cred.credentials)
    if user_id is None:
        raise HTTPException(401, "未登录或登录已过期")
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(401, "用户不存在")
    if user.status != 1:
        raise HTTPException(403, "账号已被禁用")
    return user


def user_permissions(db: Session, user) -> set[str]:
    """一次查库拿到权限码集合；角色/权限变更后下一次请求即生效。"""
    from ..models import Permission, RolePermission, UserRole

    rows = db.execute(
        select(Permission.permission_code)
        .join(RolePermission, RolePermission.permission_id == Permission.id)
        .join(UserRole, UserRole.role_id == RolePermission.role_id)
        .where(UserRole.user_id == user.id)
    ).scalars()
    return set(rows)


def require_permission(code: str):
    def dep(user=Depends(get_current_user), db: Session = Depends(get_db)):
        if code not in user_permissions(db, user):
            raise HTTPException(403, f"无权限：{code}")
        return user

    return dep


class Page:
    def __init__(self, page: int = 1, page_size: int = 20):
        self.page = max(1, page)
        self.page_size = min(max(1, page_size), 200)

    @property
    def offset(self) -> int:
        return (self.page - 1) * self.page_size

    def wrap(self, items: list, total: int) -> dict:
        return {"items": items, "total": total, "page": self.page, "page_size": self.page_size}


def client_ip(request: Request) -> str | None:
    fwd = request.headers.get("x-forwarded-for")
    return (fwd.split(",")[0].strip() if fwd else request.client.host if request.client else None)
