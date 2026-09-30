"""Asset-report step-2 JSON parser.

U4 step 3: ``report.step2_json`` is worker-synthesized (not emitted via an
in-graph middleware). The original plan preferred a middleware emission path
(replicating DeerFlow's native custom-event pattern), but
``get_stream_writer()`` is no-op on numina's sync ``stream()`` path
(PatchedChatOpenAI), so the worker synthesizes the event from the final AI
message text instead (see ``_run_asset_report_agent`` step 9).

``parse_report_json`` is the shared parser used by the worker (event
synthesis + persistence) and by the import-parse router. It is kept here to
avoid a circular import between the worker and the router.

The deprecated ``AssetReportStep2Middleware`` / ``_extract_ai_content`` were
removed as NO-OP residue (P2 #10): the middleware was never instantiated —
``create_deerflow_client`` is called without a ``middlewares`` argument for
asset-report runs.
"""

from __future__ import annotations

from packages.core.logging import get_logger

logger = get_logger(__name__)


def normalize_indicator_data_items(items: list) -> list[dict]:
    """Normalize non-standard data.items formats to canonical {key, zh, en, value}.

    The LLM may output alternative shapes such as:
    - ``{category_name, percentage}`` (from the asset-report pilot)
    - ``{name, value}`` with no labels
    - ``{label, value}`` with no bilingual labels

    All are mapped to the canonical format so the frontend can rely on a single
    rendering path. Labels that can't be bilingualized get ``zh = en = label``.
    """
    result: list[dict] = []
    for idx, item in enumerate(items):
        if not isinstance(item, dict):
            continue
        # Extract label (prefer explicit bilingual, fall back to generic name fields)
        zh = (
            item.get("zh")
            or item.get("category_name")
            or item.get("name")
            or item.get("label")
        )
        en = (
            item.get("en")
            or item.get("category_name")
            or item.get("name")
            or item.get("label")
        )
        if not zh:
            zh = f"item_{idx}"
        if not en:
            en = zh
        key = (
            item.get("key")
            or item.get("category_name")
            or item.get("name")
            or f"item_{idx}"
        )
        if isinstance(key, str):
            # Normalize to snake_case key for consistency
            key = key.lower().replace(" ", "_").replace("-", "_")
        value = item.get("value") or item.get("percentage") or item.get("amount") or 0
        try:
            value = float(value)
        except (TypeError, ValueError):
            value = 0
        result.append({"key": str(key), "zh": str(zh), "en": str(en), "value": value})
    return result


def normalize_indicator(item: dict, idx: int) -> dict:
    """Normalize a single indicator to the canonical {key, label, score, narrative, data} shape.

    The LLM may use ``name`` instead of ``key``, omit ``label``/``score``/
    ``narrative``, or use ``description`` instead of ``narrative``. This
    function fills in defaults so the frontend can rely on a single shape.
    """
    key = item.get("key") or item.get("name") or f"indicator_{idx}"
    if isinstance(key, str):
        key = key.lower().replace(" ", "_").replace("-", "_")
    label = item.get("label") or item.get("name") or key
    score = item.get("score")
    if score is None or not isinstance(score, (int, float)):
        score = 3  # default to middle score
    score = max(1, min(5, int(score)))
    narrative = item.get("narrative") or item.get("description") or ""
    data = item.get("data") if isinstance(item.get("data"), dict) else {"items": []}
    return {
        "key": key,
        "label": str(label),
        "score": score,
        "narrative": str(narrative),
        "data": data,
        "suggestions": item.get("suggestions")
        if isinstance(item.get("suggestions"), list)
        else [],
    }


def _synthesize_summary(indicators: list[dict]) -> str:
    """Synthesize a short markdown summary from indicator narratives when the LLM
    omitted the ``summary`` field. Uses each indicator's label + score + the
    first sentence of its narrative to produce a coherent overview."""
    if not indicators:
        return ""
    parts: list[str] = []
    for ind in indicators:
        label = ind.get("label") or ind.get("key") or "指标"
        score = ind.get("score", 0)
        narrative = ind.get("narrative") or ""
        # Take the first line/sentence (up to ~80 chars) for brevity
        first_line = narrative.split("\n")[0].strip()
        if len(first_line) > 80:
            first_line = first_line[:77] + "…"
        stars = "★" * min(score, 5) + "☆" * max(0, 5 - score)
        parts.append(f"- **{label}**（{stars}）{first_line}")
    return "\n".join(parts)


def _compute_completeness_score(indicators: list[dict]) -> float:
    """Derive a data-completeness proxy from indicator coverage when the LLM
    omitted ``data_completeness_score``.

    Heuristic: 10 points per indicator with valid data.items (max 7 indicators
    = 70 base) + 30 points if all indicators have suggestions (coverage depth).
    This produces a reasonable 0-100 score without needing the original family
    data (which is not available at normalization time)."""
    if not indicators:
        return 0.0
    score = 0.0
    # Base: 10 points per indicator with non-empty data.items
    for ind in indicators:
        data_obj = ind.get("data")
        if isinstance(data_obj, dict):
            items = data_obj.get("items")
            if isinstance(items, list) and len(items) > 0:
                score += 10.0
    # Cap base at 70 (7 indicators × 10)
    score = min(score, 70.0)
    # Bonus: 30 points if all indicators have suggestions
    all_have_suggestions = all(
        isinstance(ind.get("suggestions"), list) and len(ind["suggestions"]) > 0
        for ind in indicators
    )
    if all_have_suggestions:
        score += 30.0
    return round(score, 1)


def normalize_report_json(data: dict) -> dict:
    """Normalize report JSON after parsing — ensures indicators and data.items use canonical format.

    Two normalization passes:
    1. Top-level indicator fields: ``name`` → ``key``, fill missing
       ``label``/``score``/``narrative`` with defaults.
    2. ``data.items`` arrays: transform non-standard shapes
       (``{category_name, percentage}``, ``{name, value}``, etc.) into the
       canonical ``{key, zh, en, value}`` shape that the frontend expects.

    Safety-net defaults (KTD-8 hardening): when the LLM omits critical
    fields, derive them from available indicator data so the user always
    sees a meaningful report:
    - ``summary`` ← synthesized from indicator narratives
    - ``data_completeness_score`` ← computed from indicator coverage
    - per-indicator ``suggestions`` ← ensured as empty list (not missing)
    """
    if not isinstance(data, dict):
        return data
    indicators = data.get("indicators")
    if not isinstance(indicators, list):
        return data

    # Safety-net: fill missing top-level fields BEFORE indicator normalization
    # so downstream code can rely on their presence.
    if not data.get("summary"):
        data["summary"] = _synthesize_summary(indicators)
    if data.get("data_completeness_score") is None:
        data["data_completeness_score"] = _compute_completeness_score(indicators)

    for idx, indicator in enumerate(indicators):
        if not isinstance(indicator, dict):
            continue

        # Pass 1: normalize top-level indicator fields
        indicators[idx] = normalize_indicator(indicator, idx)

        # Pass 2: normalize data.items (existing logic)
        data_obj = indicator.get("data")
        if not isinstance(data_obj, dict):
            continue
        items = data_obj.get("items")
        if isinstance(items, list) and items:
            first = items[0]
            if isinstance(first, dict) and "zh" in first and "en" in first:
                continue  # Already canonical, skip
            # Non-standard format → normalize
            indicators[idx]["data"]["items"] = normalize_indicator_data_items(items)
    return data


def parse_report_json(ai_text: str) -> dict | None:
    """Parse the indicators JSON from the asset-report AI output.

    Tries fenced ```json blocks first, then the bare text, via json_repair
    (tolerant of trailing commas / minor syntax drift). Returns None on failure
    so the caller can skip emitting report.step2_json (plan F8: step2
    incomplete => 0 events). Shared by the worker (in-graph emission) and
    the router (harvest) — kept here to avoid a circular import.

    The AI output may contain multiple JSON blocks (e.g. tool results, intermediate
    steps). We prefer the one with the "indicators" key (canonical asset report schema).
    If none has "indicators", fall back to the first valid dict.

    On success the parsed dict is passed through ``normalize_report_json``
    to ensure ``data.items`` uses the canonical ``{key, zh, en, value}``
    format regardless of the LLM's output shape.
    """
    if not ai_text:
        return None
    import re

    import json_repair

    fence_re = re.compile(r"```(?:json)?\s*(\{.*?\})\s*```", re.DOTALL)
    candidates: list[str] = [m.group(1) for m in fence_re.finditer(ai_text)]
    candidates.append(ai_text)

    first_valid: dict | None = None
    for cand in candidates:
        try:
            parsed = json_repair.repair_json(cand, return_objects=True)
            if isinstance(parsed, dict):
                # Prefer JSON with "indicators" key (canonical asset report schema)
                if "indicators" in parsed:
                    return normalize_report_json(parsed)
                # Otherwise remember the first valid dict as fallback
                if first_valid is None:
                    first_valid = parsed
        except Exception:
            continue

    # No JSON with "indicators" found — return the first valid dict (if any)
    if first_valid is not None:
        return normalize_report_json(first_valid)
    return None
