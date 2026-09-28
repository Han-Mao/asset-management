from datetime import datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    ForeignKey,
    Index,
    SmallInteger,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import INET
from sqlalchemy.orm import Mapped, mapped_column

from ..core.database import BIGINT, Base, UTCDateTime, now

IP = String(45).with_variant(INET, "postgresql")


class Department(Base):
    """部门（树形，parent_id 自关联）"""

    __tablename__ = "sys_department"

    id: Mapped[int] = mapped_column(BIGINT, primary_key=True, autoincrement=True)
    parent_id: Mapped[int | None] = mapped_column(ForeignKey("sys_department.id"))
    department_name: Mapped[str] = mapped_column(String(100))
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=now)

    __table_args__ = (Index("idx_department_parent_id", "parent_id"),)


class User(Base):
    __tablename__ = "sys_user"

    id: Mapped[int] = mapped_column(BIGINT, primary_key=True, autoincrement=True)
    username: Mapped[str] = mapped_column(String(50), unique=True)
    password_hash: Mapped[str] = mapped_column(String(255))

    real_name: Mapped[str] = mapped_column(String(50))
    email: Mapped[str | None] = mapped_column(String(100))
    phone: Mapped[str | None] = mapped_column(String(20))

    department_id: Mapped[int | None] = mapped_column(ForeignKey("sys_department.id"))

    status: Mapped[int] = mapped_column(SmallInteger, default=1)  # 1 正常 0 禁用
    last_login_at: Mapped[datetime | None] = mapped_column(UTCDateTime)

    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=now)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime, default=now, onupdate=now)

    __table_args__ = (
        CheckConstraint("status IN (0, 1)", name="ck_user_status"),
        Index("idx_user_department", "department_id"),
        Index("idx_user_status", "status"),
    )


class Role(Base):
    __tablename__ = "sys_role"

    id: Mapped[int] = mapped_column(BIGINT, primary_key=True, autoincrement=True)
    role_name: Mapped[str] = mapped_column(String(50))
    role_code: Mapped[str] = mapped_column(String(50), unique=True)
    description: Mapped[str | None] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=now)


class Permission(Base):
    __tablename__ = "sys_permission"

    id: Mapped[int] = mapped_column(BIGINT, primary_key=True, autoincrement=True)
    permission_name: Mapped[str] = mapped_column(String(100))
    permission_code: Mapped[str] = mapped_column(String(100), unique=True)
    resource: Mapped[str | None] = mapped_column(String(50))
    action: Mapped[str | None] = mapped_column(String(50))
    description: Mapped[str | None] = mapped_column(String(255))


class UserRole(Base):
    __tablename__ = "sys_user_role"

    id: Mapped[int] = mapped_column(BIGINT, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("sys_user.id", ondelete="CASCADE"))
    role_id: Mapped[int] = mapped_column(ForeignKey("sys_role.id", ondelete="CASCADE"))

    __table_args__ = (
        UniqueConstraint("user_id", "role_id", name="uq_user_role"),
        Index("idx_user_role_user_id", "user_id"),
        Index("idx_user_role_role_id", "role_id"),
    )


class RolePermission(Base):
    __tablename__ = "sys_role_permission"

    id: Mapped[int] = mapped_column(BIGINT, primary_key=True, autoincrement=True)
    role_id: Mapped[int] = mapped_column(ForeignKey("sys_role.id", ondelete="CASCADE"))
    permission_id: Mapped[int] = mapped_column(ForeignKey("sys_permission.id", ondelete="CASCADE"))

    __table_args__ = (UniqueConstraint("role_id", "permission_id", name="uq_role_permission"),)


class Notification(Base):
    __tablename__ = "sys_notification"

    id: Mapped[int] = mapped_column(BIGINT, primary_key=True, autoincrement=True)
    receiver_id: Mapped[int] = mapped_column(ForeignKey("sys_user.id", ondelete="CASCADE"))

    title: Mapped[str] = mapped_column(String(200))
    content: Mapped[str] = mapped_column(Text)
    notification_type: Mapped[str] = mapped_column(String(50))

    related_type: Mapped[str | None] = mapped_column(String(50))
    related_id: Mapped[int | None] = mapped_column(BIGINT)

    is_read: Mapped[bool] = mapped_column(Boolean, default=False)
    read_at: Mapped[datetime | None] = mapped_column(UTCDateTime)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=now)

    __table_args__ = (
        Index("idx_notification_receiver", "receiver_id"),
        Index("idx_notification_unread", "receiver_id", "is_read"),
        Index("idx_notification_created_at", "created_at"),
    )


class OperationLog(Base):
    __tablename__ = "sys_operation_log"

    id: Mapped[int] = mapped_column(BIGINT, primary_key=True, autoincrement=True)
    operator_id: Mapped[int | None] = mapped_column(ForeignKey("sys_user.id", ondelete="SET NULL"))

    operation_type: Mapped[str] = mapped_column(String(50))
    target_type: Mapped[str | None] = mapped_column(String(50))
    target_id: Mapped[int | None] = mapped_column(BIGINT)
    operation_content: Mapped[str | None] = mapped_column(Text)

    ip_address: Mapped[str | None] = mapped_column(IP)
    user_agent: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=now)

    __table_args__ = (
        Index("idx_operation_operator", "operator_id"),
        Index("idx_operation_target", "target_type", "target_id"),
        Index("idx_operation_created_at", "created_at"),
    )
