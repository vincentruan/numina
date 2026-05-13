"""JTI revocation persistence model."""

from sqlalchemy import Float, Index, String
from sqlalchemy.orm import Mapped, mapped_column

from packages.db.session import Base


class RevokedToken(Base):
    """Persistent record of revoked JWT tokens."""

    __tablename__ = "revoked_tokens"

    id: Mapped[int] = mapped_column(primary_key=True)
    jti: Mapped[str | None] = mapped_column(String(36), unique=True, index=True, nullable=True)
    user_id: Mapped[str | None] = mapped_column(String(36), index=True, nullable=True)
    revoked_at: Mapped[float] = mapped_column(Float, nullable=False)
    expires_at: Mapped[float] = mapped_column(Float, index=True, nullable=False)

    __table_args__ = (
        Index("ix_revoked_tokens_user_expires", "user_id", "expires_at"),
    )
