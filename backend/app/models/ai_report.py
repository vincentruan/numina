from datetime import datetime

from sqlalchemy import (
    JSON,
    BigInteger,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.utils.snowflake import next_id


class AIReport(Base):
    __tablename__ = "ai_reports"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, default=next_id)
    family_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("families.id"), nullable=False, index=True)
    report_json: Mapped[dict] = mapped_column(JSON, nullable=False)
    overall_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    data_completeness_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    generated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=func.now())
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="completed")
    # status: pending | completed | error
