"""Chore template and instance models for the Core Earn Loop."""

from datetime import datetime
from typing import ClassVar

from sqlalchemy import (
    BigInteger,
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Table,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from apps.backend.app.database import Base, UTCDateTime
from apps.backend.app.utils.snowflake import next_id

# Association table: template ↔ assigned children
chore_template_assignees = Table(
    "chore_template_assignees",
    Base.metadata,
    Column("template_id", BigInteger, ForeignKey("chore_templates.id"), primary_key=True),
    Column("child_user_id", BigInteger, ForeignKey("users.id"), primary_key=True),
)


class ChoreTemplate(Base):
    __tablename__ = "chore_templates"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, default=next_id)
    family_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("families.id"), nullable=False)
    created_by: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    emoji: Mapped[str | None] = mapped_column(String(10), nullable=True)
    coin_reward: Mapped[int] = mapped_column(Integer, nullable=False)
    frequency: Mapped[str] = mapped_column(String(10), nullable=False)  # 'daily' | 'weekly'
    assignment_type: Mapped[str] = mapped_column(String(10), nullable=False)  # 'assigned' | 'pool'
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    # B1 per-template granularity: parent opt-out flag. When False, approving this
    # template's instances will NOT write the education_reward Activity — even if the
    # family-level education_reward_enabled switch is ON. Queried at approval time
    # (not snapshotted) so editing a template never retroactively changes approvals.
    real_reward_enabled: Mapped[bool] = mapped_column(
        Boolean, default=True, server_default=text("true"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime(), server_default=func.now(), onupdate=func.now())

    assignees = relationship("User", secondary=chore_template_assignees, lazy="selectin")
    instances = relationship("ChoreInstance", back_populates="template", lazy="dynamic")


class ChoreInstance(Base):
    __tablename__ = "chore_instances"
    __allow_unmapped__ = True

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, default=next_id)
    template_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("chore_templates.id"), nullable=False)
    family_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("families.id"), nullable=False)
    child_user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"), nullable=False)
    # Snapshot fields — preserved even if template is deleted/renamed
    chore_name: Mapped[str] = mapped_column(String(100), nullable=False)
    chore_emoji: Mapped[str | None] = mapped_column(String(10), nullable=True)
    coin_reward: Mapped[int] = mapped_column(Integer, nullable=False)
    # Date bucket: YYYY-MM-DD for daily, YYYY-Www for weekly
    date_bucket: Mapped[str] = mapped_column(String(10), nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="available", nullable=False)
    # available / pending_approval / approved / rejected
    submitted_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)
    approved_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)
    streak_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    streak_bonus: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    # Tracks the actual child who submitted — needed for pool chores where child_user_id is family_id
    submitted_by_user_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("users.id"), nullable=True)
    # Pool chore assignment tracking
    assigned_by_user_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("users.id"), nullable=True)
    claimed_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)
    consumed_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), server_default=func.now())

    # Transient (non-persisted) flags set by service layer for response serialization
    _is_pool_unclaimed: ClassVar[bool] = False
    _milestone_triggered: ClassVar[str | None] = None
    _child_display_name: ClassVar[str | None] = None
    _child_avatar_color: ClassVar[str | None] = None
    _child_user_id: ClassVar[int | None] = None

    template = relationship("ChoreTemplate", back_populates="instances")

    __table_args__ = (
        UniqueConstraint(
            "template_id", "child_user_id", "date_bucket",
            name="uq_chore_instance"
        ),
    )
