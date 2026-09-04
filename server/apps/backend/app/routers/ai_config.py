"""AI 配置管理路由。"""

import json
import logging
import threading
from datetime import UTC, datetime

import httpx
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from apps.backend.app.auth.deps import require_adult, require_owner
from apps.backend.app.config import settings
from apps.backend.app.database import get_db
from apps.backend.app.errors import AppError, ErrorCode
from apps.backend.app.models.ai_provider_config import (
    AIProviderConfig,
    AIProviderTestResult,
)
from apps.backend.app.models.family_web_search_provider import FamilyWebSearchProvider
from apps.backend.app.models.user import User
from apps.backend.app.schemas.ai_config import (
    AICircuitResetResponse,
    AIConfigCreate,
    AIConfigListResponse,
    AIConfigResponse,
    AIConfigTestResult,
    AIConfigUpdate,
    AIProviderTestResultResponse,
    ModelInfo,
    ModelListResponse,
)
from apps.backend.app.services.agent_client import AgentClient
from apps.backend.app.services.ai_crypto import (
    decrypt_api_key,
    encrypt_api_key,
    mask_api_key,
)
from apps.backend.app.services.circuit_breaker.adapters.ai_provider import (
    AIProviderAdapter,
)
from apps.backend.app.services.security_log import _log_security_event

router = APIRouter(prefix="/ai", tags=["ai-config"])

logger = logging.getLogger(__name__)


def _invalidate_agent_cache(family_id: int) -> None:
    """Notify the agent to invalidate its DeerFlowClient cache for this family.

    Provider config changes (create/update/delete/reorder) bake model_id,
    api_key, and base_url into DeerFlowClient's temp config.yaml at adapter
    creation time. Without invalidation the agent keeps reusing stale cached
    clients indefinitely. This is a best-effort fire-and-forget call — a
    failed invalidation just means the stale cache survives until LRU eviction.

    The call is dispatched in a daemon thread so it never blocks the HTTP
    response, even when the agent is temporarily unreachable.
    """
    family_id_str = str(family_id)
    agent_url = f"{settings.AGENT_BASE_URL.rstrip('/')}/internal/cache/invalidate/{family_id_str}"

    def _call():
        try:
            from packages.security.service_auth.agent_jwt import create_agent_token

            resp = httpx.post(
                agent_url,
                headers={
                    "X-Agent-Token": create_agent_token(family_id_str),
                    "Content-Type": "application/json",
                },
                timeout=5.0,
            )
            if resp.status_code != 200:
                logger.warning(
                    "[ai_config] agent cache invalidation returned %s for family=%s",
                    resp.status_code,
                    family_id_str,
                )
        except Exception:
            logger.debug(
                "[ai_config] agent cache invalidation failed for family=%s",
                family_id_str,
                exc_info=True,
            )

    threading.Thread(target=_call, daemon=True).start()


def get_active_configs_with_recovery(
    db: Session,
    family_id: int,
) -> list[AIProviderConfig]:
    """Query active AI providers and attempt circuit-breaker recovery.

    Returns providers that are usable *right now* — i.e. already closed, or
    were open but recovered to half_open/closed after calling
    ``attempt_recovery``.  Providers that remain open (cooldown not expired
    or recovery schedule not matched yet) are filtered out.

    Also evaluates ``half_open`` windows: if the window expired with
    insufficient success rate the provider re-opens and is filtered out.

    Used by ``get_tenant_models``, ``_get_active_providers`` (ai_internal),
    and ``ai_result_parser``.
    """
    configs = (
        db.query(AIProviderConfig)
        .filter(
            AIProviderConfig.family_id == family_id,
            AIProviderConfig.is_active,
            AIProviderConfig.api_key_encrypted.isnot(None),
        )
        .order_by(
            AIProviderConfig.display_order.asc().nulls_last(),
            AIProviderConfig.created_at.asc(),
        )
        .all()
    )

    for cfg in configs:
        adapter = AIProviderAdapter(cfg.id, int(family_id))
        adapter.bind(cfg)
        if cfg.circuit_state == "open":
            adapter.attempt_recovery(db)
        elif cfg.circuit_state == "half_open":
            adapter.evaluate_half_open_window(db)

    return [c for c in configs if c.circuit_state != "open"]


def _deserialize_capabilities(cap_str: str | None) -> list[str]:
    """Deserialize JSON capability string to list."""
    if not cap_str:
        return []
    try:
        return list(json.loads(cap_str))
    except json.JSONDecodeError:
        return []


def _serialize_capabilities(cap_list: list[str] | None) -> str | None:
    """Serialize capability list to JSON string."""
    if not cap_list:
        return None
    return json.dumps(cap_list)


def _cfg_to_response(
    cfg: AIProviderConfig, test_results: list, api_key_masked: str | None
) -> AIConfigResponse:
    return AIConfigResponse(
        id=cfg.id,
        name=cfg.name,
        provider=cfg.provider,
        ai_api_key_masked=api_key_masked,
        base_url=cfg.base_url,
        model_id=cfg.model_id,
        vision_model_id=cfg.vision_model_id,
        timeout_seconds=cfg.timeout_seconds if cfg.timeout_seconds is not None else 60,
        is_active=cfg.is_active,
        max_tokens=cfg.max_tokens,
        provider_name=cfg.provider_name or "",
        display_order=cfg.display_order or 0,
        model_2_id=cfg.model_2_id,
        model_3_id=cfg.model_3_id,
        model_1_capabilities=_deserialize_capabilities(cfg.model_1_capabilities),
        model_2_capabilities=_deserialize_capabilities(cfg.model_2_capabilities),
        model_3_capabilities=_deserialize_capabilities(cfg.model_3_capabilities),
        # Circuit breaker fields (three-state model)
        circuit_state=cfg.circuit_state,
        circuit_reason=cfg.circuit_reason,
        recovery_schedule=cfg.recovery_schedule,
        last_failure_type=cfg.last_failure_type,
        half_open_window_start=cfg.half_open_window_start,
        # Legacy circuit breaker fields
        circuit_open=cfg.circuit_open,
        circuit_open_until=cfg.circuit_open_until,
        failure_count=cfg.failure_count,
        test_results=[
            AIProviderTestResultResponse.model_validate(r) for r in test_results
        ],
    )


@router.get("/config", response_model=AIConfigListResponse)
def get_ai_configs(
    current_user: User = Depends(require_adult),
    db: Session = Depends(get_db),
) -> AIConfigListResponse:
    """获取当前家庭所有 AI 配置（所有成员可查看）。"""
    configs = (
        db.query(AIProviderConfig)
        .filter(AIProviderConfig.family_id == current_user.family_id)
        .order_by(AIProviderConfig.created_at)
        .all()
    )
    result = []
    for cfg in configs:
        test_results = (
            db.query(AIProviderTestResult)
            .filter(AIProviderTestResult.config_id == cfg.id)
            .all()
        )
        api_key_masked = None
        if cfg.api_key_encrypted:
            decrypted = decrypt_api_key(cfg.api_key_encrypted)
            if decrypted:
                api_key_masked = mask_api_key(decrypted)
        result.append(_cfg_to_response(cfg, test_results, api_key_masked))
    return AIConfigListResponse(configs=result)


@router.post("/config", response_model=AIConfigResponse, status_code=201)
def create_ai_config(
    payload: AIConfigCreate,
    current_user: User = Depends(require_owner),
    db: Session = Depends(get_db),
) -> AIConfigResponse:
    """创建新 AI 配置（仅 owner）。is_active 表示该供应商是否启用参与调用。"""
    encrypted = None
    if payload.ai_api_key:
        encrypted = encrypt_api_key(payload.ai_api_key)
        if encrypted is None:
            raise AppError(ErrorCode.AI_SERVICE_UNAVAILABLE)

    # Auto-assign display_order if not provided
    if payload.display_order is None:
        max_order = (
            db.query(AIProviderConfig)
            .filter(AIProviderConfig.family_id == current_user.family_id)
            .count()
        )
    else:
        max_order = payload.display_order

    cfg = AIProviderConfig(
        family_id=current_user.family_id,
        name=payload.name,
        provider=payload.provider,
        api_key_encrypted=encrypted,
        base_url=payload.base_url,
        model_id=payload.model_id,
        vision_model_id=payload.vision_model_id,
        timeout_seconds=payload.timeout_seconds
        if payload.timeout_seconds is not None
        else 60,
        is_active=payload.is_active,
        max_tokens=payload.max_tokens,
        provider_name=payload.provider_name or payload.provider.capitalize(),
        display_order=max_order,
        model_2_id=payload.model_2_id,
        model_3_id=payload.model_3_id,
        model_1_capabilities=_serialize_capabilities(payload.model_1_capabilities),
        model_2_capabilities=_serialize_capabilities(payload.model_2_capabilities),
        model_3_capabilities=_serialize_capabilities(payload.model_3_capabilities),
        recovery_schedule=payload.recovery_schedule,
    )
    db.add(cfg)
    db.commit()
    db.refresh(cfg)

    _log_security_event(
        "ai_config_created",
        user_id=current_user.id,
        family_id=current_user.family_id,
        provider=cfg.provider,
    )

    _invalidate_agent_cache(current_user.family_id)

    return _cfg_to_response(cfg, [], None)


class _ReorderPayload(BaseModel):
    order: list[str]  # IDs serialized as strings (Snowflake)


@router.put("/config/reorder", response_model=dict)
def reorder_ai_configs(
    payload: _ReorderPayload,
    current_user: User = Depends(require_owner),
    db: Session = Depends(get_db),
) -> dict:
    """按给定顺序更新供应商 display_order（仅 owner）。"""
    for idx, config_id_str in enumerate(payload.order):
        config_id = int(config_id_str)  # Snowflake ID (serialized as string)
        db.query(AIProviderConfig).filter(
            AIProviderConfig.id == config_id,
            AIProviderConfig.family_id == current_user.family_id,
        ).update({"display_order": idx})
    db.commit()

    _invalidate_agent_cache(current_user.family_id)

    return {"ok": True}


@router.put("/config/{config_id}", response_model=AIConfigResponse)
def update_ai_config(
    config_id: int,
    payload: AIConfigUpdate,
    current_user: User = Depends(require_owner),
    db: Session = Depends(get_db),
) -> AIConfigResponse:
    """更新 AI 配置（仅 owner）。is_active 表示该供应商是否启用参与调用。"""
    cfg = (
        db.query(AIProviderConfig)
        .filter(
            AIProviderConfig.id == config_id,
            AIProviderConfig.family_id == current_user.family_id,
        )
        .first()
    )
    if not cfg:
        raise AppError(ErrorCode.FAMILY_NOT_FOUND)

    if payload.name is not None:
        cfg.name = payload.name
    if payload.provider is not None:
        cfg.provider = payload.provider
    if payload.base_url is not None:
        cfg.base_url = payload.base_url
    if payload.model_id is not None:
        cfg.model_id = payload.model_id
    if payload.vision_model_id is not None:
        cfg.vision_model_id = payload.vision_model_id
    if payload.timeout_seconds is not None:
        cfg.timeout_seconds = payload.timeout_seconds
    if payload.is_active is not None:
        cfg.is_active = payload.is_active
    # max_tokens: 0/None means "use server default (yaml prefix)"; positive int → explicit override.
    # We treat None as "field not in payload" (don't touch); to clear, client should send 0.
    if payload.max_tokens is not None:
        cfg.max_tokens = payload.max_tokens if payload.max_tokens > 0 else None
    if payload.ai_api_key is not None:
        if payload.ai_api_key == "":
            cfg.api_key_encrypted = None
        else:
            encrypted = encrypt_api_key(payload.ai_api_key)
            if encrypted is None:
                raise AppError(ErrorCode.AI_SERVICE_UNAVAILABLE)
            cfg.api_key_encrypted = encrypted
        # 清空测试结果（API Key 变更后需重新测试）
        db.query(AIProviderTestResult).filter_by(config_id=cfg.id).delete()
    if payload.provider_name is not None:
        cfg.provider_name = payload.provider_name
    if payload.display_order is not None:
        cfg.display_order = payload.display_order
    if payload.model_2_id is not None:
        cfg.model_2_id = payload.model_2_id
    if payload.model_3_id is not None:
        cfg.model_3_id = payload.model_3_id
    if payload.model_1_capabilities is not None:
        cfg.model_1_capabilities = _serialize_capabilities(payload.model_1_capabilities)
    if payload.model_2_capabilities is not None:
        cfg.model_2_capabilities = _serialize_capabilities(payload.model_2_capabilities)
    if payload.model_3_capabilities is not None:
        cfg.model_3_capabilities = _serialize_capabilities(payload.model_3_capabilities)
    if payload.recovery_schedule is not None:
        cfg.recovery_schedule = payload.recovery_schedule

    db.commit()
    db.refresh(cfg)

    _log_security_event(
        "ai_config_updated",
        user_id=current_user.id,
        family_id=current_user.family_id,
        provider=cfg.provider,
    )

    _invalidate_agent_cache(current_user.family_id)

    test_results = db.query(AIProviderTestResult).filter_by(config_id=cfg.id).all()
    api_key_masked = None
    if cfg.api_key_encrypted:
        decrypted = decrypt_api_key(cfg.api_key_encrypted)
        if decrypted:
            api_key_masked = mask_api_key(decrypted)

    return _cfg_to_response(cfg, test_results, api_key_masked)


@router.get("/config/{config_id}/reveal-key")
def reveal_ai_config_key(
    config_id: int,
    current_user: User = Depends(require_owner),
    db: Session = Depends(get_db),
) -> dict:
    """返回 AI 配置的明文 API Key（仅 owner）。"""
    cfg = (
        db.query(AIProviderConfig)
        .filter(
            AIProviderConfig.id == config_id,
            AIProviderConfig.family_id == current_user.family_id,
        )
        .first()
    )
    if not cfg:
        raise AppError(ErrorCode.FAMILY_NOT_FOUND)
    if not cfg.api_key_encrypted:
        raise AppError(ErrorCode.AI_SERVICE_UNAVAILABLE)
    decrypted = decrypt_api_key(cfg.api_key_encrypted)
    if not decrypted:
        raise AppError(ErrorCode.AI_SERVICE_UNAVAILABLE)

    _log_security_event(
        "ai_key_revealed",
        user_id=current_user.id,
        family_id=current_user.family_id,
        provider=cfg.provider,
    )

    return {"api_key": decrypted}


@router.delete("/config/{config_id}", status_code=204)
def delete_ai_config(
    config_id: int,
    current_user: User = Depends(require_owner),
    db: Session = Depends(get_db),
) -> None:
    """删除 AI 配置（仅 owner）。"""
    cfg = (
        db.query(AIProviderConfig)
        .filter(
            AIProviderConfig.id == config_id,
            AIProviderConfig.family_id == current_user.family_id,
        )
        .first()
    )
    if not cfg:
        raise AppError(ErrorCode.FAMILY_NOT_FOUND)

    db.query(AIProviderTestResult).filter_by(config_id=cfg.id).delete()
    db.delete(cfg)
    db.commit()

    _invalidate_agent_cache(current_user.family_id)


@router.post("/config/{config_id}/reset-circuit", response_model=AICircuitResetResponse)
def reset_circuit_breaker(
    config_id: int,
    current_user: User = Depends(require_owner),
    db: Session = Depends(get_db),
) -> AICircuitResetResponse:
    """手动重置供应商熔断状态（仅 owner）。"""
    cfg = (
        db.query(AIProviderConfig)
        .filter(
            AIProviderConfig.id == config_id,
            AIProviderConfig.family_id == current_user.family_id,
        )
        .first()
    )
    if not cfg:
        raise AppError(ErrorCode.FAMILY_NOT_FOUND)

    # Clear all circuit breaker state (three-state model)
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
    return AICircuitResetResponse(ok=True)


# ── Model fallback helpers for test_ai_config ────────────────────────────────


def _is_transient_test_error(message: str) -> bool:
    """Detect transient errors (429 rate limit, 5xx server, timeout) that warrant fallback."""
    msg_lower = message.lower()
    if "429" in message:
        return True
    if "502" in message or "503" in message or "504" in message:
        return True
    if "throttl" in msg_lower or "quota" in msg_lower or "rate limit" in msg_lower:
        return True
    return "timeout" in msg_lower or "timed out" in msg_lower


def _parse_caps(raw: str | None) -> list[str]:
    """Parse capabilities JSON string from DB column to list."""
    if not raw:
        return []
    try:
        val = json.loads(raw)
        return val if isinstance(val, list) else []
    except (json.JSONDecodeError, TypeError):
        return []


def _build_target_only_candidates(target_cfg: AIProviderConfig, api_key: str) -> list[dict]:
    """Build test candidates from the target config ONLY, ignoring circuit state.

    The model test is meant to verify whether a specific provider/model works.
    Circuit breaker state must not prevent testing — the user explicitly chose
    this provider to test.

    Priority: slots 1→2→3, then vision fallback.
    """
    cfg_name = target_cfg.provider_name or target_cfg.name or "Unknown"
    caps_1 = _parse_caps(target_cfg.model_1_capabilities)
    caps_2 = _parse_caps(target_cfg.model_2_capabilities)

    candidates: list[dict] = []
    seen: set[tuple[int, str]] = set()

    # Slot 1: primary model
    if target_cfg.model_id:
        key = (target_cfg.id, target_cfg.model_id)
        if key not in seen:
            seen.add(key)
            candidates.append({
                "config": target_cfg,
                "model_id": target_cfg.model_id,
                "vision_model_id": target_cfg.vision_model_id or target_cfg.model_id,
                "slot": 1,
                "api_key": api_key,
                "display_label": f"{cfg_name} ({target_cfg.model_id})",
                "has_vision_cap": "vision_understanding" in caps_1,
            })

    # Slot 2: alternate model (only if different from slot 1)
    if target_cfg.model_2_id and target_cfg.model_2_id != target_cfg.model_id:
        key = (target_cfg.id, target_cfg.model_2_id)
        if key not in seen:
            seen.add(key)
            candidates.append({
                "config": target_cfg,
                "model_id": target_cfg.model_2_id,
                "vision_model_id": target_cfg.vision_model_id or target_cfg.model_2_id,
                "slot": 2,
                "api_key": api_key,
                "display_label": f"{cfg_name} ({target_cfg.model_2_id})",
                "has_vision_cap": "vision_understanding" in caps_2,
            })

    # Slot 3: third model (only if different from slot 1 & 2)
    if target_cfg.model_3_id and target_cfg.model_3_id not in (
        target_cfg.model_id,
        target_cfg.model_2_id,
    ):
        key = (target_cfg.id, target_cfg.model_3_id)
        if key not in seen:
            seen.add(key)
            candidates.append({
                "config": target_cfg,
                "model_id": target_cfg.model_3_id,
                "vision_model_id": target_cfg.vision_model_id or target_cfg.model_3_id,
                "slot": 3,
                "api_key": api_key,
                "display_label": f"{cfg_name} ({target_cfg.model_3_id})",
                "has_vision_cap": "vision_understanding" in _parse_caps(target_cfg.model_3_capabilities),
            })

    # Vision fallback: vision_model_id if different from slot 1 model
    if (
        target_cfg.vision_model_id
        and target_cfg.vision_model_id != target_cfg.model_id
        and target_cfg.vision_model_id != target_cfg.model_2_id
    ):
        key = (target_cfg.id, target_cfg.vision_model_id)
        if key not in seen:
            seen.add(key)
            candidates.append({
                "config": target_cfg,
                "model_id": target_cfg.vision_model_id,
                "vision_model_id": target_cfg.vision_model_id,
                "slot": "vision",
                "api_key": api_key,
                "display_label": f"{cfg_name} vision ({target_cfg.vision_model_id})",
                "has_vision_cap": True,
            })

    return candidates


def _reset_circuit_state(cfg: AIProviderConfig) -> None:
    """Reset circuit breaker state on a config (in-place, caller commits)."""
    cfg.circuit_state = "closed"
    cfg.circuit_reason = None
    cfg.failure_count = 0
    cfg.circuit_open = False
    cfg.circuit_open_until = None
    cfg.last_failure_type = None
    cfg.half_open_success_count = 0
    cfg.half_open_failure_count = 0
    cfg.half_open_window_start = None


def _call_agent_model_test(
    agent_client: AgentClient, candidate: dict, test_types: list[str]
) -> dict:
    """Call agent's /test/model with a single candidate. Returns the JSON response dict."""
    # For vision-only slot, only run vision tests
    actual_test_types = test_types
    if candidate["slot"] == "vision":
        actual_test_types = [t for t in test_types if t in ("vision", "vision_ocr")]
        if not actual_test_types:
            actual_test_types = ["vision"]

    return {
        "provider": candidate["config"].provider,
        "api_key": candidate["api_key"],
        "model_id": candidate["model_id"],
        "base_url": candidate["config"].base_url,
        "vision_model_id": candidate["vision_model_id"],
        "test_types": actual_test_types,
    }


@router.post("/config/{config_id}/test", response_model=AIConfigTestResult)
async def test_ai_config(
    config_id: int,
    current_user: User = Depends(require_owner),
    db: Session = Depends(get_db),
) -> AIConfigTestResult:
    """测试 AI 配置的连通性和模型能力（仅 owner）。

    直接测试用户指定的供应商配置，不受熔断状态影响。
    当同一供应商有多个模型槽位时，支持槽位间 fallback（瞬时错误时尝试下一个槽位）。
    测试成功后自动重置熔断状态（视为已恢复）。
    """
    # Validate target config exists and belongs to this family
    target_cfg = (
        db.query(AIProviderConfig)
        .filter(
            AIProviderConfig.id == config_id,
            AIProviderConfig.family_id == current_user.family_id,
        )
        .first()
    )
    if not target_cfg:
        raise AppError(ErrorCode.FAMILY_NOT_FOUND)

    if not target_cfg.api_key_encrypted:
        return AIConfigTestResult(
            connected=False, message="", error_code="noApiKey"
        )

    target_api_key = decrypt_api_key(target_cfg.api_key_encrypted)
    if not target_api_key:
        return AIConfigTestResult(
            connected=False, message="", error_code="decryptFailed"
        )

    target_api_key = target_api_key.strip()
    if not target_cfg.model_id:
        return AIConfigTestResult(
            connected=False, message="", error_code="noModelId"
        )

    agent_client = AgentClient(current_user.family_id, current_user.id, timeout=300.0)

    # Build candidates from target config ONLY — bypass circuit state.
    # The test is meant to verify whether this specific provider/model works;
    # circuit breaker state must not prevent testing.
    candidates = _build_target_only_candidates(target_cfg, target_api_key)

    if not candidates:
        return AIConfigTestResult(
            connected=False, message="", error_code="noCandidates"
        )

    test_types = ["connection", "thinking", "vision", "vision_ocr"]
    last_result: dict | None = None
    last_failure_msg: str = ""
    fallback_count = 0

    for idx, candidate in enumerate(candidates):
        try:
            payload = _call_agent_model_test(agent_client, candidate, test_types)
            resp = await agent_client.post(
                "/test/model",
                headers={"Content-Type": "application/json"},
                json=payload,
            )
            resp.raise_for_status()
            data = resp.json()
        except httpx.HTTPStatusError as e:
            last_result = None
            last_failure_msg = f"Agent 服务返回错误: HTTP {e.response.status_code}"
            if idx < len(candidates) - 1:
                fallback_count += 1
            continue
        except Exception:
            logger.exception("agent model-test call failed")
            last_result = None
            last_failure_msg = "无法连接 Agent 服务，请检查 Agent 服务状态"
            break  # Agent unreachable, no point trying more candidates

        # Check if connection succeeded
        if data.get("connected", False):
            # Connection OK — store results and reset circuit breaker.
            # A successful manual test proves the provider has recovered.
            used_cfg = candidate["config"]
            _upsert_test_results(db, used_cfg.id, data)
            circuit_was_open = used_cfg.circuit_state != "closed"
            if circuit_was_open:
                _reset_circuit_state(used_cfg)
            db.commit()

            if circuit_was_open:
                _invalidate_agent_cache(current_user.family_id)

            result = AIConfigTestResult(
                connected=data.get("connected", False),
                message=data.get("message", "测试完成"),
                latency_ms=data.get("latency_ms"),
                thinking_success=data.get("thinking_success"),
                thinking_message=data.get("thinking_message"),
                thinking_latency_ms=data.get("thinking_latency_ms"),
                vision_success=data.get("vision_success"),
                vision_message=data.get("vision_message"),
                vision_latency_ms=data.get("vision_latency_ms"),
                vision_text_success=data.get("vision_text_success"),
                vision_text_message=data.get("vision_text_message"),
                vision_text_latency_ms=data.get("vision_text_latency_ms"),
                used_config_id=str(used_cfg.id),
                used_provider_name=used_cfg.provider_name or used_cfg.name,
                used_model_id=candidate["model_id"],
                used_circuit_state=used_cfg.circuit_state,
                fallback_count=fallback_count,
            )

            # Annotate message if fallback was used
            if fallback_count > 0:
                result.message = (
                    f"主模型不可用，已自动切换至 {candidate['display_label']}"
                )

            return result

        # Connection failed — check if transient → try next candidate
        msg = data.get("message", "")
        if _is_transient_test_error(msg) and idx < len(candidates) - 1:
            last_failure_msg = msg
            fallback_count += 1
            logger.info(
                "[test_ai_config] transient error on model=%s config_id=%s, "
                "falling back (attempt %d): %s",
                candidate["model_id"],
                candidate["config"].id,
                fallback_count,
                msg,
            )
            continue

        # Permanent error — stop fallback, record and return
        _upsert_test_results(db, candidate["config"].id, data)
        db.commit()
        return AIConfigTestResult(
            connected=False,
            message=msg,
            latency_ms=data.get("latency_ms"),
            error_detail=data.get("error_detail"),
            thinking_success=data.get("thinking_success"),
            thinking_message=data.get("thinking_message"),
            thinking_latency_ms=data.get("thinking_latency_ms"),
            vision_success=data.get("vision_success"),
            vision_message=data.get("vision_message"),
            vision_latency_ms=data.get("vision_latency_ms"),
            vision_text_success=data.get("vision_text_success"),
            vision_text_message=data.get("vision_text_message"),
            vision_text_latency_ms=data.get("vision_text_latency_ms"),
            used_config_id=str(candidate["config"].id),
            used_provider_name=candidate["config"].provider_name or candidate["config"].name,
            used_model_id=candidate["model_id"],
            used_circuit_state=candidate["config"].circuit_state,
            fallback_count=fallback_count,
        )

    # All candidates exhausted (all transient failures)
    # Record last failure against target config
    if last_result is None and last_failure_msg:
        _upsert_test_results(
            db,
            config_id,
            {"connected": False, "message": last_failure_msg},
        )
        db.commit()
        return AIConfigTestResult(
            connected=False,
            message=(
                f"所有 {fallback_count + 1} 个候选模型均不可用: {last_failure_msg}"
            ),
        )

    # Should not reach here, but handle gracefully
    return AIConfigTestResult(connected=False, message="测试异常，请重试")


def _upsert_test_results(db: Session, config_id: int, data: dict) -> None:
    """Store test results against the given config."""

    def _upsert_test(
        test_type: str, success: bool | None, message: str, latency_ms: int | None
    ) -> None:
        existing = (
            db.query(AIProviderTestResult)
            .filter_by(config_id=config_id, test_type=test_type)
            .first()
        )
        if existing:
            existing.success = success
            existing.message = message
            existing.latency_ms = latency_ms
            existing.tested_at = datetime.now(UTC)
        else:
            db.add(
                AIProviderTestResult(
                    config_id=config_id,
                    test_type=test_type,
                    success=success,
                    message=message,
                    latency_ms=latency_ms,
                )
            )

    _upsert_test(
        "main",
        data.get("connected", False),
        data.get("message", ""),
        data.get("latency_ms"),
    )
    if data.get("thinking_success") is not None:
        _upsert_test(
            "thinking",
            data["thinking_success"],
            data.get("thinking_message", ""),
            data.get("thinking_latency_ms"),
        )
    if data.get("vision_success") is not None:
        _upsert_test(
            "vision",
            data["vision_success"],
            data.get("vision_message", ""),
            data.get("vision_latency_ms"),
        )
    if data.get("vision_text_success") is not None:
        _upsert_test(
            "vision_text",
            data["vision_text_success"],
            data.get("vision_text_message", ""),
            data.get("vision_text_latency_ms"),
        )


@router.get("/config/defaults", response_model=dict)
def get_provider_defaults(
    model_id: str,
    current_user: User = Depends(require_adult),
) -> dict:
    """Resolve system-default ``max_tokens`` for a given model_id by prefix match.

    Used by the frontend AI provider form to pre-fill the max_tokens field when
    the user types a model_id. Returns ``{"max_tokens": null}`` if no prefix
    matches; the form should then fall back to placeholder hint text.

    The defaults table is maintained in ``system-config.yaml`` at the project
    root; see ``packages/core/system_config.py``.
    """
    from packages.core.system_config import get_max_tokens_default

    return {"max_tokens": get_max_tokens_default(model_id)}


@router.get("/models", response_model=ModelListResponse)
def get_tenant_models(
    current_user: User = Depends(require_adult),
    db: Session = Depends(get_db),
) -> ModelListResponse:
    """Return tenant-filtered model list for DeerFlow-style execution mode selection.

    Extracts models from active AIProviderConfig records, including:
    - model_id (primary model)
    - model_2_id (secondary model, e.g., reasoning-focused)
    - model_3_id (tertiary model, e.g., vision-focused)

    Each model includes capabilities (thinking, vision, tool_calling) derived
    from the config's capability flags and test results.

    Also returns tenant-level feature flags:
    - subagent_enabled: Always true — ultra mode availability depends on model's reasoning_effort support
    - websearch_enabled: Whether family has web search provider configured
    """
    configs = get_active_configs_with_recovery(db, current_user.family_id)

    models: list[ModelInfo] = []
    seen_model_ids: set[str] = set()  # Dedup across configs

    for cfg in configs:
        # Extract all model IDs from the config
        model_entries = [
            (cfg.model_id, cfg.model_1_capabilities, True),  # Primary is default
            (cfg.model_2_id, cfg.model_2_capabilities, False),
            (cfg.model_3_id, cfg.model_3_capabilities, False),
        ]

        for model_id, capabilities_json, is_default in model_entries:
            if not model_id or model_id in seen_model_ids:
                continue
            seen_model_ids.add(model_id)

            # Parse capabilities
            capabilities = _deserialize_capabilities(capabilities_json)

            # Determine capability flags
            supports_thinking = (
                "deep_thinking" in capabilities or cfg.thinking_supported
            )
            supports_vision = (
                "vision" in capabilities
                or "vision_understanding" in capabilities
                or bool(cfg.vision_model_id)
            )
            supports_tool_calling = (
                "tool_calling" in capabilities
            )  # Default True if not specified

            # Build display name from model_id
            # E.g., "claude-sonnet-4-20250514" -> "Claude Sonnet 4"
            display_name = _model_id_to_display_name(
                model_id, cfg.provider_name or cfg.provider
            )

            models.append(
                ModelInfo(
                    name=model_id,
                    display_name=display_name,
                    provider=cfg.provider,
                    provider_name=cfg.provider_name or cfg.provider.capitalize(),
                    supports_thinking=supports_thinking,
                    supports_vision=supports_vision,
                    supports_tool_calling=supports_tool_calling
                    if supports_tool_calling
                    else True,
                    is_default=is_default
                    and len([m for m in models if m.is_default])
                    == 0,  # Only first primary is default
                    config_id=str(cfg.id),
                )
            )

    # Check tenant-level feature flags
    family_id_int = int(current_user.family_id)

    # Subagent capability: depends on whether any model supports thinking.
    # Ultra mode requires the same model capability as thinking/pro — no
    # separate MCP/skill dependency.
    subagent_enabled = any(m.supports_thinking for m in models)

    # Web search capability
    websearch_enabled = (
        db.query(FamilyWebSearchProvider)
        .filter(
            FamilyWebSearchProvider.family_id == family_id_int,
            FamilyWebSearchProvider.is_enabled,
        )
        .count()
        > 0
    )

    return ModelListResponse(
        models=models,
        subagent_enabled=subagent_enabled,
        websearch_enabled=websearch_enabled,
    )


def _model_id_to_display_name(model_id: str, provider_name: str) -> str:
    """Convert model_id to user-friendly display name.

    E.g., "claude-sonnet-4-20250514" -> "Claude Sonnet 4"
         "gpt-4o-2024-05-13" -> "GPT-4o"
    """
    if not model_id:
        return ""

    # Known model patterns
    if model_id.startswith("claude-"):
        # Claude models: extract version
        parts = model_id.replace("claude-", "").split("-")
        if len(parts) >= 2:
            # e.g., "sonnet-4" or "opus-4"
            return f"Claude {parts[0].capitalize()} {parts[1]}"
        return f"Claude {model_id.replace('claude-', '')}"

    if model_id.startswith("gpt-"):
        # GPT models
        if "gpt-4o" in model_id:
            return "GPT-4o"
        if "gpt-4-turbo" in model_id:
            return "GPT-4 Turbo"
        if "gpt-4" in model_id:
            return "GPT-4"
        if "gpt-3.5" in model_id:
            return "GPT-3.5"
        return model_id

    if model_id.startswith("deepseek-"):
        # DeepSeek models
        if "deepseek-reasoner" in model_id:
            return "DeepSeek Reasoner"
        if "deepseek-chat" in model_id:
            return "DeepSeek Chat"
        return model_id.replace("deepseek-", "DeepSeek ")

    if model_id.startswith("qwen"):
        # Qwen models
        return model_id.replace("qwen", "Qwen")

    # Fallback: use provider name + model_id prefix
    prefix = model_id.split("-")[0] if "-" in model_id else model_id[:10]
    return f"{provider_name} {prefix}" if provider_name else prefix.capitalize()
