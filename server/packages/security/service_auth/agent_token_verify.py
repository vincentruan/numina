"""Verify JWT service-to-service tokens from the backend.

Used by agent-side routers to validate the ``X-Agent-Token`` header.
Accepts JWT tokens created by ``create_agent_token()`` in ``agent_jwt.py``.
"""

from __future__ import annotations

import logging

import jwt
from fastapi import Header, HTTPException
from jwt.exceptions import PyJWTError

from packages.core.settings import settings

logger = logging.getLogger(__name__)

ALGORITHM = "HS256"


def verify_service_token(
    x_agent_token: str = Header(..., alias="X-Agent-Token"),
    x_family_id: str = Header("", alias="X-Family-Id"),
) -> str:
    """FastAPI dependency: verify JWT agent token, return family_id.

    Raises 401 if the token is invalid or expired.
    Raises 403 if the token's family_id doesn't match X-Family-Id header.
    """
    try:
        payload = jwt.decode(x_agent_token, settings.SECRET_KEY, algorithms=[ALGORITHM])
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="agent token expired") from None
    except PyJWTError:
        raise HTTPException(status_code=401, detail="invalid agent token") from None

    if payload.get("type") != "agent":
        raise HTTPException(status_code=401, detail="invalid agent token type")

    token_family_id = payload.get("fid")
    if not token_family_id:
        raise HTTPException(status_code=401, detail="missing family_id in token")

    # If X-Family-Id is provided, verify it matches the JWT claim
    if x_family_id and token_family_id != x_family_id:
        raise HTTPException(status_code=403, detail="family_id mismatch")

    return token_family_id  # type: ignore[no-any-return]


def verify_mcp_agent_token(
    x_agent_token: str = Header(..., alias="X-Agent-Token"),
    x_family_id: str = Header("", alias="X-Family-Id"),
) -> str:
    """Verify JWT agent token for MCP internal endpoints.

    Same JWT verification as ``verify_service_token`` but uses ``AppError``
    for consistency with backend error handling, and enforces family_id
    matching against the URL path parameter.

    Returns the family_id from the JWT.
    """
    from apps.backend.app.errors import AppError, ErrorCode

    try:
        payload = jwt.decode(x_agent_token, settings.SECRET_KEY, algorithms=[ALGORITHM])
    except jwt.ExpiredSignatureError:
        raise AppError(ErrorCode.AUTH_INVALID_CREDENTIALS, "agent token expired") from None
    except PyJWTError:
        raise AppError(ErrorCode.AUTH_INVALID_CREDENTIALS, "invalid agent token") from None

    if payload.get("type") != "agent":
        raise AppError(ErrorCode.AUTH_INVALID_CREDENTIALS, "invalid token type")

    token_family_id = payload.get("fid")
    if not token_family_id:
        raise AppError(ErrorCode.AUTH_INVALID_CREDENTIALS, "missing family_id in token")

    # MCP endpoints use family_id from URL path — verify it matches JWT
    if x_family_id and token_family_id != x_family_id:
        raise AppError(ErrorCode.FORBIDDEN, "family_id mismatch")

    return token_family_id  # type: ignore[no-any-return]


def verify_system_token_jwt(
    authorization: str = Header(..., alias="Authorization"),
) -> bool:
    """Verify JWT system token for system-level endpoints (no family context).

    Used by scheduler_worker calling backend system endpoints.
    """
    from apps.backend.app.errors import AppError, ErrorCode

    if not authorization.startswith("Bearer "):
        raise AppError(ErrorCode.AUTH_INVALID_CREDENTIALS, "Invalid system token format")

    token = authorization[7:]

    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[ALGORITHM])
    except jwt.ExpiredSignatureError:
        raise AppError(ErrorCode.AUTH_INVALID_CREDENTIALS, "system token expired") from None
    except PyJWTError:
        raise AppError(ErrorCode.AUTH_INVALID_CREDENTIALS, "Invalid system token") from None

    if payload.get("type") != "system":
        raise AppError(ErrorCode.AUTH_INVALID_CREDENTIALS, "Invalid token type")

    return True
