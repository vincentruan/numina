"""JTI revocation persistence model.

Replaces in-memory dicts in auth/deps.py with SQLite-backed storage,
ensuring revocation state survives server restarts.
"""

from sqlalchemy import Float, Index, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class RevokedToken(Base):
    """Persistent record of revoked JWT tokens.

    Two revocation modes:
    1. Single JTI revocation: jti field populated, user_id = None
    2. User-level revocation: user_id field populated, jti = None

    expires_at enables automatic cleanup of expired records.
    """

    __tablename__ = "revoked_tokens"

    id: Mapped[int] = mapped_column(primary_key=True)
    jti: Mapped[str | None] = mapped_column(String(36), unique=True, index=True, nullable=True)
    user_id: Mapped[str | None] = mapped_column(String(36), index=True, nullable=True)
    revoked_at: Mapped[float] = mapped_column(Float, nullable=False)  # Unix timestamp
    expires_at: Mapped[float] = mapped_column(Float, index=True, nullable=False)  # TTL expiry

    __table_args__ = (
        Index("ix_revoked_tokens_user_expires", "user_id", "expires_at"),
    )