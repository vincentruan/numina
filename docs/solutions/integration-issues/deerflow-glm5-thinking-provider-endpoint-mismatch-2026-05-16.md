---
title: GLM-5 Deep Thinking Not Working — Provider/Endpoint Mismatch in DeerFlow Adapter
date: 2026-05-16
category: docs/solutions/integration-issues
module: agent/deerflow_adapter
problem_type: integration_issue
component: assistant
symptoms:
  - deep_think=true requests produce no phase.thinking event in NDJSON stream
  - No token.stream events with is_thinking=true
  - Stream goes directly from phase.connecting to phase.answering, skipping thinking phase
  - '"LLM request failed: Error code: 404"' when ReasoningChatOpenAI used against Anthropic-compatible endpoint
root_cause: wrong_api
resolution_type: code_fix
severity: high
tags:
  - glm-5
  - deep-think
  - deerflow
  - langchain
  - openai-compatible
  - anthropic-endpoint
  - reasoning-content
  - enable-thinking
  - ReasoningChatOpenAI
  - ChatAnthropic
  - phase-thinking
  - family-adapter-cache
---

# GLM-5 Deep Thinking Not Working — Provider/Endpoint Mismatch in DeerFlow Adapter

## Problem

GLM-5's deep thinking feature (`deep_think=true`) produced no `phase.thinking` events in the NDJSON stream. The AI agent microservice uses DeerFlow, where `family_adapter_cache.py` generates per-family DeerFlow config YAML and selects a LangChain model class based on the `provider` and `thinking_supported` fields. `adapter.py` wraps DeerFlowClient, extracts `reasoning_content` from stream events, and emits `[THINK]`-prefixed chunks that the orchestrator converts to `phase.thinking` NDJSON events. The entire thinking pipeline was silently bypassed because the model was pointed at the wrong API endpoint format.

## Symptoms

- `deep_think=true` requests return normal responses with no `phase.thinking` event
- No `token.stream` events with `is_thinking: true`
- Stream sequence: `session.start` → `phase.connecting` → `phase.answering` → `token.stream` (no thinking phase)
- `LLM request failed: Error code: 404` when `ReasoningChatOpenAI` is used against an Anthropic-compatible endpoint
- `TypeError: Messages.create() got an unexpected keyword argument 'enable_thinking'` when `model_kwargs` workaround is attempted

## What Didn't Work

### Attempt 1: `ReasoningChatOpenAI` + Anthropic-compatible endpoint

Configured `ReasoningChatOpenAI` (which extends `ChatOpenAI`) against DashScope's Anthropic-compatible endpoint (`https://...dashscope.../apps/anthropic`).

**Result:** `LLM request failed: Error code: 404`

**Why it failed:** `ReasoningChatOpenAI` is an OpenAI-based LangChain class. It calls `/v1/chat/completions`. DashScope's Anthropic-compatible endpoint expects Anthropic-style requests at `/v1/messages`. The path mismatch causes a 404 — the model class and endpoint format are incompatible.

### Attempt 2: `ChatAnthropic` + `thinking: {type: enabled, budget_tokens: 10000}`

Switched to `ChatAnthropic` with the standard Anthropic thinking parameter against the same Anthropic-compatible endpoint.

**Result:** Normal response, no thinking content, no errors.

**Why it failed:** DashScope's Anthropic-compatible endpoint silently ignores the Anthropic `thinking` parameter for GLM-5. GLM-5 is not a native Anthropic model — the endpoint accepts the request but discards the thinking instruction without error.

### Attempt 3: `ChatAnthropic` + `model_kwargs: {enable_thinking: True}`

Tried passing `enable_thinking: True` via `model_kwargs` to inject the OpenAI-style thinking flag through the Anthropic client.

**Result:** `TypeError: Messages.create() got an unexpected keyword argument 'enable_thinking'`

**Why it failed:** The Anthropic SDK's `Messages.create()` validates parameters strictly. `enable_thinking` is an OpenAI-compatible API parameter — it is not valid in the Anthropic SDK and cannot be injected via `model_kwargs`.

## Solution

### 1. Configuration Change (required)

The model was misconfigured with `provider="anthropic"` pointing at DashScope's Anthropic-compatible endpoint. GLM-5 thinking requires the **OpenAI-compatible endpoint** with `enable_thinking: true` in `extra_body`.

Update the AI provider config in the database:

| Field | Old Value | New Value |
|-------|-----------|-----------|
| `provider` | `"anthropic"` | `"openai"` or `"openai_compatible"` |
| `base_url` | `https://...dashscope.../apps/anthropic` | `https://...dashscope.../v1` |
| `thinking_supported` | `True` | `True` (unchanged) |

### 2. Code Fix in `family_adapter_cache.py`

Model class selection — route by `provider`, not model name prefix:

```python
if thinking_supported:
    if "deepseek" in model_id.lower():
        use_class = "deerflow.models.patched_deepseek:PatchedChatDeepSeek"
    elif provider in ("openai", "openai_compatible"):
        use_class = "deerflow.models.patched_openai:ReasoningChatOpenAI"
    elif provider == "anthropic":
        # Native Anthropic Claude models only
        use_class = "langchain_anthropic:ChatAnthropic"
    else:
        use_class = provider_class_map.get(provider, "langchain_openai:ChatOpenAI")
else:
    use_class = provider_class_map.get(provider, "langchain_openai:ChatOpenAI")
```

Thinking config per provider:

```python
if thinking_supported:
    if "deepseek" in model_id.lower():
        model_entry["when_thinking_enabled"] = {"extra_body": {"thinking": {"type": "enabled"}}}
        model_entry["when_thinking_disabled"] = {"extra_body": {"thinking": {"type": "disabled"}}}
    elif provider in ("openai", "openai_compatible"):
        # GLM-5, Qwen3, QwQ via OpenAI-compatible endpoint
        model_entry["when_thinking_enabled"] = {"extra_body": {"enable_thinking": True}}
        model_entry["when_thinking_disabled"] = {"extra_body": {"enable_thinking": False}}
    elif provider == "anthropic":
        # Native Claude models only — GLM/Qwen MUST use openai_compatible endpoint
        model_entry["when_thinking_enabled"] = {"thinking": {"type": "enabled", "budget_tokens": 10000}}
        model_entry["when_thinking_disabled"] = {"thinking": {"type": "disabled"}}
```

### 3. Code Improvement in `adapter.py`

Added Anthropic-style thinking content block handling alongside the existing `reasoning_content` extraction. This supports native Claude models (which return thinking as content blocks) in addition to OpenAI-compatible models (which return `reasoning_content` in `additional_kwargs`):

```python
# Emit reasoning/thinking content before the answer text
additional_kwargs = event.data.get("additional_kwargs") or {}
content = event.data.get("content")
reasoning = additional_kwargs.get("reasoning_content")
if isinstance(reasoning, str) and reasoning:
    loop.call_soon_threadsafe(queue.put_nowait, f"[THINK]{reasoning}")
# Also handle Anthropic-style thinking content blocks (native Claude models)
if isinstance(content, list):
    text_parts: list[str] = []
    for block in content:
        if isinstance(block, dict):
            if block.get("type") == "thinking" and block.get("thinking"):
                loop.call_soon_threadsafe(queue.put_nowait, f"[THINK]{block['thinking']}")
            elif block.get("type") == "text" and block.get("text"):
                text_parts.append(block["text"])
    if text_parts:
        loop.call_soon_threadsafe(queue.put_nowait, "".join(text_parts))
elif isinstance(content, str) and content:
    loop.call_soon_threadsafe(queue.put_nowait, content)
```

## Why This Works

The fundamental constraint is that **each LangChain model class is tightly coupled to a specific API wire format**:

| LangChain Class | API Format | Endpoint Path | Thinking Param |
|----------------|------------|---------------|----------------|
| `ChatOpenAI` / `ReasoningChatOpenAI` | OpenAI | `/v1/chat/completions` | `extra_body: {enable_thinking: true}` |
| `ChatAnthropic` / `ClaudeChatModel` | Anthropic | `/v1/messages` | `thinking: {type: enabled, budget_tokens: N}` |
| `PatchedChatDeepSeek` | OpenAI | `/v1/chat/completions` | `extra_body: {thinking: {type: enabled}}` |

DashScope's Anthropic-compatible endpoint (`/apps/anthropic`) accepts Anthropic-format requests but does **not** support GLM-5 thinking in any format — it silently ignores the `thinking` parameter. GLM-5 thinking is only available via DashScope's OpenAI-compatible endpoint (`/v1`) with `enable_thinking: true` in `extra_body`.

`ReasoningChatOpenAI` (DeerFlow's patched `ChatOpenAI`) correctly extracts `reasoning_content` from streaming deltas and stores it in `AIMessageChunk.additional_kwargs["reasoning_content"]`, which the adapter then emits as `[THINK]` chunks → `phase.thinking` NDJSON events.

## Provider/Model/Thinking Configuration Reference

| Provider | Model Examples | `thinking_supported` | LangChain Class | Thinking Config |
|----------|---------------|---------------------|-----------------|-----------------|
| `openai` / `openai_compatible` | GLM-5, Qwen3, QwQ | `True` | `ReasoningChatOpenAI` | `extra_body: {enable_thinking: true/false}` |
| `anthropic` | claude-sonnet-4-x, claude-haiku-4-x | `True` | `ChatAnthropic` | `thinking: {type: enabled/disabled, budget_tokens: N}` |
| `openai` / `openai_compatible` | DeepSeek-R1 | `True` | `PatchedChatDeepSeek` | `extra_body: {thinking: {type: enabled/disabled}}` |
| Any | Any | `False` | Standard class | No thinking config |

**Key rule:** GLM-5, Qwen3, QwQ accessed via DashScope **must** use `provider="openai"` or `provider="openai_compatible"` with the OpenAI-compatible base URL, even though DashScope also offers an Anthropic-compatible endpoint for these models. The Anthropic-compatible endpoint does not support thinking for non-Anthropic models.

## Verification

```bash
TOKEN=$(curl -s -X POST 'http://localhost/api/v1/auth/login' \
  -H 'Content-Type: application/json' \
  -d '{"username": "demouser", "password": "DemoPass123"}' \
  | python3 -c "import sys,json; d=json.load(sys.stdin); print(d['data']['access_token'])")

# deep_think=true: must see phase.thinking event
curl -s -X POST 'http://localhost/api/v1/ai/chat/stream' \
  -H "Authorization: Bearer $TOKEN" \
  -H 'Content-Type: application/json' \
  -d '{"question": "深度分析我的净资产", "deep_think": true}' \
  --no-buffer | grep '"type":"phase.thinking"'
# Expected: one matching line

# deep_think=false: must see NO phase.thinking event
curl -s -X POST 'http://localhost/api/v1/ai/chat/stream' \
  -H "Authorization: Bearer $TOKEN" \
  -H 'Content-Type: application/json' \
  -d '{"question": "你好", "deep_think": false}' \
  --no-buffer | grep '"type":"phase.thinking"'
# Expected: no output
```

Expected NDJSON event sequence for `deep_think=true`:

```
{"type":"session.start",...}
{"type":"phase.connecting",...}
{"type":"phase.thinking",...}                    ← thinking phase marker
{"type":"token.stream","is_thinking":true,...}   ← thinking tokens
{"type":"phase.answering",...}
{"type":"token.stream","is_thinking":false,...}  ← answer tokens
{"type":"capability.end",...}
```

## Prevention

- When adding a new AI provider config with `thinking_supported=True`, verify the `provider` field matches the endpoint format — not the model vendor. DashScope's `/v1` endpoint → `provider="openai_compatible"`. DashScope's `/apps/anthropic` endpoint → `provider="anthropic"` (but GLM/Qwen thinking won't work here).
- After changing `provider` or `base_url` in the AI config, invalidate the DeerFlow adapter cache: `POST /internal/cache/invalidate/{family_id}` with `X-Agent-Token` header, then restart the agent container to reload Python modules.
- The DeerFlow adapter cache holds a compiled `DeerFlowClient` per family. Config changes are not picked up until the cache entry is evicted or explicitly invalidated.
- Add a validation step in the AI provider config test endpoint that checks `provider` + `base_url` + `thinking_supported` consistency before saving.

## Related Issues

- [`deerflow-harness-silent-fallback-and-concurrency-fixes-2026-04-12.md`](./deerflow-harness-silent-fallback-and-concurrency-fixes-2026-04-12.md) — DeerFlow adapter initialization, singleton export, and concurrency patterns
