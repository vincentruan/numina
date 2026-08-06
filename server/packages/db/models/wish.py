from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    TIMESTAMP,
    BigInteger,
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Numeric,
    String,
    Text,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from packages.core.snowflake import next_id
from packages.db.session import Base


class Wish(Base):
    __tablename__ = "wishes"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, default=next_id)
    family_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("families.id"), nullable=False)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    expected_price: Mapped[Decimal | None] = mapped_column(Numeric(18, 2), nullable=True)
    priority: Mapped[str] = mapped_column(String(20), default="medium")  # low/medium/high
    status: Mapped[str] = mapped_column(String(20), default="pending")  # pending/realized/cancelled
    category_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("categories.id"), nullable=True)
    currency: Mapped[str] = mapped_column(String(10), default="CNY")
    # Plan B W1: savings progress fields.
    # saved_amount is a DERIVED cache of SUM(wish_savings_log.amount); maintained
    # in-transaction by the savings CRUD (see wish_savings.py). source of truth =
    # wish_savings_log. NUMERIC(18,2) — serialized as str (2 decimals) in API.
    saved_amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False, default=Decimal("0"), server_default="0")
    target_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    monthly_saving: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False, default=Decimal("0"), server_default="0")
    # Plan B W5: per-wish opt-out of the high-interest-debt linkage hint.
    ignore_debt_warning: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default=text("false"))
    converts_to_asset: Mapped[bool] = mapped_column(Boolean, default=True, server_default=text("true"))
    realized_asset_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("assets.id"), nullable=True)
    fulfilled_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())

    user = relationship("User", back_populates="wishes")
    category = relationship("Category")
    realized_asset = relationship("Asset", foreign_keys=[realized_asset_id])
