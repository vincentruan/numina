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
        raise HTTPException(status_code=401, detail="invalid token type")

    token_family_id = payload.get("fid")
    if not token_family_id:
        raise HTTPException(status_code=401, detail="missing family_id in token")

    # If X-Family-Id is provided, verify it matches the JWT claim
    if x_family_id and token_family_id != x_family_id:
        raise HTTPException(status_code=403, detail="family_id mismatch")

    return token_family_id  # type: ignore[no-any-return]
