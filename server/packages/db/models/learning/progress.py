"""Per-family learning progress models."""

from datetime import datetime

from sqlalchemy import (
    BigInteger,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from packages.core.snowflake import next_id
from packages.db.mixins.json_text import json_text
from packages.db.session import Base, UTCDateTime


class LearningProgress(Base):
    __tablename__ = "learning_progress"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, default=next_id)
    child_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id"), nullable=False, index=True
    )
    topic_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("learning_topics.id"), nullable=False, index=True
    )
    mastery_level: Mapped[str] = mapped_column(
        String(20), nullable=False, default="locked", index=True
    )
    mastery_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    completed_via: Mapped[str | None] = mapped_column(String(20), nullable=True)
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    xp_earned: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_practice_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)
    first_mastered_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)
    stability: Mapped[float | None] = mapped_column(Float, nullable=True, default=1.0)
    next_review_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)
    ability_dimensions_score_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        UTCDateTime(), server_default=func.now(), onupdate=func.now()
    )

    __table_args__ = (
        UniqueConstraint("child_id", "topic_id", name="uq_learning_progress_child_topic"),
    )

    # JSON accessor
    ability_dimensions_score: dict | None = json_text("ability_dimensions_score_json")
