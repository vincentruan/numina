from datetime import datetime

from sqlalchemy import BigInteger, DateTime, Float, ForeignKey, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.utils.snowflake import next_id


class AssetValuation(Base):
    __tablename__ = "asset_valuations"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, default=next_id)
    asset_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("assets.id"), nullable=False)
    value: Mapped[float] = mapped_column(Float, nullable=False)
    valued_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
