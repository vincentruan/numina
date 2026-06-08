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


def _extract_report_scores_from_markdown(answer_text: str) -> dict | None:
    """Extract scoring data from markdown tables and prose sections in report output.

    Handles multiple formats the model produces:
    1. Scoring table: | 维度 | 85/100 | ... |
    2. Health indicator table: | 指标 | 值 | 范围 | 🔴 状态 |
    3. Markdown section headers with prose analysis
    4. Suggestion lists under "建议" or numbered points
    """
    # Strategy 1: Direct X/100 scoring tables
    score_pattern = re.compile(
        r'\|\s*([^|]+?)\s*\|\s*(\d{1,3})/100\s*\|',
        re.MULTILINE
    )

    scores: dict[str, dict] = {}
    for match in score_pattern.finditer(answer_text):
        dimension = match.group(1).strip()
        score = int(match.group(2))
        if '资产规模' in dimension or '净资产' in dimension:
            scores['net_worth_health'] = {'score': min(5, max(1, score // 20)), 'narrative': dimension}
        elif '资产配置' in dimension or '配置' in dimension or '多元化' in dimension:
            scores['allocation_analysis'] = {'score': min(5, max(1, score // 20)), 'narrative': dimension}
        elif '负债' in dimension:
            scores['liability_pressure'] = {'score': min(5, max(1, score // 20)), 'narrative': dimension}
        elif '流动性' in dimension or '流动' in dimension:
            scores['asset_efficiency'] = {'score': min(5, max(1, score // 20)), 'narrative': dimension}
        scores[dimension] = score

    # Strategy 2: Health indicator tables with emoji status (🔴/🟡/🟢)
    if not scores:
        indicator_pattern = re.compile(
            r'\|\s*([^|]+?)\s*\|\s*([^|]+?)\s*\|\s*([^|]+?)\s*\|\s*(🔴|🟡|🟢|⚠️)?\s*([^|]*?)\s*\|',
            re.MULTILINE
        )
        emoji_score_map = {'🟢': 4, '🟡': 3, '🔴': 1, '⚠️': 2}
        raw_indicators = {}

        # Broader keyword sets for dimension mapping
        LIABILITY_KEYWORDS = ('负债', '债务', '杠杆', '偿债', '还款', '贷款', '债', '月供')
        EFFICIENCY_KEYWORDS = ('流动', '现金', '应急', '储备', '变现', '活期', '余额')
        ALLOCATION_KEYWORDS = ('配置', '集中', '分散', '多元', '房产', '投资', '结构')
        NET_WORTH_KEYWORDS = ('净资产', '资产规模', '总资产', '净值', '财富', '增长')
        # Header/separator patterns to skip
        SKIP_KEYWORDS = ('指标', '项目', '---', '状态', '评价', '维度', '评级', '说明')

        for match in indicator_pattern.finditer(answer_text):
            indicator = match.group(1).strip()
            emoji = match.group(4) or ''
            status_text = match.group(5).strip()

            # Skip table headers and separator rows
            if any(kw in indicator for kw in SKIP_KEYWORDS):
                continue

            if emoji not in emoji_score_map:
                # Try to find emoji in the status text column
                for e in emoji_score_map:
                    if e in status_text:
                        emoji = e
                        status_text = status_text.replace(e, '').strip()
                        break
                if emoji not in emoji_score_map:
                    continue

            s = emoji_score_map[emoji]
            narrative = f'{indicator}: {status_text}' if status_text else indicator

            if any(kw in indicator for kw in LIABILITY_KEYWORDS):
                scores.setdefault('liability_pressure', {'score': s, 'narrative': narrative})
            elif any(kw in indicator for kw in EFFICIENCY_KEYWORDS):
                scores.setdefault('asset_efficiency', {'score': s, 'narrative': narrative})
            elif any(kw in indicator for kw in ALLOCATION_KEYWORDS):
                scores.setdefault('allocation_analysis', {'score': s, 'narrative': narrative})
            elif any(kw in indicator for kw in NET_WORTH_KEYWORDS):
                scores.setdefault('net_worth_health', {'score': s, 'narrative': narrative})
            raw_indicators[indicator] = s

        # Derive net_worth_health from overall pattern if not directly matched
        if raw_indicators and 'net_worth_health' not in scores:
            avg = sum(raw_indicators.values()) / len(raw_indicators)
            # Net worth is usually better than individual indicators suggest
            scores['net_worth_health'] = {'score': min(5, max(1, round(avg + 1))), 'narrative': '净资产综合评估'}

    # Strategy 3: Pure prose-based sentiment extraction (works without tables)
    # Detect if this looks like a report by checking for section headers
    IS_REPORT_KEYWORDS = ('家庭资产', '体检报告', '资产结构', '负债分析', '净资产', '家庭概况')
    if not scores and any(kw in answer_text for kw in IS_REPORT_KEYWORDS):
        NEGATIVE_WORDS = ('偏高', '过高', '不足', '严重', '风险', '过低', '失衡', '极高', '过于集中', '过度')
        MODERATE_WORDS = ('一般', '尚可', '适中', '中等')
        POSITIVE_WORDS = ('健康', '良好', '充足', '合理', '优秀')

        def _sentiment_score(text_segment: str) -> int:
            if any(w in text_segment for w in NEGATIVE_WORDS):
                return 2
            if any(w in text_segment for w in POSITIVE_WORDS):
                return 4
            if any(w in text_segment for w in MODERATE_WORDS):
                return 3
            return 3

        # Initialize all 4 dimensions from prose
        for sentence in re.split(r'[。\n]', answer_text):
            sentence = sentence.strip()
            if not sentence or len(sentence) < 10:
                continue

            if 'net_worth_health' not in scores and any(kw in sentence for kw in ('净资产', '资产规模', '总资产', '净值')):
                scores['net_worth_health'] = {'score': _sentiment_score(sentence), 'narrative': sentence[:200]}
            if 'allocation_analysis' not in scores and any(kw in sentence for kw in ('配置', '资产结构', '集中', '分散')):
                scores['allocation_analysis'] = {'score': _sentiment_score(sentence), 'narrative': sentence[:200]}
            if 'liability_pressure' not in scores and any(kw in sentence for kw in ('负债', '债务', '贷款', '月供', '杠杆')):
                scores['liability_pressure'] = {'score': _sentiment_score(sentence), 'narrative': sentence[:200]}
            if 'asset_efficiency' not in scores and any(kw in sentence for kw in ('流动', '现金', '低效', '闲置', '效率')):
                scores['asset_efficiency'] = {'score': _sentiment_score(sentence), 'narrative': sentence[:200]}

    # Strategy 3b: Prose-based sentiment scan to fill missing dimensions (when some exist)
    if scores:
        NEGATIVE_WORDS = ('偏高', '过高', '不足', '严重', '风险', '过低', '失衡', '极高', '过于集中', '过度')
        MODERATE_WORDS = ('一般', '尚可', '适中', '中等')
        POSITIVE_WORDS = ('健康', '良好', '充足', '合理', '优秀')

        def _sentiment_score(text_segment: str) -> int:
            if any(w in text_segment for w in NEGATIVE_WORDS):
                return 2
            if any(w in text_segment for w in POSITIVE_WORDS):
                return 4
            if any(w in text_segment for w in MODERATE_WORDS):
                return 3
            return 3

        if 'liability_pressure' not in scores:
            # Scan for liability-related sentences
            for sentence in re.split(r'[。\n]', answer_text):
                if any(kw in sentence for kw in ('负债', '债务', '贷款', '月供', '杠杆', '偿债')):
                    scores['liability_pressure'] = {'score': _sentiment_score(sentence), 'narrative': sentence.strip()[:200]}
                    break

        if 'asset_efficiency' not in scores:
            for sentence in re.split(r'[。\n]', answer_text):
                if any(kw in sentence for kw in ('流动', '现金', '应急', '储备', '变现', '活期')):
                    scores['asset_efficiency'] = {'score': _sentiment_score(sentence), 'narrative': sentence.strip()[:200]}
                    break

    # Strategy 4: Extract full narratives from markdown section headers
    # Look for sections like "## 二、资产结构分析" and capture the prose
    SECTION_HEADER_MAP = {
        ('净资产', '资产规模', '总资产', '净值', '一、家庭概况', '家庭概况'): 'net_worth_health',
        ('资产配置', '配置', '多元化', '资产结构', '二、资产结构', '结构分析'): 'allocation_analysis',
        ('负债', '债务', '杠杆', '三、负债', '负债分析'): 'liability_pressure',
        ('流动', '现金', '效率', '低效', '四、风险', '资产效率'): 'asset_efficiency',
    }

    # Split by section headers (## ...)
    section_pattern = re.compile(r'##\s+([^\n]+)\n([\s\S]*?)(?=##|\Z)', re.MULTILINE)
    for match in section_pattern.finditer(answer_text):
        header = match.group(1).strip()
        content = match.group(2).strip()

        # Find which dimension this section belongs to
        for keywords, dim_key in SECTION_HEADER_MAP.items():
            if any(kw in header for kw in keywords):
                if dim_key in scores and len(content) > 50:
                    # Extract first meaningful paragraph as narrative (up to 350 chars)
                    # Skip empty lines and markdown formatting
                    prose_lines = []
                    for line in content.split('\n'):
                        line = line.strip()
                        if line and not line.startswith('|') and not line.startswith('---'):
                            prose_lines.append(line)
                    if prose_lines:
                        full_narrative = ' '.join(prose_lines[:3])[:350]
                        scores[dim_key]['narrative'] = full_narrative
                break

    # Strategy 5: Extract suggestions from "建议" sections or numbered lists
    # Keywords for finding suggestion sections: '建议', '五、建议', '六、建议', '核心建议', '以下建议', '改进建议'

    # Find suggestion section
    suggestion_pattern = re.compile(
        r'(?:^##\s*建议|建议[：:]\s*)([\s\S]*?)(?=##|\Z)',
        re.MULTILINE
    )
    suggestion_match = suggestion_pattern.search(answer_text)

    global_suggestions: list[str] = []
    if suggestion_match:
        suggestion_text = suggestion_match.group(1).strip()
        # Extract numbered/bulleted items
        item_pattern = re.compile(r'^\s*(?:[\d]+[\.、]|[•\-\*])\s*([^\n]+)', re.MULTILINE)
        for item_match in item_pattern.finditer(suggestion_text):
            item = item_match.group(1).strip()
            if item and len(item) >= 10:
                global_suggestions.append(item[:50])

    # Also try extracting inline suggestions from each dimension's section
    for dim_key in ['net_worth_health', 'allocation_analysis', 'liability_pressure', 'asset_efficiency']:
        if dim_key in scores and 'suggestions' not in scores[dim_key]:
            dim_suggestions: list[str] = []
            # Look for suggestions near this dimension's keywords
            dim_keywords_map = {
                'net_worth_health': ('净资产', '资产规模'),
                'allocation_analysis': ('配置', '资产结构'),
                'liability_pressure': ('负债', '债务'),
                'asset_efficiency': ('流动', '低效'),
            }
            dim_kws = dim_keywords_map.get(dim_key, ())
            # Find the relevant section and look for suggestion patterns
            for section_match in section_pattern.finditer(answer_text):
                header = section_match.group(1).strip()
                content = section_match.group(2).strip()
                if any(kw in header for kw in dim_kws):
                    # Look for numbered/bulleted suggestions within this section
                    for item_match in item_pattern.finditer(content):
                        item = item_match.group(1).strip()
                        if item and len(item) >= 10 and any(sw in item for sw in ('建议', '可', '应', '考虑', '关注', '优先')):
                            dim_suggestions.append(item[:50])
                    break
            if dim_suggestions:
                scores[dim_key]['suggestions'] = dim_suggestions[:3]

    if not scores:
        return None

    # Calculate overall_score
    dimension_scores = []
    weights = {'net_worth_health': 0.30, 'allocation_analysis': 0.25, 'liability_pressure': 0.25, 'asset_efficiency': 0.20}
    for key, weight in weights.items():
        if key in scores:
            dimension_scores.append(scores[key]['score'] * weight)
        else:
            dimension_scores.append(3 * weight)  # Default to "average"

    overall_score = round(sum(dimension_scores) * 20)

    # Strategy 6: Better summary extraction with multiple patterns
    summary = ""
    summary_patterns = [
        # "总结：" pattern
        re.compile(r'\*{0,2}总结\*{0,2}[：:]\s*([^\n]+(?:\n[^\n|#]+)*?)(?:\n\n|\n##|\Z)', re.DOTALL),
        # "综合" or "核心建议" in markdown
        re.compile(r'(?:综合[分析评估]|核心建议)[：:]\s*([^\n]+(?:\n[^\n|#]+)*?)(?:\n\n|\n##|\Z)', re.DOTALL),
        # Final section before STRUCTURED_DATA
        re.compile(r'##\s*[五六七八九十]+、[^\n]*\n([\s\S]*?)(?=<!-- STRUCTURED_DATA|\Z)', re.DOTALL),
    ]

    for pattern in summary_patterns:
        match = pattern.search(answer_text)
        if match:
            candidate = match.group(1).strip()
            if len(candidate) > 50:
                summary = candidate[:300]
                break

    # Fallback: use first paragraph if no summary found
    if not summary:
        first_para_pattern = re.compile(r'^([^#\n|][^\n]+(?:\n[^\n|#|]+)*?)(?:\n\n|\n##)', re.MULTILINE)
        match = first_para_pattern.search(answer_text)
        if match:
            summary = match.group(1).strip()[:200]

    result = {
        'overall_score': overall_score,
        'data_completeness_score': 0.8,
        'summary': summary if summary else "家庭资产体检报告",
    }
    if global_suggestions:
        result['suggestions'] = global_suggestions[:5]

    for key in ['net_worth_health', 'allocation_analysis', 'liability_pressure', 'asset_efficiency']:
        if key in scores:
            result[key] = scores[key]

    return result


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

    # Step 2: Capability-specific markdown extraction (report only)
    if capability == "report":
        report_data = _extract_report_scores_from_markdown(answer_text)
        if report_data and _validate_json(report_data, capability):
            logger.info("[report] markdown score extraction succeeded")
            return report_data, "regex_markdown_scores"

    # Step 3: LLM fallback
    fallback_data = await _llm_fallback_extract(capability, answer_text, family_id, db)
    if fallback_data is not None:
        return fallback_data, "llm_fallback_hit"

    logger.warning(f"[{capability}] structured data extraction failed, no results persisted")
    return None, "failed"


def _build_extraction_prompt(capability: str, answer_text: str) -> str:
    schema = CAPABILITY_SCHEMAS.get(capability, {})
    schema_str = json.dumps(schema, ensure_ascii=False, indent=2)
    if capability == "report" and len(answer_text) > 3000:
        truncated = answer_text[:1500] + "\n...\n" + answer_text[-2000:]
    else:
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