"""Orchestrator — central dispatch pipeline for all agent capabilities.

Pipeline per request:
  1. PolicyGuard.check()          — enforce admin switches
  2. BackendClient.fetch_context() — pull family data
  3. PIIRedactor.redact()          — strip PII before any LLM call
  4. DeerFlowAdapter.dispatch()    — mandatory execution path
  5. AuditLogger.log_call()        — structured audit entry

DeerFlow failures are surfaced to the caller as structured error responses.
There is no silent fallback to a direct LLM path.
"""

import asyncio
import logging
import random
import time
import uuid
from collections.abc import AsyncGenerator

from apps.agent.app.config import settings
from apps.agent.core.backend_client import BackendClient
from apps.agent.schemas.context import FamilyContext
from apps.agent.schemas.policy import CapabilityPolicy
from apps.agent.schemas.response import AgentResponse
from apps.agent.services.audit_logger import AuditEntry, audit_logger
from apps.agent.services.chat_adapter import ChatAdapter
from apps.agent.services.deerflow_adapter.adapter import (
    DeerFlowTimeoutError,
    StreamChunk,
)
from apps.agent.services.deerflow_adapter.adapter import (
    create_family_adapter as _create_family_adapter,
)
from apps.agent.services.deerflow_adapter.skill_loader import skill_loader
from apps.agent.services.output_mapper import output_mapper
from apps.agent.services.pii_redactor import pii_redactor
from apps.agent.services.policy_guard import policy_guard

logger = logging.getLogger(__name__)


def _select_model(providers: list[dict], task_type: str) -> tuple[dict, str, list[str]]:
    """基于任务类型从 providers 列表中选择合适的模型。

    Args:
        providers: 供应商列表（已按优先级排序、已过滤熔断），每个包含 config_id 和 3 个模型槽位
        task_type: 任务类型 ("thinking" / "vision" / "text")

    Returns:
        (selected_provider_dict, model_id, selected_capabilities) — 返回完整 provider dict、
        选中的 model_id，以及选中槽位的 capabilities 列表（用于 thinking 能力判断）

    Raises:
        ValueError: providers 列表为空
    """
    if not providers:
        raise ValueError("providers list is empty — no available AI provider")

    required_capability: str
    if task_type == "thinking":
        required_capability = "deep_thinking"
    elif task_type == "vision":
        required_capability = "vision_understanding"
    else:
        required_capability = "text_generation"

    # 遍历 providers，检查每个槽位
    for provider in providers:
        # 检查槽位1 (model_id / ai_model_id)
        caps_1: list[str] = provider.get("model_1_capabilities", [])
        if required_capability in caps_1 and provider.get("ai_model_id"):
            return provider, provider["ai_model_id"], caps_1

        # 检查槽位2 (model_2_id)
        caps_2: list[str] = provider.get("model_2_capabilities", [])
        if required_capability in caps_2 and provider.get("model_2_id"):
            return provider, provider["model_2_id"], caps_2

        # 检查槽位3 (model_3_id)
        caps_3: list[str] = provider.get("model_3_capabilities", [])
        if required_capability in caps_3 and provider.get("model_3_id"):
            return provider, provider["model_3_id"], caps_3

    # Fallback: 无匹配能力时返回第一个 provider 的槽位1
    first_provider = providers[0]
    fallback_model_id = first_provider.get("ai_model_id", "")
    fallback_caps: list[str] = first_provider.get("model_1_capabilities", [])
    logger.warning(
        "[orchestrator] _select_model: no provider with capability '%s', fallback to model='%s'",
        required_capability,
        fallback_model_id,
    )
    return first_provider, fallback_model_id, fallback_caps


def _is_transient_error(error_type: str) -> bool:
    """Check if error type is transient (can cascade to next provider)."""
    return error_type.startswith("transient_") or error_type in (
        "DeerFlowTimeoutError",
        "ConnectionError",
        "TimeoutError",
    )


def _should_route_to_half_open() -> bool:
    """Decide whether to route traffic to a half-open provider (10% chance).

    Callers must filter providers to those with circuit_state == 'half_open'
    before invoking this function.
    """
    return random.random() < 0.1


def _select_provider_with_retry(
    providers: list[dict],
    task_type: str,
    attempted_config_ids: set[str],
) -> tuple[dict, str, list[str]] | None:
    """Select next provider for retry, considering half-open routing.

    Args:
        providers: List of providers sorted by display_order
        task_type: Model task type (thinking/vision/text)
        attempted_config_ids: Set of config_ids already tried

    Returns:
        (provider, model_id, capabilities) when a provider with the required
        capability is found, otherwise None. Returns None rather than falling
        back to a capability-mismatched provider, so the caller fails cleanly
        instead of silently degrading the task.
    """
    required_capability: str
    if task_type == "thinking":
        required_capability = "deep_thinking"
    elif task_type == "vision":
        required_capability = "vision_understanding"
    else:
        required_capability = "text_generation"

    # Filter providers not yet attempted
    available_providers = [
        p for p in providers if p.get("config_id") not in attempted_config_ids
    ]

    if not available_providers:
        return None

    # Prefer half_open providers for recovery testing (10% chance)
    half_open_providers = [
        p for p in available_providers if p.get("circuit_state") == "half_open"
    ]
    if half_open_providers and _should_route_to_half_open():
        # Use half_open provider for 10% traffic
        for provider in half_open_providers:
            caps = provider.get("model_1_capabilities", [])
            if required_capability in caps and provider.get("ai_model_id"):
                return provider, provider["ai_model_id"], caps

    # Normal selection: check each provider's capabilities
    for provider in available_providers:
        # Skip providers with permanent circuit state
        circuit_state = provider.get("circuit_state", "closed")
        if circuit_state == "open":
            # Open provider should not be in list, but check anyway
            continue

        caps_1 = provider.get("model_1_capabilities", [])
        if required_capability in caps_1 and provider.get("ai_model_id"):
            return provider, provider["ai_model_id"], caps_1

        caps_2 = provider.get("model_2_capabilities", [])
        if required_capability in caps_2 and provider.get("model_2_id"):
            return provider, provider["model_2_id"], caps_2

        caps_3 = provider.get("model_3_capabilities", [])
        if required_capability in caps_3 and provider.get("model_3_id"):
            return provider, provider["model_3_id"], caps_3

    # No provider with required capability — fail cleanly so caller can return
    # an error message rather than silently degrading to a mismatched provider.
    return None


def _fire_and_forget(coro: "asyncio.Coroutine") -> None:  # type: ignore[type-arg]
    """Schedule a coroutine as a fire-and-forget task."""
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        return
    task = loop.create_task(coro)
    task.add_done_callback(
        lambda t: t.exception() and logger.warning("fire-and-forget task failed: %s", t.exception())
    )


# Module-level adapter factory — exposed for patching in tests
_deerflow_adapter = None


class Orchestrator:
    """Routes a capability request through the full dispatch pipeline."""

    def __init__(self) -> None:
        self._chat_adapter = ChatAdapter(
            backend_base_url=settings.BACKEND_BASE_URL,
            internal_token=settings.AGENT_INTERNAL_TOKEN,
        )

    async def dispatch(
        self,
        capability: str,
        family_id: str,
        user_id: str | None = None,
        free_text: str | None = None,
        thread_id: str | None = None,
    ) -> AgentResponse:
        """Run the full pipeline. Never raises — always returns AgentResponse."""
        audit_id = str(uuid.uuid4())
        effective_thread_id = thread_id if thread_id is not None else audit_id
        start_ms = int(time.monotonic() * 1000)
        error_type: str | None = None
        deerflow_attempted = False
        response: AgentResponse | None = None

        try:
            # ── 1. Fetch AI config & build policy ──────────────────────────
            client = BackendClient(family_id=family_id)
            try:
                ai_config = await client.get_family_ai_config()
            except Exception as e:
                logger.error("[orchestrator] fetch ai_config failed family=%s: %s", family_id, e)
                error_type = type(e).__name__
                return self._error_response(capability, audit_id, "无法获取 AI 配置，请稍后重试")

            policy = CapabilityPolicy(
                ai_enabled=ai_config.get("ai_enabled", False),
                allowed_capabilities=ai_config.get("allowed_capabilities", []),
                admin_only_capabilities=ai_config.get("admin_only_capabilities", []),
                member_role=ai_config.get("member_role", "member"),
            )

            # ── 2. Policy check ────────────────────────────────────────────
            decision = policy_guard.check(policy, capability)
            if not decision.allowed:
                error_type = "PolicyDenied"
                return AgentResponse(
                    capability=capability,
                    summary=decision.reason,
                    fallback_used=False,
                    audit_id=audit_id,
                )

            # ── 3. Fetch family context ────────────────────────────────────
            if capability == "suggest":
                raw_context = FamilyContext(family_id=family_id, free_text=free_text)
            else:
                raw_context = await self._build_context(client, family_id, free_text)

            # ── 4. PII redaction ───────────────────────────────────────────
            redacted = pii_redactor.redact(raw_context)

            # ── 5. DeerFlow dispatch ───────────────────────────────────────
            deerflow_attempted = True
            try:
                providers = ai_config.get("providers", [])
                if not providers:
                    raise ValueError("No AI providers configured for this family")
                selected_provider, _, _ = _select_model(providers, "text")
                family_adapter = _deerflow_adapter or _create_family_adapter(
                    family_id, selected_provider, timeout_seconds=max(selected_provider.get("timeout_seconds", 60), 240)
                )
                raw_output = await family_adapter.dispatch(
                    skill_name=capability,
                    context=redacted,
                    thread_id=effective_thread_id,
                )
                response = output_mapper.from_deerflow(raw_output, capability, audit_id)
            except Exception as e:
                logger.error("[orchestrator] DeerFlow failed capability=%s: %s", capability, e)
                error_type = type(e).__name__
                response = self._error_response(capability, audit_id, "AI 服务暂时不可用，请稍后重试")

        except Exception as e:
            logger.error("[orchestrator] unhandled error capability=%s: %s", capability, e)
            error_type = type(e).__name__
            response = self._error_response(capability, audit_id)

        finally:
            duration_ms = int(time.monotonic() * 1000) - start_ms
            if response is None:
                response = self._error_response(capability, audit_id)
            raw_summary = response.summary[:200] if response.summary else None
            if raw_summary:
                raw_summary = pii_redactor.redact_text(raw_summary)[0]
            audit_logger.log_call(AuditEntry(
                family_id=family_id,
                capability=capability,
                success=error_type is None,
                audit_id=audit_id,
                user_id=user_id,
                skill_triggered=capability if error_type is None else None,
                fallback_used=False,
                deerflow_attempted=deerflow_attempted,
                duration_ms=duration_ms,
                error_type=error_type,
                output_summary=raw_summary,
            ))

        return response

orchestrator = Orchestrator()
