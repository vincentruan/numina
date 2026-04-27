"""AI 配置相关 Pydantic schemas。"""

from pydantic import BaseModel, ConfigDict, field_validator


class AIConfigResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    ai_enabled: bool
    ai_provider: str | None
    ai_api_key_masked: str | None  # 脱敏展示，如 sk-****xxxx
    ai_base_url: str | None  # 自定义 API Base URL，None 表示使用默认端点
    ai_model_id: str | None  # 主模型 ID，None 使用 provider 默认
    ai_vision_model_id: str | None  # 图像模型 ID，None 使用主模型


class AIConfigUpdate(BaseModel):
    ai_enabled: bool | None = None
    ai_provider: str | None = None
    ai_api_key: str | None = None  # 明文，后端加密存储
    ai_base_url: str | None = None  # 自定义 API Base URL
    ai_model_id: str | None = None  # 主模型 ID
    ai_vision_model_id: str | None = None  # 图像模型 ID

    @field_validator("ai_provider")
    @classmethod
    def validate_provider(cls, v: str | None) -> str | None:
        if v is not None and v not in ("anthropic", "openai"):
            raise ValueError("ai_provider 必须为 'anthropic' 或 'openai'")
        return v

    @field_validator("ai_base_url")
    @classmethod
    def validate_base_url(cls, v: str | None) -> str | None:
        if v is not None:
            stripped = v.strip()
            return stripped if stripped else None
        return None


class AIConfigTestResult(BaseModel):
    success: bool
    message: str
    latency_ms: int | None = None
    supports_text: bool = False
    supports_thinking: bool = False
    supports_image: bool = False
