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
        zh = item.get("zh") or item.get("category_name") or item.get("name") or item.get("label")
        en = item.get("en") or item.get("category_name") or item.get("name") or item.get("label")
        if not zh:
            zh = f"item_{idx}"
        if not en:
            en = zh
        key = item.get("key") or item.get("category_name") or item.get("name") or f"item_{idx}"
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
        "suggestions": item.get("suggestions") if isinstance(item.get("suggestions"), list) else [],
    }


def normalize_report_json(data: dict) -> dict:
    """Normalize report JSON after parsing — ensures indicators and data.items use canonical format.

    Two normalization passes:
    1. Top-level indicator fields: ``name`` → ``key``, fill missing
       ``label``/``score``/``narrative`` with defaults.
    2. ``data.items`` arrays: transform non-standard shapes
       (``{category_name, percentage}``, ``{name, value}``, etc.) into the
       canonical ``{key, zh, en, value}`` shape that the frontend expects.
    """
    if not isinstance(data, dict):
        return data
    indicators = data.get("indicators")
    if not isinstance(indicators, list):
        return data

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


def validate_report_json(data: dict) -> list[str]:
    """Validate a normalized report JSON dict against the canonical schema.

    Returns a list of human-readable error strings (empty list = valid).
    The canonical schema (after ``normalize_report_json``) requires:

    - ``indicators`` is a non-empty list
    - each indicator has a non-empty ``data.items`` list

    ``overall_score`` is optional (informational) and not strictly required.
    """
    if not isinstance(data, dict):
        return ["报告结果不是有效的 JSON 对象"]

    errors: list[str] = []

    indicators = data.get("indicators")
    if not isinstance(indicators, list) or len(indicators) == 0:
        errors.append("缺少 indicators 数组或为空")
        return errors

    for idx, indicator in enumerate(indicators):
        if not isinstance(indicator, dict):
            errors.append(f"indicator[{idx}] 不是有效对象")
            continue
        # Validate per-indicator required fields (key/label/score/narrative)
        # After normalize_report_json, ``name`` → ``key``, missing score → 3,
        # missing narrative → "". We only hard-fail on structural gaps that
        # normalization cannot fix (missing key/name and missing score).
        key = indicator.get("key") or indicator.get("name")
        if not key:
            errors.append(f"indicator[{idx}] 缺少 key 或 name 字段")
        score = indicator.get("score")
        if score is None or not isinstance(score, (int, float)):
            errors.append(f"indicator[{idx}] 缺少 score 字段或 score 非数字")
        elif not (1 <= score <= 5):
            errors.append(f"indicator[{idx}].score 超出范围 (1-5)")

        data_obj = indicator.get("data")
        if not isinstance(data_obj, dict):
            errors.append(f"indicator[{idx}] 缺少 data 对象")
            continue
        items = data_obj.get("items")
        if not isinstance(items, list) or len(items) == 0:
            errors.append(f"indicator[{idx}].data.items 为空")
            continue

        # P2-7 fix: validate per-item field structure (key, zh, en, value)
        for item_idx, item in enumerate(items):
            if not isinstance(item, dict):
                errors.append(
                    f"indicator[{idx}].data.items[{item_idx}] 不是有效对象"
                )
                continue
            for field in ("key", "zh", "en"):
                if field not in item or not item[field]:
                    errors.append(
                        f"indicator[{idx}].data.items[{item_idx}] 缺少 '{field}' 字段"
                    )
            value = item.get("value")
            if value is None or not isinstance(value, (int, float)):
                errors.append(
                    f"indicator[{idx}].data.items[{item_idx}].value 必须是数字"
                )

    return errors

