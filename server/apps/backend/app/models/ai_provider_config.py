from datetime import datetime

from sqlalchemy import BigInteger, Boolean, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from apps.backend.app.database import Base, UTCDateTime
from apps.backend.app.utils.snowflake import next_id
from packages.db.mixins import CircuitBreakerMixin


class AIProviderConfig(CircuitBreakerMixin, Base):
    __tablename__ = "ai_providers"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, default=next_id)
    family_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    provider: Mapped[str] = mapped_column(String(20), nullable=False)  # 'anthropic' | 'openai' | 'openai_compatible'
    api_key_encrypted: Mapped[str | None] = mapped_column(Text, nullable=True)
    base_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    model_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    vision_model_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    timeout_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True, default=60)
    thinking_supported: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    # Per-response output token cap. NULL → resolved by agent's _resolve_max_tokens
    # via system-config.yaml prefix table; explicit non-NULL overrides the default.
    max_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # Multi-provider fields
    provider_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    display_order: Mapped[int | None] = mapped_column(Integer, nullable=True)
    model_2_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    model_3_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    model_1_capabilities: Mapped[str | None] = mapped_column(Text, nullable=True)
    model_2_capabilities: Mapped[str | None] = mapped_column(Text, nullable=True)
    model_3_capabilities: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Circuit breaker FSM columns are provided by CircuitBreakerMixin
    # Legacy fields retained for migration compatibility
    circuit_open: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    circuit_open_until: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime(), server_default=func.now(), onupdate=func.now())


class AIProviderTestResult(Base):
    __tablename__ = "ai_provider_test_results"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, default=next_id)
    config_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    test_type: Mapped[str] = mapped_column(String(20), nullable=False)  # 'main' | 'thinking' | 'vision' | 'vision_text'
    success: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    message: Mapped[str | None] = mapped_column(Text, nullable=True)
    latency_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    tested_at: Mapped[datetime] = mapped_column(UTCDateTime(), server_default=func.now())
