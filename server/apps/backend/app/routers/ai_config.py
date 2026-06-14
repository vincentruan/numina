"""AI 配置管理路由。"""

import json
import logging
from datetime import UTC, datetime

import httpx
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from apps.backend.app.auth.ai_deps import require_owner
from apps.backend.app.auth.deps import require_adult
from apps.backend.app.config import settings
from apps.backend.app.database import get_db
from apps.backend.app.errors import AppError, ErrorCode
from apps.backend.app.models.ai_provider_config import (
    AIProviderConfig,
    AIProviderTestResult,
)
from apps.backend.app.models.family_mcp_server import FamilyMCPServer
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
from apps.backend.app.services.ai_crypto import (
    decrypt_api_key,
    encrypt_api_key,
    mask_api_key,
)
from apps.backend.app.services.security_log import _log_security_event

router = APIRouter(prefix="/ai", tags=["ai-config"])

logger = logging.getLogger(__name__)


def _deserialize_capabilities(cap_str: str | None) -> list[str]:
    """Deserialize JSON capability string to list."""
    if not cap_str:
        return []
    try:
        return json.loads(cap_str)
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

    return _cfg_to_response(cfg, [], None)


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
    return {"ok": True}


@router.post("/config/{config_id}/test", response_model=AIConfigTestResult)
async def test_ai_config(
    config_id: int,
    current_user: User = Depends(require_owner),
    db: Session = Depends(get_db),
) -> AIConfigTestResult:
    """测试指定 AI 配置的连通性和模型能力（仅 owner）。"""
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
        return AIConfigTestResult(connected=False, message="未配置 API Key")

    api_key = decrypt_api_key(cfg.api_key_encrypted)
    if not api_key:
        return AIConfigTestResult(
            connected=False, message="API Key 解密失败，请重新配置"
        )

    api_key = api_key.strip()
    if not cfg.model_id:
        return AIConfigTestResult(connected=False, message="未配置主模型 ID")

    async with httpx.AsyncClient(timeout=300.0) as client:
        try:
            resp = await client.post(
                f"{settings.AGENT_BASE_URL}/test/model",
                headers={
                    "X-Agent-Token": settings.AGENT_INTERNAL_TOKEN,
                    "Content-Type": "application/json",
                },
                json={
                    "provider": cfg.provider,
                    "api_key": api_key,
                    "model_id": cfg.model_id,
                    "base_url": cfg.base_url,
                    "vision_model_id": cfg.vision_model_id,
                    "test_types": ["connection", "thinking", "vision", "vision_ocr"],
                },
            )
            resp.raise_for_status()
            data = resp.json()
        except httpx.HTTPStatusError as e:
            return AIConfigTestResult(
                connected=False,
                message=f"Agent 服务返回错误: HTTP {e.response.status_code}",
            )
        except Exception:
            logger.exception("agent model-test call failed")
            return AIConfigTestResult(
                connected=False, message="无法连接 Agent 服务，请检查 Agent 服务状态"
            )

    def _upsert_test(
        test_type: str, success: bool | None, message: str, latency_ms: int | None
    ) -> None:
        existing = (
            db.query(AIProviderTestResult)
            .filter_by(config_id=cfg.id, test_type=test_type)
            .first()
        )
        if existing:
            existing.success = success
            existing.message = message
            existing.latency_ms = latency_ms
            existing.tested_at = datetime.now(UTC).replace(tzinfo=None)
        else:
            db.add(
                AIProviderTestResult(
                    config_id=cfg.id,
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
    db.commit()

    return AIConfigTestResult(
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
    - subagent_enabled: Whether family has MCP/skill subagent capability
    - websearch_enabled: Whether family has web search provider configured
    """
    # Query active AI providers for the family
    configs = (
        db.query(AIProviderConfig)
        .filter(
            AIProviderConfig.family_id == current_user.family_id,
            AIProviderConfig.is_active == True,  # noqa: E712
            AIProviderConfig.api_key_encrypted.isnot(None),
            AIProviderConfig.circuit_state != "open",
        )
        .order_by(AIProviderConfig.display_order.asc().nulls_last())
        .all()
    )

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
            supports_thinking = "thinking" in capabilities or cfg.thinking_supported
            supports_vision = "vision" in capabilities or bool(cfg.vision_model_id)
            supports_tool_calling = "tool_calling" in capabilities  # Default True if not specified

            # Build display name from model_id
            # E.g., "claude-sonnet-4-20250514" -> "Claude Sonnet 4"
            display_name = _model_id_to_display_name(model_id, cfg.provider_name or cfg.provider)

            models.append(ModelInfo(
                name=model_id,
                display_name=display_name,
                provider=cfg.provider,
                provider_name=cfg.provider_name or cfg.provider.capitalize(),
                supports_thinking=supports_thinking,
                supports_vision=supports_vision,
                supports_tool_calling=supports_tool_calling if supports_tool_calling else True,
                is_default=is_default and len([m for m in models if m.is_default]) == 0,  # Only first primary is default
                config_id=str(cfg.id),
            ))

    # Check tenant-level feature flags
    family_id_int = int(current_user.family_id)

    # Subagent capability: MCP servers or skills enabled
    subagent_enabled = (
        db.query(FamilyMCPServer)
        .filter(
            FamilyMCPServer.family_id == family_id_int,
            FamilyMCPServer.is_enabled == True,  # noqa: E712
        )
        .count() > 0
    )

    # Web search capability
    websearch_enabled = (
        db.query(FamilyWebSearchProvider)
        .filter(
            FamilyWebSearchProvider.family_id == family_id_int,
            FamilyWebSearchProvider.is_enabled == True,  # noqa: E712
        )
        .count() > 0
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
