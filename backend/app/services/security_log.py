"""Security event logging service."""

from typing import Any

from app.config import settings
from app.core.logging_config import get_logger

logger = get_logger("security")


class SecurityEventType:
    """Security event type constants."""

    LOGIN_SUCCESS = "login_success"
    LOGIN_FAILED_WRONG_PASSWORD = "login_failed_wrong_password"
    LOGIN_FAILED_USER_NOT_FOUND = "login_failed_user_not_found"
    LOGIN_RATE_LIMITED = "login_rate_limited"
    REGISTER_SUCCESS = "register_success"
    REGISTER_RATE_LIMITED = "register_rate_limited"
    TOKEN_REFRESH_SUCCESS = "token_refresh_success"
    TOKEN_REFRESH_FAILED = "token_refresh_failed"
    UPLOAD_MAGIC_BYTES_MISMATCH = "upload_magic_bytes_mismatch"
    GLOBAL_RATE_LIMITED = "global_rate_limited"
    CAPTCHA_VERIFICATION_FAILED = "captcha_verification_failed"
    CAPTCHA_REPLAY_ATTACK = "captcha_replay_attack"
    # Child PIN authentication events
    CHILD_PIN_SUCCESS = "child_pin_success"
    CHILD_PIN_FAILED = "child_pin_failed"
    CHILD_PIN_RATE_LIMITED = "child_pin_rate_limited"


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
    elif (
        event_type.endswith("_failed")
        or event_type.endswith("_blocked")
        or event_type.endswith("_limited")
    ):
        logger.warning(message)
    else:
        logger.info(message)
