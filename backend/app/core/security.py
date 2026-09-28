from datetime import timedelta

import bcrypt
import jwt

from .config import settings
from .database import now


def hash_password(raw: str) -> str:
    # bcrypt 只取前 72 字节，先截断避免 ValueError
    return bcrypt.hashpw(raw.encode()[:72], bcrypt.gensalt()).decode()


def verify_password(raw: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(raw.encode()[:72], hashed.encode())
    except ValueError:
        return False


def create_token(user_id: int) -> str:
    payload = {"sub": str(user_id), "exp": now() + timedelta(minutes=settings.token_expire_minutes)}
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_alg)


def parse_token(token: str) -> int | None:
    """返回用户 ID；token 无效/过期返回 None。"""
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_alg])
    except jwt.PyJWTError:
        return None
    sub = payload.get("sub")
    return int(sub) if sub and str(sub).isdigit() else None
