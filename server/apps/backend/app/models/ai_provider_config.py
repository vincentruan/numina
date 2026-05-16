from datetime import datetime

from sqlalchemy import BigInteger, Boolean, DateTime, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from apps.backend.app.database import Base
from apps.backend.app.utils.snowflake import next_id


class AIProviderConfig(Base):
    __tablename__ = "ai_provider_configs"

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
    is_active: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    # Multi-provider fields
    provider_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    display_order: Mapped[int | None] = mapped_column(Integer, nullable=True)
    model_2_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    model_3_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    model_1_capabilities: Mapped[str | None] = mapped_column(Text, nullable=True)
    model_2_capabilities: Mapped[str | None] = mapped_column(Text, nullable=True)
    model_3_capabilities: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Circuit breaker fields
    circuit_open: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    circuit_open_until: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    failure_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    last_failure_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())


class AIProviderTestResult(Base):
    __tablename__ = "ai_provider_test_results"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, default=next_id)
    config_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    test_type: Mapped[str] = mapped_column(String(20), nullable=False)  # 'main' | 'thinking' | 'vision' | 'vision_text'
    success: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    message: Mapped[str | None] = mapped_column(Text, nullable=True)
    latency_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    tested_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
