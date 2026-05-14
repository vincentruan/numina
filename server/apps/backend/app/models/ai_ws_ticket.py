from datetime import datetime

from sqlalchemy import BigInteger, Boolean, DateTime, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column

from apps.backend.app.database import Base
from apps.backend.app.utils.snowflake import next_id


class AIWsTicket(Base):
    """One-time WebSocket authentication ticket (30s TTL)."""

    __tablename__ = "ai_ws_tickets"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, default=next_id)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"), nullable=False, index=True)
    family_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("families.id"), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    used: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
