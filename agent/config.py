"""Agent 服务配置。"""

from pydantic_settings import BaseSettings


class AgentSettings(BaseSettings):
    ENVIRONMENT: str = "development"

    # Backend 内部通信
    BACKEND_BASE_URL: str = "http://backend:8000"
    AGENT_INTERNAL_TOKEN: str = ""  # 与 backend 共享的 service-to-service token

    # 加密（与 backend 共享同一个 Fernet key，用于解密 API Key）
    AI_ENCRYPTION_KEY: str = ""

    # 日志
    LOG_LEVEL: str = "INFO"

    model_config = {"env_file": ".env", "extra": "ignore"}


settings = AgentSettings()
