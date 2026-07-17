"""AI 对话消息反馈模型 (点赞/点踩)。

消息内容本身由 DeerFlow checkpointer 持久化,不在 DB 中;
本表仅记录用户对某条 AI 消息的反馈状态,按 (family_id, thread_id, message_id, user_id) 唯一。
"""

from datetime import datetime

from sqlalchemy import (
    BigInteger,
    DateTime,
    ForeignKey,
    SmallInteger,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from apps.backend.app.database import Base
from apps.backend.app.utils.snowflake import next_id


class AIChatMessageFeedback(Base):
    __tablename__ = "ai_chat_message_feedback"
    __table_args__ = (
        # 每个用户对同一条消息只有一个反馈状态
        UniqueConstraint(
            "family_id",
            "thread_id",
            "message_id",
            "user_id",
            name="uq_feedback_family_thread_msg_user",
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, default=next_id)
    family_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("families.id"), nullable=False, index=True
    )
    user_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("users.id"), nullable=True, index=True
    )
    # thread_id 兼容 Snowflake(int) 和 UUID(str) 两种格式,统一存字符串
    thread_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    # message_id 是 LangGraph 分配的 UUID
    message_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    # feedback: 1=点赞, -1=点踩, 0=已取消
    feedback: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=func.now(), onupdate=func.now()
    )
