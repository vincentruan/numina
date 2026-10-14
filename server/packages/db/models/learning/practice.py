"""Practice session and attempt models."""

from datetime import datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    Float,
    ForeignKey,
    Index,
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


class PracticeSession(Base):
    """A practice session for a child on a specific topic."""

    __tablename__ = "practice_sessions"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, default=next_id)
    child_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id"), nullable=False, index=True
    )
    topic_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("learning_topics.id"), nullable=False, index=True
    )
    session_mode: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    question_ids_json: Mapped[str] = mapped_column(Text, nullable=False)
    started_at: Mapped[datetime] = mapped_column(
        UTCDateTime(), server_default=func.now()
    )
    ended_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)
    total_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    completed_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    source: Mapped[str] = mapped_column(String(20), nullable=False, default="adaptive")
    learning_progress_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("learning_progress.id"), nullable=True
    )
    validity_flag: Mapped[str | None] = mapped_column(String(20), nullable=True)

    # JSON accessor
    question_ids: list[int] = json_text("question_ids_json")


class PracticeAttempt(Base):
    """Individual answer attempt within a practice session."""

    __tablename__ = "practice_attempts"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, default=next_id)
    session_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("practice_sessions.id"),
        nullable=False,
        index=True,
    )
    question_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("questions.id"), nullable=False, index=True
    )
    child_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id"), nullable=False, index=True
    )
    topic_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("learning_topics.id"), nullable=False, index=True
    )
    user_answer_json: Mapped[str] = mapped_column(Text, nullable=False)
    is_correct: Mapped[bool] = mapped_column(Boolean, nullable=False)
    time_spent_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)
    attempt_number: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    is_retry: Mapped[bool] = mapped_column(Boolean, default=False, server_default="0")
    created_at: Mapped[datetime] = mapped_column(
        UTCDateTime(), server_default=func.now()
    )

    # JSON accessor
    user_answer: dict = json_text("user_answer_json")

    __table_args__ = (
        Index(
            "ix_practice_attempt_child_topic_created",
            "child_id",
            "topic_id",
            "created_at",
        ),
        UniqueConstraint(
            "session_id", "question_id", name="uq_attempt_session_question"
        ),
    )
