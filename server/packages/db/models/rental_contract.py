from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    BigInteger,
    Boolean,
    Date,
    ForeignKey,
    Numeric,
    String,
    Text,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from packages.core.snowflake import next_id
from packages.db.session import Base, UTCDateTime


class RentalContract(Base):
    """租约合同 — 房东收租或租客付租。

    role='landlord': linked_asset_id 指向出租的房产资产
    role='tenant': linked_asset_id 为 null（承租不关联自有资产）
    end_date 为 null 表示不定期租约
    is_active=False 表示合同已结束（软删除）
    """

    __tablename__ = "rental_contracts"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, default=next_id)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"), nullable=False)
    family_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("families.id"), nullable=False)
    # landlord=房东(收租) / tenant=租客(付租)
    role: Mapped[str] = mapped_column(String(10), nullable=False)
    # Money fields are NUMERIC(18,2) — Decimal in Python, serialized as str on
    # the wire (SnowflakeBase money-as-str convention, CLAUDE.md §bigint).
    monthly_rent: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    deposit: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False, default=0)
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date | None] = mapped_column(Date, nullable=True)  # null=不定期
    # 房东时关联出租房产；租客时为 null
    linked_asset_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("assets.id"), nullable=True
    )
    counterparty: Mapped[str | None] = mapped_column(String(200), nullable=True)  # 租客/房东姓名
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    currency: Mapped[str] = mapped_column(String(10), default="CNY", server_default="CNY")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default=text("true"))
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime(), server_default=func.now(), onupdate=func.now())

    linked_asset = relationship("Asset", foreign_keys=[linked_asset_id])
