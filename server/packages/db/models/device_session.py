from datetime import datetime

from sqlalchemy import BigInteger, Boolean, DateTime, ForeignKey, Index, String, func
from sqlalchemy.orm import Mapped, mapped_column

from packages.core.snowflake import next_id
from packages.db.session import Base


class DeviceSession(Base):
    """Trusted device session record."""

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
    browser_fingerprint: Mapped[str | None] = mapped_column(String(64), nullable=True)
    device_id: Mapped[str | None] = mapped_column(String(36), nullable=True)

    __table_args__ = (
        Index("ix_device_sessions_user_active", "user_id", "is_revoked", "expires_at"),
        Index("ix_device_sessions_family", "family_id"),
        # Partial unique index: one active session per (user_id, device_id).
        # Prevents duplicate active sessions from concurrent trust requests.
        Index(
            "uq_device_sessions_user_device_active",
            "user_id", "device_id",
            unique=True,
            postgresql_where=(is_revoked == False),  # noqa: E712
            sqlite_where=(is_revoked == False),  # noqa: E712
        ),
    )
