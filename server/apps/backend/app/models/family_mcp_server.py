from datetime import datetime

from sqlalchemy import BigInteger, Boolean, DateTime, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from apps.backend.app.database import Base, UTCDateTime
from apps.backend.app.utils.snowflake import next_id


class FamilyMCPServer(Base):
    __tablename__ = "ai_mcp_servers"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, default=next_id)
    family_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    url: Mapped[str] = mapped_column(Text, nullable=False)
    transport: Mapped[str] = mapped_column(String(20), nullable=False, default="sse")  # 'sse' | 'stdio'
    env_vars_encrypted: Mapped[str | None] = mapped_column(Text, nullable=True)  # Fernet-encrypted JSON
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    mcp_type: Mapped[str] = mapped_column(String(20), default="general", nullable=False)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime(), server_default=func.now(), onupdate=func.now())
