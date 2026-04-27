# backend/app/models/notification_subscription.py
from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.utils.snowflake import next_id


class NotificationSubscription(Base):
    __tablename__ = "notification_subscriptions"
    __table_args__ = (
        UniqueConstraint(
            "channel_id", "reminder_type", name="uq_channel_reminder_type"
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, default=next_id)
    channel_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("notification_channels.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    reminder_type: Mapped[str] = mapped_column(String(30), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
