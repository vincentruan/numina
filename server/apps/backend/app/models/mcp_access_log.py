"""Per-family MCP access audit log.

Append-only: never UPDATE or DELETE rows from this table.
Records every external MCP session connection and tool call.
"""

from datetime import datetime

from sqlalchemy import BigInteger, Index, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from packages.core.snowflake import next_id
from packages.db.session import Base, UTCDateTime


class MCPAccessLog(Base):
    """Immutable access log for external MCP API token usage."""

    __tablename__ = "mcp_access_logs"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, default=next_id)
    family_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    # Nullable: token may be rotated mid-session; keeps the historical reference.
    token_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    session_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    # 'connect' | 'disconnect' | 'tool_call'
    event_type: Mapped[str] = mapped_column(String(16), nullable=False, index=True)
    tool_name: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    # 'success' | 'failure' | 'permission_denied' | 'error'
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    client_ip: Mapped[str] = mapped_column(String(45), nullable=False)
    user_agent: Mapped[str | None] = mapped_column(String(512), nullable=True)
    # Truncated JSON of tool arguments, max 1024 chars, with secrets redacted.
    args_digest: Mapped[str | None] = mapped_column(Text, nullable=True)
    error_code: Mapped[str | None] = mapped_column(String(32), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        UTCDateTime(), server_default=func.now(), nullable=False, index=True
    )

    __table_args__ = (
        Index("ix_mcp_access_logs_family_created", "family_id", "created_at"),
        Index(
            "ix_mcp_access_logs_family_event_created",
            "family_id",
            "event_type",
            "created_at",
        ),
    )
