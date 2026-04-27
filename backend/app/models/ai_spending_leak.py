from datetime import datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    String,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.utils.snowflake import next_id


class AISpendingLeak(Base):
    __tablename__ = "ai_spending_leaks"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, default=next_id)
    family_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("families.id"), nullable=False, index=True)
    asset_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("assets.id"), nullable=False)
    asset_name: Mapped[str] = mapped_column(String(200), nullable=False)
    leak_type: Mapped[str] = mapped_column(String(50), nullable=False)
    # leak_type: high_idle_cost | redundant | high_maintenance
    severity: Mapped[str] = mapped_column(String(20), nullable=False, default="medium")
    # severity: low | medium | high
    estimated_annual_waste: Mapped[float | None] = mapped_column(Float, nullable=True)
    suggestion: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_dismissed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=func.now())
    dismissed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
