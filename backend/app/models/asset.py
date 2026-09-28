from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    CheckConstraint,
    Date,
    ForeignKey,
    Index,
    Numeric,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column

from ..core.constants import ASSET_STATUS
from ..core.database import BIGINT, Base, UTCDateTime, now

MONEY = Numeric(12, 2)


class AssetCategory(Base):
    __tablename__ = "asset_category"

    id: Mapped[int] = mapped_column(BIGINT, primary_key=True, autoincrement=True)
    category_name: Mapped[str] = mapped_column(String(100))
    category_code: Mapped[str] = mapped_column(String(50), unique=True)
    description: Mapped[str | None] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=now)


class Asset(Base):
    __tablename__ = "asset"

    id: Mapped[int] = mapped_column(BIGINT, primary_key=True, autoincrement=True)
    asset_code: Mapped[str] = mapped_column(String(50), unique=True)
    asset_name: Mapped[str] = mapped_column(String(100))
    category_id: Mapped[int] = mapped_column(ForeignKey("asset_category.id"))

    brand: Mapped[str | None] = mapped_column(String(100))
    model: Mapped[str | None] = mapped_column(String(100))
    serial_number: Mapped[str | None] = mapped_column(String(100))

    purchase_date: Mapped[date | None] = mapped_column(Date)
    purchase_price: Mapped[Decimal | None] = mapped_column(MONEY)
    warranty_expire_date: Mapped[date | None] = mapped_column(Date)

    # 业务状态只能由业务动作驱动，AssetUpdate Schema 里故意不含此字段
    status: Mapped[str] = mapped_column(String(30), default="IN_STOCK")

    location: Mapped[str | None] = mapped_column(String(200))
    supplier: Mapped[str | None] = mapped_column(String(200))
    remark: Mapped[str | None] = mapped_column(Text)

    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=now)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime, default=now, onupdate=now)

    __table_args__ = (
        CheckConstraint(
            "status IN (" + ", ".join(f"'{s}'" for s in ASSET_STATUS) + ")", name="ck_asset_status"
        ),
        Index("idx_asset_category", "category_id"),
        Index("idx_asset_status", "status"),
        Index("idx_asset_purchase_date", "purchase_date"),
        Index("idx_asset_warranty_expire", "warranty_expire_date"),
        Index("idx_asset_serial_number", "serial_number"),
    )
