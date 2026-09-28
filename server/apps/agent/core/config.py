"""Standalone AI config helper for scripts.

Reads AI provider settings from environment variables and returns a dict
compatible with ``translate_topic(topic, ai_config)``.
"""

import os


def get_ai_config() -> dict:
    """Return an AI config dict from environment variables.

    Reads:
        AI_PROVIDER  — provider name (default: "openai")
        AI_MODEL     — model identifier (default: "gpt-4o-mini")
        AI_API_KEY   — API key (required for translation)
        AI_BASE_URL  — optional base URL override

    Returns:
        dict with keys: ai_provider, ai_model_id, api_key, ai_base_url
    """
    return {
        "ai_provider": os.environ.get("AI_PROVIDER", "openai"),
        "ai_model_id": os.environ.get("AI_MODEL", "gpt-4o-mini"),
        "api_key": os.environ.get("AI_API_KEY", ""),
        "ai_base_url": os.environ.get("AI_BASE_URL", ""),
    }
