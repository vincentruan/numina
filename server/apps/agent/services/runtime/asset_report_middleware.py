"""Asset-report step-2 middleware: emit report.step2_json via get_stream_writer.

U4 step 3 (preferred middleware emission path, replicating DeerFlow's native
custom-event pattern — see safety_finish_reason_middleware.py:183 and
llm_error_handling_middleware.py:304). Replaces the worker-synthesized
report.step2_json emission: the middleware fires the custom event from inside
the graph (where get_stream_writer() works natively on the async node path),
and the worker forwards it unchanged via its `custom` frame handling.

The middleware inspects each model response's AI message content; when a
fenced ```json block (or bare JSON object) parses successfully, it emits
exactly one report.step2_json event with the parsed payload. Tool-call
messages (step 1) carry no such block, so only the final step-2 AI message
triggers emission — no dedup needed.
"""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable
from typing import Any

from langchain.agents.middleware import AgentMiddleware

logger = logging.getLogger(__name__)


def parse_report_json(ai_text: str) -> dict | None:
    """Parse the indicators JSON from the asset-report AI output.

    Tries fenced ```json blocks first, then the bare text, via json_repair
    (tolerant of trailing commas / minor syntax drift). Returns None on failure
    so the caller can skip emitting report.step2_json (plan F8: step2
    incomplete => 0 events). Shared by the middleware (in-graph emission) and
    the worker (persistence) — kept here to avoid a circular import.
    """
    if not ai_text:
        return None
    import re

    import json_repair

    fence_re = re.compile(r"```(?:json)?\s*(\{.*?\})\s*```", re.DOTALL)
    candidates: list[str] = [m.group(1) for m in fence_re.finditer(ai_text)]
    candidates.append(ai_text)
    for cand in candidates:
        try:
            parsed = json_repair.repair_json(cand, return_objects=True)
            if isinstance(parsed, dict):
                return parsed
        except Exception:
            continue
    return None


class AssetReportStep2Middleware(AgentMiddleware):
    """Emit ``report.step2_json`` when the asset-report LLM outputs its JSON.

    Attached only to the asset-report adapter (via DeerFlowClient middlewares).
    Best-effort: get_stream_writer() is no-op on the ThreadPoolExecutor sync-
    tool path (see sync_tool_patch.py:211), but the async graph node / model-
    call path works — which is exactly where awrap_model_call runs.
    """

    async def awrap_model_call(
        self,
        request: Any,
        handler: Callable[[Any], Awaitable[Any]],
    ) -> Any:
        response = await handler(request)
        try:
            content = _extract_ai_content(response)
            if content:
                payload = parse_report_json(content)
                if payload is not None:
                    from langgraph.config import get_stream_writer

                    get_stream_writer()(
                        {"type": "report.step2_json", "payload": payload}
                    )
        except Exception:
            logger.debug(
                "[asset-report-step2] emit failed (best-effort, skipped)",
                exc_info=True,
            )
        return response


def _extract_ai_content(response: Any) -> str:
    """Best-effort extraction of the AI message text content from a model response.

    DeerFlow's ModelResponse/ModelCallResult wraps an AIMessage; the exact shape
    varies across langchain versions, so try the common attribute paths.
    """
    # AIMessage-like direct content
    content = getattr(response, "content", None)
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        # content blocks: join text parts
        parts = [p for p in content if isinstance(p, str)]
        if parts:
            return "".join(parts)
    # ModelResponse wrapping a message
    message = getattr(response, "message", None)
    if message is not None:
        mcontent = getattr(message, "content", None)
        if isinstance(mcontent, str):
            return mcontent
        if isinstance(mcontent, list):
            parts = [p for p in mcontent if isinstance(p, str)]
            if parts:
                return "".join(parts)
    return ""
