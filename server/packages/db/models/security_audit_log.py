"""Immutable security audit log model.

Append-only: never UPDATE or DELETE rows from this table.
"""

from datetime import datetime

from sqlalchemy import BigInteger, DateTime, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from packages.core.snowflake import next_id
from packages.db.session import Base


class SecurityAuditLog(Base):
    __tablename__ = "security_audit_logs"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, default=next_id)
    event_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    user_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True, index=True)
    family_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True, index=True)
    ip_address: Mapped[str | None] = mapped_column(String(45), nullable=True)
    user_agent: Mapped[str | None] = mapped_column(String(512), nullable=True)
    outcome: Mapped[str] = mapped_column(String(16), nullable=False)  # 'success' | 'failure'
    detail: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False, index=True
    )
