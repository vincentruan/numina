"""AI 配置相关 Pydantic schemas。"""

from datetime import datetime

from pydantic import BaseModel, field_validator

from apps.backend.app.schemas.base import SnowflakeBase

_VALID_PROVIDERS = ("anthropic", "openai", "openai_compatible")


class AIProviderTestResultResponse(SnowflakeBase):
    id: int
    test_type: str
    success: bool | None
    message: str | None
    latency_ms: int | None
    tested_at: datetime


class AIConfigResponse(SnowflakeBase):
    id: int
    name: str
    provider: str
    ai_api_key_masked: str | None = None
    base_url: str | None = None
    model_id: str | None = None
    vision_model_id: str | None = None
    timeout_seconds: int | None = 60
    is_active: bool
    # Multi-provider fields
    provider_name: str = ""
    display_order: int = 0
    model_2_id: str | None = None
    model_3_id: str | None = None
    model_1_capabilities: list[str] = []
    model_2_capabilities: list[str] = []
    model_3_capabilities: list[str] = []
    # Circuit breaker fields (three-state model)
    circuit_state: str = "closed"
    # circuit_state: closed | open | half_open
    circuit_reason: str | None = None
    # circuit_reason: transient | permanent_auth | permanent_account
    recovery_schedule: str | None = None
    # recovery_schedule: comma-separated time patterns like ":01,:31"
    last_failure_type: str | None = None
    # last_failure_type: transient_rate_limit | transient_server | transient_timeout | transient_network | permanent_auth | permanent_account
    half_open_window_start: datetime | None = None
    # Legacy circuit breaker fields (retained for backward compatibility)
    circuit_open: bool = False
    circuit_open_until: datetime | None = None
    failure_count: int = 0
    test_results: list[AIProviderTestResultResponse] = []


class AIConfigListResponse(BaseModel):
    configs: list[AIConfigResponse] = []


class AIConfigCreate(BaseModel):
    name: str
    provider: str
    ai_api_key: str | None = None
    base_url: str | None = None
    model_id: str | None = None
    vision_model_id: str | None = None
    timeout_seconds: int | None = 60
    is_active: bool = False
    # Multi-provider fields
    provider_name: str | None = None
    display_order: int | None = None
    model_2_id: str | None = None
    model_3_id: str | None = None
    model_1_capabilities: list[str] | None = None
    model_2_capabilities: list[str] | None = None
    model_3_capabilities: list[str] | None = None
    # Circuit breaker config
    recovery_schedule: str | None = None  # e.g., ":01,:31" for DashScope quota resets

    @field_validator("provider")
    @classmethod
    def validate_provider(cls, v: str) -> str:
        if v not in _VALID_PROVIDERS:
            raise ValueError(f"provider 必须为 {_VALID_PROVIDERS} 之一")
        return v


class AIConfigUpdate(BaseModel):
    name: str | None = None
    provider: str | None = None
    ai_api_key: str | None = None
    base_url: str | None = None
    model_id: str | None = None
    vision_model_id: str | None = None
    timeout_seconds: int | None = None
    is_active: bool | None = None
    # Multi-provider fields
    provider_name: str | None = None
    display_order: int | None = None
    model_2_id: str | None = None
    model_3_id: str | None = None
    model_1_capabilities: list[str] | None = None
    model_2_capabilities: list[str] | None = None
    model_3_capabilities: list[str] | None = None
    # Circuit breaker config
    recovery_schedule: str | None = None  # e.g., ":01,:31" for DashScope quota resets

    @field_validator("provider")
    @classmethod
    def validate_provider(cls, v: str | None) -> str | None:
        if v is not None and v not in _VALID_PROVIDERS:
            raise ValueError(f"provider 必须为 {_VALID_PROVIDERS} 之一")
        return v


class AICircuitResetResponse(BaseModel):
    ok: bool


class AIConfigTestResult(BaseModel):
    connected: bool  # 连接测试成功与否
    message: str  # 连接测试消息
    latency_ms: int | None = None  # 连接测试延迟
    # 思考能力测试结果（独立）
    thinking_success: bool | None = None
    thinking_message: str | None = None
    thinking_latency_ms: int | None = None
    # 图像模型测试结果（独立）
    vision_success: bool | None = None
    vision_message: str | None = None
    vision_latency_ms: int | None = None
    # OCR文本准确度测试结果（独立）
    vision_text_success: bool | None = None
    vision_text_message: str | None = None
    vision_text_latency_ms: int | None = None
