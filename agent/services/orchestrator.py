"""Orchestrator — central dispatch pipeline for all agent capabilities.

Pipeline per request:
  1. PolicyGuard.check()        — enforce admin switches
  2. BackendClient.fetch_context() — pull family data
  3. PIIRedactor.redact()       — strip PII before any LLM call
  4. DeerFlowAdapter.dispatch() — if USE_DEERFLOW=true (家庭级配置)
     OR FallbackEngine.run()   — legacy path / DeerFlow failure
  5. AuditLogger.log_call()     — structured audit entry

All exceptions are caught here; callers always receive an AgentResponse.
"""

import json
import logging
import time
import uuid
from collections.abc import AsyncGenerator

from app.config import settings
from core.backend_client import BackendClient
from core.llm import LLMClient
from schemas.context import FamilyContext
from schemas.policy import CapabilityPolicy
from schemas.response import AgentResponse
from services.audit_logger import AuditEntry, audit_logger
from services.deerflow_adapter.adapter import (
    create_family_adapter as _create_family_adapter,
)
from services.deerflow_adapter.skill_loader import skill_loader
from services.fallback_engine import fallback_engine
from services.output_mapper import output_mapper
from services.pii_redactor import pii_redactor
from services.policy_guard import policy_guard

logger = logging.getLogger(__name__)

# Module-level adapter factory — exposed for patching in tests
_deerflow_adapter = None  # sentinel; real adapter is created per-request via _create_family_adapter


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
        # Use caller-supplied thread_id for DeerFlow session continuity;
        # fall back to audit_id for backward compatibility (e.g. non-chat capabilities)
        effective_thread_id = thread_id if thread_id is not None else audit_id
        start_ms = int(time.monotonic() * 1000)
        fallback_used = False
        deerflow_attempted = False
        skill_triggered: str | None = None
        error_type: str | None = None
        response: AgentResponse | None = None

        try:
            # ── 1. Fetch AI config & build policy ──────────────────────────
            client = BackendClient(family_id=family_id)
            try:
                ai_config = await client.get_family_ai_config()
            except Exception as e:
                logger.error(f"[orchestrator] fetch ai_config failed family={family_id}: {e}")
                return self._safe_response(capability, audit_id, "无法获取 AI 配置，请稍后重试")

            policy = CapabilityPolicy(
                ai_enabled=ai_config.get("ai_enabled", False),
                allowed_capabilities=ai_config.get("allowed_capabilities", []),
                admin_only_capabilities=ai_config.get("admin_only_capabilities", []),
                member_role=ai_config.get("member_role", "member"),
            )

            # ── 2. Policy check ────────────────────────────────────────────
            decision = policy_guard.check(policy, capability)
            if not decision.allowed:
                return AgentResponse(
                    capability=capability,
                    summary=decision.reason,
                    fallback_used=False,
                    audit_id=audit_id,
                )

            # ── 3. Fetch family context ────────────────────────────────────
            # suggest only needs free_text (asset name/category) — skip heavy fetches
            if capability == "suggest":
                raw_context = FamilyContext(family_id=family_id, free_text=free_text)
            else:
                raw_context = await self._build_context(client, family_id, free_text)

            # ── 4. PII redaction ───────────────────────────────────────────
            redacted = pii_redactor.redact(raw_context)

            # ── 5. Build LLM client ────────────────────────────────────────
            llm = LLMClient(
                provider=ai_config.get("ai_provider", ""),
                api_key=ai_config.get("api_key", ""),
                model_id=ai_config.get("ai_model_id", ""),
                vision_model_id=ai_config.get("ai_vision_model_id"),
                base_url=ai_config.get("ai_base_url"),
                timeout=float(ai_config.get("timeout_seconds", 60)),
            )

            # ── 6. Dispatch: DeerFlow or legacy ────────────────────────────
            if settings.USE_DEERFLOW:
                deerflow_attempted = True
                try:
                    # 使用家庭级 DeerFlowAdapter（动态注入 ai_config）
                    family_adapter = _deerflow_adapter or _create_family_adapter(family_id, ai_config)
                    raw_output = await family_adapter.dispatch(
                        skill_name=capability,
                        context=redacted,
                        thread_id=effective_thread_id,
                    )
                    response = output_mapper.from_deerflow(raw_output, capability, audit_id)
                    skill_triggered = capability
                except Exception as e:
                    logger.warning(
                        f"[orchestrator] DeerFlow failed capability={capability}, "
                        f"falling back to legacy: {e}"
                    )
                    response = await fallback_engine.run(
                        capability, redacted, llm, audit_id, is_deerflow_fallback=True
                    )
                    fallback_used = True
                    error_type = type(e).__name__
            else:
                # USE_DEERFLOW=False: legacy is the normal path, not a fallback
                response = await fallback_engine.run(
                    capability, redacted, llm, audit_id, is_deerflow_fallback=False
                )
                fallback_used = False

        except Exception as e:
            logger.error(f"[orchestrator] unhandled error capability={capability}: {e}")
            error_type = type(e).__name__
            response = output_mapper.from_error(e, capability, audit_id)
            fallback_used = True

        finally:
            duration_ms = int(time.monotonic() * 1000) - start_ms
            if response is None:
                response = self._safe_response(capability, audit_id)
            # Redact LLM output before writing to audit log
            raw_summary = response.summary[:200] if response.summary else None
            if raw_summary:
                raw_summary = pii_redactor.redact_text(raw_summary)[0]
            audit_logger.log_call(AuditEntry(
                family_id=family_id,
                capability=capability,
                success=error_type is None,
                audit_id=audit_id,
                user_id=user_id,
                skill_triggered=skill_triggered,
                fallback_used=fallback_used,
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

        # ── 1. Fetch AI config & build policy ──────────────────────────
        client = BackendClient(family_id=family_id)
        try:
            ai_config = await client.get_family_ai_config()
        except Exception as e:
            logger.error(f"[orchestrator] stream_dispatch fetch ai_config failed: {e}")
            yield "暂时无法完成分析，请稍后重试。"
            return

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
        context = await self._build_context(client, family_id, free_text=free_text)

        # ── 4. Redact PII ──────────────────────────────────────────────
        redacted_context = pii_redactor.redact(context)

        # ── 5. Load skill config + thinking flag ───────────────────────
        skill_config = skill_loader.load(capability)
        thinking_supported = ai_config.get("thinking_supported", False)
        enable_thinking = (
            bool(enable_thinking_override) and thinking_supported
            if enable_thinking_override is not None
            else skill_config.thinking and thinking_supported
        )

        # ── 6. Stream dispatch ─────────────────────────────────────────
        if settings.USE_DEERFLOW:
            try:
                adapter = _create_family_adapter(family_id, ai_config)
                async for chunk in adapter.stream_dispatch(
                    capability,
                    redacted_context,
                    effective_thread_id,
                    enable_thinking=enable_thinking,
                ):
                    yield chunk
                audit_logger.log_call(
                    AuditEntry(
                        audit_id=audit_id,
                        capability=capability,
                        family_id=family_id,
                        user_id=user_id,
                        success=True,
                        deerflow_attempted=True,
                        duration_ms=int(time.monotonic() * 1000) - start_ms,
                    )
                )
                return
            except Exception as e:
                logger.warning(f"[orchestrator] stream_dispatch DeerFlow failed: {e}")

        # ── 7. Fallback (non-streaming) ────────────────────────────────
        fallback_used = False
        try:
            llm = LLMClient(
                provider=ai_config.get("ai_provider", ""),
                api_key=ai_config.get("api_key", ""),
                model_id=ai_config.get("ai_model_id", ""),
                vision_model_id=ai_config.get("ai_vision_model_id"),
                base_url=ai_config.get("ai_base_url"),
                timeout=float(ai_config.get("timeout_seconds", 60)),
            )
            if capability == "chat" and redacted_context.free_text:
                async for chunk in self._stream_chat_fallback(
                    redacted_context.free_text,
                    client,
                    llm,
                    enable_thinking,
                ):
                    yield chunk
                fallback_used = True
            raw_output = await fallback_engine.run(
                capability, redacted_context, llm, audit_id, is_deerflow_fallback=settings.USE_DEERFLOW
            ) if not fallback_used else None
            if raw_output is not None:
                # PII redaction before yielding to stream
                raw_summary = raw_output.summary or "分析完成。"
                redacted_summary, _ = pii_redactor.redact_text(raw_summary)
                yield redacted_summary
                fallback_used = True
        except Exception as e:
            logger.error(f"[orchestrator] stream_dispatch fallback failed: {e}")
            yield "暂时无法完成分析，请稍后重试。"
            fallback_used = True

        audit_logger.log_call(
            AuditEntry(
                audit_id=audit_id,
                capability=capability,
                family_id=family_id,
                user_id=user_id,
                success=True,
                fallback_used=fallback_used,
                deerflow_attempted=settings.USE_DEERFLOW,
                duration_ms=int(time.monotonic() * 1000) - start_ms,
            )
        )

    async def _stream_chat_fallback(
        self,
        question: str,
        client: BackendClient,
        llm: LLMClient,
        enable_thinking: bool,
    ) -> AsyncGenerator[str, None]:
        """Stream chat answers on the direct LLM path using the shared pipeline config."""
        from services.chat import (
            ANSWER_PROMPT,
            _classify_intent,
            _fetch_data_for_intent,
        )

        intent = await _classify_intent(question, llm)
        if intent == "unknown":
            yield "抱歉，我目前只能回答关于净资产、资产配置、负债、趋势、日均成本、低效资产和到期资产的问题。"
            return

        try:
            data = await _fetch_data_for_intent(intent, client)
        except Exception as e:
            logger.error(f"[chat] stream data fetch failed: {e}")
            data = {}

        prompt = ANSWER_PROMPT.format(
            question=question,
            data=json.dumps(data, ensure_ascii=False, default=str),
        )

        if enable_thinking:
            async for block_type, chunk in llm.stream_with_thinking(
                prompt,
                max_tokens=8000,
                thinking_budget=5000,
            ):
                prefix = "[THINK]" if block_type == "thinking" else "[TEXT]"
                yield f"{prefix}{chunk}"
            return

        async for chunk in llm.stream_text(prompt, max_tokens=1024):
            yield f"[TEXT]{chunk}"

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
            logger.warning(f"[orchestrator] fetch liabilities failed family={family_id}: {e}")
            liabilities = []
        try:
            dashboard_overview = await client.get_dashboard_overview()
        except Exception as e:
            logger.warning(f"[orchestrator] fetch dashboard_overview failed family={family_id}: {e}")
            dashboard_overview = {}
        try:
            dashboard_allocation = await client.get_dashboard_allocation()
        except Exception as e:
            logger.warning(f"[orchestrator] fetch dashboard_allocation failed family={family_id}: {e}")
            dashboard_allocation = {}
        try:
            dashboard_trend = await client.get_dashboard_trend()
        except Exception as e:
            logger.warning(f"[orchestrator] fetch dashboard_trend failed family={family_id}: {e}")
            dashboard_trend = {}
        try:
            low_usage_assets = await client.get_dashboard_low_usage()
        except Exception as e:
            logger.warning(f"[orchestrator] fetch low_usage_assets failed family={family_id}: {e}")
            low_usage_assets = []
        assets: list[dict] = []   # no backend endpoint yet — context will be empty
        members: list[dict] = []  # no backend endpoint yet — context will be empty
        logger.debug("[orchestrator] assets/members not fetched — no backend endpoint available")

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
    def _safe_response(
        capability: str,
        audit_id: str,
        message: str = "暂时无法完成分析，请稍后重试。",
    ) -> AgentResponse:
        return AgentResponse(
            capability=capability,
            summary=message,
            disclaimers=["本次分析未能完成，结果不可用。"],
            fallback_used=True,
            audit_id=audit_id,
        )


orchestrator = Orchestrator()
