"""AI 对话会话模型 - 存储会话元数据。

消息内容由 DeerFlow checkpointer 持久化，不再写 JSONL 文件。
"""

from datetime import datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    ForeignKey,
    String,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from apps.backend.app.database import Base
from apps.backend.app.utils.snowflake import next_id


class AIChatSession(Base):
    __tablename__ = "ai_chat_sessions"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, default=next_id)
    family_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("families.id"), nullable=False, index=True
    )
    user_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("users.id"), nullable=True
    )
    agent_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("ai_agents.id", ondelete="SET NULL"), nullable=True, index=True
    )
    title: Mapped[str | None] = mapped_column(String(256), nullable=True)
    # Preserved auto-generated title (from DeerFlow TitleMiddleware) before the
    # user manually renames — see internal_update_session_summary's preserve logic.
    original_title: Mapped[str | None] = mapped_column(String(256), nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="active")
    last_message_summary: Mapped[str | None] = mapped_column(String(200), nullable=True)
    last_model: Mapped[str | None] = mapped_column(String(128), nullable=True)
    is_pinned: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    # LangGraph thread_id (UUID) — populated when the session originates from
    # the frontend createThread path (agent generates UUID).  Null for sessions
    # created via the backend chat_stream path (thread_id == str(id)).
    # Lookup must check this column when the caller passes a UUID string,
    # because the PK ``id`` is BigInteger and cannot store UUIDs.
    thread_id: Mapped[str | None] = mapped_column(
        String(64), nullable=True, unique=True, index=True
    )
    source: Mapped[str | None] = mapped_column(String(32), nullable=True)
    # Thread this session was branched from (UUID string of the parent thread).
    # No FK: the parent thread may live in a different family's checkpoint
    # context and cross-family access is enforced at the application layer
    # (get_thread family gating). Null for non-branch sessions.
    parent_thread_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=func.now(), onupdate=func.now()
    )
