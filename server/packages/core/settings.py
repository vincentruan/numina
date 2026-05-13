import secrets
from pathlib import Path

from pydantic_settings import BaseSettings

from packages.core.logging import get_logger

logger = get_logger(__name__)

_DEFAULT_SECRET = "CHANGE_ME_IN_PRODUCTION"


class Settings(BaseSettings):
    DATABASE_URL: str = "sqlite:///./data/numina.db"
    SECRET_KEY: str = _DEFAULT_SECRET
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 15
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    # WebAuthn settings
    WEBAUTHN_RP_ID: str = "localhost"  # Domain (no protocol, no port)
    WEBAUTHN_RP_NAME: str = "Numina"
    WEBAUTHN_ORIGIN: str = "http://localhost:8080"  # Full origin with protocol
    CORS_ORIGINS: list[str] = ["http://localhost:5173", "http://127.0.0.1:5173", "http://localhost:8080", "http://127.0.0.1:8080"]
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
    PIN_BCRYPT_ROUNDS: int = 8  # Lower cost for child PIN (still secure for 4-emoji)
    CHILD_REFRESH_TOKEN_EXPIRE_DAYS: int = 30  # 30 days, same as trusted adult sessions
    ENABLE_SECURITY_LOGGING: bool = True
    ALTCHA_HMAC_KEY: str = ""  # Required in production for captcha
    SEED_SECRET: str = ""  # If set, requests with X-Seed-Secret header bypass captcha
    DISABLE_CAPTCHA: bool = False  # Set to true to disable captcha regardless of environment

    # File storage configuration
    UPLOAD_DIR: str = "./data/uploads"
    WORKSPACE_ROOT: str = "./data/workspace"
    FILE_SYNC_INTERVAL_MINUTES: int = 15
    STORAGE_ENCRYPTION_KEY: str = ""

    # Chat session storage configuration
    CHAT_DIR: str = "./data/chat"
    CHAT_ENABLE_REMOTE_SYNC: bool = False

    # AI Agent 配置
    AI_ENCRYPTION_KEY: str = ""
    AGENT_INTERNAL_TOKEN: str = ""
    AGENT_BASE_URL: str = "http://agent:8001"

    # Snowflake ID generator
    SNOWFLAKE_MACHINE_ID: int | None = None  # 0-1023; None = auto-derive from container IP

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
        raise RuntimeError("SECRET_KEY 未配置！生产环境必须设置 SECRET_KEY 环境变量。")
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

# CORS production validation - must configure specific domains
if settings.ENVIRONMENT == "production" and settings.CORS_ORIGINS == ["*"]:
    raise RuntimeError(
        "CORS_ORIGINS 设置为 ['*']！生产环境必须配置具体域名，不允许全开放。"
    )

# AI encryption key validation
if settings.ENVIRONMENT == "production" and not settings.AI_ENCRYPTION_KEY:
    raise RuntimeError(
        "AI_ENCRYPTION_KEY 未配置！生产环境必须设置 AI_ENCRYPTION_KEY 环境变量，"
        "否则 AI API Key 将无法加密存储。"
    )

# Storage encryption key validation
if settings.ENVIRONMENT == "production" and not settings.STORAGE_ENCRYPTION_KEY:
    raise RuntimeError(
        "STORAGE_ENCRYPTION_KEY 未配置！生产环境必须设置独立的存储加密密钥，"
        "避免与 SECRET_KEY 共用导致密钥轮换风险。"
    )

# CHAT_DIR validation - must not be under UPLOAD_DIR (UPLOAD_DIR is served as static files)
try:
    chat_dir_resolved = Path(settings.CHAT_DIR).resolve()
    upload_dir_resolved = Path(settings.UPLOAD_DIR).resolve()
    if chat_dir_resolved == upload_dir_resolved or chat_dir_resolved.is_relative_to(upload_dir_resolved):
        raise RuntimeError(
            f"CHAT_DIR ({settings.CHAT_DIR}) 不能位于 UPLOAD_DIR ({settings.UPLOAD_DIR}) 下！"
            "对话历史不应通过静态文件 URL 暴露。"
        )
except ValueError:
    pass
