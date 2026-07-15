"""DeerFlow2 model entry construction from DB provider data.

Single source of truth for the per-family ``models[0]`` block in the
generated DeerFlow temp config. Consumed by ``EffectiveConfigBuilder.build``
on every dispatch.

Provider-specific contracts (verified against context7 official docs, 2026):

- **DeepSeek R1** — ``extra_body.thinking.{type: enabled|disabled}`` (DeerFlow CONFIGURATION.md).
- **OpenAI-compatible vendors** (GLM/Qwen/QwQ via DashScope/Novita/vLLM) —
  ``extra_body.enable_thinking`` boolean (vendor extension).
- **Native OpenAI** (gpt-5*, o-series) — ``supports_reasoning_effort: true``
  + Responses API (``use_responses_api: true`` + ``output_version: responses/v1``).
- **Anthropic Claude** (native Messages API) — ``thinking.type=enabled`` with
  ``budget_tokens`` computed dynamically as a fraction of resolved max_tokens.

max_tokens resolution
---------------------
Three-tier priority via ``_resolve_max_tokens``:
  1. ``ai_provider['max_tokens']`` — user-set in DB ``ai_providers`` row
  2. ``system-config.yaml`` prefix-matched default
  3. ``None`` — key omitted; SDK / vendor defaults take over
"""
from __future__ import annotations

import logging
from typing import Any

from packages.core.system_config import get_max_tokens_default

logger = logging.getLogger(__name__)


# ── Provider class mapping ──────────────────────────────────────────
_PROVIDER_CLASS_MAP: dict[str, str] = {
    "anthropic": "langchain_anthropic:ChatAnthropic",
    "openai": "langchain_openai:ChatOpenAI",
    "openai_compatible": "langchain_openai:ChatOpenAI",
}

_THINKING_CLASS_OVERRIDES: dict[str, str] = {
    "deepseek": "deerflow.models.patched_deepseek:PatchedChatDeepSeek",
    "openai_compatible": "deerflow.models.patched_openai:PatchedChatOpenAI",
}


# ── Anthropic extended-thinking budget tokens (fraction-based) ──────
# Anthropic API constraints (verified via context7 against
# anthropic-sdk-python `examples/thinking.py`):
#   - budget_tokens >= 1024  (hard minimum)
#   - budget_tokens <  max_tokens  (must leave room for visible output)
ANTHROPIC_BUDGET_MIN_TOKENS = 1024
ANTHROPIC_HIGH_EFFORT_FRACTION = 0.60
ANTHROPIC_BUDGET_OUTPUT_HEADROOM_TOKENS = 256
# Used when neither user nor yaml gives a max_tokens (matches DeerFlow
# `claude-sonnet-4.6` example).
ANTHROPIC_FALLBACK_MAX_TOKENS = 4096


def _resolve_max_tokens(ai_provider: dict[str, Any]) -> int | None:
    """Resolve effective max_tokens with three-tier priority.

    1. ``ai_provider['max_tokens']`` — user-set positive int.
    2. ``system-config.yaml`` prefix-matched default for the model_id.
    3. ``None`` — caller should NOT emit max_tokens in the model entry.
    """
    explicit = ai_provider.get("max_tokens")
    if isinstance(explicit, int) and explicit > 0:
        return explicit
    model_id = (ai_provider.get("ai_model_id") or "").strip()
    return get_max_tokens_default(model_id)


def _compute_anthropic_thinking_budget(
    max_tokens: int,
    fraction: float,
) -> int | None:
    """Compute Anthropic ``budget_tokens`` for the given max_tokens / fraction.

    Returns ``None`` when ``max_tokens`` is too small to satisfy both
    ``budget >= ANTHROPIC_BUDGET_MIN_TOKENS`` and ``budget < max_tokens`` —
    caller must fall back to ``thinking.type=disabled``.
    """
    if max_tokens <= 0 or fraction <= 0:
        return None
    raw = int(max_tokens * fraction)
    capped = min(raw, max_tokens - ANTHROPIC_BUDGET_OUTPUT_HEADROOM_TOKENS)
    if capped < ANTHROPIC_BUDGET_MIN_TOKENS:
        return None
    return capped


def build_model_entry(ai_provider: dict[str, Any]) -> dict[str, Any]:
    """Build the ``models[0]`` dict for the DeerFlow temp config.

    Caller passes the ai_provider dict from BackendClient. Returns a fully-
    formed model entry honouring per-provider thinking, reasoning_effort,
    Responses API, and max_tokens conventions.
    """
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

    # Pick LangChain class. Native OpenAI uses the stock class because
    # reasoning is delivered via standard top-level fields (not vendor
    # reasoning_content streams that need a patched class).
    use_class = _PROVIDER_CLASS_MAP.get(provider, "langchain_openai:ChatOpenAI")
    if thinking_supported:
        if "deepseek" in model_id.lower():
            use_class = _THINKING_CLASS_OVERRIDES["deepseek"]
        elif provider == "openai" and not base_url:
            # Native OpenAI: stock ChatOpenAI; reasoning effort via
            # supports_reasoning_effort + Responses API.
            use_class = "langchain_openai:ChatOpenAI"
        elif provider in ("openai", "openai_compatible"):
            use_class = _THINKING_CLASS_OVERRIDES["openai_compatible"]

    entry: dict[str, Any] = {
        "name": "main",
        "use": use_class,
        "model": model_id,
        "api_key": api_key,
        "supports_thinking": thinking_supported,
    }

    if base_url:
        entry["base_url"] = base_url

    # Resolve max_tokens (user → yaml → None) and emit when known.
    resolved_max_tokens = _resolve_max_tokens(ai_provider)
    if resolved_max_tokens is not None:
        entry["max_tokens"] = resolved_max_tokens

    # Native OpenAI → Responses API path (DeerFlow 2 README's gpt-5-responses recipe).
    # OpenAI-compatible gateways stay on Chat Completions (no Responses upstream).
    if provider == "openai" and not base_url:
        entry["use_responses_api"] = True
        entry["output_version"] = "responses/v1"

    if thinking_supported:
        entry.update(_build_thinking_config(provider, base_url, model_id, resolved_max_tokens))

    # ── DeerFlow factory.py parity: stream_usage + stream_chunk_timeout ──
    # DeerFlow's factory.create_chat_model() auto-injects these for all
    # OpenAI-compatible models. Without them:
    #   - stream_usage: LangChain only auto-enables when no custom base_url
    #     is set, so third-party endpoints silently lose token usage data
    #     (TokenUsage shows 0/0/0).
    #   - stream_chunk_timeout: LangChain default is 60s, too aggressive for
    #     reasoning models (DeepSeek-R1, QwQ) whose first chunk can take
    #     90~150s. We use the user-configured timeout_seconds from DB.
    _openai_compat_use_paths = (
        "langchain_openai:ChatOpenAI",
        "deerflow.models.patched_openai:PatchedChatOpenAI",
    )
    if use_class in _openai_compat_use_paths:
        entry.setdefault("stream_usage", True)
        db_timeout = ai_provider.get("timeout_seconds")
        if isinstance(db_timeout, int) and db_timeout > 0:
            entry.setdefault("stream_chunk_timeout", float(db_timeout))

    # ── api_base → base_url normalisation ──
    # langchain_openai.ChatOpenAI accepts the endpoint override as ``base_url``
    # (with ``openai_api_base`` as a legacy alias). If a caller passes
    # ``api_base`` (a common mistake copied from other model classes),
    # LangChain silently diverts it into ``model_kwargs``, which then gets
    # spread into every Completions.create() call and rejected by the OpenAI
    # SDK with "unexpected keyword argument 'api_base'". Normalise here so
    # the endpoint override works as the user intended.
    if "api_base" in entry and "base_url" not in entry:
        entry["base_url"] = entry.pop("api_base")

    return entry


def _build_thinking_config(
    provider: str,
    base_url: str | None,
    model_id: str,
    resolved_max_tokens: int | None,
) -> dict[str, Any]:
    """Build the per-provider when_thinking_enabled/disabled config block.

    See module docstring for provider contracts.
    """
    if "deepseek" in model_id.lower():
        # DeepSeek R1 thinking is intrinsic; both branches set extra_body.thinking.type.
        return {
            "when_thinking_enabled": {"extra_body": {"thinking": {"type": "enabled"}}},
            "when_thinking_disabled": {"extra_body": {"thinking": {"type": "disabled"}}},
        }
    if provider == "openai" and not base_url:
        # Native OpenAI: top-level reasoning_effort. DeerFlow harness emits
        # reasoning.effort (Responses) or reasoning_effort (Chat Completions)
        # depending on the use_responses_api flag.
        return {
            "supports_reasoning_effort": True,
            "when_thinking_enabled": {"reasoning_effort": "high"},
            "when_thinking_disabled": {"reasoning_effort": "low"},
        }
    if provider in ("openai", "openai_compatible"):
        # OpenAI-compatible vendors: extra_body.enable_thinking vendor extension.
        return {
            "when_thinking_enabled": {"extra_body": {"enable_thinking": True}},
            "when_thinking_disabled": {"extra_body": {"enable_thinking": False}},
        }
    if provider == "anthropic":
        # Native Anthropic: thinking.type + budget_tokens (fraction-based).
        budget_max = resolved_max_tokens or ANTHROPIC_FALLBACK_MAX_TOKENS
        high_budget = _compute_anthropic_thinking_budget(
            budget_max, ANTHROPIC_HIGH_EFFORT_FRACTION
        )
        if high_budget is None:
            logger.info(
                "anthropic max_tokens=%s too small for budget>=%s with %.0f%% fraction; "
                "falling back to thinking.type=disabled",
                budget_max,
                ANTHROPIC_BUDGET_MIN_TOKENS,
                ANTHROPIC_HIGH_EFFORT_FRACTION * 100,
            )
            return {
                "when_thinking_enabled": {"thinking": {"type": "disabled"}},
                "when_thinking_disabled": {"thinking": {"type": "disabled"}},
            }
        return {
            "when_thinking_enabled": {
                "thinking": {"type": "enabled", "budget_tokens": high_budget}
            },
            "when_thinking_disabled": {"thinking": {"type": "disabled"}},
        }
    return {}
