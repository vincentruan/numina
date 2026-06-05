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
from apps.agent.core.backend_client import BackendClient, classify_error_type
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
from apps.agent.services.session_journal import session_journal
from apps.agent.services.stream_events import EventStreamBuilder

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

    async def stream_dispatch(
        self,
        capability: str,
        family_id: str,
        task_id: str,
        user_id: str | None = None,
        thread_id: str | None = None,
        free_text: str | None = None,
        enable_thinking_override: bool | None = None,
    ) -> AsyncGenerator[str, None]:
        """流式 dispatch — yield text chunks. Never raises after first yield."""
        audit_id = str(uuid.uuid4())
        effective_thread_id = thread_id if thread_id is not None else audit_id
        start_ms = int(time.monotonic() * 1000)
        error_type: str | None = None
        answer_parts: list[str] = []
        model_name: str | None = None
        user_segment = user_id if user_id else "_shared"
        jsonl_path = f"{settings.SESSIONS_DATA_DIR}/{family_id}/agent/{capability}/{user_segment}/{effective_thread_id}.jsonl"
        session_started = False

        # ── 1. Fetch AI config & build policy ──────────────────────────
        client = BackendClient(family_id=family_id)
        try:
            ai_configs = await client.get_family_ai_configs()
        except Exception as e:
            logger.error("[orchestrator] stream_dispatch fetch ai_configs failed: %s", e)
            yield "暂时无法完成分析，请稍后重试。"
            return

        providers: list[dict] = ai_configs.get("providers", [])
        ai_enabled: bool = ai_configs.get("ai_enabled", False)

        # ── 2. Select model ────────────────────────────────────────────
        selected_provider: dict = {}
        config_id: str = ""
        selected_caps: list[str] = []
        try:
            # Determine task_type for model selection
            if enable_thinking_override:
                task_type = "thinking"
            elif capability == "import_parse":
                task_type = "vision"
            else:
                task_type = "text"
            selected_provider, model_id, selected_caps = _select_model(providers, task_type)
            config_id = selected_provider.get("config_id", "")
        except ValueError as e:
            logger.error("[orchestrator] stream_dispatch _select_model failed: %s", e)
            audit_logger.log_call(
                AuditEntry(
                    audit_id=audit_id,
                    capability=capability,
                    family_id=family_id,
                    user_id=user_id,
                    success=False,
                    deerflow_attempted=False,
                    duration_ms=int(time.monotonic() * 1000) - start_ms,
                    error_type="NoProvider",
                )
            )
            yield "暂时无法完成分析，请稍后重试。"
            return

        if not model_id:
            logger.error("[orchestrator] stream_dispatch: model_id is empty for family=%s", family_id)
            audit_logger.log_call(
                AuditEntry(
                    audit_id=audit_id,
                    capability=capability,
                    family_id=family_id,
                    user_id=user_id,
                    success=False,
                    deerflow_attempted=False,
                    duration_ms=int(time.monotonic() * 1000) - start_ms,
                    error_type="NoModelId",
                )
            )
            yield "暂时无法完成分析，请稍后重试。"
            return

        model_name: str | None = model_id

        policy = CapabilityPolicy(
            ai_enabled=ai_enabled,
            allowed_capabilities=ai_configs.get("allowed_capabilities", []),
            admin_only_capabilities=ai_configs.get("admin_only_capabilities", []),
            member_role=ai_configs.get("member_role", "member"),
        )

        # ── 2. Policy check ────────────────────────────────────────────
        decision = policy_guard.check(policy, capability)
        if not decision.allowed:
            yield decision.reason
            return

        # ── 3. Fetch context ───────────────────────────────────────────
        try:
            context = await self._build_context(client, family_id, free_text=free_text)
            # ── 4. Redact PII ──────────────────────────────────────────────
            redacted_context = pii_redactor.redact(context)
        except Exception as e:
            logger.error("[orchestrator] stream_dispatch pre-dispatch failed: %s", e)
            yield "暂时无法完成分析，请稍后重试。"
            return

        # ── 5. Journal: session start + user message ───────────────────
        session_journal.write_session_start(
            family_id=family_id,
            session_id=effective_thread_id,
            user_id=user_id,
            capability=capability,
            model_name=model_name,
            jsonl_path=jsonl_path,
        )
        session_started = True
        redacted_free_text = redacted_context.free_text or ""
        if redacted_free_text:
            session_journal.write_user_message(
                family_id=family_id,
                session_id=effective_thread_id,
                user_id=user_id,
                content=redacted_free_text,
            )
        _fire_and_forget(self._upsert_session(
            session_id=effective_thread_id,
            family_id=family_id,
            user_id=user_id,
            jsonl_path=jsonl_path,
            model_name=model_name,
        ))

        # ── 6. Load thinking flag ──────────────────────────────────────
        skill_config = skill_loader.load(capability)
        thinking_supported = "deep_thinking" in selected_caps
        enable_thinking = (
            bool(enable_thinking_override) and thinking_supported
            if enable_thinking_override is not None
            else skill_config.thinking and thinking_supported
        )

        # ── 7. DeerFlow stream dispatch with cascade retry ────────────────────────
        attempted_config_ids: set[str] = set()
        max_attempts = len(providers)
        attempt_count = 0

        try:
            while attempt_count < max_attempts and config_id not in attempted_config_ids:
                attempt_count += 1
                attempted_config_ids.add(config_id)

                try:
                    adapter = _create_family_adapter(
                        family_id,
                        selected_provider,
                        timeout_seconds=selected_provider.get("timeout_seconds", 60),
                        subagent_enabled=skill_config.subagent_enabled,
                        plan_mode=skill_config.plan_mode,
                    )
                    async for chunk in adapter.stream_dispatch(
                        capability,
                        redacted_context,
                        effective_thread_id,
                        enable_thinking=enable_thinking,
                    ):
                        text = chunk.content if chunk.type == "text" else None
                        if text:
                            answer_parts.append(text)
                            yield text

                    # Success: reset circuit failure count or report half-open success
                    circuit_state = selected_provider.get("circuit_state", "closed")
                    if circuit_state == "half_open":
                        _fire_and_forget(client.report_half_open_result(config_id, success=True))
                    elif config_id:
                        _fire_and_forget(client.reset_circuit_success(config_id))

                    audit_logger.log_call(
                        AuditEntry(
                            audit_id=audit_id,
                            capability=capability,
                            family_id=family_id,
                            user_id=user_id,
                            success=True,
                            skill_triggered=capability,
                            deerflow_attempted=True,
                            duration_ms=int(time.monotonic() * 1000) - start_ms,
                        )
                    )
                    break  # Success, exit retry loop

                except DeerFlowTimeoutError:
                    logger.warning("[orchestrator] stream_dispatch timeout attempt=%d family=%s", attempt_count, family_id)
                    error_type = "transient_timeout"
                    # Report failure based on circuit state
                    circuit_state = selected_provider.get("circuit_state", "closed")
                    if circuit_state == "half_open":
                        _fire_and_forget(client.report_half_open_result(config_id, success=False))
                    elif config_id:
                        _fire_and_forget(client.report_circuit_event(config_id, 0, error_type=error_type))

                    # Try next provider on transient error
                    next_provider = _select_provider_with_retry(providers, task_type, attempted_config_ids)
                    if next_provider and _is_transient_error(error_type):
                        selected_provider, model_id, selected_caps = next_provider
                        config_id = selected_provider.get("config_id", "")
                        logger.info("[orchestrator] cascade retry attempt=%d config_id=%s", attempt_count + 1, config_id)
                        continue
                    else:
                        yield "AI 响应超时，请稍后重试。"
                        audit_logger.log_call(
                            AuditEntry(
                                audit_id=audit_id,
                                capability=capability,
                                family_id=family_id,
                                user_id=user_id,
                                success=False,
                                deerflow_attempted=True,
                                duration_ms=int(time.monotonic() * 1000) - start_ms,
                                error_type="DeerFlowTimeoutError",
                            )
                        )
                        break

                except Exception as e:
                    logger.error("[orchestrator] stream_dispatch DeerFlow failed attempt=%d: %s", attempt_count, e)
                    error_type = type(e).__name__
                    # Classify error type for circuit reporting
                    classified_error_type = classify_error_type(500, str(e))

                    # Report failure based on circuit state
                    circuit_state = selected_provider.get("circuit_state", "closed")
                    if circuit_state == "half_open":
                        _fire_and_forget(client.report_half_open_result(config_id, success=False))
                    elif config_id:
                        _fire_and_forget(client.report_circuit_event(config_id, 500, error_type=classified_error_type))

                    # Check if permanent error (no cascade)
                    if classified_error_type in ("permanent_auth", "permanent_account"):
                        yield "AI 服务暂时不可用，请稍后重试。"
                        audit_logger.log_call(
                            AuditEntry(
                                audit_id=audit_id,
                                capability=capability,
                                family_id=family_id,
                                user_id=user_id,
                                success=False,
                                deerflow_attempted=True,
                                duration_ms=int(time.monotonic() * 1000) - start_ms,
                                error_type=classified_error_type,
                            )
                        )
                        break

                    # Transient error: cascade to next provider
                    next_provider = _select_provider_with_retry(providers, task_type, attempted_config_ids)
                    if next_provider and _is_transient_error(classified_error_type):
                        selected_provider, model_id, selected_caps = next_provider
                        config_id = selected_provider.get("config_id", "")
                        logger.info("[orchestrator] cascade retry attempt=%d config_id=%s", attempt_count + 1, config_id)
                        continue
                    else:
                        # All providers exhausted
                        yield "AI 服务暂时不可用，请稍后重试。"
                        audit_logger.log_call(
                            AuditEntry(
                                audit_id=audit_id,
                                capability=capability,
                                family_id=family_id,
                                user_id=user_id,
                                success=False,
                                deerflow_attempted=True,
                                duration_ms=int(time.monotonic() * 1000) - start_ms,
                                error_type=error_type,
                            )
                        )
                        break
        finally:
            if session_started:
                duration_ms = int(time.monotonic() * 1000) - start_ms
                final_answer = "".join(answer_parts)
                if final_answer:
                    redacted_answer, _ = pii_redactor.redact_text(final_answer)
                else:
                    redacted_answer = ""
                session_journal.write_assistant_message(
                    family_id=family_id,
                    session_id=effective_thread_id,
                    content=redacted_answer,
                    model_name=model_name,
                )
                session_journal.write_session_end(
                    family_id=family_id,
                    session_id=effective_thread_id,
                    success=error_type is None,
                    duration_ms=duration_ms,
                )
                _fire_and_forget(self._update_session_summary(
                    session_id=effective_thread_id,
                    family_id=family_id,
                    summary=redacted_answer[:200] if redacted_answer else None,
                    model=model_name,
                    status="completed" if error_type is None else "error",
                ))
                # Generate title for new chat sessions (thread_id is None) and
                # always for non-chat capabilities (thread_id is always set by backend).
                should_generate_title = (
                    redacted_free_text
                    and error_type is None
                    and (thread_id is None or capability != "chat")
                )
                if should_generate_title:
                    _fire_and_forget(self._generate_title(
                        session_id=effective_thread_id,
                        family_id=family_id,
                        first_user_message=redacted_free_text,
                        ai_config=selected_provider,
                        capability=capability,
                        user_id=user_id,
                    ))

    async def stream_dispatch_events(
        self,
        capability: str,
        family_id: str,
        task_id: str,
        user_id: str | None = None,
        thread_id: str | None = None,
        free_text: str | None = None,
        enable_thinking_override: bool | None = None,
        web_search: bool = False,
    ) -> AsyncGenerator[str, None]:
        """Stream structured NDJSON events."""
        try:
            async for event_line in self._stream_dispatch_event_lines(
                capability=capability,
                family_id=family_id,
                task_id=task_id,
                user_id=user_id,
                thread_id=thread_id,
                free_text=free_text,
                enable_thinking_override=enable_thinking_override,
                web_search=web_search,
            ):
                yield event_line
        except Exception as e:
            logger.error("[orchestrator] stream_dispatch_events failed: %s", e)
            builder = EventStreamBuilder(capability, task_id)
            yield builder.error("暂时无法完成分析，请稍后重试。").to_ndjson()

    async def _stream_dispatch_event_lines(
        self,
        capability: str,
        family_id: str,
        task_id: str,
        user_id: str | None = None,
        thread_id: str | None = None,
        free_text: str | None = None,
        enable_thinking_override: bool | None = None,
        web_search: bool = False,
    ) -> AsyncGenerator[str, None]:
        """Normalize DeerFlow output into the AgentEvent NDJSON contract."""
        builder = EventStreamBuilder(capability, task_id)
        audit_id = str(uuid.uuid4())
        effective_thread_id = thread_id if thread_id is not None else audit_id
        start_ms = int(time.monotonic() * 1000)
        answer_parts: list[str] = []
        success = True
        error_type: str | None = None
        model_name: str | None = None
        redacted_free_text: str = ""
        redacted_answer: str = ""
        selected_provider: dict = {}
        session_started = False
        user_segment = user_id if user_id else "_shared"
        jsonl_path = f"{settings.SESSIONS_DATA_DIR}/{family_id}/agent/{capability}/{user_segment}/{effective_thread_id}.jsonl"

        yield builder.phase("connecting").to_ndjson()

        try:
            client = BackendClient(family_id=family_id)
            try:
                ai_configs = await client.get_family_ai_configs()
            except Exception as e:
                logger.error("[orchestrator] stream events fetch ai_configs failed: %s", e)
                success = False
                error_type = type(e).__name__
                yield builder.error("无法获取 AI 配置，请稍后重试。", code="ai_config_error").to_ndjson()
                return

            providers: list[dict] = ai_configs.get("providers", [])
            ai_enabled: bool = ai_configs.get("ai_enabled", False)

            # ── Select model ──────────────────────────────────────────────
            config_id: str = ""
            selected_caps: list[str] = []
            try:
                if enable_thinking_override:
                    task_type = "thinking"
                elif capability == "import_parse":
                    task_type = "vision"
                else:
                    task_type = "text"
                selected_provider, model_id, selected_caps = _select_model(providers, task_type)
                config_id = selected_provider.get("config_id", "")
            except ValueError as e:
                logger.error("[orchestrator] stream events _select_model failed: %s", e)
                success = False
                error_type = "NoProvider"
                yield builder.error("暂时无法完成分析，请稍后重试。", code="no_provider").to_ndjson()
                return

            if not model_id:
                logger.error("[orchestrator] stream events: model_id is empty for family=%s", family_id)
                success = False
                error_type = "NoModelId"
                yield builder.error("暂时无法完成分析，请稍后重试。", code="no_model_id").to_ndjson()
                return

            model_name = model_id

            policy = CapabilityPolicy(
                ai_enabled=ai_enabled,
                allowed_capabilities=ai_configs.get("allowed_capabilities", []),
                admin_only_capabilities=ai_configs.get("admin_only_capabilities", []),
                member_role=ai_configs.get("member_role", "member"),
            )
            decision = policy_guard.check(policy, capability)
            if not decision.allowed:
                success = False
                error_type = "PolicyDenied"
                yield builder.error(decision.reason, code="policy_denied").to_ndjson()
                return

            # CHAT BRANCH: skip _build_context, use ChatAdapter
            if capability == "chat":
                redacted_free_text = pii_redactor.redact_text(free_text or "")[0]

                # Session lifecycle — must happen before streaming so finally block handles cleanup
                session_journal.write_session_start(
                    family_id=family_id,
                    session_id=effective_thread_id,
                    user_id=user_id,
                    capability=capability,
                    model_name=model_name,
                    jsonl_path=jsonl_path,
                )
                session_started = True
                if redacted_free_text:
                    session_journal.write_user_message(
                        family_id=family_id,
                        session_id=effective_thread_id,
                        user_id=user_id,
                        content=redacted_free_text,
                    )
                _fire_and_forget(self._upsert_session(
                    session_id=effective_thread_id,
                    family_id=family_id,
                    user_id=user_id,
                    jsonl_path=jsonl_path,
                    model_name=model_name,
                ))

                try:
                    chat_tool_id_map: dict[str, str] = {}
                    async for chunk in self._chat_adapter.stream(
                        family_id=family_id,
                        question=redacted_free_text,
                        thread_id=effective_thread_id,
                        ai_config=selected_provider,
                        deep_think=bool(enable_thinking_override),
                        web_search=web_search,
                        enable_thinking=("deep_thinking" in selected_caps and bool(enable_thinking_override)),
                        caller_user_id=user_id,
                    ):
                        async for event_line in self._chunk_to_event_lines(
                            builder, chunk, answer_parts, family_id, effective_thread_id,
                            tool_call_id_map=chat_tool_id_map,
                        ):
                            yield event_line
                    elapsed_ms = int(time.monotonic() * 1000) - start_ms
                    yield builder.end("".join(answer_parts), execution_time_ms=elapsed_ms).to_ndjson()
                    if config_id:
                        _fire_and_forget(client.reset_circuit_success(config_id))
                    return
                except DeerFlowTimeoutError:
                    success = False
                    error_type = "DeerFlowTimeoutError"
                    yield builder.error("AI 响应超时，请稍后重试。", code="deerflow_timeout").to_ndjson()
                    return
                except Exception as e:
                    logger.error("[orchestrator] chat stream failed: %s", e)
                    success = False
                    error_type = type(e).__name__
                    if config_id:
                        _fire_and_forget(client.report_circuit_event(config_id, 500))
                    yield builder.error("AI 服务暂时不可用，请稍后重试。", code="deerflow_error").to_ndjson()
                    return

            context = await self._build_context(client, family_id, free_text=free_text)
            redacted_context = pii_redactor.redact(context)

            # ── Journal: session start + user message ──────────────────────
            session_journal.write_session_start(
                family_id=family_id,
                session_id=effective_thread_id,
                user_id=user_id,
                capability=capability,
                model_name=model_name,
                jsonl_path=jsonl_path,
            )
            session_started = True
            redacted_free_text = redacted_context.free_text or ""
            if redacted_free_text:
                session_journal.write_user_message(
                    family_id=family_id,
                    session_id=effective_thread_id,
                    user_id=user_id,
                    content=redacted_free_text,
                )
            _fire_and_forget(self._upsert_session(
                session_id=effective_thread_id,
                family_id=family_id,
                user_id=user_id,
                jsonl_path=jsonl_path,
                model_name=model_name,
            ))

            skill_config = skill_loader.load(capability)
            thinking_supported = "deep_thinking" in selected_caps
            enable_thinking = (
                bool(enable_thinking_override) and thinking_supported
                if enable_thinking_override is not None
                else skill_config.thinking and thinking_supported
            )

            # ── DeerFlow stream ────────────────────────────────────────────
            try:
                adapter = _create_family_adapter(family_id, selected_provider, timeout_seconds=max(selected_provider.get("timeout_seconds", 60), 240), subagent_enabled=skill_config.subagent_enabled, plan_mode=skill_config.plan_mode)
                deerflow_tool_id_map: dict[str, str] = {}
                async for chunk in adapter.stream_dispatch(
                    capability,
                    redacted_context,
                    effective_thread_id,
                    enable_thinking=enable_thinking,
                ):
                    async for event_line in self._chunk_to_event_lines(
                        builder, chunk, answer_parts, family_id, effective_thread_id,
                        tool_call_id_map=deerflow_tool_id_map,
                    ):
                        yield event_line
                elapsed_ms = int(time.monotonic() * 1000) - start_ms
                yield builder.end(
                    "".join(answer_parts),
                    execution_time_ms=elapsed_ms,
                ).to_ndjson()
                # Success: reset circuit failure count
                if config_id:
                    _fire_and_forget(client.reset_circuit_success(config_id))
                return
            except DeerFlowTimeoutError:
                logger.warning("[orchestrator] event stream timed out family=%s", family_id)
                success = False
                error_type = "DeerFlowTimeoutError"
                yield builder.error("AI 响应超时，请稍后重试。", code="deerflow_timeout").to_ndjson()
            except Exception as e:
                logger.error("[orchestrator] event stream DeerFlow failed: %s", e)
                success = False
                error_type = type(e).__name__
                # Report circuit event for provider errors
                if config_id:
                    _fire_and_forget(client.report_circuit_event(config_id, 500))
                yield builder.error("AI 服务暂时不可用，请稍后重试。", code="deerflow_error").to_ndjson()

        except Exception as e:
            logger.error("[orchestrator] _stream_dispatch_event_lines failed: %s", e)
            success = False
            error_type = type(e).__name__
            yield builder.error("暂时无法完成分析，请稍后重试。").to_ndjson()
        finally:
            duration_ms = int(time.monotonic() * 1000) - start_ms
            if session_started:
                final_answer = "".join(answer_parts)
                if final_answer:
                    redacted_answer, _ = pii_redactor.redact_text(final_answer)
                    session_journal.write_assistant_message(
                        family_id=family_id,
                        session_id=effective_thread_id,
                        content=redacted_answer,
                        model_name=model_name,
                    )
                else:
                    redacted_answer = ""
                session_journal.write_session_end(
                    family_id=family_id,
                    session_id=effective_thread_id,
                    success=success and error_type is None,
                    duration_ms=duration_ms,
                )
                _fire_and_forget(self._update_session_summary(
                    session_id=effective_thread_id,
                    family_id=family_id,
                    summary=redacted_answer[:200] if redacted_answer else None,
                    model=model_name,
                    status="completed" if success and error_type is None else "error",
                ))
                should_generate_title = (
                    redacted_free_text
                    and success
                    and error_type is None
                    and (thread_id is None or capability != "chat")
                )
                if should_generate_title:
                    _fire_and_forget(self._generate_title(
                        session_id=effective_thread_id,
                        family_id=family_id,
                        first_user_message=redacted_free_text,
                        ai_config=selected_provider,
                    ))
            audit_logger.log_call(
                AuditEntry(
                    audit_id=audit_id,
                    capability=capability,
                    family_id=family_id,
                    user_id=user_id,
                    success=success and error_type is None,
                    fallback_used=False,
                    deerflow_attempted=True,
                    duration_ms=duration_ms,
                    error_type=error_type,
                    output_summary=redacted_answer[:200] if redacted_answer else None,
                )
            )

    async def _chunk_to_event_lines(
        self,
        builder: EventStreamBuilder,
        chunk: StreamChunk,
        answer_parts: list[str],
        family_id: str = "",
        session_id: str = "",
        tool_call_id_map: dict[str, str] | None = None,
    ) -> AsyncGenerator[str, None]:
        if tool_call_id_map is None:
            tool_call_id_map = {}

        if chunk.type == "thinking":
            yield builder.phase("thinking").to_ndjson()
            yield builder.token(chunk.content, is_thinking=True).to_ndjson()
            return

        if chunk.type == "tool_call":
            data = chunk.data or {}
            tool_name = data.get("tool_name", "")
            args = data.get("args") or {}
            tool_call_id = str(data.get("tool_call_id") or "")
            if data.get("internal"):
                evt = builder.tool_call(
                    tool_name=tool_name,
                    arguments=args,
                    display_name="规划步骤",
                    icon="🗂️",
                    tool_type="internal",
                )
            else:
                evt = builder.tool_call(
                    tool_name=tool_name,
                    arguments=args,
                    display_name=data.get("display_name") or tool_name,
                    icon=data.get("icon") or "tool",
                    tool_type=data.get("tool_type") or "unknown",
                )
            backend_id = evt.payload["tool"]["id"]
            if tool_call_id:
                tool_call_id_map[tool_call_id] = backend_id
            yield evt.to_ndjson()
            return

        if chunk.type == "tool_result":
            data = chunk.data or {}
            provider_id = str(data.get("tool_call_id") or "")
            backend_id = tool_call_id_map.get(provider_id, provider_id)
            yield builder.tool_result(
                tool_id=backend_id,
                success=True,
                execution_time_ms=0,
                data=data.get("content"),
            ).to_ndjson()
            return

        if chunk.type == "plan_update":
            data = chunk.data or {}
            todos = data.get("todos")
            if todos is None:
                return
            yield builder.plan_update(todos).to_ndjson()
            return

        if chunk.content:
            answer_parts.append(chunk.content)
            yield builder.phase("answering").to_ndjson()
            yield builder.token(chunk.content, is_thinking=False).to_ndjson()

    async def _upsert_session(
        self,
        *,
        session_id: str,
        family_id: str,
        user_id: str | None,
        jsonl_path: str,
        model_name: str | None,
    ) -> None:
        try:
            from apps.agent.services.session_store import AiSessionRepository
            repo = AiSessionRepository(family_id)
            await repo.upsert(
                session_id=session_id,
                family_id=family_id,
                user_id=user_id,
                jsonl_path=jsonl_path,
                last_model=model_name,
            )
        except Exception as e:
            logger.warning("[orchestrator] session upsert failed session=%s: %s", session_id, e)

    async def _update_session_summary(
        self,
        *,
        session_id: str,
        family_id: str,
        summary: str | None,
        model: str | None,
        status: str,
        title: str | None = None,
    ) -> None:
        try:
            from apps.agent.services.session_store import AiSessionRepository
            repo = AiSessionRepository(family_id)
            await repo.update_summary(
                session_id=session_id,
                family_id=family_id,
                summary=summary,
                model=model,
                status=status,
                title=title,
            )
        except Exception as e:
            logger.warning("[orchestrator] session summary update failed session=%s: %s", session_id, e)

    async def _generate_title(
        self,
        *,
        session_id: str,
        family_id: str,
        first_user_message: str,
        ai_config: dict,
        capability: str = "chat",
        user_id: str | None = None,
    ) -> None:
        """Fire-and-forget: generate a short session title and persist it.

        For chat: use LLM to summarize the first user message.
        For other AI capabilities: use format "日期+AI功能名+用户名".

        Skips generation if the session already has a title (multi-turn continuation).
        """
        try:
            logger.info("[orchestrator] title generation starting session=%s capability=%s", session_id, capability)
            from apps.agent.services.session_store import AiSessionRepository
            repo = AiSessionRepository(family_id)
            # Check if title already exists — skip for multi-turn continuations
            existing = await repo.get_title(session_id=session_id, family_id=family_id)
            if existing:
                logger.info("[orchestrator] title already exists session=%s, skipping", session_id)
                return

            # For non-chat capabilities, generate title directly without LLM
            if capability != "chat":
                from apps.agent.services.capability_registry import CapabilityRegistry
                registry = CapabilityRegistry()
                cap_def = registry.get(capability)
                cap_name = cap_def.name if cap_def else capability
                # Format: "YYYY-MM-DD 功能名 用户名"
                date_str = time.strftime("%Y-%m-%d", time.localtime())
                # Fetch user display name if available
                user_name = "匿名用户"
                if user_id:
                    try:
                        client = BackendClient(family_id=family_id)
                        user_info = await client.get_user(user_id)
                        if user_info:
                            user_name = user_info.get("display_name") or user_info.get("username") or "匿名用户"
                    except Exception as e:
                        logger.warning("[orchestrator] failed to fetch user name: %s", e)
                title = f"{date_str} {cap_name} {user_name}"
                title = title[:50]  # Truncate to max length
                logger.info("[orchestrator] non-chat title generated session=%s title=%s", session_id, title)
                await repo.update_summary(
                    session_id=session_id,
                    family_id=family_id,
                    summary=None,
                    title=title,
                )
                return

            # For chat: use LLM summarization
            from apps.agent.core.llm import LLMClient
            provider = ai_config.get("ai_provider", "")
            api_key = ai_config.get("api_key", "")
            model_id = ai_config.get("ai_model_id", "")
            base_url = ai_config.get("ai_base_url", "") or None
            logger.info("[orchestrator] title generation params session=%s provider=%s model=%s base_url=%s",
                        session_id, provider, model_id, base_url[:50] if base_url else "None")
            if not (provider and api_key and model_id):
                logger.warning("[orchestrator] title generation skipped session=%s: missing ai_config", session_id)
                return
            llm = LLMClient(provider=provider, api_key=api_key, model_id=model_id, base_url=base_url)
            prompt = f"请用10字以内概括以下问题的主题，只输出标题，不要标点：{first_user_message[:200]}"
            logger.info("[orchestrator] title generation calling LLM session=%s prompt=%s", session_id, prompt[:80])
            title = (await llm.complete(prompt, max_tokens=30)).strip()
            logger.info("[orchestrator] title generation received session=%s title=%s", session_id, repr(title[:50] if title else ""))
            if title:
                await repo.update_summary(
                    session_id=session_id,
                    family_id=family_id,
                    summary=None,
                    title=title[:50],
                )
        except Exception as e:
            logger.warning("[orchestrator] title generation failed session=%s: %s", session_id, e)

    async def _build_context(
        self,
        client: BackendClient,
        family_id: str,
        free_text: str | None,
    ) -> FamilyContext:
        """Fetch all family data from backend and assemble FamilyContext."""
        results = await asyncio.gather(
            client.get_liabilities(),
            client.get_dashboard_overview(),
            client.get_dashboard_allocation(),
            client.get_dashboard_trend(),
            client.get_dashboard_low_usage(),
            return_exceptions=True,
        )

        liabilities = results[0] if not isinstance(results[0], Exception) else []
        if isinstance(results[0], Exception):
            logger.warning("[orchestrator] fetch liabilities failed family=%s: %s", family_id, results[0])

        dashboard_overview = results[1] if not isinstance(results[1], Exception) else {}
        if isinstance(results[1], Exception):
            logger.warning("[orchestrator] fetch dashboard_overview failed family=%s: %s", family_id, results[1])

        dashboard_allocation = results[2] if not isinstance(results[2], Exception) else {}
        if isinstance(results[2], Exception):
            logger.warning("[orchestrator] fetch dashboard_allocation failed family=%s: %s", family_id, results[2])

        dashboard_trend = results[3] if not isinstance(results[3], Exception) else {}
        if isinstance(results[3], Exception):
            logger.warning("[orchestrator] fetch dashboard_trend failed family=%s: %s", family_id, results[3])

        low_usage_assets = results[4] if not isinstance(results[4], Exception) else []
        if isinstance(results[4], Exception):
            logger.warning("[orchestrator] fetch low_usage_assets failed family=%s: %s", family_id, results[4])

        assets: list[dict] = []   # no backend endpoint yet
        members: list[dict] = []  # no backend endpoint yet

        return FamilyContext(
            family_id=family_id,
            assets=assets,
            liabilities=liabilities,
            members=members,
            dashboard_overview=dashboard_overview,
            dashboard_allocation=dashboard_allocation,
            dashboard_trend=dashboard_trend,
            low_usage_assets=low_usage_assets,
            free_text=free_text,
        )

    @staticmethod
    def _error_response(
        capability: str,
        audit_id: str,
        message: str = "暂时无法完成分析，请稍后重试。",
    ) -> AgentResponse:
        return AgentResponse(
            capability=capability,
            summary=message,
            disclaimers=["本次分析未能完成，结果不可用。"],
            fallback_used=False,
            audit_id=audit_id,
        )


orchestrator = Orchestrator()
