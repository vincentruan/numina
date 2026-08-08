from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    BigInteger,
    Boolean,
    Date,
    DateTime,
    Float,
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


class Liability(Base):
    __tablename__ = "liabilities"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, default=next_id)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"), nullable=False)
    family_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("families.id"), nullable=False)
    category: Mapped[str] = mapped_column(String(30), nullable=False)  # mortgage/car_loan/credit_card/personal_loan/other
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    # Money fields are NUMERIC(18,2) — Decimal in Python, serialized as str on
    # the wire (SnowflakeBase money-as-str convention, CLAUDE.md §bigint). Was
    # Float pre-T8b (precision risk for currency); migrated to Numeric.
    original_amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    remaining_amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    monthly_payment: Mapped[Decimal | None] = mapped_column(Numeric(18, 2), nullable=True)
    interest_rate: Mapped[float | None] = mapped_column(Float, nullable=True)
    start_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    end_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    institution: Mapped[str | None] = mapped_column(String(200), nullable=True)
    linked_asset_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("assets.id"), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    is_archived: Mapped[bool] = mapped_column(Boolean, default=False, server_default=text("false"))
    currency: Mapped[str] = mapped_column(String(10), default="CNY")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())

    user = relationship("User", back_populates="liabilities")
    linked_asset = relationship("Asset", back_populates="linked_liabilities")
