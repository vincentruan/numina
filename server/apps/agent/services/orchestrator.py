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
import time
import uuid
from collections.abc import AsyncGenerator

from apps.agent.app.config import settings
from apps.agent.core.backend_client import BackendClient
from apps.agent.schemas.context import FamilyContext
from apps.agent.schemas.policy import CapabilityPolicy
from apps.agent.schemas.response import AgentResponse
from apps.agent.services.audit_logger import AuditEntry, audit_logger
from apps.agent.services.deerflow_adapter.adapter import (
    DeerFlowTimeoutError,
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
                family_adapter = _deerflow_adapter or _create_family_adapter(
                    family_id, ai_config, timeout_seconds=ai_config.get("timeout_seconds", 60)
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
        jsonl_path = f"{settings.SESSIONS_DATA_DIR}/{family_id}/{effective_thread_id}.jsonl"
        session_started = False

        # ── 1. Fetch AI config & build policy ──────────────────────────
        client = BackendClient(family_id=family_id)
        try:
            ai_config = await client.get_family_ai_config()
        except Exception as e:
            logger.error("[orchestrator] stream_dispatch fetch ai_config failed: %s", e)
            yield "暂时无法完成分析，请稍后重试。"
            return

        model_name = ai_config.get("ai_model_id")

        policy = CapabilityPolicy(
            ai_enabled=ai_config.get("ai_enabled", False),
            allowed_capabilities=ai_config.get("allowed_capabilities", []),
            admin_only_capabilities=ai_config.get("admin_only_capabilities", []),
            member_role=ai_config.get("member_role", "member"),
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
            capability=capability,
            jsonl_path=jsonl_path,
            model_name=model_name,
        ))

        # ── 6. Load thinking flag ──────────────────────────────────────
        skill_config = skill_loader.load(capability)
        thinking_supported = ai_config.get("thinking_supported", False)
        enable_thinking = (
            bool(enable_thinking_override) and thinking_supported
            if enable_thinking_override is not None
            else skill_config.thinking and thinking_supported
        )

        # ── 7. DeerFlow stream dispatch ────────────────────────────────
        try:
            adapter = _create_family_adapter(family_id, ai_config, timeout_seconds=ai_config.get("timeout_seconds", 60))
            async for chunk in adapter.stream_dispatch(
                capability,
                redacted_context,
                effective_thread_id,
                enable_thinking=enable_thinking,
            ):
                text = chunk[6:] if chunk.startswith("[TEXT]") else (None if chunk.startswith("[THINK]") else chunk)
                if text:
                    answer_parts.append(text)
                yield chunk
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
        except DeerFlowTimeoutError:
            logger.warning("[orchestrator] stream_dispatch timed out family=%s", family_id)
            error_type = "DeerFlowTimeoutError"
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
        except Exception as e:
            logger.error("[orchestrator] stream_dispatch DeerFlow failed: %s", e)
            error_type = type(e).__name__
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
                if redacted_free_text and thread_id is None:
                    _fire_and_forget(self._generate_title(
                        session_id=effective_thread_id,
                        family_id=family_id,
                        first_user_message=redacted_free_text,
                        ai_config=ai_config,
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
        ai_config: dict = {}
        session_started = False
        jsonl_path = f"{settings.SESSIONS_DATA_DIR}/{family_id}/{effective_thread_id}.jsonl"

        yield builder.phase("connecting").to_ndjson()

        try:
            client = BackendClient(family_id=family_id)
            try:
                ai_config = await client.get_family_ai_config()
            except Exception as e:
                logger.error("[orchestrator] stream events fetch ai_config failed: %s", e)
                success = False
                error_type = type(e).__name__
                yield builder.error("无法获取 AI 配置，请稍后重试。", code="ai_config_error").to_ndjson()
                return

            model_name = ai_config.get("ai_model_id")

            policy = CapabilityPolicy(
                ai_enabled=ai_config.get("ai_enabled", False),
                allowed_capabilities=ai_config.get("allowed_capabilities", []),
                admin_only_capabilities=ai_config.get("admin_only_capabilities", []),
                member_role=ai_config.get("member_role", "member"),
            )
            decision = policy_guard.check(policy, capability)
            if not decision.allowed:
                success = False
                error_type = "PolicyDenied"
                yield builder.error(decision.reason, code="policy_denied").to_ndjson()
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
                capability=capability,
                jsonl_path=jsonl_path,
                model_name=model_name,
            ))

            skill_config = skill_loader.load(capability)
            thinking_supported = ai_config.get("thinking_supported", False)
            enable_thinking = (
                bool(enable_thinking_override) and thinking_supported
                if enable_thinking_override is not None
                else skill_config.thinking and thinking_supported
            )

            # ── DeerFlow stream ────────────────────────────────────────────
            try:
                adapter = _create_family_adapter(family_id, ai_config, timeout_seconds=ai_config.get("timeout_seconds", 60))
                async for chunk in adapter.stream_dispatch(
                    capability,
                    redacted_context,
                    effective_thread_id,
                    enable_thinking=enable_thinking,
                ):
                    async for event_line in self._chunk_to_event_lines(
                        builder, chunk, answer_parts, family_id, effective_thread_id
                    ):
                        yield event_line
                elapsed_ms = int(time.monotonic() * 1000) - start_ms
                yield builder.end(
                    "".join(answer_parts),
                    execution_time_ms=elapsed_ms,
                ).to_ndjson()
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
                if redacted_free_text and success and error_type is None and thread_id is None:
                    _fire_and_forget(self._generate_title(
                        session_id=effective_thread_id,
                        family_id=family_id,
                        first_user_message=redacted_free_text,
                        ai_config=ai_config,
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
        chunk: str,
        answer_parts: list[str],
        family_id: str = "",
        session_id: str = "",
    ) -> AsyncGenerator[str, None]:
        if chunk.startswith("[THINK]"):
            yield builder.phase("thinking").to_ndjson()
            yield builder.token(chunk[7:], is_thinking=True).to_ndjson()
            return
        text = chunk[6:] if chunk.startswith("[TEXT]") else chunk
        if text:
            answer_parts.append(text)
            yield builder.phase("answering").to_ndjson()
            yield builder.token(text, is_thinking=False).to_ndjson()

    async def _upsert_session(
        self,
        *,
        session_id: str,
        family_id: str,
        user_id: str | None,
        capability: str,
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
                capability=capability,
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
    ) -> None:
        """Fire-and-forget: generate a short session title via LLM and persist it."""
        try:
            from apps.agent.core.llm import LLMClient
            provider = ai_config.get("ai_provider", "")
            api_key = ai_config.get("api_key", "")
            model_id = ai_config.get("ai_model_id", "")
            if not (provider and api_key and model_id):
                return
            llm = LLMClient(provider=provider, api_key=api_key, model_id=model_id)
            prompt = f"请用10字以内概括以下问题的主题，只输出标题，不要标点：{first_user_message[:200]}"
            title = (await llm.complete(prompt, max_tokens=30)).strip()
            if title:
                from apps.agent.services.session_store import AiSessionRepository
                repo = AiSessionRepository(family_id)
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
        try:
            liabilities = await client.get_liabilities()
        except Exception as e:
            logger.warning("[orchestrator] fetch liabilities failed family=%s: %s", family_id, e)
            liabilities = []
        try:
            dashboard_overview = await client.get_dashboard_overview()
        except Exception as e:
            logger.warning("[orchestrator] fetch dashboard_overview failed family=%s: %s", family_id, e)
            dashboard_overview = {}
        try:
            dashboard_allocation = await client.get_dashboard_allocation()
        except Exception as e:
            logger.warning("[orchestrator] fetch dashboard_allocation failed family=%s: %s", family_id, e)
            dashboard_allocation = {}
        try:
            dashboard_trend = await client.get_dashboard_trend()
        except Exception as e:
            logger.warning("[orchestrator] fetch dashboard_trend failed family=%s: %s", family_id, e)
            dashboard_trend = {}
        try:
            low_usage_assets = await client.get_dashboard_low_usage()
        except Exception as e:
            logger.warning("[orchestrator] fetch low_usage_assets failed family=%s: %s", family_id, e)
            low_usage_assets = []
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
