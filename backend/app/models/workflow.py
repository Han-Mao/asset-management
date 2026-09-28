from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    CheckConstraint,
    ForeignKey,
    Index,
    Numeric,
    String,
    Text,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from ..core.constants import APPLICATION_STATUS, ASSIGNMENT_STATUS, REPAIR_STATUS
from ..core.database import BIGINT, Base, UTCDateTime, now

MONEY = Numeric(12, 2)


def _check(column: str, values: dict[str, str]) -> str:
    return f"{column} IN (" + ", ".join(f"'{v}'" for v in values) + ")"


class AssetApplication(Base):
    """领用申请：一个申请对应一台资产"""

    __tablename__ = "asset_application"

    id: Mapped[int] = mapped_column(BIGINT, primary_key=True, autoincrement=True)
    application_no: Mapped[str] = mapped_column(String(50), unique=True)

    applicant_id: Mapped[int] = mapped_column(ForeignKey("sys_user.id"))
    asset_id: Mapped[int] = mapped_column(ForeignKey("asset.id"))

    reason: Mapped[str] = mapped_column(Text)
    apply_time: Mapped[datetime] = mapped_column(UTCDateTime, default=now)
    expected_return_time: Mapped[datetime] = mapped_column(UTCDateTime)

    status: Mapped[str] = mapped_column(String(20), default="PENDING")

    approver_id: Mapped[int | None] = mapped_column(ForeignKey("sys_user.id"))
    approval_time: Mapped[datetime | None] = mapped_column(UTCDateTime)
    approval_remark: Mapped[str | None] = mapped_column(Text)

    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=now)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime, default=now, onupdate=now)

    __table_args__ = (
        CheckConstraint(_check("status", APPLICATION_STATUS), name="ck_application_status"),
        Index("idx_application_applicant", "applicant_id"),
        Index("idx_application_asset", "asset_id"),
        Index("idx_application_status", "status"),
        Index("idx_application_apply_time", "apply_time"),
    )


class AssetAssignment(Base):
    """正式领用记录 = 资产的历史领用关系（asset 只存当前状态）"""

    __tablename__ = "asset_assignment"

    id: Mapped[int] = mapped_column(BIGINT, primary_key=True, autoincrement=True)

    asset_id: Mapped[int] = mapped_column(ForeignKey("asset.id"))
    user_id: Mapped[int] = mapped_column(ForeignKey("sys_user.id"))
    application_id: Mapped[int] = mapped_column(ForeignKey("asset_application.id"))

    assign_time: Mapped[datetime] = mapped_column(UTCDateTime, default=now)
    expected_return_time: Mapped[datetime] = mapped_column(UTCDateTime)
    actual_return_time: Mapped[datetime | None] = mapped_column(UTCDateTime)

    status: Mapped[str] = mapped_column(String(20), default="ACTIVE")
    remark: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=now)

    __table_args__ = (
        CheckConstraint(_check("status", ASSIGNMENT_STATUS), name="ck_assignment_status"),
        Index("idx_assignment_asset", "asset_id"),
        Index("idx_assignment_user", "user_id"),
        Index("idx_assignment_expected_return", "expected_return_time"),
        Index("idx_assignment_status", "status"),
        # 数据库层兜底：一台资产只能有一条“当前领用记录”
        Index(
            "uq_active_asset_assignment",
            "asset_id",
            unique=True,
            postgresql_where=text("status IN ('ACTIVE', 'OVERDUE')"),
            sqlite_where=text("status IN ('ACTIVE', 'OVERDUE')"),
        ),
    )


class AssetRepair(Base):
    __tablename__ = "asset_repair"

    id: Mapped[int] = mapped_column(BIGINT, primary_key=True, autoincrement=True)
    repair_no: Mapped[str] = mapped_column(String(50), unique=True)

    asset_id: Mapped[int] = mapped_column(ForeignKey("asset.id"))
    reporter_id: Mapped[int] = mapped_column(ForeignKey("sys_user.id"))

    fault_description: Mapped[str] = mapped_column(Text)
    repair_company: Mapped[str | None] = mapped_column(String(200))
    repair_cost: Mapped[Decimal | None] = mapped_column(MONEY)

    start_time: Mapped[datetime | None] = mapped_column(UTCDateTime)
    end_time: Mapped[datetime | None] = mapped_column(UTCDateTime)
    repair_result: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(20), default="PENDING")

    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=now)

    __table_args__ = (
        CheckConstraint(_check("status", REPAIR_STATUS), name="ck_repair_status"),
        Index("idx_repair_asset", "asset_id"),
        Index("idx_repair_reporter", "reporter_id"),
        Index("idx_repair_status", "status"),
    )
