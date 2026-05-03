"""Backend 内部端点 — 仅供 agent 微服务调用。

所有端点使用 verify_agent_token dependency 验证 service-to-service token，
并以 X-Family-Id header 中的 family_id 为边界过滤数据。
"""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.auth.ai_deps import verify_agent_token
from app.database import get_db
from app.errors import AppError, ErrorCode
from app.models.user import User
from app.services import dashboard as dashboard_service
from app.services.ai_crypto import decrypt_api_key

router = APIRouter(prefix="/internal", tags=["internal-agent"])


def _get_mock_user(family_id: str, db: Session) -> User:
    """为 agent 调用构造一个代理 User 对象（使用家庭 owner）。"""
    user = (
        db.query(User)
        .filter(User.family_id == family_id, User.role == "owner", User.is_active == True)
        .first()
    )
    if not user:
        # fallback: 取任意活跃成员
        user = (
            db.query(User)
            .filter(User.family_id == family_id, User.is_active == True)
            .first()
        )
    if not user:
        raise AppError(ErrorCode.FAMILY_NO_ACTIVE_MEMBERS)
    return user


@router.get("/dashboard/overview")
def internal_get_overview(
    family_id: str = Depends(verify_agent_token),
    db: Session = Depends(get_db),
):
    user = _get_mock_user(family_id, db)
    return dashboard_service.get_overview(db, user)


@router.get("/dashboard/allocation")
def internal_get_allocation(
    family_id: str = Depends(verify_agent_token),
    db: Session = Depends(get_db),
):
    user = _get_mock_user(family_id, db)
    return dashboard_service.get_allocation(db, user)


@router.get("/dashboard/trend")
def internal_get_trend(
    period: str = Query("year"),
    family_id: str = Depends(verify_agent_token),
    db: Session = Depends(get_db),
):
    user = _get_mock_user(family_id, db)
    return dashboard_service.get_trend(db, user, period)


@router.get("/dashboard/low-usage")
def internal_get_low_usage(
    family_id: str = Depends(verify_agent_token),
    db: Session = Depends(get_db),
):
    user = _get_mock_user(family_id, db)
    return dashboard_service.get_low_usage_assets(db, user)


@router.get("/dashboard/daily-cost-ranking")
def internal_get_daily_cost(
    family_id: str = Depends(verify_agent_token),
    db: Session = Depends(get_db),
):
    user = _get_mock_user(family_id, db)
    return dashboard_service.get_daily_cost_ranking(db, user)


@router.get("/dashboard/expiring-soon")
def internal_get_expiring_soon(
    days_threshold: int = Query(180),
    family_id: str = Depends(verify_agent_token),
    db: Session = Depends(get_db),
):
    user = _get_mock_user(family_id, db)
    return dashboard_service.get_expiring_soon_assets(db, user, days_threshold)


@router.get("/liabilities")
def internal_get_liabilities(
    family_id: str = Depends(verify_agent_token),
    db: Session = Depends(get_db),
):
    from app.models.liability import Liability
    liabilities = (
        db.query(Liability)
        .filter(Liability.family_id == family_id, Liability.is_active == True)
        .all()
    )
    return [
        {
            "id": li.id,
            "category": li.category,
            "remaining_amount": li.remaining_amount,
            "original_amount": li.original_amount,
            "monthly_payment": li.monthly_payment,
            "interest_rate": li.interest_rate,
            "start_date": li.start_date.isoformat() if li.start_date else None,
            "end_date": li.end_date.isoformat() if li.end_date else None,
            "currency": li.currency,
        }
        for li in liabilities
    ]


@router.get("/ai/config")
def internal_get_ai_config(
    family_id: str = Depends(verify_agent_token),
    db: Session = Depends(get_db),
):
    """返回家庭 AI 配置，包含解密后的 API Key（仅供 agent 内部使用）。"""
    from app.models.ai_provider_config import AIProviderConfig

    cfg = (
        db.query(AIProviderConfig)
        .filter(
            AIProviderConfig.family_id == family_id,
            AIProviderConfig.is_active == True,  # noqa: E712
        )
        .first()
    )
    if not cfg or not cfg.api_key_encrypted:
        return {"ai_enabled": False}

    api_key = decrypt_api_key(cfg.api_key_encrypted)

    return {
        "ai_enabled": True,
        "ai_provider": cfg.provider,
        "api_key": api_key,  # 明文，仅在内部网络传输
        "ai_base_url": cfg.base_url,
        "ai_model_id": cfg.model_id,
        "ai_vision_model_id": cfg.vision_model_id,
        "timeout_seconds": cfg.timeout_seconds if cfg.timeout_seconds is not None else 60,
    }


@router.get("/ai/enabled-families")
def internal_get_enabled_families(
    db: Session = Depends(get_db),
    _family_id: str = Depends(verify_agent_token),
):
    """返回所有已开启 AI 功能的家庭 ID 列表（定时任务使用）。

    注意：verify_agent_token 要求 X-Family-Id header，定时任务调用时传入任意有效 family_id 即可。
    实际返回所有有激活 AIProviderConfig 的家庭，不受 family_id 过滤。
    """
    from app.models.ai_provider_config import AIProviderConfig

    rows = (
        db.query(AIProviderConfig.family_id)
        .filter(
            AIProviderConfig.is_active == True,  # noqa: E712
            AIProviderConfig.api_key_encrypted.isnot(None),
        )
        .distinct()
        .all()
    )
    return [r.family_id for r in rows]
