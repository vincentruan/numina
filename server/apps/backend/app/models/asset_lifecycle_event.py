from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import BigInteger, Date, DateTime, Numeric, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from apps.backend.app.database import Base, UTCDateTime
from apps.backend.app.utils.snowflake import next_id


class AssetLifecycleEvent(Base):
    __tablename__ = "asset_lifecycle_events"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, default=next_id)
    asset_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    event_type: Mapped[str] = mapped_column(String(20), nullable=False)  # 'sold' | 'retired'
    event_date: Mapped[date] = mapped_column(Date, nullable=False)
    sell_price: Mapped[Decimal | None] = mapped_column(Numeric(18, 2), nullable=True)
    sell_fee: Mapped[Decimal | None] = mapped_column(Numeric(18, 2), nullable=True)
    sell_channel: Mapped[str | None] = mapped_column(String(100), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), server_default=func.now())
