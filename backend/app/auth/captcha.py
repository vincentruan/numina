"""Captcha verification dependency for ALTCHA."""

import hashlib
import logging

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.config import settings
from app.core.logging_config import get_logger
from app.database import get_db
from app.services.cache import get_captcha_payload_cache
from app.services.security_log import _log_security_event, SecurityEventType

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
        HTTPException: 400 with specific error message if captcha verification fails
        HTTPException: 503 if captcha service (cache) is unavailable
    """
    # Skip verification in development mode
    if settings.ENVIRONMENT != "production":
        return

    # Extract altcha field from request body
    # Note: We read the body here since schemas may have altcha as optional
    try:
        body = await request.json()
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="请完成验证码验证",
        )

    altcha = body.get("altcha")

    # Handle missing altcha field
    if altcha is None:
        _log_security_event(
            SecurityEventType.CAPTCHA_VERIFICATION_FAILED,
            client_id=request.client.host if request.client else "unknown",
            error_type="missing",
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="请完成验证码验证",
        )

    # Handle empty altcha field
    if altcha == "":
        _log_security_event(
            SecurityEventType.CAPTCHA_VERIFICATION_FAILED,
            client_id=request.client.host if request.client else "unknown",
            error_type="empty",
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="验证码不能为空",
        )

    # Verify the solution
    from altcha import verify_solution

    verified, err = verify_solution(altcha, settings.ALTCHA_HMAC_KEY, check_expires=True)

    if not verified:
        _log_security_event(
            SecurityEventType.CAPTCHA_VERIFICATION_FAILED,
            client_id=request.client.host if request.client else "unknown",
            error_type="invalid",
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="验证码验证失败，请重试",
        )

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
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="验证码验证失败，请重试",
            )
        # Store hash with 1 hour TTL (matches challenge expiry)
        cache.set(cache_key, "1", ttl_seconds=3600)
    except HTTPException:
        raise
    except Exception as e:
        # Fail-closed: if cache unavailable, reject request
        logger.error(f"Captcha cache error: {e}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="验证服务暂时不可用",
        )