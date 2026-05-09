"""Captcha verification dependency for ALTCHA."""

import hashlib

from fastapi import Depends, Request
from sqlalchemy.orm import Session

from app.config import settings
from app.core.logging_config import get_logger
from app.database import get_db
from app.errors import AppError, ErrorCode
from app.services.cache import get_captcha_payload_cache
from app.services.security_log import SecurityEventType, _log_security_event

logger = get_logger("captcha")


async def verify_captcha(
    request: Request,
    db: Session = Depends(get_db),
) -> None:
    """Verify ALTCHA captcha payload in production environment.

    This dependency is added to auth endpoints that need captcha protection.
    In development mode, verification is skipped for smooth DX.

    Args:
        request: FastAPI request to extract altcha payload from body
        db: Database session (unused but kept for dependency injection pattern)

    Raises:
        AppError: CAPTCHA_MISSING if captcha is absent or empty
        AppError: CAPTCHA_INVALID if captcha verification fails
        AppError: CAPTCHA_REPLAY if captcha payload was already used
        AppError: CAPTCHA_SERVICE_UNAVAILABLE if captcha cache is unavailable
    """
    # Skip verification in development mode or when explicitly disabled
    if settings.ENVIRONMENT != "production" or settings.DISABLE_CAPTCHA:
        return

    # Allow seed/test scripts to bypass captcha with a pre-shared secret
    if settings.SEED_SECRET and request.headers.get("X-Seed-Secret") == settings.SEED_SECRET:
        return

    # Extract altcha field from request body
    # Note: We read the body here since schemas may have altcha as optional
    try:
        body = await request.json()
    except Exception:
        raise AppError(ErrorCode.CAPTCHA_MISSING)

    altcha = body.get("altcha")

    # Handle missing altcha field
    if altcha is None:
        _log_security_event(
            SecurityEventType.CAPTCHA_VERIFICATION_FAILED,
            client_id=request.client.host if request.client else "unknown",
            error_type="missing",
        )
        raise AppError(ErrorCode.CAPTCHA_MISSING)

    # Handle empty altcha field
    if altcha == "":
        _log_security_event(
            SecurityEventType.CAPTCHA_VERIFICATION_FAILED,
            client_id=request.client.host if request.client else "unknown",
            error_type="empty",
        )
        raise AppError(ErrorCode.CAPTCHA_MISSING)

    # Verify the solution
    from altcha import verify_solution

    verified, err = verify_solution(altcha, settings.ALTCHA_HMAC_KEY, check_expires=True)

    if not verified:
        _log_security_event(
            SecurityEventType.CAPTCHA_VERIFICATION_FAILED,
            client_id=request.client.host if request.client else "unknown",
            error_type="invalid",
        )
        raise AppError(ErrorCode.CAPTCHA_INVALID)

    # R23: Replay attack prevention
    # Compute SHA-256 hash of payload and check if already used
    cache = get_captcha_payload_cache()
    payload_hash = hashlib.sha256(altcha.encode()).hexdigest()
    cache_key = f"altcha:used:{payload_hash}"

    try:
        if cache.get(cache_key):
            _log_security_event(
                SecurityEventType.CAPTCHA_REPLAY_ATTACK,
                client_id=request.client.host if request.client else "unknown",
            )
            raise AppError(ErrorCode.CAPTCHA_REPLAY)
        # Store hash with 1 hour TTL (matches challenge expiry)
        cache.set(cache_key, "1", ttl_seconds=3600)
    except AppError:
        raise
    except Exception as e:
        # Fail-closed: if cache unavailable, reject request
        logger.error(f"Captcha cache error: {e}")
        raise AppError(ErrorCode.CAPTCHA_SERVICE_UNAVAILABLE)