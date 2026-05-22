"""DeerFlow2 model entry construction from DB provider data.

Extracted from family_adapter_cache._generate_temp_config() for reuse.
Bug fix: uses PatchedChatOpenAI (not ReasoningChatOpenAI).
"""
from __future__ import annotations
from typing import Any

_PROVIDER_CLASS_MAP: dict[str, str] = {
    "anthropic": "langchain_anthropic:ChatAnthropic",
    "openai": "langchain_openai:ChatOpenAI",
    "openai_compatible": "langchain_openai:ChatOpenAI",
}

_THINKING_CLASS_OVERRIDES: dict[str, str] = {
    "deepseek": "deerflow.models.patched_deepseek:PatchedChatDeepSeek",
    "openai": "deerflow.models.patched_openai:PatchedChatOpenAI",
    "openai_compatible": "deerflow.models.patched_openai:PatchedChatOpenAI",
}


def build_model_entry(ai_provider: dict[str, Any]) -> dict[str, Any]:
    provider = ai_provider.get("ai_provider", "openai")
    model_id = ai_provider.get("ai_model_id")
    if not model_id:
        raise ValueError("ai_model_id 未配置。请在 AI 配置中填写模型 ID。")

    api_key = ai_provider.get("api_key", "")
    base_url = ai_provider.get("ai_base_url")

    model_1_caps = ai_provider.get("model_1_capabilities")
    if model_1_caps is not None:
        thinking_supported = "deep_thinking" in model_1_caps
    else:
        thinking_supported = bool(ai_provider.get("thinking_supported", False))

    use_class = _PROVIDER_CLASS_MAP.get(provider, "langchain_openai:ChatOpenAI")
    if thinking_supported:
        if "deepseek" in model_id.lower():
            use_class = _THINKING_CLASS_OVERRIDES["deepseek"]
        elif provider in ("openai", "openai_compatible"):
            use_class = _THINKING_CLASS_OVERRIDES[provider]

    entry: dict[str, Any] = {
        "name": "main",
        "use": use_class,
        "model": model_id,
        "api_key": api_key,
        "supports_thinking": thinking_supported,
    }

    if base_url:
        entry["base_url"] = base_url

    if thinking_supported:
        entry.update(_build_thinking_config(provider, model_id))

    return entry


def _build_thinking_config(provider: str, model_id: str) -> dict[str, Any]:
    if "deepseek" in model_id.lower():
        return {
            "when_thinking_enabled": {"extra_body": {"thinking": {"type": "enabled"}}},
            "when_thinking_disabled": {"extra_body": {"thinking": {"type": "disabled"}}},
        }
    elif provider in ("openai", "openai_compatible"):
        return {
            "when_thinking_enabled": {"extra_body": {"enable_thinking": True}},
            "when_thinking_disabled": {"extra_body": {"enable_thinking": False}},
        }
    elif provider == "anthropic":
        return {
            "when_thinking_enabled": {"thinking": {"type": "enabled", "budget_tokens": 10000}},
            "when_thinking_disabled": {"thinking": {"type": "disabled"}},
        }
    return {}
