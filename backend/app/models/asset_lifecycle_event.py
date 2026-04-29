import datetime as dt
from datetime import datetime

from sqlalchemy import BigInteger, Date, DateTime, Float, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.utils.snowflake import next_id


class AssetLifecycleEvent(Base):
    __tablename__ = "asset_lifecycle_events"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, default=next_id)
    asset_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    event_type: Mapped[str] = mapped_column(String(20), nullable=False)  # 'sold' | 'retired'
    event_date: Mapped[dt.date] = mapped_column(Date, nullable=False)
    sell_price: Mapped[float | None] = mapped_column(Float, nullable=True)
    sell_fee: Mapped[float | None] = mapped_column(Float, nullable=True)
    sell_channel: Mapped[str | None] = mapped_column(String(100), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
