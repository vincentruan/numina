"""Learning path — ordered group of topics assigned to a child."""

from datetime import date, datetime

from sqlalchemy import (
    BigInteger,
    Date,
    ForeignKey,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from packages.core.snowflake import next_id
from packages.db.mixins.json_text import json_text
from packages.db.session import Base, UTCDateTime


class LearningPath(Base):
    __tablename__ = "learning_paths"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, default=next_id)
    family_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("families.id"), nullable=False, index=True
    )
    child_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id"), nullable=False, index=True
    )
    created_by: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    name_zh: Mapped[str | None] = mapped_column(String(200), nullable=True)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    description_zh: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="active")
    per_task_score: Mapped[int] = mapped_column(Integer, nullable=False, default=5)
    bonus_score: Mapped[int] = mapped_column(Integer, nullable=False, default=10)
    milestone_scores_json: Mapped[str] = mapped_column(
        Text, nullable=False, default="[]"
    )
    due_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        UTCDateTime(), server_default=func.now()
    )
    completed_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)

    # JSON accessor: list[dict] e.g. [{"threshold": 3, "bonus": 10}]
    milestone_scores: list = json_text("milestone_scores_json")


class LearningPathItem(Base):
    __tablename__ = "learning_path_items"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, default=next_id)
    path_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("learning_paths.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    topic_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("learning_topics.id"), nullable=False
    )
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")
    completed_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)
