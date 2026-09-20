"""Trip model for the family travel module."""

from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    BigInteger,
    Boolean,
    Date,
    ForeignKey,
    Numeric,
    String,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from packages.core.snowflake import next_id
from packages.db.session import Base, UTCDateTime


class Trip(Base):
    """家庭旅行 — 从心愿转化或直接创建。

    status: planning → active → settled → archived
    is_active=False 表示已取消或已归档（软删除）
    wish_id 非 null 时表示从心愿转化而来
    """

    __tablename__ = "trips"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, default=next_id)
    family_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("families.id"), nullable=False)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    destination: Mapped[str] = mapped_column(String(200), nullable=False)
    departure_date: Mapped[date] = mapped_column(Date, nullable=False)
    return_date: Mapped[date | None] = mapped_column(Date, nullable=True)  # null=不定返程
    status: Mapped[str] = mapped_column(String(20), default="planning", server_default="planning")
    # Money fields are NUMERIC(18,2) — Decimal in Python, serialized as str on the wire.
    planned_budget: Mapped[Decimal | None] = mapped_column(Numeric(18, 2), nullable=True)
    initial_funding: Mapped[Decimal | None] = mapped_column(Numeric(18, 2), nullable=True)  # from wish savings
    actual_spend: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False, default=0, server_default=text("0"))
    currency: Mapped[str] = mapped_column(String(10), default="CNY", server_default="CNY")
    wish_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("wishes.id"), nullable=True)
    timezone: Mapped[str | None] = mapped_column(String(50), nullable=True)  # IANA TZ for display
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default=text("true"))
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime(), server_default=func.now(), onupdate=func.now())
