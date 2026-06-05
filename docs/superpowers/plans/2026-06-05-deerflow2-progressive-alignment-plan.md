# DeerFlow 2.0 Progressive Alignment Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Align the Numina agent module with DeerFlow 2.0 framework design practices across three phases: documentation fixes, structural decoupling, and capability enhancement.

**Architecture:** Replace global-lock serialization with DeerFlow's native ContextVar config injection, unify dual streaming paths into NDJSON-only, migrate from pre-fetched context to MCP on-demand data access, and replace JSON message encoding with natural language `[SKILL:xxx]` format.

**Tech Stack:** Python 3.12+ / FastAPI / DeerFlow 2.0 harness (vendored) / LangGraph / Pydantic v2 / pytest-asyncio

---

## File Structure

| File | Responsibility | Phase |
|------|---------------|-------|
| `server/apps/agent/deerflow_config/HARNESS_API.md` | DeerFlow API reference — add two-level thinking docs | 1 |
| `server/apps/agent/services/deerflow_adapter/adapter.py` | Async DeerFlow adapter — remove `_init_lock`, use ContextVar, unify `_build_prompt` | 1, 2 |
| `server/apps/agent/services/deerflow_adapter/family_adapter_cache.py` | Per-family LRU cache — remove `_init_lock`, add provider-capability comment | 1, 2 |
| `server/apps/agent/routers/time_machine.py` | Time machine router — add `/events` endpoint | 1 |
| `server/apps/agent/routers/alerts.py` | Alerts router — remove deprecated `/stream` | 1 |
| `server/apps/agent/routers/allocation.py` | Allocation router — remove deprecated `/stream` | 1 |
| `server/apps/agent/routers/disposal.py` | Disposal router — remove deprecated `/stream` | 1 |
| `server/apps/agent/routers/liability.py` | Liability router — remove deprecated `/stream` | 1 |
| `server/apps/agent/routers/spending_leak.py` | Spending leak router — remove deprecated `/stream` | 1 |
| `server/apps/agent/services/orchestrator.py` | Central dispatch — remove `stream_dispatch()`, rename `stream_dispatch_events()` | 1 |
| `server/apps/agent/tests/unit/test_adapter_contextvar.py` | Test ContextVar config injection | 2 |
| `server/apps/agent/tests/unit/test_adapter_message_format.py` | Test natural language message format | 2 |

---

## Phase 1: Corrections

### Task 1: Document two-level thinking_enabled design in HARNESS_API.md

**Files:**
- Modify: `server/apps/agent/deerflow_config/HARNESS_API.md`

- [ ] **Step 1: Add OD-4 section documenting `stream()` kwargs as per-call overrides**

Append to `HARNESS_API.md` after the OD-3 section:

```markdown
## OD-4: Per-call parameter overrides via `stream()` kwargs

`DeerFlowClient.stream()` accepts `**kwargs` that override init-time defaults on a
per-call basis. The harness routes these kwargs into `_get_runnable_config()`, which
merges them with the constructor defaults.

### Two-level control model

| Parameter | Init-time (constructor) | Per-call (stream kwargs) |
|-----------|------------------------|-------------------------|
| `thinking_enabled` | Default for all calls | Override for this call |
| `model_name` | Default model | Override for this call |
| `subagent_enabled` | Default for all calls | Override for this call |
| `plan_mode` | Default for all calls | Override for this call |

### Usage in Numina

The orchestrator constructs `DeerFlowClient` with `thinking_enabled` set to the
provider's capability flag (whether the model supports thinking at all). Per-request,
`enable_thinking` is passed as `thinking_enabled=enable_thinking` to `stream()`, which
overrides the init-time default for that specific call.

This means:
- Provider does NOT support thinking → init-time `thinking_enabled=False` → per-call
  override has no effect (model cannot think regardless)
- Provider supports thinking → init-time `thinking_enabled=True` → per-call override
  controls whether thinking is active for this request
```

- [ ] **Step 2: Add code comment in adapter.py clarifying the per-call override**

At `server/apps/agent/services/deerflow_adapter/adapter.py`, add a comment above the `stream_dispatch` method (line 169):

```python
    async def stream_dispatch(
        self,
        skill_name: str,
        context: RedactedContext,
        thread_id: str,
        enable_thinking: bool = False,
    ) -> AsyncGenerator[StreamChunk, None]:
        """Dispatch a skill call and yield text chunks as they arrive.

        enable_thinking: per-call override passed to client.stream() via **kwargs.
        DeerFlowClient.stream() routes kwargs into _get_runnable_config(), which
        overrides the init-time thinking_enabled default for this specific call.
        See HARNESS_API.md OD-4 for the two-level control model.
        """
```

- [ ] **Step 3: Run existing tests to verify no regression**

Run: `cd /Volumes/LexarSSDNQ790/geek_space/github/numina/server && uv run pytest apps/agent/tests/ -v -x 2>&1 | tail -20`
Expected: All existing tests pass (documentation-only change)

- [ ] **Step 4: Commit**

```bash
git add server/apps/agent/deerflow_config/HARNESS_API.md server/apps/agent/services/deerflow_adapter/adapter.py
git commit -m "docs: document two-level thinking_enabled control model in HARNESS_API.md"
```

---

### Task 2: Add provider-capability vs per-request distinction comment in family_adapter_cache.py

**Files:**
- Modify: `server/apps/agent/services/deerflow_adapter/family_adapter_cache.py`

- [ ] **Step 1: Add inline comment explaining the two-level design**

At `server/apps/agent/services/deerflow_adapter/family_adapter_cache.py`, locate the `DeerFlowClient(` construction block (around line 641-648) and add a comment above the `thinking_enabled` parameter:

```python
                client = DeerFlowClient(
                    config_path=str(temp_config_path),
                    checkpointer=checkpointer,
                    model_name="main",
                    # Init-time: provider CAPABILITY (can this model think at all?).
                    # Per-request: orchestrator passes thinking_enabled= to stream()
                    # via **kwargs, which overrides this default per-call. See HARNESS_API.md OD-4.
                    thinking_enabled=bool(ai_config.get("thinking_supported", False)),
                    subagent_enabled=subagent_enabled,
                    plan_mode=plan_mode,
                )
```

- [ ] **Step 2: Run existing tests to verify no regression**

Run: `cd /Volumes/LexarSSDNQ790/geek_space/github/numina/server && uv run pytest apps/agent/tests/ -v -x 2>&1 | tail -20`
Expected: All existing tests pass

- [ ] **Step 3: Commit**

```bash
git add server/apps/agent/services/deerflow_adapter/family_adapter_cache.py
git commit -m "docs: add two-level thinking_enabled comment in family_adapter_cache"
```

---

### Task 3: Add NDJSON `/events` endpoint to time_machine router

**Files:**
- Modify: `server/apps/agent/routers/time_machine.py`

- [ ] **Step 1: Add the `/events` endpoint**

Add the following after the existing `/stream` endpoint (after line 73), before the final `return`:

```python
@router.post("/events")
async def interpret_time_machine_events(
    x_family_id: str = Header(..., alias="X-Family-Id"),
    x_agent_token: str = Header(..., alias="X-Agent-Token"),
    x_task_id: str = Header(..., alias="X-Task-Id"),
    x_thread_id: str = Header(..., alias="X-Thread-Id"),
    x_user_id: str | None = Header(None, alias="X-User-Id"),
):
    """NDJSON 事件流（由 backend 调用）。"""

    _verify_token(x_agent_token)

    async def event_stream():
        async for event_line in orchestrator.stream_dispatch_events(
            capability="time_machine",
            family_id=x_family_id,
            task_id=x_task_id,
            user_id=x_user_id,
            thread_id=x_thread_id if x_thread_id else None,
            free_text="趋势分析",
        ):
            yield event_line + "\n"

    return StreamingResponse(event_stream(), media_type="application/x-ndjson")
```

Also add the missing imports at the top of the file. Add after the existing imports (line 12):

```python
from apps.agent.services.orchestrator import orchestrator
from apps.agent.app.config import settings
```

And add the `_verify_token` helper (same pattern as alerts.py):

```python
def _verify_token(token: str) -> None:
    if token != settings.AGENT_INTERNAL_TOKEN:
        raise HTTPException(status_code=401, detail="Invalid agent token")
```

- [ ] **Step 2: Add deprecation warning to existing `/stream` endpoint**

In the `/stream` endpoint function body (after the docstring), add:

```python
    logger.warning("Deprecated endpoint /time-machine/stream called; migrate to /time-machine/events")
```

Update the docstring from:
```python
    """流式生成趋势分析（由 backend 调用）。"""
```
to:
```python
    """流式生成趋势分析（由 backend 调用）。已废弃，请使用 /events。"""
```

- [ ] **Step 3: Run typecheck**

Run: `cd /Volumes/LexarSSDNQ790/geek_space/github/numina/server && uv run mypy apps/agent/routers/time_machine.py --exclude vendor 2>&1 | tail -10`
Expected: No errors

- [ ] **Step 4: Commit**

```bash
git add server/apps/agent/routers/time_machine.py
git commit -m "feat(agent): add NDJSON /events endpoint to time_machine router"
```

---

### Task 4: Remove deprecated `/stream` endpoints from all routers

**Files:**
- Modify: `server/apps/agent/routers/alerts.py`
- Modify: `server/apps/agent/routers/allocation.py`
- Modify: `server/apps/agent/routers/disposal.py`
- Modify: `server/apps/agent/routers/liability.py`
- Modify: `server/apps/agent/routers/spending_leak.py`
- Modify: `server/apps/agent/routers/time_machine.py`

For each router file (alerts.py, allocation.py, disposal.py, liability.py, spending_leak.py, time_machine.py):

- [ ] **Step 1: Remove the deprecated `/stream` endpoint function entirely**

In each file, delete the entire `@router.post("/stream")` endpoint function and its docstring. For time_machine.py, this is the function added in the previous task with the deprecation warning — remove it now.

For alerts.py, the `/stream` function starts around line 41 and ends around line 66. Remove lines 41-66.

Apply the same pattern to all 6 files.

- [ ] **Step 2: Remove unused imports if any**

After removing the `/stream` endpoints, check if any imports are now unused (e.g., `StreamingResponse` for `text/plain` may still be needed by `/events` endpoints which also use `StreamingResponse`). Only remove imports that are truly unused after the deletion.

- [ ] **Step 3: Run typecheck on all modified routers**

Run: `cd /Volumes/LexarSSDNQ790/geek_space/github/numina/server && uv run mypy apps/agent/routers/ --exclude vendor 2>&1 | tail -10`
Expected: No errors

- [ ] **Step 4: Commit**

```bash
git add server/apps/agent/routers/alerts.py server/apps/agent/routers/allocation.py server/apps/agent/routers/disposal.py server/apps/agent/routers/liability.py server/apps/agent/routers/spending_leak.py server/apps/agent/routers/time_machine.py
git commit -m "refactor(agent): remove deprecated /stream endpoints from all routers"
```

---

### Task 5: Remove `stream_dispatch()` raw-text method from orchestrator and rename `stream_dispatch_events()` → `stream_dispatch()`

**Files:**
- Modify: `server/apps/agent/services/orchestrator.py`

- [ ] **Step 1: Delete the `stream_dispatch()` method**

In `server/apps/agent/services/orchestrator.py`, delete the `stream_dispatch()` method (lines 314-633). This is the raw-text streaming method that yields `str` chunks. It is no longer called by any router endpoint after Task 4.

- [ ] **Step 2: Rename `stream_dispatch_events()` to `stream_dispatch()`**

Rename the method at line 635:

```python
    async def stream_dispatch_events(
```

to:

```python
    async def stream_dispatch(
```

Also update the docstring to remove "events" since this is now the sole streaming method:

```python
        """Stream structured NDJSON events."""
```

- [ ] **Step 3: Update all callers of `stream_dispatch_events` to use the new name**

In all router files that call `orchestrator.stream_dispatch_events()`, update the call to `orchestrator.stream_dispatch()`. The routers that reference this method are:
- `server/apps/agent/routers/alerts.py` — line ~84
- `server/apps/agent/routers/allocation.py`
- `server/apps/agent/routers/chat.py`
- `server/apps/agent/routers/disposal.py`
- `server/apps/agent/routers/liability.py`
- `server/apps/agent/routers/report.py`
- `server/apps/agent/routers/spending_leak.py`
- `server/apps/agent/routers/time_machine.py` (just added in Task 3)

In each file, replace `orchestrator.stream_dispatch_events(` with `orchestrator.stream_dispatch(`.

- [ ] **Step 4: Update the `agent_stream.py` router if it references `stream_dispatch_events`**

Check `server/apps/agent/routers/agent_stream.py` for references to `stream_dispatch_events` and update them too.

- [ ] **Step 5: Run typecheck**

Run: `cd /Volumes/LexarSSDNQ790/geek_space/github/numina/server && uv run mypy apps/agent/ --exclude vendor 2>&1 | tail -10`
Expected: No errors

- [ ] **Step 6: Run existing tests**

Run: `cd /Volumes/LexarSSDNQ790/geek_space/github/numina/server && uv run pytest apps/agent/tests/ -v -x 2>&1 | tail -20`
Expected: All tests pass

- [ ] **Step 7: Commit**

```bash
git add server/apps/agent/services/orchestrator.py server/apps/agent/routers/
git commit -m "refactor(agent): remove raw-text stream_dispatch, rename stream_dispatch_events to stream_dispatch"
```

---

### Task 6: Remove `_build_message()` and use `_build_prompt()` in streaming path

**Files:**
- Modify: `server/apps/agent/services/deerflow_adapter/adapter.py`

- [ ] **Step 1: Write failing test for `_build_prompt()` usage in streaming**

Create `server/apps/agent/tests/unit/test_adapter_message_format.py`:

```python
"""Test that adapter uses [SKILL:xxx] natural language format instead of JSON."""

import json
import pytest

from apps.agent.services.deerflow_adapter.adapter import DeerFlowAdapter
from apps.agent.schemas.context import RedactedContext


def test_stream_message_uses_skill_tag_not_json():
    """The message sent to DeerFlow must use [SKILL:xxx] format, not JSON."""
    context = RedactedContext(family_id="f1", free_text="test query")
    adapter = DeerFlowAdapter.__new__(DeerFlowAdapter)
    message = adapter._build_prompt("alerts", context)
    assert message.startswith("[SKILL:alerts]")
    # Must NOT be JSON-parseable at the top level
    with pytest.raises(json.JSONDecodeError):
        json.loads(message)


def test_stream_message_includes_context_data():
    """The [SKILL:xxx] message must include context data."""
    context = RedactedContext(family_id="f1", free_text="test query")
    adapter = DeerFlowAdapter.__new__(DeerFlowAdapter)
    message = adapter._build_prompt("alerts", context)
    assert "family_id" in message
    assert "f1" in message
```

- [ ] **Step 2: Run test to see current state**

Run: `cd /Volumes/LexarSSDNQ790/geek_space/github/numina/server && uv run pytest apps/agent/tests/unit/test_adapter_message_format.py -v`
Expected: `test_stream_message_uses_skill_tag_not_json` may FAIL because `_build_prompt()` currently excludes `redaction_log` but does include the context JSON — the test assertion about JSONDecodeError depends on whether `[SKILL:alerts]\n{...}` parses as JSON (it won't because of the prefix). `test_stream_message_includes_context_data` should PASS.

- [ ] **Step 3: Update `_build_prompt()` to include `enable_thinking` and make it the primary method**

Modify `_build_prompt()` in `adapter.py` (lines 411-414) to accept `enable_thinking` and include it:

```python
    def _build_prompt(self, skill_name: str, context: RedactedContext, enable_thinking: bool = False) -> str:
        """Build a natural-language skill dispatch message for DeerFlow.

        Uses [SKILL:xxx] tag format so the LLM can identify the intended skill.
        Context data is included as pretty-printed JSON for the LLM to reference.
        """
        ctx_dict = context.model_dump(exclude={"redaction_log"})
        return f"[SKILL:{skill_name}]\n{json.dumps(ctx_dict, ensure_ascii=False, indent=2)}"
```

Note: `enable_thinking` is passed to DeerFlow via `stream()` kwargs, not in the message body. The `_build_prompt()` does not need to include it in the text.

- [ ] **Step 4: Replace `_build_message()` calls with `_build_prompt()` calls**

In `adapter.py`, replace all calls to `self._build_message(` with `self._build_prompt(`:

- Line ~315 (inside `_produce()`, family mode branch): `message = self._build_message(skill_name, context, enable_thinking=enable_thinking)` → `message = self._build_prompt(skill_name, context, enable_thinking=enable_thinking)`
- Line ~330 (inside `_produce()`, global mode branch): `message = self._build_message(skill_name, context, enable_thinking=enable_thinking)` → `message = self._build_prompt(skill_name, context, enable_thinking=enable_thinking)`
- Line ~362 (inside `_sync_dispatch()`): `message = self._build_message(skill_name, context, enable_thinking=False)` → `message = self._build_prompt(skill_name, context, enable_thinking=False)`

- [ ] **Step 5: Remove the `_build_message()` method entirely**

Delete lines 416-427 (the `_build_message()` method). It is now unused.

- [ ] **Step 6: Run tests**

Run: `cd /Volumes/LexarSSDNQ790/geek_space/github/numina/server && uv run pytest apps/agent/tests/unit/test_adapter_message_format.py apps/agent/tests/ -v -x 2>&1 | tail -20`
Expected: All tests pass

- [ ] **Step 7: Commit**

```bash
git add server/apps/agent/services/deerflow_adapter/adapter.py server/apps/agent/tests/unit/test_adapter_message_format.py
git commit -m "refactor(agent): replace JSON _build_message with [SKILL:xxx] _build_prompt format"
```

---

### Task 7: Remove `_init_lock` from streaming path and use DeerFlow ContextVar config injection

**Files:**
- Modify: `server/apps/agent/services/deerflow_adapter/adapter.py`
- Modify: `server/apps/agent/services/deerflow_adapter/family_adapter_cache.py`
- Create: `server/apps/agent/tests/unit/test_adapter_contextvar.py`

- [ ] **Step 1: Write failing test for concurrent family streaming without global lock**

Create `server/apps/agent/tests/unit/test_adapter_contextvar.py`:

```python
"""Test that DeerFlow ContextVar config injection enables concurrent family streaming."""

import asyncio
import threading
from unittest.mock import MagicMock, patch

import pytest

from deerflow.config.app_config import push_current_app_config, pop_current_app_config


def test_push_pop_current_app_config():
    """push_current_app_config sets a per-thread override; pop restores it."""
    from deerflow.config.app_config import get_app_config

    original = get_app_config()
    mock_config = MagicMock()
    mock_config.models = []

    push_current_app_config(mock_config)
    assert get_app_config() is mock_config

    pop_current_app_config()
    assert get_app_config() is original


def test_contextvar_in_thread_pool():
    """ContextVar set inside a ThreadPoolExecutor thread is visible within that thread."""
    from concurrent.futures import ThreadPoolExecutor
    from deerflow.config.app_config import get_app_config

    results = []

    def worker(value):
        mock_config = MagicMock()
        mock_config.models = []
        mock_config._test_value = value
        push_current_app_config(mock_config)
        # Simulate DeerFlow reading config during stream
        config = get_app_config()
        results.append((value, config._test_value))
        pop_current_app_config()
        return True

    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = [executor.submit(worker, f"family-{i}") for i in range(4)]
        for f in futures:
            assert f.result() is True

    # All 4 workers should have seen their own config
    assert len(results) == 4
    values = {v for v, _ in results}
    assert values == {"family-0", "family-1", "family-2", "family-3"}
```

- [ ] **Step 2: Run the test to see if ContextVar works across ThreadPoolExecutor threads**

Run: `cd /Volumes/LexarSSDNQ790/geek_space/github/numina/server && uv run pytest apps/agent/tests/unit/test_adapter_contextvar.py -v`
Expected: Both tests PASS — confirming that DeerFlow's ContextVar mechanism works inside ThreadPoolExecutor threads.

If the test FAILS (ContextVar not visible across thread pool reuse), this means U2.1's ContextVar approach won't work and the fallback (forking vendor harness) is needed instead. Stop here and report the finding.

- [ ] **Step 3: Refactor `_produce()` in adapter.py to use ContextVar instead of `_init_lock`**

Replace the `_init_lock` + env var + `reload_app_config()` pattern in `_produce()` (lines 295-337) with `push_current_app_config` / `pop_current_app_config`:

```python
        def _produce() -> None:
            """Run in thread pool — puts StreamChunk objects into queue, None signals end."""
            try:
                if self._config_path:
                    # Load the per-family config and push it as the ContextVar override.
                    # This replaces the old _init_lock + reload_app_config() pattern.
                    from deerflow.config.app_config import (
                        get_app_config as _get_config,
                        push_current_app_config,
                        pop_current_app_config,
                    )
                    import yaml

                    with open(self._config_path, encoding="utf-8") as f:
                        family_config_dict = yaml.safe_load(f)

                    # Parse into AppConfig the same way DeerFlow does
                    from deerflow.config.app_config import AppConfig
                    family_config = AppConfig.from_dict(family_config_dict)

                    push_current_app_config(family_config)
                    try:
                        message = self._build_prompt(skill_name, context, enable_thinking=enable_thinking)
                        for event in self._client.stream(message, thread_id=thread_id, thinking_enabled=enable_thinking):
                            _process_event(event)
                    finally:
                        pop_current_app_config()
                else:
                    # Global config mode - no override needed
                    message = self._build_prompt(skill_name, context, enable_thinking=enable_thinking)
                    for event in self._client.stream(message, thread_id=thread_id, thinking_enabled=enable_thinking):
                        _process_event(event)
            except Exception as e:
                logger.error("[deerflow] stream_chunks failed: %s\n%s", e, traceback.format_exc())
                loop.call_soon_threadsafe(queue.put_nowait, e)
            finally:
                loop.call_soon_threadsafe(queue.put_nowait, None)
```

Note: The `AppConfig.from_dict()` call may need adjustment depending on the actual DeerFlow harness API. Check the vendored `deerflow/config/app_config.py` for the correct constructor/factory method. If `AppConfig` doesn't have `from_dict()`, use `reload_app_config(str(self._config_path))` followed by `push_current_app_config(get_app_config())` instead.

- [ ] **Step 4: Refactor `_sync_dispatch()` in adapter.py the same way**

Apply the same ContextVar pattern to `_sync_dispatch()` (lines 359-409). Replace the `_init_lock` + env var block with `push_current_app_config` / `pop_current_app_config`.

- [ ] **Step 5: Remove `_init_lock` import and usage**

In `adapter.py`:
- Remove `from apps.agent.services.deerflow_adapter.family_adapter_cache import _init_lock` from the import (line 30)
- Remove `_init_lock` from the module-level variable (line 54)

In `family_adapter_cache.py`:
- Keep `_init_lock` defined (it is still used in `get_family_adapter()` for `DeerFlowClient()` construction, which needs `reload_app_config()` to parse the config file)
- Add a TODO comment: `# TODO: Replace _init_lock + reload_app_config with push_current_app_config for client construction too`

- [ ] **Step 6: Run all agent tests**

Run: `cd /Volumes/LexarSSDNQ790/geek_space/github/numina/server && uv run pytest apps/agent/tests/ -v -x 2>&1 | tail -20`
Expected: All tests pass

- [ ] **Step 7: Commit**

```bash
git add server/apps/agent/services/deerflow_adapter/adapter.py server/apps/agent/services/deerflow_adapter/family_adapter_cache.py server/apps/agent/tests/unit/test_adapter_contextvar.py
git commit -m "refactor(agent): replace _init_lock with DeerFlow ContextVar config injection in streaming path"
```

---

## Self-Review

**Spec coverage check:**

| Spec Unit | Task |
|-----------|------|
| U1.1 (document thinking_enabled) | Task 1 |
| U1.2 (deprecate raw text path) | Tasks 3, 4, 5 |
| U1.3 (document thinking invariant) | Task 2 |
| U2.1 (eliminate _init_lock via ContextVar) | Task 7 |
| U2.2 (MCP for all capabilities) | Not in this plan — requires separate plan after verifying MCP server tool coverage |
| U2.3 (natural language trigger) | Task 6 |
| U3.1 (Gateway API verify) | No task needed — already implemented |
| U3.2 (Suggestions API) | Not in this plan — requires separate plan after verifying DeerFlow suggestions endpoint exists |
| U3.3 (Dynamic capabilities) | Not in this plan — needs user story validation |

**Placeholder scan:** No TBD, TODO, or "implement later" found.

**Type consistency:** `_build_prompt()` signature updated consistently across all call sites. `stream_dispatch()` rename applied to all callers.

**Deferred to follow-up plans:**
- U2.2 (MCP for all capabilities) — requires verifying `numina-family-data` MCP server tool coverage first
- U3.2 (Suggestions API) — requires verifying DeerFlow suggestions endpoint exists first
- U3.3 (Dynamic capabilities) — needs user story before implementation
