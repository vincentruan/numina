"""Security event logging service."""

import logging
from datetime import datetime
from pathlib import Path
from typing import Any

from app.config import settings

logger = logging.getLogger("security")


class SecurityEventType:
    """Security event type constants."""

    LOGIN_SUCCESS = "login_success"
    LOGIN_FAILED_WRONG_PASSWORD = "login_failed_wrong_password"
    LOGIN_FAILED_USER_NOT_FOUND = "login_failed_user_not_found"
    LOGIN_RATE_LIMITED = "login_rate_limited"
    REGISTER_SUCCESS = "register_success"
    TOKEN_REFRESH_SUCCESS = "token_refresh_success"
    TOKEN_REFRESH_FAILED = "token_refresh_failed"
    UPLOAD_MAGIC_BYTES_MISMATCH = "upload_magic_bytes_mismatch"
    GLOBAL_RATE_LIMITED = "global_rate_limited"


def setup_security_logging() -> None:
    """Configure security logger with appropriate handlers."""
    if not settings.ENABLE_SECURITY_LOGGING:
        return

    # Set level
    logger.setLevel(logging.INFO)

    # Add handler if not already configured
    if not logger.handlers:
        # Ensure logs directory exists
        logs_dir = Path("logs")
        logs_dir.mkdir(exist_ok=True)

        # File handler with rotation (keep 7 days)
        from logging.handlers import TimedRotatingFileHandler
        handler = TimedRotatingFileHandler(
            "logs/security.log",
            when="midnight",
            backupCount=7,
            encoding="utf-8"
        )
        handler.setFormatter(logging.Formatter(
            "%(asctime)s - %(levelname)s - %(message)s"
        ))
        logger.addHandler(handler)


def _log_security_event(
    event_type: str,
    **details: Any,
) -> None:
    """Log a security event with structured details.

    Args:
        event_type: Event type identifier (e.g., "login_success", "login_failed")
        **details: Additional context (username, user_id, ip_address, etc.)
    """
    if not settings.ENABLE_SECURITY_LOGGING:
        return

    # Build log message
    details_str = " | ".join(f"{k}={v}" for k, v in details.items())
    message = f"[{event_type}] {details_str}"

    # Log at appropriate level
    if event_type.endswith("_success"):
        logger.info(message)
    elif event_type.endswith("_failed") or event_type.endswith("_blocked") or event_type.endswith("_limited"):
        logger.warning(message)
    else:
        logger.info(message)