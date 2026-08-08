"""AI 功能相关的 FastAPI dependencies。"""

import logging

import jwt
from fastapi import Depends, Header, HTTPException, Request, status
from jwt.exceptions import PyJWTError
from sqlalchemy.orm import Session

from apps.backend.app.auth.deps import ALGORITHM, get_current_user
from apps.backend.app.config import settings
from apps.backend.app.database import get_db
from apps.backend.app.errors import AppError, ErrorCode
from apps.backend.app.models.ai_provider_config import AIProviderConfig
from apps.backend.app.models.family import Family
from apps.backend.app.models.user import User
from apps.backend.app.services.audit_log import write_audit_log

logger = logging.getLogger(__name__)


def require_ai_enabled(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> User:
    """要求当前家庭已开启 AI 功能（Family.ai_enabled 开关）。

    When ai_enabled is True but no active provider is configured, log a
    warning so the misconfiguration surfaces in diagnostics rather than
    failing later with an opaque LLM error.
    """
    family = (
        db.query(Family)
        .filter(Family.id == current_user.family_id)
        .first()
    )
    if not family or not family.ai_enabled:
        raise AppError(ErrorCode.AI_NOT_ENABLED)
    # Secondary check: warn when the flag is on but no provider exists.
    # Does not block the request — the agent will fail with a clear
    # "未配置 AI 供应商" error from RunPipeline.__aenter__.
    provider_count = (
        db.query(AIProviderConfig)
        .filter(
            AIProviderConfig.family_id == current_user.family_id,
            AIProviderConfig.is_active.is_(True),
        )
        .count()
    )
    if provider_count == 0:
        logger.warning(
            "family_id=%s has ai_enabled=True but no active AIProviderConfig",
            current_user.family_id,
        )
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

    # JWT verification
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[ALGORITHM])
    except PyJWTError:
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
