"""AI 资产配置目标模型。"""

from datetime import datetime

from sqlalchemy import JSON, BigInteger, DateTime, Float, ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column

from apps.backend.app.database import Base
from apps.backend.app.utils.snowflake import next_id


class AIAllocationTarget(Base):
    __tablename__ = "ai_allocation_targets"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, default=next_id)
    family_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("families.id"), nullable=False, unique=True, index=True)
    # category_targets: {"physical": 60, "financial": 40} or per-category
    category_targets: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    drift_threshold: Mapped[float] = mapped_column(Float, nullable=False, default=10.0)
    # percentage points before alerting
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=func.now(), onupdate=func.now())
