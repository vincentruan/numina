import os
import secrets
from pathlib import Path

from pydantic import model_validator
from pydantic_settings import BaseSettings

from packages.core.logging import get_logger

logger = get_logger(__name__)

_DEFAULT_SECRET = "CHANGE_ME_IN_PRODUCTION"

_OLD_DEFAULTS = {
    "DATABASE_URL": "sqlite:///./data/numina.db",
    "UPLOAD_DIR": "./data/uploads",
    "WORKSPACE_ROOT": "./data/workspaces",
    "CHAT_DIR": "./data/workspaces",
    "LOG_DIR": "logs",
}


class Settings(BaseSettings):
    DATA_ROOT: str = "~/.numina/data"

    DATABASE_URL: str = "sqlite:///./data/numina.db"
    SECRET_KEY: str = _DEFAULT_SECRET
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60  # 1 hour (was 15 min — too short for dev/testing)
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    DEVICE_TRUST_EXPIRE_DAYS: int = 30  # Device trust expiry (days since last login)
    # WebAuthn settings
    WEBAUTHN_RP_ID: str = "localhost"  # Domain (no protocol, no port)
    WEBAUTHN_RP_NAME: str = "Numina"
    WEBAUTHN_ORIGIN: str = "http://localhost:8080"  # Full origin with protocol
    CORS_ORIGINS: list[str] = ["http://localhost:5173", "http://127.0.0.1:5173", "http://localhost:8080", "http://127.0.0.1:8080"]
    ENVIRONMENT: str = "development"  # development / production

    # Bootstrap: initial invitation codes for production (comma-separated)
    INIT_INVITATION_CODES: str = ""

    # Reconciliation system
    DISABLE_RECONCILE: bool = False  # Set True to skip reconciliation (fallback to legacy bootstrap)
    RECONCILE_MODE: str = ""  # Override mode: "normal", "check-only", "dry-run", "offline", "strict"

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
    WORKSPACE_ROOT: str = "./data/workspaces"
    FILE_SYNC_INTERVAL_MINUTES: int = 15
    STORAGE_ENCRYPTION_KEY: str = ""

    # Chat session storage configuration
    CHAT_DIR: str = "./data/workspaces"  # Base dir; sessions stored under tenants/{fid}/chat/
    CHAT_ENABLE_REMOTE_SYNC: bool = False

    # AI Agent 配置
    AI_ENCRYPTION_KEY: str = ""
    AGENT_BASE_URL: str = "http://agent:8001"

    # Backend external URL (for constructing internal MCP SSE endpoint URLs)
    BACKEND_BASE_URL: str = "http://localhost:8000"

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

    # Load `.env` (CWD-local, e.g. server/.env) then the repo-root `.env`
    # with higher precedence — same precedence as apps/agent/app/config.py.
    # This keeps shared secrets (SECRET_KEY) in sync
    # between the backend and the agent, which both read the root .env.
    model_config = {
        "env_file": [".env", str(Path(__file__).resolve().parents[3] / ".env")],
        "env_file_encoding": "utf-8",
        "extra": "ignore",
    }

    @model_validator(mode="after")
    def _resolve_data_root(self) -> "Settings":
        root = str(Path(self.DATA_ROOT).expanduser().resolve())
        self.DATA_ROOT = root

        # ── DATABASE_URL: expand ~ in SQLite paths ──────────────────────
        # SQLAlchemy does not expand "~" in URLs — it treats it as a literal
        # relative directory from CWD, silently creating a separate empty DB
        # under server/~/.numina/ instead of using the home directory.
        # Always expand "~" regardless of whether the URL is explicit or default.
        if self.DATABASE_URL and self.DATABASE_URL.startswith("sqlite:///"):
            # sqlite:/// has 3 slashes: the database part starts after the 3rd /
            db_part = self.DATABASE_URL[len("sqlite:///"):]
            if db_part.startswith("~"):
                expanded = str(Path(db_part).expanduser().resolve())
                self.DATABASE_URL = f"sqlite:///{expanded}"

        # Derive from DATA_ROOT only when DATABASE_URL still matches the old default
        if _OLD_DEFAULTS["DATABASE_URL"] == self.DATABASE_URL or not self.DATABASE_URL:
            db_path = Path(root) / "db" / "numina.db"
            self.DATABASE_URL = f"sqlite:///{db_path}"

        # ── Other file-path settings: always expand ~ ───────────────────
        # These are consumed by PathManager and OS APIs which *do* expand ~,
        # but expanding here ensures consistent resolution regardless of
        # which consumer reads the value.
        for attr in ("UPLOAD_DIR", "WORKSPACE_ROOT", "CHAT_DIR", "LOG_DIR"):
            val = getattr(self, attr, None)
            if val and val.startswith("~"):
                setattr(self, attr, str(Path(val).expanduser().resolve()))

        # Derive from DATA_ROOT when still at old defaults
        if _OLD_DEFAULTS["UPLOAD_DIR"] == self.UPLOAD_DIR or not self.UPLOAD_DIR:
            self.UPLOAD_DIR = str(Path(root) / "workspaces")

        if _OLD_DEFAULTS["WORKSPACE_ROOT"] == self.WORKSPACE_ROOT or not self.WORKSPACE_ROOT:
            self.WORKSPACE_ROOT = str(Path(root) / "workspaces")

        if _OLD_DEFAULTS["CHAT_DIR"] == self.CHAT_DIR or not self.CHAT_DIR:
            self.CHAT_DIR = str(Path(root) / "workspaces")

        if _OLD_DEFAULTS["LOG_DIR"] == self.LOG_DIR or not self.LOG_DIR:
            self.LOG_DIR = str(Path(root) / "logs")

        return self


def _is_weak_secret(value: str) -> bool:
    """Return True if value is empty or contains a known-weak placeholder pattern."""
    if not value:
        return True
    return "change-me" in value.lower() or "change_me" in value.lower()


settings = Settings()


# Auto-generate a random key for dev convenience, but hard-fail in production
if _is_weak_secret(settings.SECRET_KEY):
    if settings.ENVIRONMENT == "production":
        raise RuntimeError(
            "SECRET_KEY 未配置或使用了默认占位符！"
            "生产环境必须设置强随机 SECRET_KEY 环境变量。"
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

# Legacy storage backend environment variables check
# Remote storage is now configured per-family via the Settings UI.
# These env vars are no longer supported and must be removed before startup.
_LEGACY_STORAGE_ENV_KEYS = (
    "STORAGE_BACKEND_TYPE",
    "STORAGE_BACKEND_NAME",
    "STORAGE_BACKEND_IS_DEFAULT",
    "STORAGE_BACKEND_IS_ACTIVE",
    "STORAGE_GITHUB_REPO_OWNER",
    "STORAGE_GITHUB_REPO_NAME",
    "STORAGE_GITHUB_BRANCH",
    "STORAGE_GITHUB_TOKEN",
    "STORAGE_WEBDAV_BASE_URL",
    "STORAGE_WEBDAV_USERNAME",
    "STORAGE_WEBDAV_PASSWORD",
)

_legacy_storage_vars_found = [k for k in _LEGACY_STORAGE_ENV_KEYS if os.environ.get(k)]
if _legacy_storage_vars_found:
    raise RuntimeError(
        "检测到已废弃的远程存储环境变量: "
        f"{', '.join(_legacy_storage_vars_found)}。\n"
        "远程备份已改为按家庭维度配置，请在「设置 → 家庭管理 → 家庭远程备份」中配置，"
        "并删除上述环境变量后重新启动。"
    )

# CHAT_DIR validation - must not be a strict subdirectory of UPLOAD_DIR
# (UPLOAD_DIR subtree is served as static files; equality is OK because
# the StaticFiles mount is scoped to the upload/ subdirectory at runtime)
try:
    chat_dir_resolved = Path(settings.CHAT_DIR).resolve()
    upload_dir_resolved = Path(settings.UPLOAD_DIR).resolve()
    if chat_dir_resolved != upload_dir_resolved and chat_dir_resolved.is_relative_to(upload_dir_resolved):
        raise RuntimeError(
            f"CHAT_DIR ({settings.CHAT_DIR}) 不能位于 UPLOAD_DIR ({settings.UPLOAD_DIR}) 下！"
            "对话历史不应通过静态文件 URL 暴露。"
        )
except ValueError:
    pass
