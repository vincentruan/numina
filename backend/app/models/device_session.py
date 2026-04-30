from datetime import datetime

from sqlalchemy import BigInteger, Boolean, DateTime, ForeignKey, Index, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.utils.snowflake import next_id


class DeviceSession(Base):
    """Trusted device session record.

    Created when a user opts in to "remember this device" after login.
    refresh_jti links this record to the live JWT refresh token.
    Revocation sets is_revoked=True and adds refresh_jti to RevokedToken.
    """

    __tablename__ = "device_sessions"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, default=next_id)
    user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id"), nullable=False
    )
    family_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("families.id"), nullable=False
    )
    device_name: Mapped[str] = mapped_column(String(200), nullable=False)
    refresh_jti: Mapped[str] = mapped_column(String(36), unique=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    last_seen_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    is_revoked: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    browser_fingerprint: Mapped[str | None] = mapped_column(String(64), nullable=True)  # SHA-256 hex

    __table_args__ = (
        Index("ix_device_sessions_user_active", "user_id", "is_revoked", "expires_at"),
        Index("ix_device_sessions_family", "family_id"),
    )
