"""Backend 内部端点 — 仅供 agent 微服务调用。

所有端点使用 verify_agent_token dependency 验证 service-to-service token，
并以 X-Family-Id header 中的 family_id 为边界过滤数据。
"""

import json
from datetime import datetime

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from apps.backend.app.auth.ai_deps import verify_agent_token
from apps.backend.app.config import settings
from apps.backend.app.database import get_db
from apps.backend.app.errors import AppError, ErrorCode
from apps.backend.app.models.ai_provider_config import (
    AIProviderConfig,
)
from apps.backend.app.models.family_mcp_server import FamilyMCPServer
from apps.backend.app.models.family_skill_config import FamilySkillConfig
from apps.backend.app.models.skill_registry import SkillRegistry
from apps.backend.app.models.user import User
from apps.backend.app.services import dashboard as dashboard_service
from apps.backend.app.services.ai_crypto import decrypt_api_key

router = APIRouter(prefix="/internal", tags=["internal-agent"])


def _get_mock_user(family_id: str, db: Session) -> User:
    """为 agent 调用构造一个代理 User 对象（使用家庭 owner）。"""
    user = (
        db.query(User)
        .filter(User.family_id == family_id, User.role == "owner", User.is_active == True)  # noqa: E712
        .first()
    )
    if not user:
        # fallback: 取任意活跃成员
        user = (
            db.query(User)
            .filter(User.family_id == family_id, User.is_active == True)  # noqa: E712
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
    from apps.backend.app.models.liability import Liability
    liabilities = (
        db.query(Liability)
        .filter(Liability.family_id == family_id, Liability.is_active == True)  # noqa: E712
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
    """返回家庭 AI 供应商列表（按 display_order 排序，已过滤熔断中的供应商）。"""
    from datetime import UTC

    now = datetime.now(UTC).replace(tzinfo=None)

    all_cfgs = (
        db.query(AIProviderConfig)
        .filter(
            AIProviderConfig.family_id == family_id,
            AIProviderConfig.api_key_encrypted.isnot(None),
        )
        .order_by(AIProviderConfig.display_order.asc().nulls_last(), AIProviderConfig.created_at.asc())
        .all()
    )

    if not all_cfgs:
        return {"ai_enabled": False, "providers": []}

    providers = []
    for cfg in all_cfgs:
        # Half-open: circuit expired — clear state and include
        if cfg.circuit_open and cfg.circuit_open_until and cfg.circuit_open_until <= now:
            cfg.circuit_open = False
            cfg.failure_count = 0
            cfg.circuit_open_until = None
            db.commit()

        # Skip providers still in circuit-open state
        if cfg.circuit_open and cfg.circuit_open_until and cfg.circuit_open_until > now:
            continue

        api_key = decrypt_api_key(cfg.api_key_encrypted)
        if not api_key:
            continue

        providers.append({
            "config_id": str(cfg.id),
            "ai_provider": cfg.provider,
            "api_key": api_key,
            "ai_base_url": cfg.base_url,
            "ai_model_id": cfg.model_id,
            "ai_vision_model_id": cfg.vision_model_id,
            "model_2_id": cfg.model_2_id,
            "model_3_id": cfg.model_3_id,
            "model_1_capabilities": _parse_capabilities(cfg.model_1_capabilities),
            "model_2_capabilities": _parse_capabilities(cfg.model_2_capabilities),
            "model_3_capabilities": _parse_capabilities(cfg.model_3_capabilities),
            "timeout_seconds": cfg.timeout_seconds if cfg.timeout_seconds is not None else 60,
        })

    return {"ai_enabled": bool(providers), "providers": providers}


def _parse_capabilities(cap_str: str | None) -> list[str]:
    if not cap_str:
        return []
    try:
        return json.loads(cap_str)
    except Exception:
        return []


class CircuitEventRequest(BaseModel):
    error_code: int


@router.post("/ai/config/{config_id}/circuit-event")
def internal_circuit_event(
    config_id: int,
    body: CircuitEventRequest,
    family_id: str = Depends(verify_agent_token),
    db: Session = Depends(get_db),
):
    """记录供应商调用失败，达到阈值时触发熔断。"""
    from datetime import UTC, timedelta

    cfg = (
        db.query(AIProviderConfig)
        .filter(
            AIProviderConfig.id == config_id,
            AIProviderConfig.family_id == family_id,
        )
        .first()
    )
    if not cfg:
        raise AppError(ErrorCode.FAMILY_NOT_FOUND)

    now = datetime.now(UTC).replace(tzinfo=None)
    cfg.failure_count = (cfg.failure_count or 0) + 1
    cfg.last_failure_at = now

    if cfg.failure_count >= 5:
        cfg.circuit_open = True
        cfg.circuit_open_until = now + timedelta(hours=1)

    db.commit()
    return {"circuit_open": cfg.circuit_open, "failure_count": cfg.failure_count}


@router.post("/ai/config/{config_id}/circuit-reset")
def internal_circuit_reset(
    config_id: int,
    family_id: str = Depends(verify_agent_token),
    db: Session = Depends(get_db),
):
    """成功调用后重置熔断计数。"""
    cfg = (
        db.query(AIProviderConfig)
        .filter(
            AIProviderConfig.id == config_id,
            AIProviderConfig.family_id == family_id,
        )
        .first()
    )
    if not cfg:
        raise AppError(ErrorCode.FAMILY_NOT_FOUND)

    cfg.failure_count = 0
    cfg.circuit_open = False
    cfg.circuit_open_until = None
    db.commit()
    return {"ok": True}


@router.get("/ai/enabled-families")
def internal_get_enabled_families(
    db: Session = Depends(get_db),
    _family_id: str = Depends(verify_agent_token),
):
    """返回所有已开启 AI 功能的家庭 ID 列表（定时任务使用）。

    注意：verify_agent_token 要求 X-Family-Id header，定时任务调用时传入任意有效 family_id 即可。
    实际返回所有有激活 AIProviderConfig 的家庭，不受 family_id 过滤。
    """
    from apps.backend.app.models.ai_provider_config import AIProviderConfig

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


@router.get("/skill-registry/{family_id}")
def get_skill_registry(
    family_id: int,
    x_internal_token: str = Header(..., alias="X-Internal-Token"),
    db: Session = Depends(get_db),
) -> list[dict]:
    """Internal endpoint for agent to fetch family skill registry."""
    if x_internal_token != settings.INTERNAL_TOKEN:
        raise HTTPException(status_code=401, detail="invalid token")

    records = (
        db.query(SkillRegistry)
        .filter(SkillRegistry.family_id == family_id)
        .all()
    )
    return [
        {
            "skill_id": r.skill_id,
            "skill_type": r.skill_type,
            "name": r.name,
            "description": r.description,
            "icon": r.icon,
            "color": r.color,
            "input_mode": r.input_mode,
            "is_enabled": r.is_enabled,
            "display_order": r.display_order,
        }
        for r in records
    ]


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


# ---------------------------------------------------------------------------
# AI Session CRUD — agent writes session metadata here instead of local SQLite
# ---------------------------------------------------------------------------

class SessionUpsertRequest(BaseModel):
    session_id: str
    user_id: str | None = None
    capability: str
    jsonl_path: str
    last_model: str | None = None


class SessionSummaryRequest(BaseModel):
    summary: str | None = None
    model: str | None = None
    status: str = "completed"
    title: str | None = None


def _session_to_dict(s: "object") -> dict:
    return {
        "session_id": s.id,  # type: ignore[attr-defined]
        "family_id": str(s.family_id),  # type: ignore[attr-defined]
        "user_id": str(s.user_id) if s.user_id else None,  # type: ignore[attr-defined]
        "capability": s.capability,  # type: ignore[attr-defined]
        "title": s.title,  # type: ignore[attr-defined]
        "status": s.status,  # type: ignore[attr-defined]
        "last_message_summary": s.last_message_summary,  # type: ignore[attr-defined]
        "last_model": s.last_model,  # type: ignore[attr-defined]
        "has_attachments": s.has_attachments,  # type: ignore[attr-defined]
        "created_at": s.created_at.isoformat() if s.created_at else None,  # type: ignore[attr-defined]
        "updated_at": s.updated_at.isoformat() if s.updated_at else None,  # type: ignore[attr-defined]
    }


@router.post("/ai/sessions/upsert")
def internal_upsert_session(
    body: SessionUpsertRequest,
    family_id: str = Depends(verify_agent_token),
    db: Session = Depends(get_db),
):
    from apps.backend.app.models.ai_chat_session import AIChatSession

    row = db.query(AIChatSession).filter(AIChatSession.id == body.session_id).first()
    if row is None:
        row = AIChatSession(
            id=body.session_id,
            family_id=int(family_id),
            user_id=int(body.user_id) if body.user_id else None,
            capability=body.capability,
            jsonl_path=body.jsonl_path,
            last_model=body.last_model,
        )
        db.add(row)
    else:
        if row.family_id != int(family_id):
            raise AppError(ErrorCode.FORBIDDEN)
        row.updated_at = datetime.utcnow()
        if body.last_model:
            row.last_model = body.last_model
    db.commit()
    return {"ok": True}


@router.post("/ai/sessions/{session_id}/summary")
def internal_update_session_summary(
    session_id: str,
    body: SessionSummaryRequest,
    family_id: str = Depends(verify_agent_token),
    db: Session = Depends(get_db),
):
    import logging

    from apps.backend.app.models.ai_chat_session import AIChatSession
    logger = logging.getLogger(__name__)

    logger.info("[backend] update_session_summary session=%s title=%s summary=%s status=%s model=%s",
                session_id, repr(body.title), repr(body.summary[:50] if body.summary else None),
                body.status, repr(body.model))

    row = db.query(AIChatSession).filter(AIChatSession.id == session_id).first()
    if row is None or row.family_id != int(family_id):
        raise AppError(ErrorCode.NOT_FOUND)
    if body.summary:
        row.last_message_summary = body.summary[:200]
    if body.title:
        row.title = body.title[:50]
        logger.info("[backend] updating title for session=%s to %s", session_id, repr(body.title[:50]))
    row.status = body.status
    if body.model:
        row.last_model = body.model
    row.updated_at = datetime.utcnow()
    db.commit()
    logger.info("[backend] session updated successfully session=%s title=%s", session_id, repr(row.title))
    return {"ok": True}


@router.get("/ai/sessions")
def internal_list_sessions(
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    family_id: str = Depends(verify_agent_token),
    db: Session = Depends(get_db),
):
    from apps.backend.app.models.ai_chat_session import AIChatSession

    total = (
        db.query(AIChatSession)
        .filter(AIChatSession.family_id == int(family_id))
        .count()
    )
    rows = (
        db.query(AIChatSession)
        .filter(AIChatSession.family_id == int(family_id))
        .order_by(AIChatSession.updated_at.desc())
        .limit(limit)
        .offset(offset)
        .all()
    )
    return {"sessions": [_session_to_dict(r) for r in rows], "total": total}


@router.get("/ai/sessions/{session_id}")
def internal_get_session(
    session_id: str,
    family_id: str = Depends(verify_agent_token),
    db: Session = Depends(get_db),
):
    from apps.backend.app.models.ai_chat_session import AIChatSession

    row = db.query(AIChatSession).filter(AIChatSession.id == session_id).first()
    if row is None or row.family_id != int(family_id):
        raise AppError(ErrorCode.NOT_FOUND)
    return _session_to_dict(row)


@router.get("/users/{user_id}")
def internal_get_user(
    user_id: str,
    family_id: str = Depends(verify_agent_token),
    db: Session = Depends(get_db),
):
    """Get user info by user_id for title generation."""
    try:
        user_id_int = int(user_id)
    except ValueError:
        raise AppError(ErrorCode.NOT_FOUND) from None
    user = db.query(User).filter(User.id == user_id_int).first()
    if user is None or str(user.family_id) != family_id:
        raise AppError(ErrorCode.NOT_FOUND)
    return {
        "user_id": str(user.id),
        "username": user.username,
        "display_name": user.display_name,
        "family_id": str(user.family_id),
    }
