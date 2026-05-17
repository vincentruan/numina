"""AI capability result parser — extract structured data from LLM answer text.

Strategy:
1. Regex extraction: Look for `<!-- STRUCTURED_DATA ... -->` delimiter
2. LLM fallback: Use cheapest available model from family's provider config
"""

import json
import logging
import re
from typing import Any

from sqlalchemy.orm import Session

from apps.backend.app.models.ai_provider_config import AIProviderConfig
from apps.backend.app.services.ai_crypto import decrypt_api_key

logger = logging.getLogger(__name__)

# Regex pattern for structured data block
STRUCTURED_DATA_PATTERN = re.compile(
    r'<!-- STRUCTURED_DATA\s*\n?(.*?)\n?\s*-->',
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


def _extract_structured_block(answer_text: str) -> str | None:
    """Extract the STRUCTURED_DATA block from answer text."""
    match = STRUCTURED_DATA_PATTERN.search(answer_text)
    if match:
        return match.group(1).strip()
    return None


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


def parse_capability_result(
    capability: str,
    answer_text: str,
    family_id: int,
    db: Session,
) -> list[dict] | dict | None:
    """Parse structured results from LLM answer text.

    Args:
        capability: One of alerts, disposal, spending_leak, report, allocation, liability
        answer_text: Full LLM response text
        family_id: Family ID for LLM fallback (fetches provider config)
        db: Database session

    Returns:
        - For array-type capabilities (alerts, disposal, spending_leak): list[dict]
        - For object-type capabilities (report, allocation, liability): dict
        - None if extraction fails
    """
    # Step 1: Regex extraction
    block = _extract_structured_block(answer_text)
    if block:
        try:
            data = json.loads(block)
            if _validate_json(data, capability):
                logger.info(f"[{capability}] regex extraction succeeded, got {len(data) if isinstance(data, list) else 1} items")
                return data
            else:
                logger.warning(f"[{capability}] regex extracted JSON but validation failed")
        except json.JSONDecodeError as e:
            logger.warning(f"[{capability}] regex found block but JSON parse failed: {e}")

    # Step 2: LLM fallback (not implemented yet — will be added in Phase 2)
    # For now, return None and log warning
    logger.warning(f"[{capability}] structured data extraction failed, no results persisted")
    return None


# Placeholder for LLM fallback (to be implemented)
async def _llm_fallback_extract(
    capability: str,
    answer_text: str,
    family_id: int,
    db: Session,
) -> list[dict] | dict | None:
    """Use lightweight LLM to extract structured data from answer text.

    TODO: Implement in Phase 2. This requires:
    1. Fetch family's cheapest provider config
    2. Call LLM with extraction prompt
    3. Parse and validate response
    """
    # Get cheapest provider config for this family
    configs = (
        db.query(AIProviderConfig)
        .filter(
            AIProviderConfig.family_id == family_id,
            AIProviderConfig.api_key_encrypted.isnot(None),
            AIProviderConfig.is_active.is_(True),
        )
        .order_by(AIProviderConfig.display_order.asc())
        .all()
    )

    if not configs:
        logger.warning(f"[{capability}] LLM fallback failed: no provider config for family {family_id}")
        return None

    # Pick first (cheapest) config
    config = configs[0]
    api_key = decrypt_api_key(config.api_key_encrypted)
    if not api_key:
        logger.warning(f"[{capability}] LLM fallback failed: could not decrypt API key")
        return None

    # TODO: Call LLM with extraction prompt
    # This will be implemented in a follow-up task

    return None