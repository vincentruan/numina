from datetime import datetime

from sqlalchemy import BigInteger, Boolean, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from apps.backend.app.database import Base, UTCDateTime
from apps.backend.app.utils.snowflake import next_id
from packages.db.mixins import CircuitBreakerMixin


class ASRProviderConfig(CircuitBreakerMixin, Base):
    """ASR (speech-to-text) provider configuration — independent from AIProviderConfig."""

    __tablename__ = "asr_provider_configs"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, default=next_id)
    family_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    provider: Mapped[str] = mapped_column(String(20), nullable=False)  # 'openai' | 'openai_compatible'
    api_key_encrypted: Mapped[str | None] = mapped_column(Text, nullable=True)
    base_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    model_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    model_2_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    model_3_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    # User-toggleable enable/disable. Can only be True when test_passed is True.
    display_order: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # Circuit breaker FSM columns are provided by CircuitBreakerMixin
    # Test result
    test_passed: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    test_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    test_latency_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    tested_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime(), server_default=func.now(), onupdate=func.now())
