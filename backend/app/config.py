import logging
import secrets

from pydantic_settings import BaseSettings

logger = logging.getLogger(__name__)

_DEFAULT_SECRET = "CHANGE_ME_IN_PRODUCTION"


class Settings(BaseSettings):
    DATABASE_URL: str = "sqlite:///./data/numina.db"
    SECRET_KEY: str = _DEFAULT_SECRET
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 15
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    CORS_ORIGINS: list[str] = ["*"]
    ENVIRONMENT: str = "development"  # development / production

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()

# Auto-generate a random key for dev convenience, but warn in production
if settings.SECRET_KEY == _DEFAULT_SECRET:
    if settings.ENVIRONMENT == "production":
        raise RuntimeError(
            "SECRET_KEY 未配置！生产环境必须设置 SECRET_KEY 环境变量。"
        )
    else:
        settings.SECRET_KEY = secrets.token_urlsafe(32)
        logger.warning("SECRET_KEY 未配置，已自动生成随机密钥（仅限开发环境）。")
