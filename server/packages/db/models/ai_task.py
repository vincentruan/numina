from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from packages.core.snowflake import next_id
from packages.db.session import Base


class AITask(Base):
    __tablename__ = "ai_tasks"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, default=next_id)
    family_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("families.id"), nullable=False, index=True)
    skill_id: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="running")
    # status: running | queued | completed | failed | timeout | cancelled
    queue_position: Mapped[int | None] = mapped_column(nullable=True)
    session_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("ai_chat_sessions.id"), nullable=True)
    started_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=func.now())
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
