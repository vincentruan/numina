"""AI 对话会话模型 — 存储会话元数据，消息内容存储在 JSONL 文件中。"""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class AIChatSession(Base):
    __tablename__ = "ai_chat_sessions"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    family_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("families.id"), nullable=False, index=True
    )
    user_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("users.id"), nullable=True
    )
    cached_file_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("cached_files.id"), nullable=True
    )
    jsonl_path: Mapped[str] = mapped_column(
        String(500), nullable=False
    )  # Relative to CHAT_DIR
    message_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_preview: Mapped[str | None] = mapped_column(
        Text, nullable=True
    )  # Last assistant message preview (first 100 chars)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=func.now(), onupdate=func.now()
    )
