"""LLM JSON validate-repair cycle.

Shared module for the validate→repair pattern used by all agent workers that
parse structured JSON from LLM output. Consolidates validators, LLM repair
functions, and the generic retry loop into a single location.

All agents that produce LLM→JSON→frontend output should use ``run_json_repair_loop``
to validate and repair their JSON output before emitting result events.

Pattern:
1. Parse LLM output text via ``parse_report_json`` (from asset_report_middleware).
2. Validate parsed dict against schema-specific validator.
3. On validation failure, retry via LLM repair (≤3 attempts, 120s budget).
4. Emit result event on success, error event on persistent failure.

Validators:
- ``validate_report_json`` — asset-report indicators schema
- ``validate_coach_json`` — finance-coach suggestions schema
- ``validate_wish_advice_json`` — wish-advice redistribution schema

Generic helper:
- ``_llm_repair_json`` — handles LLM client creation and repair prompt assembly

Per-schema repair functions (thin wrappers around ``_llm_repair_json``):
- ``_repair_report_json_via_llm``
- ``_repair_coach_json_via_llm``
- ``_repair_wish_advice_json_via_llm``

Generic loop:
- ``run_json_repair_loop`` — shared validate→repair loop used by all 3 agents
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable

from .asset_report_middleware import parse_report_json

logger = logging.getLogger(__name__)

# Re-export parse_report_json for callers that want a single import point.
__all__ = [
    "parse_report_json",
    "validate_report_json",
    "validate_coach_json",
    "validate_wish_advice_json",
    "run_json_repair_loop",
]


# ---------------------------------------------------------------------------
# Validators
# ---------------------------------------------------------------------------

_VALID_SEVERITIES = {"high", "medium", "low"}
_VALID_TARGET_TYPES = {"liability", "asset", "wish"}
_COACH_REQUIRED_FIELDS = (
    "id",
    "severity",
    "title",
    "action",
    "target_type",
    "target_id",
    "cta_label",
)
_WISH_ADVICE_REQUIRED_TOP_LEVEL = (
    "primary_wish_id",
    "reason",
    "suggested_monthly",
    "redistribution",
)


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

        for item_idx, item in enumerate(items):
            if not isinstance(item, dict):
                errors.append(f"indicator[{idx}].data.items[{item_idx}] 不是有效对象")
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


def validate_coach_json(data: dict | None) -> list[str]:
    """Validate parsed finance-coach JSON against the frontend FinanceSuggestion schema.

    Returns a list of human-readable error strings (empty list = valid).
    The frontend (FinanceCoachCard.vue) filters each suggestion requiring:
    ``id``, ``severity`` in {high, medium, low}, ``title``, ``action``,
    ``target_type`` in {liability, asset, wish}, ``target_id``, ``cta_label``.
    """
    if not isinstance(data, dict):
        return ["coach JSON 不是有效的对象"]

    suggestions = data.get("suggestions")
    if not isinstance(suggestions, list):
        return ["缺少 suggestions 数组"]

    if len(suggestions) == 0:
        return []  # Empty is valid (no significant issues)

    errors: list[str] = []
    for idx, s in enumerate(suggestions):
        if not isinstance(s, dict):
            errors.append(f"suggestions[{idx}] 不是有效对象")
            continue
        for field in _COACH_REQUIRED_FIELDS:
            val = s.get(field)
            if not val:  # all coach fields are strings — no numeric carve-out needed
                errors.append(f"suggestions[{idx}] 缺少必填字段 '{field}'")
        sev = s.get("severity")
        if sev is not None and sev not in _VALID_SEVERITIES:
            errors.append(
                f"suggestions[{idx}].severity 必须是 high/medium/low，实际: {sev}"
            )
        tt = s.get("target_type")
        if tt is not None and tt not in _VALID_TARGET_TYPES:
            errors.append(
                f"suggestions[{idx}].target_type 必须是 liability/asset/wish，实际: {tt}"
            )

    return errors


def validate_wish_advice_json(data: dict | None) -> list[str]:
    """Validate wish-advice JSON against the W4 advice schema.

    Returns a list of human-readable error strings (empty list = valid).
    Schema: ``{primary_wish_id, reason, suggested_monthly, redistribution[]}``
    where each redistribution item has ``{wish_id, suggested_amount, note}``.
    """
    if not isinstance(data, dict):
        return ["wish-advice JSON 不是有效的对象"]

    errors: list[str] = []

    for field in _WISH_ADVICE_REQUIRED_TOP_LEVEL:
        if field not in data:
            errors.append(f"缺少必填字段 '{field}'")

    suggested_monthly = data.get("suggested_monthly")
    if suggested_monthly is not None and not isinstance(
        suggested_monthly, (int, float)
    ):
        errors.append("suggested_monthly 必须是数字")
    elif isinstance(suggested_monthly, (int, float)) and suggested_monthly < 0:
        errors.append("suggested_monthly 必须 ≥ 0")

    redistribution = data.get("redistribution")
    if redistribution is not None and not isinstance(redistribution, list):
        errors.append("redistribution 必须是数组")
    elif isinstance(redistribution, list):
        for idx, item in enumerate(redistribution):
            if not isinstance(item, dict):
                errors.append(f"redistribution[{idx}] 不是有效对象")
                continue
            if not item.get("wish_id"):
                errors.append(f"redistribution[{idx}] 缺少必填字段 'wish_id'")
            amount = item.get("suggested_amount")
            if amount is None or not isinstance(amount, (int, float)):
                errors.append(f"redistribution[{idx}].suggested_amount 必须是数字")
            elif isinstance(amount, (int, float)) and amount < 0:
                errors.append(f"redistribution[{idx}].suggested_amount 必须 ≥ 0")

    return errors


# ---------------------------------------------------------------------------
# Generic LLM repair helper
# ---------------------------------------------------------------------------


async def _llm_repair_json(
    ai_text: str,
    validation_errors: list[str],
    repair_prompt: str,
    provider: dict | None,
) -> dict | None:
    """Repair invalid LLM JSON output via a lightweight LLM call.

    Constructs a repair LLM client from the family's provider credentials,
    appends the original output fragment and language-preservation instruction
    to the schema-specific ``repair_prompt``, and re-parses the result.

    Args:
        ai_text: The original LLM output text (last 4000 chars used as reference).
        validation_errors: Errors from the schema validator.
        repair_prompt: Schema-specific repair prompt (describes expected JSON structure).
        provider: Family's AI provider config dict (ai_provider, api_key, etc.).

    Returns:
        Parsed dict on success, None if provider unavailable or repair fails.
    """
    if not provider:
        return None
    try:
        from apps.agent.core.llm import get_llm_client

        llm = get_llm_client(
            provider=provider.get("ai_provider", ""),
            api_key=provider.get("api_key", ""),
            model_id=provider.get("ai_model_id", ""),
            base_url=provider.get("ai_base_url"),
            timeout=90.0,
        )
        error_summary = "; ".join(validation_errors[:5])
        full_prompt = (
            f"{repair_prompt}\n"
            f"Validation errors: {error_summary}\n\n"
            "IMPORTANT: Preserve the EXACT SAME language as the original output. "
            "This is a structural repair — do NOT translate text fields.\n\n"
            f"Original output fragment (for reference):\n{ai_text[-4000:]}"
        )
        repaired_text = await llm.complete(full_prompt, max_tokens=6000)
        return parse_report_json(repaired_text)
    except (ValueError, KeyError, TypeError) as exc:
        logger.warning(
            "[_llm_repair_json] parse failed: %s: %s", type(exc).__name__, exc
        )
        return None
    except Exception as exc:
        logger.warning(
            "[_llm_repair_json] repair failed: %s: %s", type(exc).__name__, exc
        )
        return None


# ---------------------------------------------------------------------------
# Per-schema repair functions
# ---------------------------------------------------------------------------

_REPORT_REPAIR_PROMPT = (
    "The family asset report JSON you previously output failed validation.\n"
    "Please re-output a valid JSON that strictly conforms to the following "
    "structure (do NOT include any markdown code blocks, explanations, or "
    "extra content):\n"
    '{"overall_score": <number>, "indicators": ['
    '{"key": "<string>", "label": "<string>", "score": <1-5>, '
    '"narrative": "<string>", "data": {"items": ['
    '{"key": "<string>", "zh": "<string>", "en": "<string>", "value": <number>}'
    "]}}]}\n\n"
    "Requirements: indicators must be non-empty; each indicator MUST have "
    '"key", "label", "score" (1-5), and "narrative" fields; each indicator '
    "must have a non-empty data.items array; value must be a number. "
    'Use "key" NOT "name" for the indicator identifier. Output ONLY the JSON itself.'
)


async def _repair_report_json_via_llm(
    ai_text: str,
    validation_errors: list[str],
    provider: dict | None,
) -> dict | None:
    """Repair an invalid asset-report JSON via LLM.

    Phase 4B (T13b): issues a single follow-up completion asking the LLM to
    re-emit a corrected indicators JSON.
    """
    return await _llm_repair_json(
        ai_text, validation_errors, _REPORT_REPAIR_PROMPT, provider
    )


_COACH_REPAIR_PROMPT = (
    "The finance coach JSON you previously output failed validation.\n"
    "Please re-output a valid JSON that strictly conforms to the following "
    "structure (do NOT include any markdown code blocks, explanations, or "
    "extra content):\n"
    '{"suggestions": [\n'
    '  {"id": "<string>", "severity": "high|medium|low", '
    '"title": "<≤20 chars>", "action": "<≤50 chars>", '
    '"target_type": "liability|asset|wish", '
    '"target_id": "<entity id string>", "cta_label": "<≤8 chars>"}\n'
    "]}\n\n"
    "Requirements:\n"
    "- suggestions must have at most 3 items\n"
    "- severity MUST be one of: high, medium, low (NOT numbers)\n"
    "- target_type MUST be one of: liability, asset, wish\n"
    "- target_id MUST be the entity's numeric id string from the snapshot\n"
    "- action: a specific, actionable suggestion referencing real data\n"
    "- cta_label: short button label (≤8 chars)"
)


async def _repair_coach_json_via_llm(
    ai_text: str,
    validation_errors: list[str],
    provider: dict | None,
) -> dict | None:
    """Repair an invalid finance-coach JSON via LLM.

    Mirrors ``_repair_report_json_via_llm``: issues a single follow-up
    completion asking the LLM to re-emit suggestions conforming to the
    frontend ``FinanceSuggestion`` schema.
    """
    return await _llm_repair_json(
        ai_text, validation_errors, _COACH_REPAIR_PROMPT, provider
    )


_WISH_ADVICE_REPAIR_PROMPT = (
    "The wish-advice JSON you previously output failed validation.\n"
    "Please re-output a valid JSON that strictly conforms to the following "
    "structure (do NOT include any markdown code blocks, explanations, or "
    "extra content):\n"
    "{\n"
    '  "primary_wish_id": "<wish id string>",\n'
    '  "reason": "<≤100 chars, data-based reason>",\n'
    '  "suggested_monthly": <number ≥ 0>,\n'
    '  "redistribution": [\n'
    '    {"wish_id": "<wish id string>", "suggested_amount": <number ≥ 0>, '
    '"note": "<short note>"}\n'
    "  ]\n"
    "}\n\n"
    "Requirements:\n"
    "- suggested_monthly = sum of all redistribution items' suggested_amount\n"
    "- suggested_amount MUST be ≥ 0\n"
    "- wish_id MUST be the wish's numeric id string from the snapshot\n"
    "- reason must reference specific data (target dates, gaps, monthly savings)"
)


async def _repair_wish_advice_json_via_llm(
    ai_text: str,
    validation_errors: list[str],
    provider: dict | None,
) -> dict | None:
    """Repair an invalid wish-advice JSON via LLM.

    Mirrors ``_repair_coach_json_via_llm``: issues a single follow-up
    completion asking the LLM to re-emit redistribution advice conforming
    to the W4 advice schema.
    """
    return await _llm_repair_json(
        ai_text, validation_errors, _WISH_ADVICE_REPAIR_PROMPT, provider
    )


# ---------------------------------------------------------------------------
# Generic validate-repair loop
# ---------------------------------------------------------------------------


async def run_json_repair_loop(
    parsed: dict | None,
    ai_text: str,
    *,
    validator: Callable[[dict], list[str]],
    repair_fn: Callable[[str, list[str]], Awaitable[dict | None]],
    publish_retry_event: Callable[[int], Awaitable[None]],
    app_name: str,
    max_retries: int = 3,
    budget_seconds: int = 120,
) -> tuple[dict | None, int]:
    """Run the validate→repair loop for LLM JSON output.

    Validates the parsed JSON, and on failure, retries repair via LLM up to
    ``max_retries`` times within ``budget_seconds``. Emits a retry event via
    ``publish_retry_event`` before each repair attempt (keeps SSE alive and
    lets the frontend show repair progress).

    Args:
        parsed: The initially parsed JSON dict (may be None if parsing failed).
        ai_text: The original LLM output text (passed to repair_fn for reference).
        validator: Schema validator; returns empty list if valid.
        repair_fn: Async callable(ai_text, errors) → repaired dict or None.
        publish_retry_event: Async callable(attempt) to emit a bridge retry event.
        app_name: Caller name for log messages.
        max_retries: Maximum repair attempts (default 3).
        budget_seconds: Total timeout budget (default 120s).

    Returns:
        (final_parsed_dict, repair_count) — repair_count is 0 if first try valid.
    """
    # When parsed is None (total parse failure), still attempt LLM repair.
    # The repair LLM receives the raw ai_text and can produce valid JSON from
    # scratch. Previously this returned (None, 0) immediately, bypassing the
    # entire repair mechanism — the user-expected validate→repair→retry cycle
    # never activated for unparseable output (e.g. agent recursion limit hit).
    validation_errors = ["无法解析报告 JSON"] if parsed is None else validator(parsed)
    retry_count = 0

    try:
        async with asyncio.timeout(budget_seconds):
            while validation_errors and retry_count < max_retries:
                retry_count += 1
                logger.warning(
                    "[%s] JSON invalid, retry=%d/%d errors=%s",
                    app_name,
                    retry_count,
                    max_retries,
                    validation_errors[:3],
                )
                await publish_retry_event(retry_count)
                repaired = await repair_fn(ai_text, validation_errors)
                if repaired is not None:
                    parsed = repaired
                    validation_errors = validator(repaired)
                else:
                    logger.warning(
                        "[%s] repair returned None, retry=%d", app_name, retry_count
                    )
                    break
    except TimeoutError:
        logger.error(
            "[%s] JSON repair timed out after %d attempts",
            app_name,
            retry_count,
        )

    return parsed, retry_count
