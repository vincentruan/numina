---
title: "DeerFlow Adapter: stream_dispatch Type Mismatch and Security Issues in 2.0 Alignment Refactor"
date: "2026-05-16"
category: integration-issues
module: server/apps/agent
problem_type: integration_issue
component: assistant
severity: critical
symptoms:
  - "All 6 raw-text streaming endpoints raise AttributeError: 'StreamChunk' object has no attribute 'encode' at runtime"
  - "Path traversal possible via unsanitized X-Family-Id header in filesystem write paths"
  - "Timing oracle in _verify_token via non-constant-time string comparison"
  - "SSRF possible via unvalidated DEERFLOW_GATEWAY_URL base URL"
root_cause: wrong_api
resolution_type: code_fix
related_components:
  - authentication
  - service_object
tags:
  - stream-dispatch
  - streamchunk
  - type-mismatch
  - path-traversal
  - ssrf
  - timing-oracle
  - security
  - async-generator
---

# DeerFlow Adapter: stream_dispatch Type Mismatch and Security Issues in 2.0 Alignment Refactor

> **Update note (2026-07-20):** The 6 raw-text streaming routers (`/alerts/stream`, `/allocation/stream`, `/liability/stream`, `/spending_leak/stream`, `/disposal/stream`, `/time_machine/stream`) and the `orchestrator.stream_dispatch()` method that Fix 1 patches were **deleted as dead code** in the two-AI-apps unified-dispatch refactor (U5/U7/U8) — the trigger-skill routers had been unreachable since commit `a97eb08c`. The `StreamChunk` type itself and `DeerFlowAdapter.stream_dispatch` survive on the adapter class. **Fix 1 is historical** (the patched code no longer exists). **Fixes 2–4 (security: `family_id` validation, `hmac.compare_digest` token comparison, `DEERFLOW_GATEWAY_URL` allowlist) remain current** — `gateway.py` still uses `_SAFE_ID_PATTERN` + `_verify_token`, and `family_id` validation now lives in `server/apps/agent/core/backend_client.py:_validate_family_id`. The security lessons are the durable part of this doc.

## Problem

The DeerFlow 2.0 adapter alignment refactor (`feat/deerflow2-alignment`) changed `orchestrator.stream_dispatch()` to yield `StreamChunk` dataclass objects instead of plain strings, but did not update the 6 raw-text streaming routers that call `.encode("utf-8")` on the yielded values. The same refactor introduced a new Gateway API proxy (`gateway.py`) with three security issues: unsanitized `family_id` header values reaching filesystem write paths (path traversal), non-constant-time token comparison (timing oracle), and an unvalidated `DEERFLOW_GATEWAY_URL` base URL (SSRF).

## Symptoms

**P0 — Runtime crash on all raw-text streaming endpoints:**
Every call to `/alerts/stream`, `/allocation/stream`, `/liability/stream`, `/spending_leak/stream`, `/disposal/stream`, or `/time_machine/stream` raises:
```
AttributeError: 'StreamChunk' object has no attribute 'encode'
```
at the router's `chunk.encode("utf-8")` call. The NDJSON path (`/alerts/events`, `/chat/ask/stream`) is unaffected — it uses `stream_dispatch_events()` which was updated correctly.

**P0 — Path traversal via X-Family-Id header:**
Attacker sends `POST /chat/ask` with valid `X-Agent-Token` and `X-Family-Id: ../../tmp/evil`. The agent writes to `data/workspace/../../tmp/evil/memory.json` (relative to CWD) and `data/sessions/../../tmp/evil/.../session.jsonl`, potentially overwriting any file the process has write access to.

**P1 — Timing oracle on token comparison:**
`gateway.py` `_verify_token` uses `x_agent_token != settings.AGENT_INTERNAL_TOKEN` (short-circuit string comparison). On a co-located Docker network, response timing differences are measurable enough to recover the token character by character.

**P1 — SSRF via DEERFLOW_GATEWAY_URL:**
An operator who can set env vars configures `DEERFLOW_GATEWAY_URL=http://backend:8000/internal`. All three gateway proxy endpoints (`/models`, `/skills/{name}`, `/threads/{id}`) redirect to arbitrary internal services, bypassing network segmentation.

## What Didn't Work

**Stream type mismatch — callers not updated:**
`adapter.stream_dispatch()` was refactored to yield `StreamChunk` objects (replacing `[THINK]`/`[TEXT]` string prefixes). The orchestrator's `stream_dispatch()` correctly extracts `chunk.content` for `answer_parts` accumulation (lines 367–369), but then `yield chunk` on line 370 yields the `StreamChunk` object itself — not the extracted string. All 6 raw-text routers still call `chunk.encode("utf-8")` expecting the old `str` contract.

The NDJSON path was updated correctly because `stream_dispatch_events()` explicitly calls `_chunk_to_event_lines(chunk)` which dispatches on `chunk.type`. The raw-text path was missed because it looked like a passthrough.

**Path traversal — validation applied to gateway but not family_id:**
`gateway.py` correctly validates `skill_name` and `thread_id` via `_SAFE_ID_PATTERN` (line 24). The same pattern was not applied to `family_id` from the `X-Family-Id` header, which reaches two filesystem write paths:
- `family_adapter_cache.py`: `Path(settings.AGENT_DATA_DIR) / family_id / "memory.json"` — `pathlib` does NOT strip `..` components on join
- `orchestrator.py`: plain string interpolation `f"{settings.SESSIONS_DATA_DIR}/{family_id}/..."` — no pathlib at all

**Timing oracle — new file, old pattern:**
`gateway.py` was written with `x_agent_token != settings.AGENT_INTERNAL_TOKEN`. Other routers (e.g., `alerts.py` line 30) correctly use `hmac.compare_digest`. The new file did not follow the established pattern.

**SSRF — path-segment guard does not protect base URL:**
`_SAFE_ID_PATTERN` only guards the path suffix appended after the base URL (`skill_name`, `thread_id`). The base URL itself (`DEERFLOW_GATEWAY_URL`) has no validation. The `_SAFE_ID_PATTERN` check on the suffix is insufficient — an attacker controls the base, not just the suffix.

## Solution

### Fix 1: Restore `str` contract in `orchestrator.stream_dispatch()`

> **Historical (2026-07):** `orchestrator.py` and its `stream_dispatch()` method were deleted in the unified-dispatch refactor. This fix is retained as a record of the `StreamChunk`-vs-`str` contract issue; the patched code path no longer exists.

**File:** `server/apps/agent/services/orchestrator.py` (~line 370) *(deleted)*

```python
# Before (broken — yields StreamChunk object):
async for chunk in adapter.stream_dispatch(...):
    text = chunk.content if chunk.type == "text" else None
    if text:
        answer_parts.append(text)
    yield chunk  # ← StreamChunk has no .encode()

# After (fixed — yields str, matching router contract):
async for chunk in adapter.stream_dispatch(...):
    if chunk.type == "text" and chunk.content:
        answer_parts.append(chunk.content)
        yield chunk.content  # ← str, routers can call .encode("utf-8")
    # thinking chunks are intentionally dropped from raw-text stream
    # they are surfaced only via stream_dispatch_events() NDJSON path
```

Routers require no changes — they already call `chunk.encode("utf-8")` on the yielded value, which works correctly when `chunk` is a `str`.

### Fix 2: Validate `family_id` at router layer

Add validation to every router that reads `X-Family-Id`. Use the same `_SAFE_ID_PATTERN` already in `gateway.py`:

```python
# Add to a shared location (e.g., apps/agent/core/validation.py) or inline per router:
import re
_SAFE_ID_RE = re.compile(r"^[A-Za-z0-9_\-]{1,64}$")

def validate_family_id(family_id: str) -> None:
    if not _SAFE_ID_RE.match(family_id):
        raise HTTPException(status_code=400, detail="无效的家庭 ID")
```

Apply at the top of each router handler that accepts `X-Family-Id` (alerts, allocation, chat, disposal, liability, spending_leak, time_machine, import_parse, suggest, report):

> **Update (2026-07):** most of those routers were deleted in the unified-dispatch refactor. The `family_id` validation pattern survived and now lives centrally in `server/apps/agent/core/backend_client.py:_validate_family_id` (called from `BackendClient.__init__` and every backend call). The `validate_family_id` per-router approach below is the historical shape; the centralized validator is the current one.

```python
@router.post("/stream")
async def stream(..., x_family_id: str = Header(..., alias="X-Family-Id"), ...):
    validate_family_id(x_family_id)  # ← add before any service call
    ...
```

### Fix 3: Use constant-time token comparison in `gateway.py`

**File:** `server/apps/agent/app/routers/gateway.py` (lines 27–29)

```python
# Before (timing oracle):
import hmac  # missing

def _verify_token(x_agent_token: str) -> None:
    if x_agent_token != settings.AGENT_INTERNAL_TOKEN:
        raise HTTPException(status_code=401, detail="invalid token")

# After (constant-time + Chinese error message per project convention):
import hmac

def _verify_token(x_agent_token: str) -> None:
    if not hmac.compare_digest(x_agent_token, settings.AGENT_INTERNAL_TOKEN):
        raise HTTPException(status_code=401, detail="无效的访问令牌")
```

### Fix 4: Validate `DEERFLOW_GATEWAY_URL` hostname at startup

**File:** `server/apps/agent/app/config.py`

```python
from urllib.parse import urlparse

class AgentSettings(BaseSettings):
    DEERFLOW_GATEWAY_URL: str = "http://deerflow:8001"

    def model_post_init(self, __context: Any) -> None:
        parsed = urlparse(self.DEERFLOW_GATEWAY_URL)
        allowed_hosts = {"deerflow", "localhost", "127.0.0.1"}
        if parsed.hostname not in allowed_hosts:
            raise ValueError(
                f"DEERFLOW_GATEWAY_URL hostname '{parsed.hostname}' not in allowlist {allowed_hosts}"
            )
```

This fails fast at startup — the process refuses to start if the URL points to an unauthorized host.

## Why This Works

**Fix 1:** Restores the `AsyncGenerator[str, None]` contract that all 6 routers expect. The orchestrator already extracted `chunk.content` for accumulation — the fix aligns the `yield` with that extraction. Thinking chunks are intentionally dropped from the raw-text stream; they are only surfaced via the NDJSON `stream_dispatch_events()` path which handles `StreamChunk` correctly.

**Fix 2:** Blocks traversal sequences (`../`, `..\\`) at the router boundary before they reach any filesystem operation. `pathlib` does NOT sanitize `..` components — `Path("data") / "../../etc"` resolves to `../../etc` relative to CWD. Regex validation (`^[A-Za-z0-9_\-]{1,64}$`) ensures `family_id` contains only safe characters. This is consistent with existing security patterns in `gateway.py` for `skill_name` and `thread_id`.

**Fix 3:** `hmac.compare_digest` performs a constant-time comparison that always compares all characters regardless of where the first mismatch occurs, preventing timing leakage. This is the standard Python pattern for credential comparison.

**Fix 4:** URL parsing at startup extracts the hostname from `DEERFLOW_GATEWAY_URL` and rejects any value not in the explicit allowlist. This prevents SSRF even if an operator can set env vars — the process refuses to start with an unauthorized gateway URL.

## Prevention

**Stream type contract:**
- Any refactor that changes a generator's yield type (`AsyncGenerator[X, None]`) must update all callers in the same commit. Search for all `async for chunk in <generator>` call sites before changing the yield type.
- Add at least one integration test covering a `*/stream` endpoint end-to-end (router → orchestrator → adapter → mock DeerFlowClient). The P0 crash would have been caught immediately by any test that calls a streaming endpoint and consumes the response.
- When `stream_dispatch()` yields `StreamChunk`, the raw-text routers must extract `.content` before encoding. The NDJSON path (`stream_dispatch_events`) handles `StreamChunk` correctly via `_chunk_to_event_lines()` — use that as the reference pattern.

**HTTP header validation:**
- Any value from an HTTP header used in a filesystem path must be validated at the router layer before entering any service.
- Standard pattern: `re.compile(r"^[A-Za-z0-9_\-]{1,64}$")` — same as `_SAFE_ID_PATTERN` in `gateway.py`.
- `pathlib` does NOT sanitize `..` components. Never assume `Path(base) / user_input` is safe.
- Add to `server/apps/agent/CLAUDE.md` Key Invariants: "All `X-Family-Id` header values must be validated against `_SAFE_ID_RE` before use in filesystem paths or service calls."

**Token comparison:**
- All secret/token/password comparisons must use `hmac.compare_digest`, never `==` or `!=`.
- When writing a new router, copy the auth pattern from an existing router (e.g., `alerts.py`) rather than writing it from scratch.

**Gateway URL validation:**
- All URLs configurable via env vars that are used for outbound HTTP requests must have hostname allowlists validated at startup (fail-fast).
- Path-segment validation on the suffix is not sufficient — the base URL must also be constrained.
- Consider a `TRUSTED_GATEWAY_HOSTS` env var for operators who need custom gateway deployments.

## Related Issues

- [`docs/solutions/integration-issues/deerflow-harness-silent-fallback-and-concurrency-fixes-2026-04-12.md`](deerflow-harness-silent-fallback-and-concurrency-fixes-2026-04-12.md) — Prior DeerFlow adapter bugs: silent fallback, `_CHECKPOINTER_LOCK` acquisition, private import violations. The stream type mismatch in this doc is a downstream consequence of the adapter refactoring covered there.
- [`docs/solutions/integration-issues/deerflow-glm5-thinking-provider-endpoint-mismatch-2026-05-16.md`](deerflow-glm5-thinking-provider-endpoint-mismatch-2026-05-16.md) — DeerFlow adapter stream event handling and cache invalidation patterns. The `StreamChunk` type introduced in this refactor is related to the stream event handling discussed there.
- [`docs/solutions/best-practices/security-protection.md`](../best-practices/security-protection.md) — Timing oracle and rate limiting patterns. The `hmac.compare_digest` fix in this doc extends the guidance there to the new gateway router.
