"""AI 负债建议结果持久化。"""

from datetime import datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    JSON,
    String,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from apps.backend.app.database import Base
from apps.backend.app.utils.snowflake import next_id


class AILiabilityResult(Base):
    """AI 负债建议分析结果（每次扫描替换旧数据）。"""

    __tablename__ = "ai_liability_results"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, default=next_id)
    family_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("families.id"), nullable=False, index=True
    )
    has_liabilities: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    total_remaining: Mapped[float | None] = mapped_column(Float, nullable=True)
    total_monthly_payment: Mapped[float | None] = mapped_column(Float, nullable=True)
    liability_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    narrative: Mapped[str | None] = mapped_column(Text, nullable=True)
    recommended_strategy: Mapped[str | None] = mapped_column(String(20), nullable=True)
    # recommended_strategy: avalanche | snowball | hybrid
    strategies_json: Mapped[list | None] = mapped_column(JSON, nullable=True)
    # [{strategy, strategy_name, estimated_interest_saved, priority_debt, order: [...]}]
    generated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=func.now())