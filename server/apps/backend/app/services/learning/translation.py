"""LLM-assisted translation service for learning content.

Translates os-taxonomy English content to Chinese for the Learning OS.
Also derives ability_dimensions from topic metadata.
"""

import asyncio
from typing import Any

# Ability dimensions for derive_ability_dimensions
ABILITY_DIMENSIONS = [
    "numerical_reasoning",
    "spatial_reasoning",
    "verbal_reasoning",
    "scientific_inquiry",
    "computational_thinking",
    "social_emotional",
    "creative_thinking",
    "physical_kinesthetic",
    "memory_recall",
    "metacognition",
]


async def translate_topic(topic: dict[str, Any]) -> dict[str, Any]:
    """Translate a topic's name, description, evidence, assessment_prompt to Chinese.

    Returns dict with keys: name_zh, description_zh, evidence_zh, assessment_prompt_zh
    """
    # Placeholder — will use DashScope/OpenAI when actual translation runs
    # For now, return None values (seed script handles gracefully)
    return {
        "name_zh": None,
        "description_zh": None,
        "evidence_zh": None,
        "assessment_prompt_zh": None,
    }


async def derive_ability_dimensions(topic: dict[str, Any]) -> list[str]:
    """Derive ability dimensions from topic metadata.

    Analyzes subject + domain + description + type to map to ability dimensions.
    Returns list of dimension strings.
    """
    # Placeholder — returns empty list (seed script handles gracefully)
    return []


async def translate_batch(topics: list[dict], batch_size: int = 50) -> list[dict]:
    """Translate a batch of topics with rate limit protection."""
    results = []
    for i in range(0, len(topics), batch_size):
        batch = topics[i : i + batch_size]
        batch_results = await asyncio.gather(*[translate_topic(t) for t in batch])
        results.extend(batch_results)
        if i + batch_size < len(topics):
            await asyncio.sleep(1)  # rate limit protection
    return results
