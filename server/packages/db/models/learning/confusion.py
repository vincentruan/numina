"""Topic confusion model — preset misconceptions for teach-back sessions."""

from datetime import datetime

from sqlalchemy import (
    BigInteger,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from packages.core.snowflake import next_id
from packages.db.session import Base, UTCDateTime


class TopicConfusion(Base):
    """A preset misconception the AI student "doesn't understand" in a teach-back session.

    Each pilot topic has 2-4 hand-authored confusions. The child must explain
    each one convincingly. ``review_status`` gates visibility: only ``approved``
    rows are served to the teach-back flow, which is the enforcement mechanism
    that prevents runtime-LLM-generated confusions.

    Modeled on ``TopicHookQuestion``.
    """

    __tablename__ = "topic_confusions"

    __table_args__ = (
        UniqueConstraint(
            "topic_id", "age_group", "sequence", name="uq_confusion_topic_age_seq"
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, default=next_id)
    topic_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("learning_topics.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    #: Order within a topic's confusion list (0-indexed).
    sequence: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    #: What the AI student "doesn't get" — shown to the child.
    confusion_text: Mapped[str] = mapped_column(Text, nullable=False)
    #: Chinese translation (nullable for future i18n).
    confusion_text_zh: Mapped[str | None] = mapped_column(Text, nullable=True)
    #: Age group this confusion targets (mirrors LearningTopic.age_group).
    age_group: Mapped[str] = mapped_column(
        String(10), nullable=False, default="mid", server_default="mid"
    )
    #: LLM grading rubric — instructions for judging whether the child's
    #: explanation hits this confusion's core concept.
    rubric: Mapped[str] = mapped_column(Text, nullable=False)
    #: Expected math expression for SymPy comparison (nullable — concept-only
    #: confusions leave this empty).
    expected_expression: Mapped[str | None] = mapped_column(Text, nullable=True)
    #: ``pending`` until a human reviews; ``approved`` once signed off.
    #: Hand-authored seed rows are written ``approved``.
    review_status: Mapped[str] = mapped_column(
        String(10), nullable=False, default="pending", server_default="pending"
    )
    created_at: Mapped[datetime] = mapped_column(
        UTCDateTime(), server_default=func.now()
    )
