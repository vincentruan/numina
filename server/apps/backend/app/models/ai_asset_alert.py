"""固定资产老化预警模型。"""

from datetime import datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from apps.backend.app.database import Base
from apps.backend.app.utils.snowflake import next_id


class AIAssetAlert(Base):
    __tablename__ = "ai_asset_alerts"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, default=next_id)
    family_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("families.id"), nullable=False, index=True)
    asset_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("assets.id"), nullable=True)
    asset_name: Mapped[str] = mapped_column(String(200), nullable=False)
    alert_type: Mapped[str] = mapped_column(String(50), nullable=False)
    # alert_type: aging | high_maintenance | idle_cost
    severity: Mapped[str] = mapped_column(String(20), nullable=False, default="medium")
    # severity: low | medium | high
    suggestion: Mapped[str] = mapped_column(Text, nullable=True)
    remaining_life_days: Mapped[int | None] = mapped_column(Integer, nullable=True)
    daily_cost: Mapped[float | None] = mapped_column(Float, nullable=True)
    is_dismissed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=func.now())
    dismissed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
