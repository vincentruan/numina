"""AI 问答消息模型。

DEPRECATED: Messages are now stored in JSONL files via AIChatSession.
This table is kept for migration rollback only — no new writes should occur.
"""

from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.utils.snowflake import next_id


class AIChatMessage(Base):
    __tablename__ = "ai_chat_messages"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, default=next_id)
    family_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("families.id"), nullable=False, index=True)
    role: Mapped[str] = mapped_column(String(10), nullable=False)
    # role: user | assistant
    content: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="completed")
    # status: pending | completed | error
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=func.now())
