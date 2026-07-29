"""AI 功能相关的 FastAPI dependencies。"""

import jwt
from fastapi import Depends, Header, HTTPException, Request, status
from jwt.exceptions import PyJWTError
from sqlalchemy.orm import Session

from apps.backend.app.auth.deps import ALGORITHM, get_current_user
from apps.backend.app.config import settings
from apps.backend.app.database import get_db
from apps.backend.app.errors import AppError, ErrorCode
from apps.backend.app.models.family import Family
from apps.backend.app.models.user import User
from apps.backend.app.services.audit_log import write_audit_log


def require_ai_enabled(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> User:
    """要求当前家庭已开启 AI 功能（有激活的 AIProviderConfig）。"""
    from apps.backend.app.models.ai_provider_config import AIProviderConfig

    active_config = (
        db.query(AIProviderConfig)
        .filter(
            AIProviderConfig.family_id == current_user.family_id,
            AIProviderConfig.is_active == True,
            AIProviderConfig.api_key_encrypted.isnot(None),
        )
        .first()
    )
    if not active_config:
        raise AppError(ErrorCode.AI_NOT_ENABLED)
    return current_user


def verify_agent_token(
    request: Request,
    authorization: str = Header(..., alias="Authorization"),
    x_family_id: str = Header(..., alias="X-Family-Id"),
    db: Session = Depends(get_db),
) -> str:
    """验证 agent 服务的 service-to-service token，返回 family_id。

    Accepts JWT Bearer token with 'fid' claim.

    Sets request.state.agent_id from JWT 'agt' claim when available.
    """
    if not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid agent token",
        )

    token = authorization[7:]

    # Try JWT verification first (production path)
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[ALGORITHM])
    except PyJWTError:
        # Development/test fallback: accept AGENT_INTERNAL_TOKEN when explicitly
        # configured. Default is empty string (inactive in production).
        if settings.AGENT_INTERNAL_TOKEN and token == settings.AGENT_INTERNAL_TOKEN:
            request.state.agent_id = "dev-static"
            _validate_family_exists(db, x_family_id)
            return x_family_id
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid agent token",
        ) from None

    if payload.get("type") != "agent":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token type",
        )

    jwt_family_id = payload.get("fid")
    if not jwt_family_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing family_id in agent token",
        )

    # Validate X-Family-Id matches JWT claim (defense in depth)
    if jwt_family_id != x_family_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="family_id mismatch",
        )

    # Inject agent identity into request state for audit logging
    request.state.agent_id = payload.get("agt", "unknown")
    _validate_family_exists(db, jwt_family_id)
    write_audit_log(
        "agent_request", "success",
        family_id=jwt_family_id,
        detail=f"agent_id={request.state.agent_id} path={request.url.path}",
        db=db,
    )
    return jwt_family_id  # type: ignore[no-any-return]


def _validate_family_exists(db: Session, family_id: str) -> None:
    family = db.query(Family).filter(Family.id == int(family_id)).first()
    if not family:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Family not found",
        )
