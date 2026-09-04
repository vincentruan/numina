from datetime import datetime

from sqlalchemy import BigInteger, Float, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from packages.core.snowflake import next_id
from packages.db.session import Base, UTCDateTime


class ExchangeRate(Base):
    __tablename__ = "exchange_rates"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, default=next_id)
    base_currency: Mapped[str] = mapped_column(String(10), default="CNY")
    target_currency: Mapped[str] = mapped_column(String(10), nullable=False)
    rate: Mapped[float] = mapped_column(Float, nullable=False)
    fetched_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), server_default=func.now())

    __table_args__ = (UniqueConstraint("target_currency", "fetched_at"),)
