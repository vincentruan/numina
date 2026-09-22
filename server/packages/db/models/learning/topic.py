"""Global knowledge graph models — shared across all families."""

from datetime import datetime

from sqlalchemy import BigInteger, Float, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from packages.core.snowflake import next_id
from packages.db.mixins.json_text import json_text
from packages.db.session import Base, UTCDateTime


class LearningTopic(Base):
    __tablename__ = "learning_topics"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, default=next_id)
    topic_key: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, index=True)
    topic_type: Mapped[str] = mapped_column(String(20), nullable=False)
    subject: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    domain: Mapped[str | None] = mapped_column(String(100), nullable=True)
    name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    name_zh: Mapped[str | None] = mapped_column(String(200), nullable=True)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    description_zh: Mapped[str | None] = mapped_column(Text, nullable=True)
    age_range_start: Mapped[int | None] = mapped_column(Integer, nullable=True)
    age_range_end: Mapped[int | None] = mapped_column(Integer, nullable=True)
    centrality: Mapped[float | None] = mapped_column(Float, nullable=True)
    # JSON-in-Text pattern: raw Text column + json_text property
    evidence_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    evidence_zh_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    assessment_prompt: Mapped[str | None] = mapped_column(Text, nullable=True)
    assessment_prompt_zh: Mapped[str | None] = mapped_column(Text, nullable=True)
    standards_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    ability_dimensions_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    age_group: Mapped[str] = mapped_column(String(10), nullable=False, default="mid")
    deprecated: Mapped[bool] = mapped_column(default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime(), server_default=func.now(), onupdate=func.now())

    # JSON accessor properties
    evidence: list = json_text("evidence_json")
    evidence_zh: list | None = json_text("evidence_zh_json")
    standards: list = json_text("standards_json")
    ability_dimensions: list | None = json_text("ability_dimensions_json")


class LearningDependency(Base):
    __tablename__ = "learning_dependencies"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, default=next_id)
    topic_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("learning_topics.id"), nullable=False, index=True
    )
    prerequisite_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("learning_topics.id"), nullable=False, index=True
    )
    strength: Mapped[str] = mapped_column(String(10), nullable=False)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)


class LearningCluster(Base):
    __tablename__ = "learning_clusters"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, default=next_id)
    subject: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    domain: Mapped[str] = mapped_column(String(100), nullable=False)
    age_range_start: Mapped[int | None] = mapped_column(Integer, nullable=True)
    age_group: Mapped[str] = mapped_column(String(10), nullable=False, default="mid")
    summary: Mapped[str] = mapped_column(Text, nullable=False, default="")
