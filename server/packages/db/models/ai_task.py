from datetime import datetime

from sqlalchemy import (
    JSON,
    BigInteger,
    DateTime,
    ForeignKey,
    Index,
    String,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from packages.core.snowflake import next_id
from packages.db.session import Base


class AITask(Base):
    __tablename__ = "ai_tasks"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, default=next_id)
    family_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("families.id"), nullable=False, index=True)
    # Legacy `capability` column kept for backward compatibility — always mirrors
    # ``skill_id`` so legacy queries (agent, scheduler) still work. New code uses
    # ``skill_id`` exclusively.
    capability: Mapped[str] = mapped_column(String(50), nullable=False, default="")
    skill_id: Mapped[str] = mapped_column(String(50), nullable=False, index=True, default="")
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="running")
    # status: running | queued | completed | failed | timeout | cancelled | interrupted
    queue_position: Mapped[int | None] = mapped_column(nullable=True)
    session_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("ai_chat_sessions.id"), nullable=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=func.now())
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    # New fields for StreamBridge task tracking (U3)
    run_id: Mapped[str | None] = mapped_column(
        String(64), nullable=True, index=True, comment="Agent RunRecord ID for bridge reconnection"
    )
    worker_id: Mapped[str | None] = mapped_column(
        String(128), nullable=True, comment="hostname:uuid of processing worker"
    )
    lease_expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, comment="Heartbeat deadline for dead-worker detection (UTC)"
    )
    progress: Mapped[dict | None] = mapped_column(
        JSON, nullable=True, comment="Optional JSON blob (step, percentage, message)"
    )

    # Composite index for efficient task queries by family + skill + status
    __table_args__ = (
        Index("ix_ai_tasks_family_skill_status", "family_id", "skill_id", "status"),
    )
