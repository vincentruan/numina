"""On-demand topic translation via LLM — agent module.

Replaces the old backend-side ``translation.py`` that called DashScope directly.
Now uses ``LLMClient.complete_json()`` so translation honours the family's
configured AI provider (multi-provider, circuit-breaker-aware via router layer).
"""

import json
import logging

from apps.agent.core.llm import LLMClient

logger = logging.getLogger(__name__)

_MAX_DESCRIPTION_CHARS = 3000
_MAX_EVIDENCE_ITEMS = 10

TRANSLATION_SYSTEM_PROMPT = (
    "You are a professional translator specializing in children's education content. "
    "Translate the following English learning topic into Chinese (Simplified). "
    "Preserve technical/mathematical terms in parentheses where helpful. "
    "Return JSON with exactly these keys: name_zh, description_zh, evidence_zh (array), assessment_prompt_zh."
)

_REQUIRED_KEYS = ("name_zh", "description_zh", "evidence_zh", "assessment_prompt_zh")


async def translate_topic(topic: dict, ai_config: dict) -> dict:
    """Translate a topic's English content to Chinese.

    Args:
        topic: dict with keys: name, description, evidence (list), assessment_prompt
        ai_config: provider config dict with keys: ai_provider, ai_model_id,
                   api_key, ai_base_url (or base_url)

    Returns:
        dict with keys: name_zh, description_zh, evidence_zh, assessment_prompt_zh

    Raises:
        ValueError: if api_key is missing or LLM returns malformed/incomplete JSON
    """
    api_key = ai_config.get("api_key")
    if not api_key:
        raise ValueError("LLM API key not configured")

    provider = (ai_config.get("ai_provider") or "openai").lower()
    model = ai_config.get("ai_model_id") or "gpt-4o-mini"
    base_url = ai_config.get("ai_base_url") or ai_config.get("base_url")

    client = LLMClient(
        provider=provider,
        api_key=api_key,
        model_id=model,
        base_url=base_url,
        timeout=60.0,
    )

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

    raw = await client.complete_json(
        prompt=prompt,
        max_tokens=4000,
        system=TRANSLATION_SYSTEM_PROMPT,
    )

    try:
        result = json.loads(raw)
    except json.JSONDecodeError as e:
        raise ValueError(f"LLM returned malformed translation response: {e}") from e

    for key in _REQUIRED_KEYS:
        if key not in result:
            raise ValueError(f"LLM response missing required key: {key}")

    return result
