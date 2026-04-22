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

    # DeerFlow 集成开关（默认关闭，迁移验证后开启）
    USE_DEERFLOW: bool = False

    model_config = {"env_file": ".env", "extra": "ignore"}

    def validate_required(self) -> None:
        """启动时校验必填配置，缺失则快速失败。"""
        if not self.AGENT_INTERNAL_TOKEN:
            raise ValueError(
                "AGENT_INTERNAL_TOKEN 未配置。"
                "请在环境变量或 .env 文件中设置此值。"
            )


settings = AgentSettings()
