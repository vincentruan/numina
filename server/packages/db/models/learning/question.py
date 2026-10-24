"""Question bank models."""
import json
from datetime import datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
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


class Question(Base):
    """A practice question linked to a knowledge point."""

    __tablename__ = "questions"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, default=next_id)
    topic_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("learning_topics.id"), nullable=False, index=True
    )
    question_type: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    stem: Mapped[str] = mapped_column(Text, nullable=False)
    stem_zh: Mapped[str | None] = mapped_column(Text, nullable=True)
    options_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    answer_json: Mapped[str] = mapped_column(Text, nullable=False)
    solution_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    difficulty: Mapped[int] = mapped_column(
        Integer, nullable=False, default=1, index=True
    )
    bloom_level: Mapped[str] = mapped_column(
        String(20), nullable=False, default="apply"
    )
    source: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    source_version: Mapped[str | None] = mapped_column(String(50), nullable=True)
    review_status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="pending", index=True
    )
    review_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    age_group: Mapped[str] = mapped_column(String(10), nullable=False, index=True)
    parameters_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    times_used: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    correct_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(
        UTCDateTime(), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        UTCDateTime(), server_default=func.now(), onupdate=func.now()
    )

    # P7a: content deduplication
    content_hash: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)

    # P7b: source metadata for external/LLM imports
    source_name: Mapped[str | None] = mapped_column(String(50), nullable=True)
    source_license: Mapped[str | None] = mapped_column(String(50), nullable=True)
    imported_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)

    # P7b: AI grading explainability
    grading_explanation_json: Mapped[str | None] = mapped_column(Text, nullable=True)

    # P7e: quality monitoring (added now to avoid future migration)
    suspicious: Mapped[bool] = mapped_column(Boolean, default=False, server_default="0")
    needs_review: Mapped[bool] = mapped_column(Boolean, default=False, server_default="0")
    empirical_difficulty: Mapped[float | None] = mapped_column(Float, nullable=True)

    # P7b: risk classification (set by classify_risk() in Task 6)
    risk: Mapped[str | None] = mapped_column(String(10), nullable=True, index=True)
    # P7b: family scoping for review-queue isolation
    family_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True, index=True)

    # JSON accessors
    options: list | None = json_text("options_json")
    answer: dict = json_text("answer_json")
    solution: dict | None = json_text("solution_json")
    parameters: dict | None = json_text("parameters_json")

    @property
    def grading_explanation(self) -> dict | None:
        if self.grading_explanation_json:
            return json.loads(self.grading_explanation_json)
        return None


class QuestionKnowledgePoint(Base):
    """Many-to-many link between questions and knowledge points."""

    __tablename__ = "question_knowledge_points"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, default=next_id)
    question_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("questions.id"), nullable=False, index=True
    )
    topic_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("learning_topics.id"), nullable=False, index=True
    )
    role: Mapped[str] = mapped_column(
        String(20), nullable=False, default="primary"
    )

    __table_args__ = (
        UniqueConstraint("question_id", "topic_id", name="uq_question_topic"),
    )
