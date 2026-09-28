from datetime import datetime, timezone

from sqlalchemy import BigInteger, DateTime, Integer, TypeDecorator, create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from .config import DATA_DIR, settings

# PostgreSQL 用 BIGSERIAL/TIMESTAMPTZ；SQLite 只用于本地跑通，故降级为 INTEGER/DATETIME
BIGINT = BigInteger().with_variant(Integer, "sqlite")


def now() -> datetime:
    """全项目统一取时区感知的 UTC 时间。"""
    return datetime.now(timezone.utc)


class UTCDateTime(TypeDecorator):
    """naive/aware 一律按 UTC 存取，避免 PG 带时区、SQLite 不带时区导致的比较报错。"""

    impl = DateTime
    cache_ok = True

    def load_dialect_impl(self, dialect):
        impl = DateTime(timezone=True) if dialect.name == "postgresql" else DateTime()
        return dialect.type_descriptor(impl)

    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)

    def process_result_value(self, value, dialect):
        if value is None:
            return None
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)


sqlite = settings.database_url.startswith("sqlite")
if sqlite:
    DATA_DIR.mkdir(parents=True, exist_ok=True)

engine = create_engine(
    settings.database_url,
    future=True,
    pool_pre_ping=not sqlite,
    connect_args={"check_same_thread": False} if sqlite else {},
)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


class Base(DeclarativeBase):
    pass
