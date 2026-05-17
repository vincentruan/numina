"""AI 资产配置偏离分析结果持久化。"""

from datetime import datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    JSON,
    String,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from apps.backend.app.database import Base
from apps.backend.app.utils.snowflake import next_id


class AIAllocationDriftResult(Base):
    """AI 资产配置偏离分析结果（每次扫描替换旧数据）。"""

    __tablename__ = "ai_allocation_drift_results"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, default=next_id)
    family_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("families.id"), nullable=False, index=True
    )
    has_significant_drift: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    narrative: Mapped[str | None] = mapped_column(Text, nullable=True)
    drifts_json: Mapped[list | None] = mapped_column(JSON, nullable=True)
    # [{category, target_pct, current_pct, drift, exceeds_threshold}]
    generated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=func.now())