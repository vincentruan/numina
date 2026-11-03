from datetime import datetime
from enum import StrEnum

from sqlalchemy import BigInteger, Boolean, ForeignKey, Index, String, Text, func, true
from sqlalchemy.orm import Mapped, mapped_column

from packages.core.snowflake import next_id
from packages.db.session import Base, UTCDateTime


class ScheduledTaskStatus(StrEnum):
    """Lifecycle state of a scheduled task.

    Inherits from str so comparisons with the raw DB column work transparently.
    """

    IDLE = "idle"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"


class ScheduledTask(Base):
    __tablename__ = "scheduled_tasks"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, default=next_id)
    family_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("families.id"), nullable=False
    )
    skill_id: Mapped[str] = mapped_column(String(50), nullable=False)
    cron_expression: Mapped[str] = mapped_column(String(100), nullable=False)
    is_enabled: Mapped[bool] = mapped_column(
        Boolean, default=True, server_default=true(), nullable=False
    )
    next_run_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False)
    last_run_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)
    status: Mapped[str] = mapped_column(
        String(20),
        default=ScheduledTaskStatus.IDLE,
        server_default=ScheduledTaskStatus.IDLE,
        nullable=False,
    )
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        UTCDateTime(), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        UTCDateTime(), server_default=func.now(), onupdate=func.now()
    )

    __table_args__ = (
        Index("ix_scheduled_tasks_family_enabled", "family_id", "is_enabled"),
        Index("ix_scheduled_tasks_poll", "is_enabled", "next_run_at"),
    )
