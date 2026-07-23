"""Asset-report step-2 JSON parser.

U4 step 3: ``report.step2_json`` is worker-synthesized (not emitted via an
in-graph middleware). The original plan preferred a middleware emission path
(replicating DeerFlow's native custom-event pattern), but
``get_stream_writer()`` is no-op on numina's sync ``stream()`` path
(PatchedChatOpenAI), so the worker synthesizes the event from the final AI
message text instead (see ``_run_asset_report_pipeline`` step 9).

``parse_report_json`` is the shared parser used by the worker (event
synthesis + persistence) and by the import-parse router. It is kept here to
avoid a circular import between the worker and the router.

The deprecated ``AssetReportStep2Middleware`` / ``_extract_ai_content`` were
removed as NO-OP residue (P2 #10): the middleware was never instantiated —
``create_deerflow_client`` is called without a ``middlewares`` argument for
asset-report runs.
"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


def parse_report_json(ai_text: str) -> dict | None:
    """Parse the indicators JSON from the asset-report AI output.

    Tries fenced ```json blocks first, then the bare text, via json_repair
    (tolerant of trailing commas / minor syntax drift). Returns None on failure
    so the caller can skip emitting report.step2_json (plan F8: step2
    incomplete => 0 events). Shared by the worker (in-graph emission) and
    the router (harvest) — kept here to avoid a circular import.
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
