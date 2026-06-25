"""JWT verification for frontend access tokens.

Validates that the ``X-Family-Id`` header matches the ``fid`` claim in the
JWT access token sent by the browser.  This prevents tenant isolation
breaks in development mode where the frontend talks directly to the agent
service (bypassing the backend's authentication layer).

Production deployments that route through the backend are already protected
by the backend's ``verify_agent_token`` dependency.
"""

from __future__ import annotations

import logging
from typing import NamedTuple

import jwt
from fastapi import Header, HTTPException, Request
from jwt.exceptions import ExpiredSignatureError, PyJWTError

from packages.core.settings import settings as _core_settings

logger = logging.getLogger(__name__)

ALGORITHM = "HS256"


class VerifiedFamily(NamedTuple):
    """Result of successful JWT family verification."""
    family_id: str
    user_id: str
    role: str


def _verify_access_token(token: str) -> dict | None:
    """Decode and verify a JWT access token.

    Only checks signature, expiry, and token type — no revocation logic
    (that lives in the backend).  Returns the payload dict if valid.
    """
    try:
        payload = jwt.decode(
            token,
            _core_settings.SECRET_KEY,
            algorithms=[ALGORITHM],
        )
    except ExpiredSignatureError:
        return None
    except PyJWTError:
        return None

    if payload.get("type") != "access":
        return None
    if payload.get("sub") is None:
        return None
    return payload


def verify_family_token(
    request: Request,
    x_family_id: str = Header(..., alias="X-Family-Id"),
    authorization: str | None = Header(None, alias="Authorization"),
) -> VerifiedFamily:
    """FastAPI dependency: verify JWT ``fid`` matches ``X-Family-Id``.

    Accepts the token from:
    1. ``Authorization: Bearer <token>`` header (preferred)
    2. ``access_token`` cookie (fallback — browser sends cookies automatically)

    Raises 401 if no token is found, 403 if ``fid`` doesn't match.
    """
    token: str | None = None

    # Extract Bearer token
    if authorization and authorization.startswith("Bearer "):
        token = authorization[7:]

    # Fallback: check cookies
    if not token:
        token = request.cookies.get("access_token")

    if not token:
        raise HTTPException(
            status_code=401,
            detail="Missing authentication token",
        )

    payload = _verify_access_token(token)
    if payload is None:
        raise HTTPException(
            status_code=401,
            detail="Invalid or expired token",
        )

    fid: str | None = payload.get("fid")
    user_id: str = payload["sub"]
    role: str = payload.get("role", "member")

    if fid is None:
        raise HTTPException(
            status_code=403,
            detail="Token missing family claim",
        )

    # CRITICAL: Verify that the JWT's family matches the requested family
    if fid != x_family_id:
        logger.warning(
            "Family mismatch: JWT fid=%s, header X-Family-Id=%s, user=%s",
            fid, x_family_id, user_id,
        )
        raise HTTPException(
            status_code=403,
            detail="家庭令牌不匹配 — 无法访问其他家庭的资源",
        )

    return VerifiedFamily(family_id=fid, user_id=user_id, role=role)
