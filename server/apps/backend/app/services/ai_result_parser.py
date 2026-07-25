"""AI skill_id result parser — extract structured data from LLM answer text.

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
LLM_FALLBACK_MAX_RETRIES_REPORT = 5  # Maximum retries for report skill (Phase 2 retry loop)

# Pre-compiled regex patterns for markdown table detection (performance optimization)
_MARKDOWN_TABLE_PATTERN_FULL = re.compile(r'\|[^\n]+\|[^\n]*\|')  # Full table row (at least 2 columns)
_MARKDOWN_TABLE_PATTERN_PARTIAL = re.compile(r'\|[^\|]+\|[^\|]+')  # Partial table without trailing |
_MARKDOWN_TABLE_PATTERN_NO_LEADING = re.compile(r'[^\|]*\|[^\|]+\|[^\|]*')  # Table without leading |

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

# Expected schemas per skill_id
# U7: 5 外扩 trigger skill (alerts/disposal/spending_leak/allocation/liability) 全栈删除，
# 仅保留 report schema；能力回归 numina SOUL（chat/SKILL.md 结构化分析框架）。
SKILL_SCHEMAS = {
    "report": {
        "type": "object",
        "required": ["overall_score", "indicators"],
        "properties": {
            "overall_score": {"type": "integer", "minimum": 0, "maximum": 100},
            "data_completeness_score": {"type": "number"},
            "summary": {"type": "string"},
            "indicators": {
                "type": "array",
                "minItems": 3,
                "maxItems": 8,
                "items": {
                    "type": "object",
                    "required": ["key", "label", "score", "narrative"],
                    "properties": {
                        "key": {"type": "string"},
                        "label": {"type": "string"},
                        "score": {"type": "integer", "minimum": 1, "maximum": 5},
                        "narrative": {"type": "string"},
                        "suggestions": {
                            "type": "array",
                            "items": {"type": "string"}
                        },
                        "data": {"type": "object"},
                    },
                },
            },
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


def _unwrap_agent_envelope(data: dict[str, Any], skill_id: str) -> dict[str, Any] | None:
    """Unwrap agent envelope formats before schema validation.

    Some LLMs output JSON wrapped in backend-style envelope:
    {"code": "OK", "message": "", "data": {"report": {...}}}

    This function unwraps such formats to extract the actual skill data.

    Args:
        data: Parsed JSON data (may be wrapped or direct)
        skill_id: The skill name (e.g., "report")

    Returns:
        Unwrapped data dict if envelope detected and inner structure valid.
        Returns original data if envelope not detected or inner structure invalid.
        Never returns None — callers use `or data` fallback for safety.
    """
    # Check for backend-style envelope: {"code": "OK", "data": {...}}
    if isinstance(data, dict) and "code" in data and "data" in data:
        inner = data.get("data")
        if isinstance(inner, dict):
            # For report skill, data may be nested as {"report": {...}}
            if skill_id == "report" and "report" in inner:
                report_data = inner.get("report")
                if isinstance(report_data, dict):
                    logger.info(f"[{skill_id}] unwrapped agent envelope: code={data.get('code')}, data.report")
                    return report_data
            # For other skills, data might be directly the result
            # Check if inner has the required fields for the skill
            schema = SKILL_SCHEMAS.get(skill_id)
            if schema and schema.get("type") == "object":
                required = schema.get("required", [])
                if all(k in inner for k in required):
                    logger.info(f"[{skill_id}] unwrapped agent envelope: code={data.get('code')}, data direct")
                    return inner
    return data


def _validate_json(data: Any, skill_id: str) -> bool:
    """Validate parsed JSON against expected schema (basic check)."""
    schema = SKILL_SCHEMAS.get(skill_id)
    if not schema:
        return True  # Unknown skill, skip validation

    # Unwrap envelope format before validation
    if isinstance(data, dict):
        data = _unwrap_agent_envelope(data, skill_id) or data

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


async def parse_skill_result(
    skill_id: str,
    answer_text: str,
    family_id: int,
    db: Session,
) -> tuple[list[dict] | dict | None, str, str | None]:
    """Parse structured results from LLM answer text.

    Args:
        skill_id: Skill name (currently only ``report``; other skills
            regressed to numina SOUL in U7 and have no schema here)
        answer_text: Full LLM response text
        family_id: Family ID for LLM fallback (fetches provider config)
        db: Database session

    Returns:
        (data, method, error_type) where:
        - data: parsed structured data or None if extraction fails
        - method: extraction method label for audit
        - error_type: specific error type for user messaging (e.g., "quota_exceeded", "timeout")
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
                logger.warning(f"[{skill_id}] repair_json returned {type(data).__name__}, expected dict/list")
                data = None
            # Unwrap envelope format before returning
            unwrapped_data = _unwrap_agent_envelope(data, skill_id) if isinstance(data, dict) else data
            if unwrapped_data is not None and _validate_json(unwrapped_data, skill_id):
                logger.info(f"[{skill_id}] regex extraction succeeded via {method}, got {len(unwrapped_data) if isinstance(unwrapped_data, list) else 1} items")
                return unwrapped_data, method, None
            elif data is not None and _validate_json(data, skill_id):
                # _validate_json already unwrapped internally, return data directly
                # This path handles cases where envelope was detected but inner structure validates
                logger.info(f"[{skill_id}] regex extraction succeeded via {method} (fallback), got {len(data) if isinstance(data, list) else 1} items")
                return data, method, None
            else:
                logger.warning(f"[{skill_id}] regex extracted JSON via {method} but validation failed")
        except (ValueError, TypeError) as e:
            logger.warning(f"[{skill_id}] regex found block via {method} but JSON repair failed: {e}")

    # Step 2: LLM fallback (convert answer text to structured JSON)
    fallback_data, fallback_error_type = await _llm_fallback_extract(skill_id, answer_text, family_id, db)
    if fallback_data is not None:
        return fallback_data, "llm_fallback_hit", None

    # Return specific error type for user messaging
    error_type = fallback_error_type or "extraction_failed"
    logger.warning(f"[{skill_id}] structured data extraction failed (error_type={error_type}), no results persisted")
    return None, "failed", error_type


def _build_extraction_prompt(skill_id: str, answer_text: str, retry_count: int = 0) -> str:
    """Build extraction prompt for LLM fallback.

    For report skill, includes special handling for markdown tables.
    """
    schema = SKILL_SCHEMAS.get(skill_id, {})
    schema_str = json.dumps(schema, ensure_ascii=False, indent=2)

    # Truncate long text to avoid token limits
    if skill_id == "report" and len(answer_text) > 3000:
        truncated = answer_text[:1500] + "\n...\n" + answer_text[-2000:]
    else:
        truncated = answer_text[:3000]

    # Base prompt
    base_prompt = (
        f"以下是 {skill_id} 分析文本，请提取其中的结构化信息为 JSON。\n"
        f"Schema：\n{schema_str}\n\n"
        f"分析文本：\n{truncated}\n\n"
        f"仅输出 JSON，不输出任何解释。"
    )

    # Enhanced prompt for report skill - handle markdown tables
    if skill_id == "report":
        retry_hint = ""
        if retry_count > 0:
            retry_hint = f"\n\n【注意：这是第{retry_count + 1}次尝试，前次提取失败。如果之前因为表格格式失败，这次必须将表格转换为列表格式。】"

        enhanced_prompt = (
            f"请从以下分析文本中提取结构化的家庭资产报告 JSON。\n\n"
            f"【输出要求】\n"
            f"1. 仅输出 JSON，不要有任何解释或额外内容\n"
            f"2. JSON 必须合法：无尾逗号、无注释、字符串正确转义\n"
            f"3. overall_score 必须是 0-100 的整数\n\n"
            f"## ⚠️⚠️⚠️ 禁止使用 Markdown 表格 ⚠️⚠️⚠️\n\n"
            f"narrative 字段**绝对禁止**使用 markdown 表格格式。表格格式会导致 JSON 解析失败。\n"
            f"必须使用**无序列表**格式。以下是多个表格 → 列表转换示例：\n\n"
            f"【示例1：单行表格转换】\n"
            f"原文表格：| 活期存款 | ¥870,000 | ⚠️ 仅覆盖1.2个月支出 |\n"
            f"转换为：- 活期存款约¥870,000，仅覆盖约1.2个月支出\n\n"
            f"【示例2：多行表格转换】\n"
            f"原文表格：\n"
            f"| 资产类型 | 金额 | 风险等级 |\n"
            f"| 活期存款 | ¥500,000 | 低 |\n"
            f"| 定期存款 | ¥300,000 | 低 |\n"
            f"转换为：\n"
            f"- 活期存款¥500,000，风险等级低\n"
            f"- 定期存款¥300,000，风险等级低\n\n"
            f"【示例3：复杂表格转换】\n"
            f"原文表格：\n"
            f"| 项目 | 当前值 | 建议值 | 状态 |\n"
            f"| 流动性覆盖率 | 1.2个月 | 3-6个月 | ⚠️ 不足 |\n"
            f"| 负债收入比 | 45% | <40% | ⚠️ 偏高 |\n"
            f"转换为：\n"
            f"- 流动性覆盖率1.2个月，建议3-6个月，状态不足\n"
            f"- 负债收入比45%，建议值小于40%，状态偏高\n\n"
            f"【正确格式示例（使用无序列表）】\n"
            f'"narrative": "**活期存款占比过高**\\n\\n- 活期存款约¥870,000，仅覆盖约1.2个月支出\\n- 建议配置部分资金为低风险理财产品"\n\n'
            f"【错误格式（绝对禁止）】\n"
            f'"narrative": "| 活期存款 | ¥870,000 | ⚠️ 仅覆盖1.2个月支出 |"  ← ⚠️⚠️⚠️ 这是表格格式，会导致解析失败！\n\n'
            f"Schema：\n{schema_str}\n\n"
            f"分析文本：\n{truncated}\n"
            f"{retry_hint}\n\n"
            f"仅输出 JSON。"
        )
        return enhanced_prompt

    return base_prompt


def _build_extraction_prompt_with_feedback(
    skill_id: str,
    answer_text: str,
    retry_count: int = 0,
    failure_reasons: list[str] | None = None,
) -> str:
    """Build extraction prompt with progressive failure feedback.

    Enhances the base prompt with failure history to help the LLM avoid
    repeating the same mistakes on retries.
    """
    # Build the base prompt first
    base_prompt = _build_extraction_prompt(skill_id, answer_text, retry_count=retry_count)

    # If no failures or first attempt, return base prompt
    if retry_count == 0 or not failure_reasons:
        return base_prompt

    # Build failure history section
    failure_history = "\n\n【历史失败记录 - 请避免重复错误】\n"
    for i, reason in enumerate(failure_reasons, 1):
        failure_history += f"第{i}次失败：{_format_failure_reason(reason)}\n"

    # Add special warning for markdown table failures
    if "markdown_table_in_narrative" in failure_reasons:
        failure_history += (
            "\n⚠️ 特别注意：如果之前因为 markdown 表格失败，这次必须将表格转换为列表！\n"
            "表格格式示例（禁止）：| 项目 | 金额 |\n"
            "列表格式示例（正确）：- 项目：金额"
        )

    # Insert failure history before the final "仅输出 JSON" instruction
    if skill_id == "report":
        # For report, insert before the retry hint section
        if "【注意：这是第" in base_prompt:
            # Insert after retry hint
            parts = base_prompt.split("仅输出 JSON。")
            return parts[0] + failure_history + "\n\n仅输出 JSON。"
        else:
            # Insert before final instruction
            parts = base_prompt.split("仅输出 JSON。")
            return parts[0] + failure_history + "\n\n仅输出 JSON。"
    else:
        # For other skills, append failure history
        return base_prompt + failure_history


def _format_failure_reason(reason: str) -> str:
    """Convert internal failure reason codes to user-friendly Chinese messages."""
    if reason == "timeout":
        return "LLM 调用超时"
    elif reason.startswith("call_failed:"):
        error_type = reason.split(": ", 1)[1] if ": " in reason else reason
        return f"LLM 调用失败（{error_type}）"
    elif reason == "empty_response":
        return "LLM 返回空响应"
    elif reason.startswith("repair_json_returned_"):
        type_name = reason.replace("repair_json_returned_", "")
        return f"JSON 解析返回了错误类型（{type_name}），期望对象或数组"
    elif reason.startswith("json_repair_failed:"):
        error_msg = reason.split(": ", 1)[1] if ": " in reason else reason
        return f"JSON 解析失败：{error_msg}"
    elif reason == "markdown_table_in_narrative":
        return "narrative 字段包含了 markdown 表格格式，这是禁止的！必须使用无序列表格式"
    elif reason == "schema_validation_failed":
        return "JSON 结构验证失败，缺少必需字段或字段类型错误"
    else:
        return f"未知错误：{reason}"


async def _llm_fallback_extract(
    skill_id: str,
    answer_text: str,
    family_id: int,
    db: Session,
) -> tuple[list[dict] | dict | None, str | None]:
    """Use lightweight LLM to extract structured data from answer text.

    Picks family's cheapest active provider (by display_order ASC NULLS LAST),
    calls LLM with extraction prompt under a 30s timeout, parses and validates.
    Retries up to LLM_FALLBACK_MAX_RETRIES times on validation failure.
    For report skill, uses LLM_FALLBACK_MAX_RETRIES_REPORT (5 retries).

    Returns:
        (data, error_type) where:
        - data: extracted structured data or None on failure
        - error_type: specific error type for user messaging (e.g., "quota_exceeded")
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
        logger.warning(f"[{skill_id}] LLM fallback: no active provider for family {family_id}")
        return None, "no_provider"

    config = configs[0]
    api_key = decrypt_api_key(config.api_key_encrypted)
    if not api_key:
        logger.warning(f"[{skill_id}] LLM fallback: could not decrypt API key")
        return None, "api_key_error"

    # Use higher retry count for report skill (Phase 2 retry loop)
    max_retries = LLM_FALLBACK_MAX_RETRIES_REPORT if skill_id == "report" else LLM_FALLBACK_MAX_RETRIES

    # Track failure reasons for feedback in retries
    failure_reasons: list[str] = []
    # Track if the LAST iteration hit a quota error (not cumulative across retries)
    last_iteration_quota_error = False

    # Retry loop: attempt extraction up to max_retries times
    for retry in range(max_retries):
        # Reset quota tracking for this iteration
        last_iteration_quota_error = False
        prompt = _build_extraction_prompt_with_feedback(
            skill_id, answer_text, retry_count=retry, failure_reasons=failure_reasons
        )

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
            failure_reasons.append("timeout")
            logger.warning(f"[{skill_id}] LLM fallback timed out after {LLM_FALLBACK_TIMEOUT_SECONDS}s (retry {retry + 1})")
            continue  # Retry on timeout
        except Exception as e:
            error_str = str(e)
            # Detect quota/throttling errors for specific user messaging
            if _is_quota_error(error_str):
                last_iteration_quota_error = True
                logger.warning(f"[{skill_id}] LLM fallback quota error: {e} (retry {retry + 1})")
            failure_reasons.append(f"call_failed: {type(e).__name__}")
            logger.warning(f"[{skill_id}] LLM fallback call failed: {e} (retry {retry + 1})")
            continue  # Retry on error

        if not raw:
            failure_reasons.append("empty_response")
            logger.warning(f"[{skill_id}] LLM fallback returned empty response (retry {retry + 1})")
            continue

        cleaned = _strip_markdown_fence(raw)

        try:
            # Use json_repair for robust parsing
            data = repair_json(cleaned, return_objects=True)
            # Type guard: repair_json may return str on partial failure
            if not isinstance(data, (dict, list)):
                failure_reasons.append(f"repair_json_returned_{type(data).__name__}")
                logger.warning(f"[{skill_id}] LLM fallback repair_json returned {type(data).__name__}, expected dict/list (retry {retry + 1})")
                continue
        except (ValueError, TypeError) as e:
            failure_reasons.append(f"json_repair_failed: {e}")
            logger.warning(f"[{skill_id}] LLM fallback JSON repair failed: {e} (retry {retry + 1})")
            continue

        # Unwrap envelope format before validation and return
        unwrapped_data = _unwrap_agent_envelope(data, skill_id) if isinstance(data, dict) else data
        # Additional validation for report: check narrative fields don't contain markdown tables
        # Apply to unwrapped data if envelope was present
        data_to_check = unwrapped_data if isinstance(unwrapped_data, dict) else data
        if skill_id == "report" and isinstance(data_to_check, dict) and _contains_markdown_table(data_to_check):
            failure_reasons.append("markdown_table_in_narrative")
            logger.warning(f"[{skill_id}] LLM fallback JSON contains markdown tables in narrative (retry {retry + 1})")
            continue

        if _validate_json(data, skill_id):
            logger.info(f"[{skill_id}] LLM fallback extraction succeeded on retry {retry + 1}")
            # Return unwrapped data if envelope was present
            return unwrapped_data if isinstance(unwrapped_data, dict) else data, None

        failure_reasons.append("schema_validation_failed")
        logger.warning(f"[{skill_id}] LLM fallback JSON validation failed (retry {retry + 1})")

    logger.warning(f"[{skill_id}] LLM fallback exhausted {max_retries} retries, giving up")
    # Return specific error type if the LAST iteration was a quota error
    if last_iteration_quota_error:
        return None, "quota_exceeded"
    return None, "llm_fallback_failed"


def _is_quota_error(error_str: str) -> bool:
    """Detect quota/throttling errors from LLM API responses.

    Patterns are specific to avoid false positives from unrelated error messages.
    """
    error_lower = error_str.lower()

    # HTTP 429 status - match as standalone status code, not part of other numbers
    # Matches: "429", "status 429", "429 Too Many Requests", "HTTP 429"
    if re.search(r"(?:^|\D)429(?:\D|$)", error_str) or "too many requests" in error_lower:
        return True

    # Quota-specific patterns - must be quota context, not general billing
    quota_patterns = [
        "quota",
        "throttling",
        "rate_limit",
        "rate limit",
        "allocated quota exceeded",
        "concurrency allocated quota exceeded",
        "account is out of quota",
        "quota exceeded",
        "insufficient_quota",
        "billing limit",
        "billing exceeded",
        "billing unavailable",
        "usage limit",
        "usage_cap",
        "capacity exceeded",
    ]
    return any(pattern in error_lower for pattern in quota_patterns)


def _contains_markdown_table(data: dict) -> bool:
    """Check if narrative fields contain markdown table patterns.

    Returns True if any narrative field contains table-like patterns:
    - Full table rows: | cell1 | cell2 | cell3 |
    - Partial tables without trailing pipe: | cell1 | cell2
    - Tables without leading pipe: cell1 | cell2 | cell3
    """
    # Use pre-compiled module-level patterns (performance optimization)
    table_patterns = [
        _MARKDOWN_TABLE_PATTERN_FULL,
        _MARKDOWN_TABLE_PATTERN_PARTIAL,
        _MARKDOWN_TABLE_PATTERN_NO_LEADING,
    ]

    # Check indicators array (new format)
    indicators = data.get("indicators", [])
    if isinstance(indicators, list):
        for indicator in indicators:
            if isinstance(indicator, dict):
                narrative = indicator.get("narrative", "")
                if narrative:
                    for pattern in table_patterns:
                        if pattern.search(narrative):
                            logger.debug(f"Found markdown table in indicator[{indicator.get('key', '?')}].narrative")
                            return True

    # Check legacy sections (old format)
    sections = ["net_worth_health", "allocation_analysis", "liability_pressure", "asset_efficiency"]
    for section in sections:
        if section in data and isinstance(data[section], dict):
            narrative = data[section].get("narrative", "")
            if narrative:
                for pattern in table_patterns:
                    if pattern.search(narrative):
                        logger.debug(f"Found markdown table in {section}.narrative (pattern: {pattern.pattern})")
                        return True

    # Also check summary field
    summary = data.get("summary", "")
    if summary:
        for pattern in table_patterns:
            if pattern.search(summary):
                logger.debug(f"Found markdown table in summary (pattern: {pattern.pattern})")
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