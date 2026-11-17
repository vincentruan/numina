"""Misconception catalog and detection recording models."""

from datetime import datetime

from sqlalchemy import (
    BigInteger,
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


class Misconception(Base):
    """A known misconception for a topic — part of the misconception catalog.

    Each entry describes a common error pattern children make on a specific topic.
    When a child's wrong answer matches the error_pattern, the system provides
    targeted emotional feedback and optionally offers a diagnostic question.

    Mirrors the TopicConfusion pattern: manual seeding, review_status gating,
    age_group segmentation, sequence ordering.
    """

    __tablename__ = "misconceptions"

    __table_args__ = (
        UniqueConstraint(
            "topic_id", "age_group", "sequence", name="uq_misconception_topic_age_seq"
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, default=next_id)
    topic_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("learning_topics.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    #: Order within a topic's misconception list (0-indexed).
    sequence: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    #: JSON pattern describing how to detect this misconception.
    #: Examples:
    #:   {"match_type": "symbolic", "expected_wrong": "2/7"}
    #:   {"match_type": "numeric", "expected_wrong": 0.286, "tolerance": 0.01}
    #:   {"match_type": "parametric", "algorithm": "fraction_add_numerators"}
    error_pattern_json: Mapped[str] = mapped_column(Text, nullable=False)
    #: Explanation of the misconception (shown to the child as feedback).
    description: Mapped[str] = mapped_column(Text, nullable=False)
    #: Chinese translation.
    description_zh: Mapped[str | None] = mapped_column(Text, nullable=True)
    #: Age group this misconception targets (mirrors LearningTopic.age_group).
    age_group: Mapped[str] = mapped_column(
        String(10), nullable=False, default="mid", server_default="mid"
    )
    #: Optional diagnostic question to offer after detection.
    diagnostic_question_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("questions.id", ondelete="SET NULL"),
        nullable=True,
    )
    #: ``pending`` until reviewed; ``approved`` once signed off.
    review_status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="pending", server_default="pending"
    )
    #: Classification of the misconception. Drives feedback tone:
    #: concept_confusion ("common mix-up"), procedural_error ("steps got
    #: mixed up"), carelessness (no misconception-specific feedback).
    #: Nullable for backward compatibility with pre-category rows.
    category: Mapped[str | None] = mapped_column(
        String(30), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        UTCDateTime(), server_default=func.now()
    )

    # JSON accessor
    error_pattern: dict | None = json_text("error_pattern_json")


class MisconceptionDetection(Base):
    """Records each time a child's wrong answer matches a known misconception.

    Written server-side when detect_misconception() returns a match after a
    wrong answer submission. Enables future analytics: which misconceptions
    are most common, per-child detection patterns, resolution tracking.
    """

    __tablename__ = "misconception_detections"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, default=next_id)
    child_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    topic_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("learning_topics.id", ondelete="CASCADE"), nullable=False, index=True
    )
    #: CASCADE — detections are meaningless without the misconception.
    misconception_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("misconceptions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    question_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("questions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    #: The child's wrong answer that triggered the detection.
    wrong_answer_json: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        UTCDateTime(), server_default=func.now()
    )

    __table_args__ = (
        Index(
            "ix_misconception_detection_child_topic_created",
            "child_id",
            "topic_id",
            "created_at",
        ),
    )


# Valid values for Misconception.category — drives feedback tone in the
# Smart Tutor SKILL.md prompt (U5) and validates the column's enum-like values.
MISCONCEPTION_CATEGORIES = frozenset(
    {"concept_confusion", "procedural_error", "carelessness"}
)
