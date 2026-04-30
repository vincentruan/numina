# backend/app/models/reminder.py
from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.utils.snowflake import next_id


class Reminder(Base):
    __tablename__ = "reminders"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, default=next_id)
    family_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("families.id"), nullable=False, index=True
    )
    reminder_type: Mapped[str] = mapped_column(String(30), nullable=False)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    severity: Mapped[str] = mapped_column(String(10), nullable=False, default="info")
    asset_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("assets.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="active")
    dismissed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )
