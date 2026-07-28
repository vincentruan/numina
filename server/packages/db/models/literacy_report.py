from datetime import date, datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from packages.core.snowflake import next_id
from packages.db.session import Base


class LiteracyWeeklyReport(Base):
    """AI-generated weekly literacy report for a child. One per child per week."""

    __tablename__ = "literacy_weekly_reports"
    __table_args__ = (
        UniqueConstraint("child_id", "week_start", name="uq_literacy_report_child_week"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, default=next_id)
    child_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id"), nullable=False, index=True
    )
    week_start: Mapped[date] = mapped_column(nullable=False, index=True)
    report_json: Mapped[str] = mapped_column(Text, nullable=False, comment="Structured report data")
    narrative: Mapped[str] = mapped_column(Text, nullable=False, comment="AI-generated narrative text")
    generated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)
