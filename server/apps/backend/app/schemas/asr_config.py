"""ASR provider config Pydantic schemas."""

from datetime import datetime

from pydantic import BaseModel, field_validator

from apps.backend.app.schemas.base import SnowflakeBase

_VALID_ASR_PROVIDERS = ("openai", "openai_compatible", "siliconflow")


class ASRConfigResponse(SnowflakeBase):
    id: int
    name: str
    provider: str
    ai_api_key_masked: str | None = None
    base_url: str | None = None
    model_id: str | None = None
    model_2_id: str | None = None
    model_3_id: str | None = None
    is_active: bool
    display_order: int = 0
    # Circuit breaker
    circuit_state: str = "closed"
    failure_count: int = 0
    last_failure_at: datetime | None = None
    # Test result
    test_passed: bool | None = None
    test_message: str | None = None
    test_latency_ms: int | None = None
    tested_at: datetime | None = None


class ASRConfigListResponse(BaseModel):
    configs: list[ASRConfigResponse] = []


class ASRConfigCreate(BaseModel):
    name: str
    provider: str
    ai_api_key: str | None = None
    base_url: str | None = None
    model_id: str | None = None
    model_2_id: str | None = None
    model_3_id: str | None = None
    display_order: int | None = None

    @field_validator("provider")
    @classmethod
    def validate_provider(cls, v: str) -> str:
        if v not in _VALID_ASR_PROVIDERS:
            raise ValueError(f"provider 必须为 {_VALID_ASR_PROVIDERS} 之一")
        return v


class ASRConfigUpdate(BaseModel):
    name: str | None = None
    provider: str | None = None
    ai_api_key: str | None = None
    base_url: str | None = None
    model_id: str | None = None
    model_2_id: str | None = None
    model_3_id: str | None = None
    is_active: bool | None = None
    display_order: int | None = None

    @field_validator("provider")
    @classmethod
    def validate_provider(cls, v: str | None) -> str | None:
        if v is not None and v not in _VALID_ASR_PROVIDERS:
            raise ValueError(f"provider 必须为 {_VALID_ASR_PROVIDERS} 之一")
        return v


class ASRDiffOp(BaseModel):
    """Single diff operation for WER comparison display."""
    op: str  # "equal" | "sub" | "ins" | "del"
    ref: str | None = None
    hyp: str | None = None


class ASRLangTestResult(BaseModel):
    """Per-language test result with WER comparison."""
    language: str  # "zh" | "en"
    reference: str  # original reference text
    transcribed: str  # ASR output
    error_rate_pct: float  # WER/CER percentage
    error_count: int
    reference_length: int
    passed: bool  # error_rate_pct <= 50
    ops: list[ASRDiffOp]  # diff operations for display
    latency_ms: int | None = None
    error: str | None = None  # error message if test failed entirely


class ASRTestResult(BaseModel):
    """Combined test result across all languages."""
    success: bool  # all languages passed (WER ≤ 50%)
    message: str
    language_results: list[ASRLangTestResult] = []


class ASRStatusResponse(BaseModel):
    available: bool
    reason: str | None = None


class ASRTranscribeResponse(BaseModel):
    text: str
