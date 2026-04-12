"""OutputMapper — transforms DeerFlow raw output or legacy service dicts into AgentResponse."""

import json
import logging
import re
import uuid
from typing import Any

from schemas.response import AgentResponse, Finding, RiskFlag, Scorecard, Recommendation

logger = logging.getLogger(__name__)

_FENCE_RE = re.compile(r'```(?:json)?\s*([\s\S]*?)\s*```')


def _extract_json(raw: str) -> dict[str, Any] | None:
    """Try to extract a JSON object from raw text. Returns None on failure."""
    fence = _FENCE_RE.search(raw)
    candidate = fence.group(1) if fence else None
    if candidate is None:
        start = raw.find("{")
        end = raw.rfind("}") + 1
        candidate = raw[start:end] if start >= 0 and end > start else None
    if not candidate:
        return None
    try:
        return json.loads(candidate)
    except json.JSONDecodeError:
        return None


class OutputMapper:
    """Maps various output sources to the stable AgentResponse schema."""

    def from_deerflow(self, raw: str, capability: str, audit_id: str) -> AgentResponse:
        """Parse DeerFlow text output into AgentResponse."""
        data = _extract_json(raw)
        if data:
            return self._from_dict(data, capability, audit_id, fallback_used=False)
        # Plain text fallback — summary only
        return AgentResponse(
            capability=capability,
            summary=raw[:500] if raw else "",
            fallback_used=False,
            audit_id=audit_id,
        )

    def from_legacy(self, legacy_dict: dict[str, Any], capability: str, audit_id: str, fallback_used: bool = False) -> AgentResponse:
        """Wrap existing service dict output in AgentResponse."""
        return self._from_dict(legacy_dict, capability, audit_id, fallback_used=fallback_used)

    def from_error(self, error: Exception, capability: str, audit_id: str) -> AgentResponse:
        """Produce a safe error response. fallback_used is always True."""
        return AgentResponse(
            capability=capability,
            summary="暂时无法完成分析，请稍后重试。",
            disclaimers=["本次分析未能完成，结果不可用。"],
            fallback_used=True,
            audit_id=audit_id,
        )

    def _from_dict(self, data: dict[str, Any], capability: str, audit_id: str, fallback_used: bool) -> AgentResponse:
        scorecards = [
            Scorecard(**s) if isinstance(s, dict) else s
            for s in data.get("scorecards", [])
        ]
        risk_flags = [
            RiskFlag(**r) if isinstance(r, dict) else r
            for r in data.get("risk_flags", [])
        ]
        recommendations = [
            Recommendation(**r) if isinstance(r, dict) else r
            for r in data.get("recommendations", [])
        ]
        followup_actions = [
            Recommendation(**r) if isinstance(r, dict) else r
            for r in data.get("followup_actions", [])
        ]
        rule_based = [
            Finding(**f) if isinstance(f, dict) else f
            for f in data.get("rule_based_findings", [])
        ]
        ai_inferences = [
            Finding(**f) if isinstance(f, dict) else f
            for f in data.get("ai_inferences", [])
        ]
        return AgentResponse(
            capability=capability,
            summary=data.get("summary", ""),
            scorecards=scorecards,
            risk_flags=risk_flags,
            recommendations=recommendations,
            followup_actions=followup_actions,
            disclaimers=data.get("disclaimers", []),
            rule_based_findings=rule_based,
            ai_inferences=ai_inferences,
            fallback_used=fallback_used,
            audit_id=audit_id,
        )


output_mapper = OutputMapper()
