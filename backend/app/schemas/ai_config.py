"""AI 配置相关 Pydantic schemas。"""

from pydantic import BaseModel, field_validator


class AIConfigResponse(BaseModel):
    ai_enabled: bool
    ai_provider: str | None
    ai_api_key_masked: str | None  # 脱敏展示，如 sk-****xxxx

    model_config = {"from_attributes": True}


class AIConfigUpdate(BaseModel):
    ai_enabled: bool | None = None
    ai_provider: str | None = None
    ai_api_key: str | None = None  # 明文，后端加密存储

    @field_validator("ai_provider")
    @classmethod
    def validate_provider(cls, v: str | None) -> str | None:
        if v is not None and v not in ("anthropic", "openai"):
            raise ValueError("ai_provider 必须为 'anthropic' 或 'openai'")
        return v


class AIConfigTestResult(BaseModel):
    success: bool
    message: str
    latency_ms: int | None = None
