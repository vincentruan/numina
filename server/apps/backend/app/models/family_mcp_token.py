from datetime import datetime

from sqlalchemy import BigInteger, Boolean, Index, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from apps.backend.app.database import Base, UTCDateTime
from apps.backend.app.utils.snowflake import next_id


class FamilyMCPToken(Base):
    """Per-family external MCP API token.

    Stores hashed token + display fragments. Plaintext is returned
    exactly once at generation time and never persisted.
    """

    __tablename__ = "family_mcp_tokens"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, default=next_id)
    family_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    token_hash: Mapped[str] = mapped_column(String(64), nullable=False)  # SHA-256 hex
    token_prefix: Mapped[str] = mapped_column(String(8), nullable=False)  # first 8 chars
    token_last4: Mapped[str] = mapped_column(String(4), nullable=False)  # last 4 chars
    allow_external: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    allow_write: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    # Per-tool whitelist: None = all tools available (Phase 1 compat);
    # non-null list = exact enabled set (future tools NOT auto-exposed).
    allowed_tools: Mapped[str | None] = mapped_column(Text, nullable=True)  # JSON list
    expires_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)
    last_used_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        UTCDateTime(), server_default=func.now(), onupdate=func.now()
    )

    __table_args__ = (
        Index("ix_family_mcp_tokens_family_prefix", "family_id", "token_prefix"),
    )
