from datetime import datetime

from sqlalchemy import BigInteger, Boolean, DateTime, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from apps.backend.app.database import Base, UTCDateTime
from apps.backend.app.utils.snowflake import next_id


class FamilyWebSearchProvider(Base):
    __tablename__ = "family_web_search_providers"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, default=next_id)
    family_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    provider_name: Mapped[str] = mapped_column(String(50), nullable=False)
    display_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    api_key_encrypted: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    display_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    max_results: Mapped[int] = mapped_column(Integer, default=5, nullable=False)
    # Circuit breaker fields (three-state: closed | open | half_open)
    circuit_state: Mapped[str] = mapped_column(String(20), default="closed", nullable=False)
    circuit_reason: Mapped[str | None] = mapped_column(String(30), nullable=True)
    recovery_schedule: Mapped[str | None] = mapped_column(String(100), nullable=True)
    last_failure_type: Mapped[str | None] = mapped_column(String(30), nullable=True)
    half_open_success_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    half_open_failure_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    half_open_window_start: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)
    failure_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    last_failure_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime(), server_default=func.now(), onupdate=func.now())