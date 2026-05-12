"""AI 对话会话模型 — 存储会话元数据，消息内容存储在 JSONL 文件中。"""

from datetime import datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.utils.snowflake import next_id


class AIChatSession(Base):
    __tablename__ = "ai_chat_sessions"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, default=next_id)
    family_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("families.id"), nullable=False, index=True
    )
    user_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("users.id"), nullable=True
    )
    cached_file_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("cached_files.id"), nullable=True
    )
    capability: Mapped[str] = mapped_column(String(32), nullable=False, default="chat")
    title: Mapped[str | None] = mapped_column(String(256), nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="active")
    jsonl_path: Mapped[str] = mapped_column(String(512), nullable=False)
    last_message_summary: Mapped[str | None] = mapped_column(String(200), nullable=True)
    last_model: Mapped[str | None] = mapped_column(String(128), nullable=True)
    has_attachments: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    # Kept for backward compatibility — no longer written by agent
    message_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_preview: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=func.now(), onupdate=func.now()
    )
