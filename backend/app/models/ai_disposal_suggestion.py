"""低效资产处置建议模型。"""

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class AIDisposalSuggestion(Base):
    __tablename__ = "ai_disposal_suggestions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    family_id: Mapped[str] = mapped_column(String(36), ForeignKey("families.id"), nullable=False, index=True)
    asset_id: Mapped[str] = mapped_column(String(36), ForeignKey("assets.id"), nullable=False)
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
