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
LLM_FALLBACK_TIMEOUT_SECONDS = 30.0
LLM_FALLBACK_MAX_RETRIES = 3  # Maximum retries for LLM fallback extraction

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
            "summary": {"type": "string"},
            "sections": {"type": "object"},
            "net_worth_health": {"type": "object"},
            "allocation_analysis": {"type": "object"},
            "liability_pressure": {"type": "object"},
            "asset_efficiency": {"type": "object"},
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

    # Step 2: LLM fallback (convert answer text to structured JSON)
    fallback_data = await _llm_fallback_extract(capability, answer_text, family_id, db)
    if fallback_data is not None:
        return fallback_data, "llm_fallback_hit"

    logger.warning(f"[{capability}] structured data extraction failed, no results persisted")
    return None, "failed"


def _build_extraction_prompt(capability: str, answer_text: str, retry_count: int = 0) -> str:
    """Build extraction prompt for LLM fallback.

    For report capability, includes special handling for markdown tables.
    """
    schema = CAPABILITY_SCHEMAS.get(capability, {})
    schema_str = json.dumps(schema, ensure_ascii=False, indent=2)

    # Truncate long text to avoid token limits
    if capability == "report" and len(answer_text) > 3000:
        truncated = answer_text[:1500] + "\n...\n" + answer_text[-2000:]
    else:
        truncated = answer_text[:3000]

    # Base prompt
    base_prompt = (
        f"以下是 {capability} 分析文本，请提取其中的结构化信息为 JSON。\n"
        f"Schema：\n{schema_str}\n\n"
        f"分析文本：\n{truncated}\n\n"
        f"仅输出 JSON，不输出任何解释。"
    )

    # Enhanced prompt for report capability - handle markdown tables
    if capability == "report":
        retry_hint = ""
        if retry_count > 0:
            retry_hint = f"\n\n【注意：这是第{retry_count + 1}次尝试，前次提取失败，请务必仔细检查格式。】"

        enhanced_prompt = (
            f"请从以下分析文本中提取结构化的家庭资产报告 JSON。\n\n"
            f"【输出要求】\n"
            f"1. 仅输出 JSON，不要有任何解释或额外内容\n"
            f"2. JSON 必须合法：无尾逗号、无注释、字符串正确转义\n"
            f"3. overall_score 必须是 0-100 的整数\n\n"
            f"【narrative 字段格式要求 - 必须遵守】\n"
            f"narrative 字段必须使用**无序列表**格式，禁止使用 markdown 表格。\n\n"
            f"正确格式示例（使用无序列表）：\n"
            f'"narrative": "**活期存款占比过高**\\n\\n- 活期存款约¥870,000，仅覆盖约1.2个月支出\\n- 建议配置部分资金为低风险理财产品"\n\n'
            f"错误格式（禁止）：\n"
            f'"narrative": "| 活期存款 | ¥870,000 | ⚠️ 仅覆盖1.2个月支出 |"  ← 这是表格格式，禁止使用！\n\n'
            f"【如果原文包含 markdown 表格，必须转换为列表】\n"
            f"原文表格：| 活期存款 | ¥870,000 | ⚠️ 仅覆盖1.2个月支出 |\n"
            f"转换为：- 活期存款约¥870,000，仅覆盖约1.2个月支出\n\n"
            f"Schema：\n{schema_str}\n\n"
            f"分析文本：\n{truncated}\n"
            f"{retry_hint}\n\n"
            f"仅输出 JSON。"
        )
        return enhanced_prompt

    return base_prompt


async def _llm_fallback_extract(
    capability: str,
    answer_text: str,
    family_id: int,
    db: Session,
) -> list[dict] | dict | None:
    """Use lightweight LLM to extract structured data from answer text.

    Picks family's cheapest active provider (by display_order ASC NULLS LAST),
    calls LLM with extraction prompt under a 30s timeout, parses and validates.
    Retries up to LLM_FALLBACK_MAX_RETRIES times on validation failure.

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

    # Retry loop: attempt extraction up to LLM_FALLBACK_MAX_RETRIES times
    for retry in range(LLM_FALLBACK_MAX_RETRIES):
        prompt = _build_extraction_prompt(capability, answer_text, retry_count=retry)

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
            logger.warning(f"[{capability}] LLM fallback timed out after {LLM_FALLBACK_TIMEOUT_SECONDS}s (retry {retry + 1})")
            continue  # Retry on timeout
        except Exception as e:
            logger.warning(f"[{capability}] LLM fallback call failed: {e} (retry {retry + 1})")
            continue  # Retry on error

        if not raw:
            logger.warning(f"[{capability}] LLM fallback returned empty response (retry {retry + 1})")
            continue

        cleaned = _strip_markdown_fence(raw)

        try:
            # Use json_repair for robust parsing
            data = repair_json(cleaned, return_objects=True)
            # Type guard: repair_json may return str on partial failure
            if not isinstance(data, (dict, list)):
                logger.warning(f"[{capability}] LLM fallback repair_json returned {type(data).__name__}, expected dict/list (retry {retry + 1})")
                continue
        except (ValueError, TypeError) as e:
            logger.warning(f"[{capability}] LLM fallback JSON repair failed: {e} (retry {retry + 1})")
            continue

        # Additional validation for report: check narrative fields don't contain markdown tables
        if capability == "report" and isinstance(data, dict) and _contains_markdown_table(data):
            logger.warning(f"[{capability}] LLM fallback JSON contains markdown tables in narrative (retry {retry + 1})")
            continue

        if _validate_json(data, capability):
            logger.info(f"[{capability}] LLM fallback extraction succeeded on retry {retry + 1}")
            return data

        logger.warning(f"[{capability}] LLM fallback JSON validation failed (retry {retry + 1})")

    logger.warning(f"[{capability}] LLM fallback exhausted {LLM_FALLBACK_MAX_RETRIES} retries, giving up")
    return None


def _contains_markdown_table(data: dict) -> bool:
    """Check if narrative fields contain markdown table patterns.

    Returns True if any narrative field contains table-like patterns:
    - Pipe-separated content: | cell1 | cell2 | cell3 |
    - Multiple pipe chars in a single line
    """
    table_pattern = re.compile(r'\|[^\n]+\|')

    # Check all narrative fields in report structure
    sections = ["net_worth_health", "allocation_analysis", "liability_pressure", "asset_efficiency"]
    for section in sections:
        if section in data and isinstance(data[section], dict):
            narrative = data[section].get("narrative", "")
            if narrative and table_pattern.search(narrative):
                logger.debug(f"Found markdown table in {section}.narrative")
                return True

    # Also check summary field
    summary = data.get("summary", "")
    if summary and table_pattern.search(summary):
        logger.debug("Found markdown table in summary")
        return True

    return False


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