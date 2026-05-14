"""AI 配置相关 Pydantic schemas。"""

from datetime import datetime

from pydantic import BaseModel, field_validator

from apps.backend.app.schemas.base import SnowflakeBase


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

    @field_validator("provider")
    @classmethod
    def validate_provider(cls, v: str) -> str:
        if v not in ("anthropic", "openai"):
            raise ValueError("provider 必须为 'anthropic' 或 'openai'")
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

    @field_validator("provider")
    @classmethod
    def validate_provider(cls, v: str | None) -> str | None:
        if v is not None and v not in ("anthropic", "openai"):
            raise ValueError("provider 必须为 'anthropic' 或 'openai'")
        return v


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
