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

from apps.backend.app.database import Base, UTCDateTime
from apps.backend.app.utils.snowflake import next_id


class AIReport(Base):
    __tablename__ = "ai_reports"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, default=next_id)
    family_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("families.id"), nullable=False, index=True)
    report_json: Mapped[dict] = mapped_column(JSON, nullable=False)
    overall_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    data_completeness_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    generated_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False, default=func.now())
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="completed")
    # Path to markdown report file (relative path under tenant reports directory)
    markdown_file_path: Mapped[str | None] = mapped_column(String(255), nullable=True)
    # Plan A: skill_id scoping. 'report' (existing, default) | 'finance_coach' |
    # 'wish_advice' (Plan B W4). server_default='report' keeps existing rows valid
    # without a data backfill migration. _latest_report / latest_by_skill
    # filter by (family_id, skill_id, status).
    skill_id: Mapped[str] = mapped_column(String(32), nullable=False, default="report", server_default="report")
    # status: pending | completed | error
