"""AI 资产配置目标模型。"""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, JSON, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class AIAllocationTarget(Base):
    __tablename__ = "ai_allocation_targets"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    family_id: Mapped[str] = mapped_column(String(36), ForeignKey("families.id"), nullable=False, unique=True, index=True)
    # category_targets: {"physical": 60, "financial": 40} or per-category
    category_targets: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    drift_threshold: Mapped[float] = mapped_column(Float, nullable=False, default=10.0)
    # percentage points before alerting
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=func.now(), onupdate=func.now())
