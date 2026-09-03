from datetime import datetime

from sqlalchemy import (
    BigInteger,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from packages.core.snowflake import next_id
from packages.db.session import Base


class LiteracyBadgeDefinition(Base):
    """Badge tier definition — shared across all children. 4 dimensions × 3 levels = 12 rows."""

    __tablename__ = "literacy_badge_definitions"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, default=next_id)
    dimension: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    level: Mapped[int] = mapped_column(Integer, nullable=False)
    name: Mapped[str] = mapped_column(String(50), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    criteria_summary: Mapped[str] = mapped_column(
        Text, nullable=False, comment="Short description for AI evaluation context"
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        UniqueConstraint("dimension", "level", name="uq_badge_def_dimension_level"),
    )


class LiteracyBadge(Base):
    """Badge earned by a child. superseded_at is set when a higher-level badge replaces it."""

    __tablename__ = "literacy_badges"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, default=next_id)
    child_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id"), nullable=False, index=True
    )
    definition_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("literacy_badge_definitions.id"), nullable=False
    )
    earned_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    superseded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    source: Mapped[str] = mapped_column(
        String(30), nullable=False, comment="scenario / scenario+passive / passive"
    )
