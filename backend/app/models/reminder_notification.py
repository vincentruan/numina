from datetime import datetime

from sqlalchemy import BigInteger, DateTime, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.utils.snowflake import next_id


class ReminderNotification(Base):
    __tablename__ = "reminder_notifications"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, default=next_id)
    reminder_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    channel_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="sent")  # 'sent' | 'failed'
    sent_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
