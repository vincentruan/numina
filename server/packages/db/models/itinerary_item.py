"""Itinerary item model — day-by-day trip planning entries."""

from datetime import date, datetime, time
from decimal import Decimal

from sqlalchemy import (
    BigInteger,
    Date,
    ForeignKey,
    Integer,
    JSON,
    Numeric,
    String,
    Text,
    Time,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from packages.core.snowflake import next_id
from packages.db.session import Base, UTCDateTime


class ItineraryItem(Base):
    """行程项 — 按天的旅行计划条目。

    type: accommodation | dining | transport | activity | custom
    type_metadata: JSON 存放类型特有字段
      - accommodation: {"check_in_time": "14:00", "check_out_time": "12:00"}
      - dining: {"diners": 4}
      - transport: {"origin": "...", "destination": "..."}
      - activity: {"ticket_price": "100.00"}
      - custom: 用户自定义
    """

    __tablename__ = "itinerary_items"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, default=next_id)
    trip_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("trips.id"), nullable=False)
    family_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("families.id"), nullable=False)
    date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    type: Mapped[str] = mapped_column(String(20), nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, default=0, server_default=text("0"))
    start_time: Mapped[time | None] = mapped_column(Time, nullable=True)
    end_time: Mapped[time | None] = mapped_column(Time, nullable=True)
    location: Mapped[str | None] = mapped_column(String(200), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    cost_amount: Mapped[Decimal | None] = mapped_column(Numeric(18, 2), nullable=True)
    cost_currency: Mapped[str | None] = mapped_column(String(10), nullable=True)
    purchase_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    custom_type_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("itinerary_item_types.id"), nullable=True
    )
    type_metadata: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime(), server_default=func.now(), onupdate=func.now())
