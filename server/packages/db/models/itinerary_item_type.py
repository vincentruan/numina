"""Itinerary item type — family-scoped custom types for itinerary items."""

from datetime import datetime

from sqlalchemy import BigInteger, ForeignKey, Integer, String, func, text
from sqlalchemy.orm import Mapped, mapped_column

from packages.core.snowflake import next_id
from packages.db.session import Base, UTCDateTime


class ItineraryItemType(Base):
    """行程项自定义类型 — 家庭范围内可复用。

    family_id=null 表示系统预置类型（当前无预置）。
    核心类型 (accommodation/dining/transport/activity) 是 ItineraryItem 上的
    硬编码 enum 值，不在本表中。
    """

    __tablename__ = "itinerary_item_types"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, default=next_id)
    family_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("families.id"), nullable=True)
    name: Mapped[str] = mapped_column(String(50), nullable=False)
    icon: Mapped[str] = mapped_column(String(50), nullable=False, default="star")
    sort_order: Mapped[int] = mapped_column(Integer, default=0, server_default=text("0"))
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime(), server_default=func.now(), onupdate=func.now())
