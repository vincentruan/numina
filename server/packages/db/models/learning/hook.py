"""Topic hook question model — Socratic curiosity hooks for topic entry."""

from datetime import datetime

from sqlalchemy import BigInteger, ForeignKey, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from packages.core.snowflake import next_id
from packages.db.session import Base, UTCDateTime


class TopicHookQuestion(Base):
    """A Socratic curiosity hook question shown before a topic's introduction.

    Each topic can have up to three age-layered variants (low/mid/high) so that
    a 6-year-old and a 12-year-old see different entry questions for the same
    topic.  The ``age_group`` key mirrors ``LearningTopic.age_group``.
    """

    __tablename__ = "topic_hook_questions"

    __table_args__ = (
        UniqueConstraint("topic_id", "age_group", name="uq_hook_topic_age"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, default=next_id)
    topic_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("learning_topics.id", ondelete="CASCADE"), nullable=False, index=True
    )
    question_text: Mapped[str] = mapped_column(Text, nullable=False)
    question_text_zh: Mapped[str | None] = mapped_column(Text, nullable=True)
    age_group: Mapped[str] = mapped_column(
        String(10), nullable=False, default="mid"
    )
    difficulty: Mapped[str] = mapped_column(
        String(10), nullable=False, default="medium"
    )
    #: ``pending`` until a human reviews the generated text; ``approved`` once
    #: it has been signed off. Hand-authored seed rows are written approved.
    review_status: Mapped[str] = mapped_column(
        String(10), nullable=False, default="pending", server_default="pending"
    )
    created_at: Mapped[datetime] = mapped_column(
        UTCDateTime(), server_default=func.now()
    )
