"""AI 功能相关的 FastAPI dependencies。"""

import hmac
from datetime import datetime, timedelta

from fastapi import Depends, Header, HTTPException, status
from jose import JWTError, jwt
from sqlalchemy.orm import Session

from app.auth.deps import get_current_user, ALGORITHM
from app.config import settings
from app.database import get_db
from app.models.family import Family
from app.models.user import User

# Agent JWT TTL: 5 minutes (short-lived, per-request)
_AGENT_TOKEN_TTL_SECONDS = 300


def require_owner(current_user: User = Depends(get_current_user)) -> User:
    """要求当前用户为家庭 owner。"""
    if current_user.role != "owner":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"code": "ai_not_authorized", "message": "此操作需要家庭管理员权限"},
        )
    return current_user


def require_ai_enabled(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> User:
    """要求当前家庭已开启 AI 功能。"""
    family = db.query(Family).filter(Family.id == current_user.family_id).first()
    if not family or not family.ai_enabled:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"code": "ai_disabled", "message": "AI 功能未开启，请联系家庭管理员在设置中开启"},
        )
    return current_user


def create_agent_token(family_id: str, agent_instance_id: str = "backend") -> str:
    """Create a short-lived JWT for backend→agent service-to-service calls.

    Cryptographically binds family_id so it cannot be tampered with.
    """
    now = datetime.utcnow()
    payload = {
        "sub": "agent",
        "fid": family_id,
        "agt": agent_instance_id,
        "iat": now,
        "exp": now + timedelta(seconds=_AGENT_TOKEN_TTL_SECONDS),
        "type": "agent",
    }
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=ALGORITHM)


def verify_agent_token(
    authorization: str = Header(..., alias="Authorization"),
    x_family_id: str = Header(..., alias="X-Family-Id"),
    db: Session = Depends(get_db),
) -> str:
    """验证 agent 服务的 service-to-service token，返回 family_id。

    Accepts two formats (for backward compatibility during migration):
    1. JWT Bearer token with 'fid' claim (new, preferred)
    2. Static HMAC Bearer token + X-Family-Id header (legacy)
    """
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid agent token")

    token = authorization[7:]

    # Try JWT verification first (new format)
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[ALGORITHM])
        if payload.get("type") == "agent":
            jwt_family_id = payload.get("fid")
            if not jwt_family_id:
                raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing family_id in agent token")
            # Validate X-Family-Id matches JWT claim (defense in depth)
            if jwt_family_id != x_family_id:
                raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="family_id mismatch")
            _validate_family_exists(db, jwt_family_id)
            return jwt_family_id
    except JWTError:
        pass  # Fall through to legacy HMAC check

    # Legacy: static HMAC token
    if not settings.AGENT_INTERNAL_TOKEN:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Agent internal token not configured")

    expected = settings.AGENT_INTERNAL_TOKEN
    if not hmac.compare_digest(token, expected):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid agent token")

    _validate_family_exists(db, x_family_id)
    return x_family_id


def _validate_family_exists(db: Session, family_id: str) -> None:
    family = db.query(Family).filter(Family.id == family_id).first()
    if not family:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Family not found")

    # 验证 family 存在
    family = db.query(Family).filter(Family.id == x_family_id).first()
    if not family:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Family {x_family_id} not found",
        )

    return x_family_id
