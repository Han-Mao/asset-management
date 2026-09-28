from sqlalchemy import select
from sqlalchemy.orm import Session

from ..core.database import now
from ..core.errors import BizError
from ..core.security import create_token, verify_password
from ..models import User
from .common import write_log


def login(db: Session, username: str, password: str, request=None) -> tuple[User, str]:
    user = db.scalar(select(User).where(User.username == username))
    if user is None or not verify_password(password, user.password_hash):
        raise BizError("账号或密码错误", 40002)
    if user.status != 1:
        raise BizError("账号已被禁用，请联系管理员", 40003)
    user.last_login_at = now()
    write_log(db, user.id, "LOGIN", "USER", user.id, f"{user.real_name} 登录系统", request)
    db.commit()
    return user, create_token(user.id)
