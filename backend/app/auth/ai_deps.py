"""AI 功能相关的 FastAPI dependencies。"""

from fastapi import Depends, Header, HTTPException, status
from sqlalchemy.orm import Session

from app.auth.deps import get_current_user
from app.config import settings
from app.database import get_db
from app.models.family import Family
from app.models.user import User


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


def verify_agent_token(
    authorization: str = Header(..., alias="Authorization"),
    x_family_id: str = Header(..., alias="X-Family-Id"),
    db: Session = Depends(get_db),
) -> str:
    """验证 agent 服务的 service-to-service token，返回 family_id。"""
    if not settings.AGENT_INTERNAL_TOKEN:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Agent internal token not configured",
        )

    expected = f"Bearer {settings.AGENT_INTERNAL_TOKEN}"
    if authorization != expected:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid agent token",
        )

    # 验证 family 存在
    family = db.query(Family).filter(Family.id == x_family_id).first()
    if not family:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Family {x_family_id} not found",
        )

    return x_family_id
