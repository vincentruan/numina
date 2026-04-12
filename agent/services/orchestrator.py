"""Orchestrator — central dispatch pipeline for all agent capabilities.

Pipeline per request:
  1. PolicyGuard.check()        — enforce admin switches
  2. BackendClient.fetch_context() — pull family data
  3. PIIRedactor.redact()       — strip PII before any LLM call
  4. DeerFlowAdapter.dispatch() — if USE_DEERFLOW=true
     OR FallbackEngine.run()   — legacy path / DeerFlow failure
  5. AuditLogger.log_call()     — structured audit entry

All exceptions are caught here; callers always receive an AgentResponse.
"""

import logging
import time
import uuid

from config import settings
from core.backend_client import BackendClient
from core.llm import LLMClient
from schemas.context import FamilyContext
from schemas.policy import CapabilityPolicy
from schemas.response import AgentResponse
from services.audit_logger import AuditEntry, audit_logger
from services.fallback_engine import fallback_engine
from services.output_mapper import output_mapper
from services.pii_redactor import pii_redactor
from services.policy_guard import policy_guard

try:
    from services.deerflow_adapter.adapter import deerflow_adapter as _deerflow_adapter
except Exception:
    _deerflow_adapter = None  # type: ignore[assignment]

logger = logging.getLogger(__name__)


class Orchestrator:
    """Routes a capability request through the full dispatch pipeline."""

    async def dispatch(
        self,
        capability: str,
        family_id: str,
        user_id: str | None = None,
        free_text: str | None = None,
    ) -> AgentResponse:
        """Run the full pipeline. Never raises — always returns AgentResponse."""
        audit_id = str(uuid.uuid4())
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

            # ── 3. Build LLM client ────────────────────────────────────────
            provider = ai_config.get("ai_provider")
            api_key = ai_config.get("api_key")
            if not provider or not api_key:
                return self._safe_response(capability, audit_id, "AI 服务商或 API Key 未配置")

            llm = LLMClient(provider=provider, api_key=api_key)

            # ── 4. Fetch family context ────────────────────────────────────
            raw_context = await self._build_context(client, family_id, free_text)

            # ── 5. PII redaction ───────────────────────────────────────────
            redacted = pii_redactor.redact(raw_context)

            # ── 6. Dispatch: DeerFlow or legacy ────────────────────────────
            if settings.USE_DEERFLOW:
                deerflow_attempted = True
                try:
                    if _deerflow_adapter is None:
                        raise RuntimeError("DeerFlow adapter not available")
                    raw_output = await _deerflow_adapter.dispatch(
                        skill_name=capability,
                        context=redacted,
                        thread_id=audit_id,
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
