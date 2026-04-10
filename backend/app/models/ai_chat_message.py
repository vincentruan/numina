"""AI 问答消息模型。"""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class AIChatMessage(Base):
    __tablename__ = "ai_chat_messages"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    family_id: Mapped[str] = mapped_column(String(36), ForeignKey("families.id"), nullable=False, index=True)
    role: Mapped[str] = mapped_column(String(10), nullable=False)
    # role: user | assistant
    content: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="completed")
    # status: pending | completed | error
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=func.now())
