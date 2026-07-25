"""Circuit-breaker gate for AI skill SSE endpoints.

KTD-7 (U4/U5 cleanup): the legacy NDJSON proxy helpers
(``proxy_capability_events`` / ``proxy_agent_first_events`` /
``_call_agent_skill`` / ``_promote_next`` / ``_write_audit``) were deleted —
report and all trigger-skill streams now route through ``stream_run`` agents
(asset-report / import-parse) or lightweight LLM single calls (suggest). The
only remaining live consumer of this module is ``check_circuit_blocked``, used
by ``trigger_generate_events`` (an SSE endpoint) to short-circuit when the
circuit breaker is open.
"""

import json
import logging

from fastapi.responses import StreamingResponse

from apps.backend.app.services.ai_extraction_circuit_service import (
    AIExtractionCircuitService,
)

logger = logging.getLogger(__name__)


def _error_event(code: str, message: str | None = None) -> bytes:
    """Build an SSE ``error`` frame for a skill error.

    The consumer (``useReportStream``) parses SSE frames — ``event: <name>\\n``
    followed by ``data: <json>\\n\\n``. The previous NDJSON form (a bare
    ``{"type":"capability.error",...}\\n`` line with ``media_type=
    application/x-ndjson``) could not be parsed by ``useReportStream`` and left
    the report timeline stuck with no error surfaced when the circuit breaker
    was open. Emitting as an ``error`` event lets the frontend's
    ``event === 'error'`` branch set ``status='error'`` + ``errorMessage``.
    """
    message_map = {
        "extraction_failed": "分析已完成，但结构化数据提取失败",
        "structured_write_failed": "分析已完成，但结果保存失败",
        "agent_stream_error": "智能体响应中断",
        "post_processing_timeout": "处理超时，请稍后重试",
        "quota_exceeded": "AI服务配额已耗尽，请检查API额度或稍后重试",
        "llm_fallback_failed": "分析已完成，但结构化数据提取失败",
    }
    final_message = message or message_map.get(code, code)
    payload = json.dumps({"code": code, "message": final_message})
    return f"event: error\ndata: {payload}\n\n".encode()


def check_circuit_blocked(family_id: int, skill_id: str, db: object) -> StreamingResponse | None:
    """Check if the circuit breaker blocks this skill for the family.

    Returns a StreamingResponse with a single SSE ``error`` frame if blocked,
    or None if the request should proceed normally. The caller
    (``trigger_generate_events``) is an SSE endpoint (``text/event-stream``),
    so the frame is SSE-framed — not NDJSON — so ``useReportStream`` can parse
    it and surface the circuit-open error to the timeline.
    """
    blocked, reason = AIExtractionCircuitService.is_open(family_id, skill_id, db)
    if not blocked:
        return None

    async def _blocked_stream():
        yield _error_event(f"circuit_blocked:{reason}", message="服务暂时不可用，请稍后重试")

    return StreamingResponse(
        _blocked_stream(),
        media_type="text/event-stream",
    )
