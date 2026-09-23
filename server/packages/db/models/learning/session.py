"""Per-family learning session and assessment models."""

from datetime import datetime

from sqlalchemy import BigInteger, Float, ForeignKey, Index, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from packages.core.snowflake import next_id
from packages.db.mixins.json_text import json_text
from packages.db.session import Base, UTCDateTime


class LearningSession(Base):
    __tablename__ = "learning_sessions"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, default=next_id)
    assignment_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("learning_assignments.id"), nullable=True
    )
    child_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id"), nullable=False, index=True
    )
    topic_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("learning_topics.id"), nullable=False, index=True
    )
    thread_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    session_type: Mapped[str] = mapped_column(
        String(20), nullable=False, default="tutorial"
    )
    ai_evaluation_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    score: Mapped[float | None] = mapped_column(Float, nullable=True)
    duration_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)
    started_at: Mapped[datetime] = mapped_column(UTCDateTime(), server_default=func.now())
    ended_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)

    # JSON accessor
    ai_evaluation: dict | None = json_text("ai_evaluation_json")


class LearningAssessmentAttempt(Base):
    __tablename__ = "learning_assessment_attempts"

    __table_args__ = (
        Index("ix_assessment_attempt_child_topic_created", "child_id", "topic_id", "created_at"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, default=next_id)
    child_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id"), nullable=False, index=True
    )
    topic_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("learning_topics.id"), nullable=False, index=True
    )
    session_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("learning_sessions.id"), nullable=True
    )
    assessment_type: Mapped[str] = mapped_column(String(20), nullable=False)
    score: Mapped[float | None] = mapped_column(Float, nullable=True)
    passed: Mapped[bool] = mapped_column(default=False, nullable=False)
    ai_confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    evidence_results_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    ability_dimensions_delta_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    duration_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), server_default=func.now())

    # JSON accessors
    evidence_results: list | None = json_text("evidence_results_json")
    ability_dimensions_delta: dict | None = json_text("ability_dimensions_delta_json")
