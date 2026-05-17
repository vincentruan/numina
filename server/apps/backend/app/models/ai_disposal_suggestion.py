"""低效资产处置建议模型。"""

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


class AIDisposalSuggestion(Base):
    __tablename__ = "ai_disposal_suggestions"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, default=next_id)
    family_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("families.id"), nullable=False, index=True)
    asset_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("assets.id"), nullable=True)
    asset_name: Mapped[str] = mapped_column(String(200), nullable=False)
    category_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    inefficiency_score: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    # 0-100, higher = more inefficient
    suggested_channel: Mapped[str | None] = mapped_column(String(100), nullable=True)
    estimated_resale_range: Mapped[str | None] = mapped_column(String(100), nullable=True)
    suggestion: Mapped[str | None] = mapped_column(Text, nullable=True)
    daily_cost: Mapped[float | None] = mapped_column(Float, nullable=True)
    is_dismissed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=func.now())
    dismissed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
