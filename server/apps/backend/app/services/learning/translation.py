"""On-demand topic translation via LLM (DashScope OpenAI-compatible endpoint)."""

import json
import logging
import os

logger = logging.getLogger(__name__)

# Preserved from original placeholder
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

# Max description length sent to LLM (characters) — prevents token limit issues
_MAX_DESCRIPTION_CHARS = 3000
_MAX_EVIDENCE_ITEMS = 10


def _get_api_key() -> str | None:
    """Return DashScope API key from environment, or None."""
    return os.environ.get("DASHSCOPE_API_KEY") or os.environ.get("OPENAI_API_KEY")


def _get_base_url() -> str:
    return os.environ.get(
        "DASHSCOPE_BASE_URL",
        "https://dashscope.aliyuncs.com/compatible-mode/v1",
    )


def _get_model() -> str:
    return os.environ.get("TRANSLATION_MODEL", "qwen-plus")


_TRANSLATION_SYSTEM_PROMPT = (
    "You are a professional translator specializing in children's education content. "
    "Translate the following English learning topic into Chinese (Simplified). "
    "Preserve technical/mathematical terms in parentheses where helpful. "
    "Return JSON with exactly these keys: name_zh, description_zh, evidence_zh (array), assessment_prompt_zh."
)


def _call_llm(prompt: str) -> dict:
    """Call LLM with a translation prompt, return parsed JSON response."""
    from openai import OpenAI

    api_key = _get_api_key()
    if not api_key:
        raise ValueError("LLM API key not configured")

    client = OpenAI(api_key=api_key, base_url=_get_base_url())
    response = client.chat.completions.create(
        model=_get_model(),
        messages=[
            {"role": "system", "content": _TRANSLATION_SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ],
        temperature=0.3,
        response_format={"type": "json_object"},
    )
    content = response.choices[0].message.content
    if not content:
        raise ValueError("LLM returned empty response")
    try:
        result = json.loads(content)
    except json.JSONDecodeError as e:
        raise ValueError(f"LLM returned malformed translation response: {e}") from e
    for key in ("name_zh", "description_zh", "evidence_zh", "assessment_prompt_zh"):
        if key not in result:
            raise ValueError(f"LLM response missing required key: {key}")
    return result


def translate_topic(topic: dict) -> dict:
    """Translate a topic's English content to Chinese.

    Args:
        topic: dict with keys: name, description, evidence (list), assessment_prompt

    Returns:
        dict with keys: name_zh, description_zh, evidence_zh, assessment_prompt_zh

    Raises:
        ValueError: if LLM API key is not configured
    """
    # Truncate long content to stay within LLM token limits
    description = topic.get("description", "")
    if len(description) > _MAX_DESCRIPTION_CHARS:
        description = description[:_MAX_DESCRIPTION_CHARS] + "..."

    evidence = topic.get("evidence", [])[:_MAX_EVIDENCE_ITEMS]

    prompt = (
        f"Topic name: {topic.get('name', '')}\n"
        f"Description: {description}\n"
        f"Evidence points: {json.dumps(evidence, ensure_ascii=False)}\n"
        f"Assessment prompt: {topic.get('assessment_prompt', '')}"
    )

    return _call_llm(prompt)


def derive_ability_dimensions(topic: dict) -> list[str]:
    """Derive ability dimensions from topic metadata. Out of scope for OQ-2."""
    return []


def translate_batch(topics: list[dict], batch_size: int = 50) -> list[dict]:
    """Translate a batch of topics. Not supported in on-demand mode."""
    raise NotImplementedError("Batch translation not supported in on-demand mode")
