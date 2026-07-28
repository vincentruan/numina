from datetime import date, datetime

from sqlalchemy import BigInteger, Boolean, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from packages.core.snowflake import next_id
from packages.db.session import Base


class LiteracyScenarioTemplate(Base):
    """Scenario template — dimension × age_group combinations. Seeded, expanded via AI batch."""

    __tablename__ = "literacy_scenario_templates"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, default=next_id)
    dimension: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    age_group: Mapped[str] = mapped_column(
        String(10), nullable=False, comment="low (5-7) / mid (8-10) / high (11+)"
    )
    story_template: Mapped[str] = mapped_column(Text, nullable=False)
    choices_json: Mapped[str] = mapped_column(
        Text, nullable=False, comment="JSON array of 2-4 choices with feedback"
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class LiteracyScenario(Base):
    """Weekly scenario assigned to a child. One per child per week."""

    __tablename__ = "literacy_scenarios"
    __table_args__ = (
        UniqueConstraint("child_id", "week_start", name="uq_literacy_scenario_child_week"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, default=next_id)
    child_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id"), nullable=False, index=True
    )
    week_start: Mapped[date] = mapped_column(nullable=False, index=True)
    template_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("literacy_scenario_templates.id"), nullable=False
    )
    content_json: Mapped[str] = mapped_column(Text, nullable=False, comment="Personalized scenario content")
    choice_index: Mapped[int | None] = mapped_column(Integer, nullable=True)
    feedback_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
