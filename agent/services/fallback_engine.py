"""FallbackEngine — runs legacy service path when DeerFlow fails or is disabled.

This is the final backstop: if the legacy path also raises, return a hardcoded
safe AgentResponse rather than propagating the exception.
"""

import contextlib
import json
import logging

from schemas.context import RedactedContext
from schemas.response import AgentResponse
from services.output_mapper import output_mapper

logger = logging.getLogger(__name__)

_SAFE_RESPONSE = AgentResponse(
    capability="unknown",
    summary="暂时无法完成分析，请稍后重试。",
    disclaimers=["本次分析未能完成，结果不可用。"],
    fallback_used=True,
)


class FallbackEngine:
    """Runs the legacy single-shot LLM service path as fallback."""

    async def run(
        self,
        capability: str,
        redacted_context: RedactedContext,
        llm,
        audit_id: str,
        is_deerflow_fallback: bool = False,
    ) -> AgentResponse:
        """Run legacy service.

        Args:
            is_deerflow_fallback: True when called after a DeerFlow failure (sets
                fallback_used=True in the response). False when USE_DEERFLOW=False
                and legacy is the normal path (sets fallback_used=False).
        """
        try:
            result = await self._run_legacy(capability, redacted_context, llm)
            return output_mapper.from_legacy(result, capability, audit_id, fallback_used=is_deerflow_fallback)
        except (ValueError, KeyError, TypeError, AttributeError) as e:
            logger.error(f"[fallback] Legacy path failed for capability={capability}: {e}")
            safe = _SAFE_RESPONSE.model_copy(update={"capability": capability, "audit_id": audit_id})
            return safe
        except Exception as e:
            logger.error(f"[fallback] Unexpected error for capability={capability}: {e}")
            safe = _SAFE_RESPONSE.model_copy(update={"capability": capability, "audit_id": audit_id})
            return safe

    async def _run_legacy(self, capability: str, ctx: RedactedContext, llm) -> dict:
        """Dispatch to the appropriate legacy service function."""
        family_id = ctx.family_id

        if capability == "report":
            from services.health_report import generate_health_report
            return await generate_health_report(family_id=family_id, llm=llm, ctx=ctx)

        elif capability == "suggest":
            # Parse free_text JSON for asset fields; fall back to stub if missing
            fields: dict = {}
            if ctx.free_text:
                with contextlib.suppress(json.JSONDecodeError, ValueError):
                    fields = json.loads(ctx.free_text)
            if fields.get("name") and fields.get("category"):
                from services.asset_suggest import suggest_asset_fields
                return await suggest_asset_fields(
                    name=fields["name"],
                    category=fields["category"],
                    asset_type=fields.get("asset_type", "physical"),
                    llm=llm,
                )
            return {"summary": "建议功能暂时不可用"}

        elif capability == "alerts":
            from services.aging_alert import scan_aging_alerts
            alerts = await scan_aging_alerts(family_id=family_id, llm=llm)
            return {"alerts": alerts, "summary": f"发现 {len(alerts)} 条老化预警"}

        elif capability == "disposal":
            from services.disposal_advisor import scan_disposal_suggestions
            suggestions = await scan_disposal_suggestions(family_id=family_id, llm=llm)
            return {"suggestions": suggestions, "summary": f"发现 {len(suggestions)} 条处置建议"}

        elif capability == "liability":
            from services.liability_advisor import analyze_liabilities
            return await analyze_liabilities(family_id=family_id, llm=llm)

        elif capability == "allocation":
            from services.allocation_advisor import analyze_allocation
            return await analyze_allocation(family_id=family_id, llm=llm)

        elif capability == "spending_leak":
            from services.spending_leak import scan_spending_leaks
            leaks = await scan_spending_leaks(family_id=family_id, llm=llm, ctx=ctx)
            return {"leaks": leaks, "summary": f"发现 {len(leaks)} 条消费漏洞"}

        elif capability == "chat":
            if ctx.free_text:
                from services.chat import answer_question
                answer = await answer_question(
                    question=ctx.free_text,
                    family_id=ctx.family_id,
                    llm=llm,
                )
                return {"summary": answer}
            return {"summary": "问答功能暂时不可用，请稍后重试"}

        else:
            return {"summary": f"未知功能: {capability}"}


fallback_engine = FallbackEngine()
