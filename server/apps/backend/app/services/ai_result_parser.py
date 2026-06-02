"""AI capability result parser — extract structured data from LLM answer text.

Strategy:
1. Regex extraction: Look for `<!-- STRUCTURED_DATA ... -->` delimiter, then
   markdown ```json fence, then bare balanced JSON at tail.
2. JSON repair: Use json_repair to handle malformed JSON (thinking tags,
   markdown fences, trailing commas, etc.)
3. LLM fallback: Use cheapest available model from family's provider config
   to coerce the answer into JSON.
"""

import asyncio
import json
import logging
import re
from typing import Any

from json_repair import repair_json
from sqlalchemy.orm import Session

from apps.backend.app.models.ai_provider_config import AIProviderConfig
from apps.backend.app.services.ai_crypto import decrypt_api_key

logger = logging.getLogger(__name__)

LLM_FALLBACK_MAX_TOKENS = 800
LLM_FALLBACK_TEMPERATURE = 0.1
LLM_FALLBACK_TIMEOUT_SECONDS = 5.0

# Regex patterns for structured data extraction (priority order)
# 1. HTML comment: <!-- STRUCTURED_DATA ... -->
STRUCTURED_DATA_PATTERN = re.compile(
    r'<!-- STRUCTURED_DATA\s*\n?(.*?)\n?\s*-->',
    re.DOTALL
)
# 2. Markdown JSON fence: ```json ... ```
JSON_FENCE_PATTERN = re.compile(
    r'```json\s*\n(.*?)\n\s*```',
    re.DOTALL
)

# Expected schemas per capability
CAPABILITY_SCHEMAS = {
    "alerts": {
        "type": "array",
        "items": {
            "type": "object",
            "required": ["asset_name", "alert_type", "severity"],
            "properties": {
                "asset_id": {"type": "integer"},
                "asset_name": {"type": "string"},
                "alert_type": {"type": "string", "enum": ["aging", "high_maintenance", "idle_cost"]},
                "severity": {"type": "string", "enum": ["low", "medium", "high"]},
                "suggestion": {"type": "string"},
                "remaining_life_days": {"type": "integer"},
                "daily_cost": {"type": "number"},
            },
        },
    },
    "disposal": {
        "type": "array",
        "items": {
            "type": "object",
            "required": ["asset_name", "inefficiency_score"],
            "properties": {
                "asset_id": {"type": "integer"},
                "asset_name": {"type": "string"},
                "category_name": {"type": "string"},
                "inefficiency_score": {"type": "integer", "minimum": 0, "maximum": 100},
                "suggested_channel": {"type": "string"},
                "estimated_resale_range": {"type": "string"},
                "suggestion": {"type": "string"},
                "daily_cost": {"type": "number"},
            },
        },
    },
    "spending_leak": {
        "type": "array",
        "items": {
            "type": "object",
            "required": ["asset_name", "leak_type", "severity"],
            "properties": {
                "asset_id": {"type": "integer"},
                "asset_name": {"type": "string"},
                "leak_type": {"type": "string", "enum": ["high_idle_cost", "redundant", "high_maintenance"]},
                "severity": {"type": "string", "enum": ["low", "medium", "high"]},
                "estimated_annual_waste": {"type": "number"},
                "suggestion": {"type": "string"},
            },
        },
    },
    "report": {
        "type": "object",
        "required": ["overall_score"],
        "properties": {
            "overall_score": {"type": "integer", "minimum": 0, "maximum": 100},
            "data_completeness_score": {"type": "number"},
            "narrative": {"type": "string"},
            "sections": {"type": "object"},
        },
    },
    "allocation": {
        "type": "object",
        "required": ["has_significant_drift"],
        "properties": {
            "has_significant_drift": {"type": "boolean"},
            "narrative": {"type": "string"},
            "drifts": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "category": {"type": "string"},
                        "target_pct": {"type": "number"},
                        "current_pct": {"type": "number"},
                        "drift": {"type": "number"},
                        "exceeds_threshold": {"type": "boolean"},
                    },
                },
            },
        },
    },
    "liability": {
        "type": "object",
        "required": ["has_liabilities"],
        "properties": {
            "has_liabilities": {"type": "boolean"},
            "total_remaining": {"type": "number"},
            "total_monthly_payment": {"type": "number"},
            "liability_count": {"type": "integer"},
            "narrative": {"type": "string"},
            "recommended_strategy": {"type": "string", "enum": ["avalanche", "snowball", "hybrid"]},
            "strategies": {"type": "array"},
        },
    },
}


def _extract_bare_json(answer_text: str) -> str | None:
    """Find the longest balanced JSON object/array in the text.

    Scans all `{` and `[` openers from left to right, returning the longest
    balanced match. Tracks string boundaries so brackets inside string literals
    do not corrupt depth counting.
    """
    if not answer_text:
        return None

    best: str | None = None
    for i, ch in enumerate(answer_text):
        if ch in ('{', '['):
            block = _balanced_walk(answer_text, i)
            if block is not None and (best is None or len(block) > len(best)):
                best = block
    return best


def _balanced_walk(text: str, start: int) -> str | None:
    """Walk from `start` forward, returning the balanced substring or None."""
    open_ch = text[start]
    close_ch = ']' if open_ch == '[' else '}'
    depth = 0
    in_string = False
    escape = False
    for i in range(start, len(text)):
        ch = text[i]
        if escape:
            escape = False
            continue
        if ch == '\\' and in_string:
            escape = True
            continue
        if ch == '"':
            in_string = not in_string
            continue
        if in_string:
            continue
        if ch == open_ch:
            depth += 1
        elif ch == close_ch:
            depth -= 1
            if depth == 0:
                return text[start:i + 1]
    return None


def _extract_structured_block(answer_text: str) -> tuple[str | None, str]:
    """Extract a structured JSON block from answer text using three carriers.

    Priority order:
    1. ``<!-- STRUCTURED_DATA ... -->`` HTML comment (current protocol)
    2. ```` ```json ... ``` ```` markdown fence
    3. Bare JSON at tail (balanced bracket walk)

    Returns:
        (block_str, method_label) where method_label is one of:
        ``regex_html`` | ``regex_fence`` | ``regex_bare`` | ``regex_failed``.
    """
    match = STRUCTURED_DATA_PATTERN.search(answer_text)
    if match:
        return match.group(1).strip(), "regex_html"

    match = JSON_FENCE_PATTERN.search(answer_text)
    if match:
        return match.group(1).strip(), "regex_fence"

    bare = _extract_bare_json(answer_text)
    if bare is not None:
        return bare, "regex_bare"

    return None, "regex_failed"


def _validate_json(data: Any, capability: str) -> bool:
    """Validate parsed JSON against expected schema (basic check)."""
    schema = CAPABILITY_SCHEMAS.get(capability)
    if not schema:
        return True  # Unknown capability, skip validation

    if schema["type"] == "array":
        if not isinstance(data, list):
            return False
        # Check first item has required fields
        if data:
            required = schema["items"].get("required", [])
            if not all(k in data[0] for k in required):
                return False
    elif schema["type"] == "object":
        if not isinstance(data, dict):
            return False
        required = schema.get("required", [])
        if not all(k in data for k in required):
            return False

    return True


async def parse_capability_result(
    capability: str,
    answer_text: str,
    family_id: int,
    db: Session,
) -> tuple[list[dict] | dict | None, str]:
    """Parse structured results from LLM answer text.

    Args:
        capability: One of alerts, disposal, spending_leak, report, allocation, liability
        answer_text: Full LLM response text
        family_id: Family ID for LLM fallback (fetches provider config)
        db: Database session

    Returns:
        (data, method) where:
        - data: parsed structured data or None if extraction fails
        - method: extraction method label for audit
    """
    # Step 1: Regex extraction (three carriers)
    block, method = _extract_structured_block(answer_text)
    if block:
        try:
            # Use json_repair for robust parsing - handles malformed JSON
            # from LLM output (thinking tags, markdown fences, trailing commas, etc)
            data = repair_json(block, return_objects=True)
            # Type guard: repair_json may return str on partial failure
            if not isinstance(data, (dict, list)):
                logger.warning(f"[{capability}] repair_json returned {type(data).__name__}, expected dict/list")
                data = None
            if data is not None and _validate_json(data, capability):
                logger.info(f"[{capability}] regex extraction succeeded via {method}, got {len(data) if isinstance(data, list) else 1} items")
                return data, method
            else:
                logger.warning(f"[{capability}] regex extracted JSON via {method} but validation failed")
        except (ValueError, TypeError) as e:
            logger.warning(f"[{capability}] regex found block via {method} but JSON repair failed: {e}")

    # Step 2: LLM fallback
    fallback_data = await _llm_fallback_extract(capability, answer_text, family_id, db)
    if fallback_data is not None:
        return fallback_data, "llm_fallback_hit"

    logger.warning(f"[{capability}] structured data extraction failed, no results persisted")
    return None, "failed"


def _build_extraction_prompt(capability: str, answer_text: str) -> str:
    schema = CAPABILITY_SCHEMAS.get(capability, {})
    schema_str = json.dumps(schema, ensure_ascii=False, indent=2)
    truncated = answer_text[:3000]
    return (
        f"以下是 {capability} 分析文本，请提取其中的结构化信息为 JSON。\n"
        f"Schema：\n{schema_str}\n\n"
        f"分析文本：\n{truncated}\n\n"
        f"仅输出 JSON，不输出任何解释。"
    )


async def _llm_fallback_extract(
    capability: str,
    answer_text: str,
    family_id: int,
    db: Session,
) -> list[dict] | dict | None:
    """Use lightweight LLM to extract structured data from answer text.

    Picks family's cheapest active provider (by display_order ASC NULLS LAST),
    calls LLM with extraction prompt under a 5s timeout, parses and validates.
    Returns None on any failure.
    """
    configs = (
        db.query(AIProviderConfig)
        .filter(
            AIProviderConfig.family_id == family_id,
            AIProviderConfig.api_key_encrypted.isnot(None),
            AIProviderConfig.is_active.is_(True),
        )
        .order_by(AIProviderConfig.display_order.asc().nulls_last())
        .all()
    )

    if not configs:
        logger.warning(f"[{capability}] LLM fallback: no active provider for family {family_id}")
        return None

    config = configs[0]
    api_key = decrypt_api_key(config.api_key_encrypted)
    if not api_key:
        logger.warning(f"[{capability}] LLM fallback: could not decrypt API key")
        return None

    prompt = _build_extraction_prompt(capability, answer_text)

    try:
        raw = await asyncio.wait_for(
            _call_llm(
                provider=config.provider,
                api_key=api_key,
                model_id=config.model_id or "gpt-4o-mini",
                base_url=config.base_url,
                prompt=prompt,
            ),
            timeout=LLM_FALLBACK_TIMEOUT_SECONDS,
        )
    except TimeoutError:
        logger.warning(f"[{capability}] LLM fallback timed out after {LLM_FALLBACK_TIMEOUT_SECONDS}s")
        return None
    except Exception as e:
        logger.warning(f"[{capability}] LLM fallback call failed: {e}")
        return None

    if not raw:
        return None

    cleaned = _strip_markdown_fence(raw)

    try:
        # Use json_repair for robust parsing
        data = repair_json(cleaned, return_objects=True)
        # Type guard: repair_json may return str on partial failure
        if not isinstance(data, (dict, list)):
            logger.warning(f"[{capability}] LLM fallback repair_json returned {type(data).__name__}, expected dict/list")
            return None
    except (ValueError, TypeError) as e:
        logger.warning(f"[{capability}] LLM fallback JSON repair failed: {e}")
        return None

    if _validate_json(data, capability):
        logger.info(f"[{capability}] LLM fallback extraction succeeded")
        return data

    logger.warning(f"[{capability}] LLM fallback JSON validation failed")
    return None


def _strip_markdown_fence(text: str) -> str:
    """If LLM output is wrapped in ```...``` fences, strip them."""
    cleaned = text.strip()
    if cleaned.startswith("```"):
        lines = cleaned.split("\n")
        lines = [ln for ln in lines if not ln.strip().startswith("```")]
        cleaned = "\n".join(lines).strip()
    return cleaned


async def _call_llm(
    provider: str,
    api_key: str,
    model_id: str,
    base_url: str | None,
    prompt: str,
) -> str | None:
    if provider == "anthropic":
        import anthropic
        kwargs: dict[str, Any] = {"api_key": api_key, "timeout": LLM_FALLBACK_TIMEOUT_SECONDS}
        if base_url:
            kwargs["base_url"] = base_url
        client = anthropic.AsyncAnthropic(**kwargs)
        try:
            msg = await client.messages.create(
                model=model_id,
                max_tokens=LLM_FALLBACK_MAX_TOKENS,
                temperature=LLM_FALLBACK_TEMPERATURE,
                messages=[{"role": "user", "content": prompt}],
            )
            return msg.content[0].text if msg.content else None
        finally:
            await client.close()
    else:
        from openai import AsyncOpenAI
        kwargs = {"api_key": api_key, "timeout": LLM_FALLBACK_TIMEOUT_SECONDS}
        if base_url:
            kwargs["base_url"] = base_url
        client = AsyncOpenAI(**kwargs)
        try:
            resp = await client.chat.completions.create(
                model=model_id,
                max_tokens=LLM_FALLBACK_MAX_TOKENS,
                temperature=LLM_FALLBACK_TEMPERATURE,
                messages=[{"role": "user", "content": prompt}],
            )
            return resp.choices[0].message.content if resp.choices else None
        finally:
            await client.close()