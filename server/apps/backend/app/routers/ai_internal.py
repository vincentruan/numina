"""Backend 内部端点 — 仅供 agent 微服务调用。

所有端点使用 verify_agent_token dependency 验证 service-to-service token，
并以 X-Family-Id header 中的 family_id 为边界过滤数据。
"""

import json
from datetime import datetime
from typing import Literal

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from apps.backend.app.auth.ai_deps import verify_agent_token
from apps.backend.app.database import get_db
from apps.backend.app.errors import AppError, ErrorCode
from apps.backend.app.models.ai_provider_config import (
    AIProviderConfig,
)
from apps.backend.app.models.family_mcp_server import FamilyMCPServer
from apps.backend.app.models.family_skill_config import FamilySkillConfig
from apps.backend.app.models.family_web_search_provider import FamilyWebSearchProvider
from apps.backend.app.models.skill_registry import SkillRegistry
from apps.backend.app.models.user import User
from apps.backend.app.services import dashboard as dashboard_service
from apps.backend.app.services.ai_crypto import decrypt_api_key
from apps.backend.app.services.web_search_provider_registry import get_provider_template

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


def _check_recovery_schedule_match(recovery_schedule: str | None, now: datetime) -> bool:
    """Check if current time matches recovery schedule pattern.

    Recovery schedule format: comma-separated time patterns like ":01,:31"
    Pattern matches when the current minute equals the specified value exactly.
    """
    if not recovery_schedule:
        return False
    current_minute = now.strftime("%M")
    for pattern in recovery_schedule.split(","):
        pattern = pattern.strip()
        if pattern.startswith(":") and current_minute == pattern[1:].zfill(2):
            return True
    return False


def _calculate_half_open_success_rate(cfg: AIProviderConfig) -> float:
    """Calculate success rate during half-open window."""
    total = cfg.half_open_success_count + cfg.half_open_failure_count
    if total == 0:
        return 0.0
    return cfg.half_open_success_count / total


@router.get("/ai/config")
def internal_get_ai_config(
    family_id: str = Depends(verify_agent_token),
    db: Session = Depends(get_db),
):
    """返回家庭已启用的 AI 供应商列表（按 display_order 排序）。

    三态熔断逻辑：
    - closed: 正常供应商，包含在列表中
    - half_open: 探测恢复，包含在列表中（agent 决定路由概率）
    - open: 熔断中，排除列表（除非恢复时间匹配触发 half_open）

    返回 circuit_state 和 circuit_reason 供 agent 路由决策。
    """
    from datetime import UTC, timedelta

    now = datetime.now(UTC).replace(tzinfo=None)

    all_cfgs = (
        db.query(AIProviderConfig)
        .filter(
            AIProviderConfig.family_id == family_id,
            AIProviderConfig.is_active == True,  # noqa: E712
            AIProviderConfig.api_key_encrypted.isnot(None),
        )
        .order_by(AIProviderConfig.display_order.asc().nulls_last(), AIProviderConfig.created_at.asc())
        .all()
    )

    if not all_cfgs:
        # No AI providers configured, but web search providers might exist
        family_id_int = int(family_id)
        web_search_providers_query = (
            db.query(FamilyWebSearchProvider)
            .filter(
                FamilyWebSearchProvider.family_id == family_id_int,
                FamilyWebSearchProvider.is_enabled == True,  # noqa: E712
                FamilyWebSearchProvider.circuit_state != "open",
            )
            .order_by(FamilyWebSearchProvider.display_order.asc())
            .all()
        )

        web_search_providers = []
        for provider in web_search_providers_query:
            template = get_provider_template(provider.provider_name)
            api_key = None
            if provider.api_key_encrypted:
                api_key = decrypt_api_key(provider.api_key_encrypted)

            web_search_providers.append({
                "provider_id": provider.id,
                "provider_name": provider.provider_name,
                "provider_class": template.get("provider_class") if template else None,
                "api_key": api_key,
                "max_results": provider.max_results,
            })

        websearch_mcp_servers = (
            db.query(FamilyMCPServer)
            .filter(
                FamilyMCPServer.family_id == family_id_int,
                FamilyMCPServer.is_enabled == True,  # noqa: E712
                FamilyMCPServer.mcp_type == "websearch",
            )
            .all()
        )

        web_search_mcp_servers = [
            {
                "name": mcp.name,
                "url": mcp.url,
                "transport": mcp.transport,
            }
            for mcp in websearch_mcp_servers
        ]

        return {
            "ai_enabled": False,
            "providers": [],
            "web_search_providers": web_search_providers,
            "web_search_mcp_servers": web_search_mcp_servers,
        }

    providers = []
    state_changed = False
    for cfg in all_cfgs:
        # Handle state transitions based on three-state model
        if cfg.circuit_state == "open":
            # Check recovery schedule to trigger half_open transition
            if _check_recovery_schedule_match(cfg.recovery_schedule, now):
                cfg.circuit_state = "half_open"
                cfg.half_open_window_start = now
                cfg.half_open_success_count = 0
                cfg.half_open_failure_count = 0
                state_changed = True
            elif cfg.circuit_open_until and cfg.circuit_open_until <= now:
                # Legacy: expired circuit_open_until → half_open
                cfg.circuit_state = "half_open"
                cfg.half_open_window_start = now
                cfg.half_open_success_count = 0
                cfg.half_open_failure_count = 0
                cfg.circuit_open_until = None
                state_changed = True
            else:
                # Still in open state, skip provider
                continue

        elif cfg.circuit_state == "half_open":
            # Check if 5-minute window expired and calculate success rate
            window_start = cfg.half_open_window_start
            if window_start and (now - window_start).total_seconds() >= 300:
                success_rate = _calculate_half_open_success_rate(cfg)
                # Success: close circuit (>=80% success)
                # Failure: re-open circuit (<80% success)
                if success_rate >= 0.8:
                    cfg.circuit_state = "closed"
                    cfg.circuit_reason = None
                    cfg.failure_count = 0
                    cfg.circuit_open = False
                    cfg.half_open_window_start = None
                    cfg.half_open_success_count = 0
                    cfg.half_open_failure_count = 0
                    state_changed = True
                else:
                    cfg.circuit_state = "open"
                    cfg.circuit_reason = "transient"
                    cfg.circuit_open = True
                    cfg.circuit_open_until = now + timedelta(hours=1)
                    cfg.half_open_window_start = None
                    state_changed = True
                    continue  # Skip provider

        # Legacy boolean migration: sync circuit_open with circuit_state
        new_circuit_open = cfg.circuit_state in ("open", "half_open")
        if cfg.circuit_open != new_circuit_open:
            cfg.circuit_open = new_circuit_open
            state_changed = True

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
            # Circuit breaker metadata for agent routing decisions
            "circuit_state": cfg.circuit_state,
            "circuit_reason": cfg.circuit_reason,
            "recovery_schedule": cfg.recovery_schedule,
        })

    # Single commit for all state transitions across all providers
    if state_changed:
        db.commit()

    # Query enabled web search providers (exclude open circuit state)
    family_id_int = int(family_id)
    web_search_providers_query = (
        db.query(FamilyWebSearchProvider)
        .filter(
            FamilyWebSearchProvider.family_id == family_id_int,
            FamilyWebSearchProvider.is_enabled == True,  # noqa: E712
            FamilyWebSearchProvider.circuit_state != "open",
        )
        .order_by(FamilyWebSearchProvider.display_order.asc())
        .all()
    )

    web_search_providers = []
    for provider in web_search_providers_query:
        template = get_provider_template(provider.provider_name)
        api_key = None
        if provider.api_key_encrypted:
            api_key = decrypt_api_key(provider.api_key_encrypted)

        web_search_providers.append({
            "provider_id": provider.id,
            "provider_name": provider.provider_name,
            "provider_class": template.get("provider_class") if template else None,
            "api_key": api_key,
            "max_results": provider.max_results,
        })

    # Query enabled websearch-type MCP servers
    websearch_mcp_servers = (
        db.query(FamilyMCPServer)
        .filter(
            FamilyMCPServer.family_id == family_id_int,
            FamilyMCPServer.is_enabled == True,  # noqa: E712
            FamilyMCPServer.mcp_type == "websearch",
        )
        .all()
    )

    web_search_mcp_servers = [
        {
            "name": mcp.name,
            "url": mcp.url,
            "transport": mcp.transport,
        }
        for mcp in websearch_mcp_servers
    ]

    return {
        "ai_enabled": bool(providers),
        "providers": providers,
        "web_search_providers": web_search_providers,
        "web_search_mcp_servers": web_search_mcp_servers,
    }


def _parse_capabilities(cap_str: str | None) -> list[str]:
    if not cap_str:
        return []
    try:
        return json.loads(cap_str)
    except Exception:
        return []


class CircuitEventRequest(BaseModel):
    error_code: int
    error_type: Literal[
        "transient_rate_limit",
        "transient_server",
        "transient_timeout",
        "transient_network",
        "permanent_auth",
        "permanent_account",
    ]
    error_message: str | None = None


@router.post("/ai/config/{config_id}/circuit-event")
def internal_circuit_event(
    config_id: int,
    body: CircuitEventRequest,
    family_id: str = Depends(verify_agent_token),
    db: Session = Depends(get_db),
):
    """记录供应商调用失败，根据错误类型触发熔断逻辑。

    错误类型分类：
    - permanent_auth (401/403): 立即熔断，无自动恢复时间
    - permanent_account (410/账号删除): 立即熔断，无自动恢复时间
    - transient_*: 累计失败次数，达到阈值后熔断，设置恢复时间
    """
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
    cfg.last_failure_at = now
    cfg.last_failure_type = body.error_type

    # Permanent errors: immediate circuit open, no scheduled recovery
    if body.error_type in ("permanent_auth", "permanent_account"):
        cfg.circuit_state = "open"
        cfg.circuit_reason = body.error_type
        cfg.circuit_open = True
        cfg.circuit_open_until = None  # Manual recovery only
        cfg.failure_count = 0  # Reset for clean state
    else:
        # Transient errors: increment failure count
        cfg.failure_count = (cfg.failure_count or 0) + 1

        if cfg.failure_count >= 5:
            cfg.circuit_state = "open"
            cfg.circuit_reason = "transient"
            cfg.circuit_open = True
            # Align recovery to schedule or default 1 hour
            if cfg.recovery_schedule:
                # Recovery schedule handled by U3 (internal_get_ai_config)
                cfg.circuit_open_until = now + timedelta(hours=1)
            else:
                cfg.circuit_open_until = now + timedelta(hours=1)

    db.commit()
    return {
        "circuit_state": cfg.circuit_state,
        "circuit_reason": cfg.circuit_reason,
        "failure_count": cfg.failure_count,
    }


@router.post("/ai/config/{config_id}/circuit-reset")
def internal_circuit_reset(
    config_id: int,
    family_id: str = Depends(verify_agent_token),
    db: Session = Depends(get_db),
):
    """成功调用后重置熔断计数，或手动重置熔断状态。"""
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

    # Clear all circuit breaker state
    cfg.circuit_state = "closed"
    cfg.circuit_reason = None
    cfg.failure_count = 0
    cfg.circuit_open = False
    cfg.circuit_open_until = None
    cfg.last_failure_type = None
    cfg.half_open_success_count = 0
    cfg.half_open_failure_count = 0
    cfg.half_open_window_start = None
    db.commit()
    return {"ok": True, "circuit_state": "closed"}


class HalfOpenResultRequest(BaseModel):
    success: bool


class WebSearchCircuitReportRequest(BaseModel):
    failure_type: Literal[
        "transient_rate_limit",
        "transient_server",
        "transient_timeout",
        "transient_network",
        "permanent_auth",
        "permanent_account",
    ]
    error_message: str | None = None


@router.post("/ai/web-search/{provider_id}/circuit")
def internal_web_search_circuit_report(
    provider_id: int,
    body: WebSearchCircuitReportRequest,
    family_id: str = Depends(verify_agent_token),
    db: Session = Depends(get_db),
):
    """记录 web search 供应商调用失败，触发熔断逻辑。

    错误类型分类：
    - permanent_auth/permanent_account: 立即熔断，无自动恢复
    - transient_*: 累计失败次数，达到阈值后熔断
    """
    from apps.backend.app.services.web_search_circuit_service import (
        WebSearchCircuitService,
    )

    provider = (
        db.query(FamilyWebSearchProvider)
        .filter(
            FamilyWebSearchProvider.id == provider_id,
            FamilyWebSearchProvider.family_id == int(family_id),
        )
        .first()
    )
    if not provider:
        raise AppError(ErrorCode.NOT_FOUND)

    WebSearchCircuitService.report_failure(provider_id, body.failure_type, db)
    db.refresh(provider)

    return {
        "ok": True,
        "circuit_state": provider.circuit_state,
        "circuit_reason": provider.circuit_reason,
    }


@router.post("/ai/config/{config_id}/half-open-result")
def internal_half_open_result(
    config_id: int,
    body: HalfOpenResultRequest,
    family_id: str = Depends(verify_agent_token),
    db: Session = Depends(get_db),
):
    """记录 half-open 状态下的调用结果（成功或失败）。

    Agent 在 half_open 状态调用供应商后，通过此端点报告结果。
    Backend 累计计数，下次 /ai/config 请求时计算成功率决定是否关闭熔断。
    """
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

    # Only accept results when in half_open state — return 409 Conflict otherwise
    # so the caller can distinguish "recorded" from "ignored" rather than
    # treating an ignored result as success.
    if cfg.circuit_state != "half_open":
        raise AppError(
            ErrorCode.AI_TASK_IN_PROGRESS,
            f"Provider not in half_open state (current: {cfg.circuit_state})",
        )

    if body.success:
        cfg.half_open_success_count = (cfg.half_open_success_count or 0) + 1
    else:
        cfg.half_open_failure_count = (cfg.half_open_failure_count or 0) + 1
        # Immediate re-open on failure during half_open
        cfg.circuit_state = "open"
        cfg.circuit_reason = "transient"
        cfg.circuit_open = True
        cfg.circuit_open_until = datetime.now(UTC).replace(tzinfo=None) + timedelta(hours=1)
        cfg.half_open_window_start = None

    db.commit()
    return {
        "ok": True,
        "half_open_success_count": cfg.half_open_success_count,
        "half_open_failure_count": cfg.half_open_failure_count,
        "circuit_state": cfg.circuit_state,
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
    family_id: str,
    auth_family_id: str = Depends(verify_agent_token),
    db: Session = Depends(get_db),
) -> list[dict]:
    """Internal endpoint for agent to fetch family skill registry.

    Uses verify_agent_token dependency like other internal routes.
    The family_id in path must match the authenticated family_id from token.
    """
    # Verify path family_id matches authenticated family_id
    if family_id != auth_family_id:
        raise AppError(ErrorCode.FORBIDDEN, "family_id mismatch")

    # Convert str to int for database query (Snowflake IDs are passed as strings)
    family_id_int = int(family_id)
    records = (
        db.query(SkillRegistry)
        .filter(SkillRegistry.family_id == family_id_int)
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
    agent_id: str | None = None
    jsonl_path: str
    last_model: str | None = None
    source: str | None = None


class SessionSummaryRequest(BaseModel):
    summary: str | None = None
    model: str | None = None
    status: str = "completed"
    title: str | None = None
    is_pinned: bool | None = None


def _session_to_dict(s: "object") -> dict:
    return {
        "session_id": s.id,  # type: ignore[attr-defined]
        "family_id": str(s.family_id),  # type: ignore[attr-defined]
        "user_id": str(s.user_id) if s.user_id else None,  # type: ignore[attr-defined]
        "agent_id": str(s.agent_id) if s.agent_id else None,  # type: ignore[attr-defined]
        "title": s.title,  # type: ignore[attr-defined]
        "original_title": s.original_title,  # type: ignore[attr-defined]
        "status": s.status,  # type: ignore[attr-defined]
        "last_message_summary": s.last_message_summary,  # type: ignore[attr-defined]
        "last_model": s.last_model,  # type: ignore[attr-defined]
        "has_attachments": s.has_attachments,  # type: ignore[attr-defined]
        "is_pinned": s.is_pinned,  # type: ignore[attr-defined]
        "source": s.source,  # type: ignore[attr-defined]
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
            agent_id=int(body.agent_id) if body.agent_id else None,
            jsonl_path=body.jsonl_path,
            last_model=body.last_model,
            source=body.source,
        )
        db.add(row)
    else:
        if row.family_id != int(family_id):
            raise AppError(ErrorCode.FORBIDDEN)
        row.updated_at = datetime.utcnow()
        if body.last_model:
            row.last_model = body.last_model
        if body.agent_id and not row.agent_id:
            row.agent_id = int(body.agent_id)
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
        # Preserve the existing (auto-generated) title on the first manual
        # rename so the original TitleMiddleware-produced title is never lost.
        if row.title and not row.original_title:
            row.original_title = row.title
        row.title = body.title[:50]
        logger.info("[backend] updating title for session=%s to %s", session_id, repr(body.title[:50]))
    row.status = body.status
    if body.model:
        row.last_model = body.model
    if body.is_pinned is not None:
        row.is_pinned = body.is_pinned
    row.updated_at = datetime.utcnow()
    db.commit()
    logger.info("[backend] session updated successfully session=%s title=%s", session_id, repr(row.title))
    return {"ok": True}


@router.get("/ai/sessions")
def internal_list_sessions(
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    agent_id: str | None = Query(default=None),
    sort_by: str = Query(default="updated_at"),
    sort_order: str = Query(default="desc"),
    family_id: str = Depends(verify_agent_token),
    db: Session = Depends(get_db),
):
    from apps.backend.app.models.ai_chat_session import AIChatSession

    q = db.query(AIChatSession).filter(AIChatSession.family_id == int(family_id))
    if agent_id:
        q = q.filter(AIChatSession.agent_id == int(agent_id))
    total = q.count()

    # Build the sort columns. Pinned sessions always surface first, then the
    # requested sort column (defaults to updated_at desc).
    sort_column = {
        "updated_at": AIChatSession.updated_at,
        "created_at": AIChatSession.created_at,
    }.get(sort_by, AIChatSession.updated_at)
    order_col = sort_column.desc() if sort_order.lower() == "desc" else sort_column.asc()

    rows = (
        q.order_by(AIChatSession.is_pinned.desc(), order_col)
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


@router.delete("/ai/sessions/{session_id}")
def internal_delete_session(
    session_id: str,
    family_id: str = Depends(verify_agent_token),
    db: Session = Depends(get_db),
):
    """Delete a session row (agent-facing). Checkpointer cleanup is the caller's responsibility."""
    from apps.backend.app.models.ai_chat_session import AIChatSession

    row = db.query(AIChatSession).filter(AIChatSession.id == session_id).first()
    if row is None or row.family_id != int(family_id):
        raise AppError(ErrorCode.NOT_FOUND)
    db.delete(row)
    db.commit()
    return {"ok": True}


@router.get("/prompts/{family_id_path}/chat")
def internal_get_chat_prompt(
    family_id_path: str,
    family_id: str = Depends(verify_agent_token),
):
    """Return family's custom chat system prompt (or null if not set)."""
    if family_id_path != str(family_id):
        raise AppError(ErrorCode.FORBIDDEN, "family_id mismatch")
    from apps.backend.app.services import workspace
    content = workspace.get_chat_prompt(family_id)
    return {"content": content}


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
