"""Backend 内部端点 — 仅供 agent 微服务调用。

所有端点使用 verify_agent_token dependency 验证 service-to-service token，
并以 X-Family-Id header 中的 family_id 为边界过滤数据。
"""

import json

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.auth.ai_deps import verify_agent_token
from app.database import get_db
from app.errors import AppError, ErrorCode
from app.models.ai_provider_config import AIProviderConfig, AIProviderTestResult
from app.models.family_mcp_server import FamilyMCPServer
from app.models.family_skill_config import FamilySkillConfig
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

    # 查询最新 thinking 测试结果
    thinking_result = (
        db.query(AIProviderTestResult)
        .filter_by(config_id=cfg.id, test_type="thinking")
        .order_by(AIProviderTestResult.tested_at.desc())
        .first()
    )

    return {
        "ai_enabled": True,
        "ai_provider": cfg.provider,
        "api_key": api_key,  # 明文，仅在内部网络传输
        "ai_base_url": cfg.base_url,
        "ai_model_id": cfg.model_id,
        "ai_vision_model_id": cfg.vision_model_id,
        "timeout_seconds": cfg.timeout_seconds if cfg.timeout_seconds is not None else 60,
        "thinking_supported": bool(thinking_result and thinking_result.success),
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


@router.get("/ai/skills/{capability}")
def internal_get_skill_config(
    capability: str,
    family_id: str = Depends(verify_agent_token),
    db: Session = Depends(get_db),
):
    """返回家庭技能配置（custom_prompt + is_enabled + updated_at），供 agent skill_loader 缓存。"""
    row = (
        db.query(FamilySkillConfig)
        .filter(
            FamilySkillConfig.family_id == family_id,
            FamilySkillConfig.capability == capability,
        )
        .first()
    )
    if not row:
        # No override configured — return defaults
        return {"capability": capability, "is_enabled": True, "custom_prompt": None, "updated_at": None}

    return {
        "capability": row.capability,
        "is_enabled": row.is_enabled,
        "custom_prompt": row.custom_prompt,
        "updated_at": row.updated_at.isoformat() if row.updated_at else None,
    }


@router.get("/ai/mcp-servers")
def internal_get_mcp_servers(
    family_id: str = Depends(verify_agent_token),
    db: Session = Depends(get_db),
):
    """返回家庭已启用的 MCP server 列表（含解密 env_vars），供 agent 注入 DeerFlow。"""
    servers = (
        db.query(FamilyMCPServer)
        .filter(
            FamilyMCPServer.family_id == family_id,
            FamilyMCPServer.is_enabled.is_(True),
        )
        .all()
    )

    result = []
    for s in servers:
        env_vars: dict = {}
        if s.env_vars_encrypted:
            raw = decrypt_api_key(s.env_vars_encrypted)
            if raw:
                try:
                    env_vars = json.loads(raw)
                except Exception:
                    env_vars = {}
        result.append({
            "id": s.id,
            "name": s.name,
            "url": s.url,
            "transport": s.transport,
            "env_vars": env_vars,
        })
    return result
