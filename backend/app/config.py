import secrets

from pydantic_settings import BaseSettings

from app.core.logging_config import get_logger

logger = get_logger(__name__)

_DEFAULT_SECRET = "CHANGE_ME_IN_PRODUCTION"


class Settings(BaseSettings):
    DATABASE_URL: str = "sqlite:///./data/numina.db"
    SECRET_KEY: str = _DEFAULT_SECRET
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 15
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    CORS_ORIGINS: list[str] = ["*"]
    ENVIRONMENT: str = "development"  # development / production

    # Cache configuration
    CACHE_BACKEND: str = "memory"  # "memory" or "redis"
    REDIS_URL: str = "redis://localhost:6379/0"
    # Granular Redis config (for production security)
    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379
    REDIS_DB: int = 0
    REDIS_PASSWORD: str | None = None  # Required in production
    REDIS_USE_TLS: bool = False

    # Rate limiting
    LOGIN_RATE_LIMIT_MAX_ATTEMPTS: int = 5
    LOGIN_RATE_LIMIT_LOCKOUT_SECONDS: int = 900  # 15 minutes
    GLOBAL_RATE_LIMIT_PER_MINUTE: int = 100
    REGISTER_RATE_LIMIT_PER_HOUR: int = 5  # Registration rate limit per IP

    # Trusted proxy configuration (for X-Forwarded-For validation)
    TRUSTED_PROXY_IPS: list[str] = []  # e.g., ["10.0.0.1", "172.16.0.0/12"]

    # Security settings
    BCRYPT_ROUNDS: int = 12
    ENABLE_SECURITY_LOGGING: bool = True
    ALTCHA_HMAC_KEY: str = ""  # Required in production for captcha

    # Logging configuration
    LOG_LEVEL: str = "INFO"
    LOG_DIR: str = "logs"
    LOG_MAX_BYTES: int = 10 * 1024 * 1024  # 10MB
    LOG_BACKUP_COUNT: int = 10
    LOG_RETENTION_DAYS: int = 30
    LOG_ROTATION_MODE: str = "size"  # "size" or "time"
    LOG_FORMAT: str | None = None  # Uses default format if None

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

# ALTCHA HMAC key validation for production
if settings.ENVIRONMENT == "production" and not settings.ALTCHA_HMAC_KEY:
    raise RuntimeError(
        "ALTCHA_HMAC_KEY 未配置！生产环境必须设置 ALTCHA_HMAC_KEY 环境变量。"
    )
elif not settings.ALTCHA_HMAC_KEY:
    settings.ALTCHA_HMAC_KEY = secrets.token_urlsafe(32)
    logger.warning("ALTCHA_HMAC_KEY 未配置，已自动生成随机密钥（仅限开发环境）。")
