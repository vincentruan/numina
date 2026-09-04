"""Skill registry model for per-family skill configuration."""

from datetime import datetime

from sqlalchemy import (
    JSON,
    BigInteger,
    Boolean,
    DateTime,
    Integer,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from apps.backend.app.database import Base, UTCDateTime
from apps.backend.app.utils.snowflake import next_id


class SkillRegistry(Base):
    """Per-family skill configuration registry.

    Stores enabled status, display order, and metadata for both built-in
    and custom skills. Built-in skill metadata is synced from SKILL.md frontmatter;
    custom skill metadata is user-provided.
    """

    __tablename__ = "ai_skills"
    __table_args__ = (
        UniqueConstraint("family_id", "skill_id", name="uq_ai_skills_family_skill"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, default=next_id)
    family_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    skill_id: Mapped[str] = mapped_column(String(64), nullable=False)
    skill_type: Mapped[str] = mapped_column(String(16), nullable=False)  # 'fixed' | 'builtin' | 'custom'

    # UI metadata (only stored for custom skills; builtin synced from SKILL.md)
    name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    description: Mapped[str | None] = mapped_column(String(512), nullable=True)
    icon: Mapped[str | None] = mapped_column(String(32), nullable=True)  # emoji
    color: Mapped[str | None] = mapped_column(String(16), nullable=True)
    route: Mapped[str | None] = mapped_column(String(64), nullable=True)
    input_mode: Mapped[str | None] = mapped_column(String(16), nullable=True, default="trigger")
    placeholder: Mapped[str | None] = mapped_column(String(256), nullable=True)
    examples: Mapped[list | None] = mapped_column(JSON, nullable=True)

    # Configuration
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    display_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    # Provenance
    creation_type: Mapped[str] = mapped_column(String(16), nullable=False, server_default="manual")  # 'manual' | 'cmd' | 'ai_created'
    source_url: Mapped[str | None] = mapped_column(String(512), nullable=True)

    # Audit
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime(), server_default=func.now(), onupdate=func.now())
    created_by: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
