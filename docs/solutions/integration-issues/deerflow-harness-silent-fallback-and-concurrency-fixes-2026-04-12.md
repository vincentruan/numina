---
module: agent
date: "2026-04-12"
problem_type: integration_issue
component: assistant
severity: critical
symptoms:
  - "USE_DEERFLOW=true but orchestrator always runs legacy path — DeerFlow silently disabled"
  - "Concurrent requests can trigger SQLITE_BUSY due to un-acquired checkpointer lock"
  - "Backend context fetch failures produce no warnings — partial context is invisible"
  - "Dead _CAPABILITY_MAP constant misleads contributors into thinking it controls dispatch"
root_cause: incomplete_setup
resolution_type: code_fix
related_components:
  - services.deerflow_adapter.adapter
  - services.orchestrator
  - services.pii_redactor
  - services.fallback_engine
  - frontend/src/components/common/AppTabBar.vue
  - frontend/src/pages/AIConfigPage.vue
  - frontend/src/pages/AIHubPage.vue
tags:
  - deerflow
  - adapter-singleton
  - asyncio-lock
  - sqlite-busy
  - pii-redaction
  - silent-exception
  - optional-type
  - accessibility
---

# DeerFlow harness integration fixes — singleton export, locking, redaction API, logging, cleanup

## Problem

A review of Numina's DeerFlow AI agent harness integration (`agent/` module, Python FastAPI + asyncio) found multiple issues that either silently disabled DeerFlow, caused concurrency failures under load, or introduced maintainability and observability hazards. Seven targeted fixes restored the intended DeerFlow execution path, made checkpoint writes safe under concurrency, clarified module boundaries, and improved runtime diagnostics. A small set of related frontend UI/accessibility issues were also corrected.

## Symptoms

- With `USE_DEERFLOW=true`, the orchestrator never successfully uses DeerFlow — it always falls back to legacy with no clear error signal.
- Under concurrent requests (semaphore allows 4 parallel calls), DeerFlow checkpointing can still perform concurrent SQLite writes and hit `SQLITE_BUSY`.
- Orchestrator imports a leading-underscore function from `pii_redactor.py`, coupling it to private internals.
- Backend context fetch failures yield empty lists with no warnings — outages produce partial context silently.
- `_CAPABILITY_MAP` in `fallback_engine.py` looks like it controls dispatch routing but is never consulted.
- `Optional[T]` type annotations contradict the project's Python 3.10+ standard (`T | None`).
- Frontend: unsafe `as string` cast in tab change handler; `aria-hidden` bound to string `'true'` instead of boolean; `role="button"` div missing keyboard handlers.

## What Didn't Work

- **Relying on the import resolving**: `from services.deerflow_adapter.adapter import deerflow_adapter` failed because no singleton was exported. The exception was swallowed by `except Exception: _deerflow_adapter = None`, so the failure was invisible.
- **Declaring the lock without acquiring it**: `_CHECKPOINTER_LOCK = asyncio.Lock()` existed with detailed comments explaining its purpose, but was never used in `dispatch()` or `_sync_dispatch()`. The comments created false confidence.
- **Acquiring the lock inside the executor thread**: `asyncio.Lock` is not thread-safe — it must be acquired in the async event loop context, not inside `run_in_executor`. The correct pattern is to acquire it before the `run_in_executor` call.

## Solution

### Bug 1 (P0) — Export a `deerflow_adapter` singleton

`adapter.py` only defined the `DeerFlowAdapter` class. The orchestrator's import of `deerflow_adapter` failed silently, leaving `_deerflow_adapter = None` and permanently routing all requests through legacy fallback.

**Fix:** add a factory function and module-level singleton at the bottom of `adapter.py`:

```python
def _make_adapter() -> DeerFlowAdapter | None:
    try:
        config_path = os.path.join(os.path.dirname(__file__), "..", "..", "deerflow_config")
        return DeerFlowAdapter(config_path=config_path, timeout_seconds=120)
    except Exception as e:
        logger.warning(f"DeerFlow adapter init failed: {e}")
        return None

deerflow_adapter: DeerFlowAdapter | None = _make_adapter()
```

The orchestrator's existing `try/except` import now resolves correctly when the config is present, and degrades gracefully (with a warning) when it isn't.

---

### Bug 2 (P1) — Actually acquire `_CHECKPOINTER_LOCK`

`_CHECKPOINTER_LOCK` was declared and documented but never acquired. Under concurrent load, SqliteSaver could still receive concurrent writes → `SQLITE_BUSY`.

**Fix:** acquire both locks together in `dispatch()` on the async side:

```python
# Before
async with _SEMAPHORE:
    try:
        result = await asyncio.wait_for(loop.run_in_executor(...), ...)

# After
async with _SEMAPHORE, _CHECKPOINTER_LOCK:
    try:
        result = await asyncio.wait_for(loop.run_in_executor(...), ...)
```

**Critical detail:** `asyncio.Lock` must be acquired in the event loop (async context), not inside the executor thread. Acquiring it before `run_in_executor` ensures the lock is held for the full duration of the synchronous DeerFlow call.

---

### Bug 3 (P1) — Replace cross-module private import with a public API

`orchestrator.py` `finally` block imported `_redact_free_text` (leading underscore = private) from `pii_redactor.py`. This coupled orchestrator to pii_redactor internals and created a second undocumented redaction call site.

**Fix:** add a public method to `PIIRedactor`:

```python
# pii_redactor.py
def redact_text(self, text: str) -> tuple[str, list[str]]:
    """对任意文本应用正则脱敏，返回（脱敏后文本, 脱敏日志）。供审计日志等外部调用使用。"""
    return _redact_free_text(text)
```

```python
# orchestrator.py — before
from services.pii_redactor import _redact_free_text
raw_summary, _ = _redact_free_text(raw_summary)

# orchestrator.py — after
raw_summary = pii_redactor.redact_text(raw_summary)[0]
```

**Test update required:** tests that mock `pii_redactor` as a `MagicMock` must configure the new method or unpacking fails:

```python
mock_redactor.redact_text.return_value = ("redacted text", [])
```

---

### Bug 4 (P2) — Remove dead `_CAPABILITY_MAP`

`fallback_engine.py` defined `_CAPABILITY_MAP: dict[str, str]` mapping capability names to dotted function paths. `_run_legacy()` used an `if/elif` chain and never consulted the map. Future contributors would update the map thinking it changed behavior.

**Fix:** delete the constant entirely. The `if/elif` chain is the single source of truth.

---

### Bug 5 (P2) — Log backend context fetch failures

`_build_context()` wrapped each backend fetch in `except Exception: []` with no logging. Backend outages were invisible; the agent produced misleading output on partial context.

**Fix:** add a warning log per failed fetch:

```python
# Before
try:
    liabilities = await client.get_liabilities()
except Exception:
    liabilities = []

# After
try:
    liabilities = await client.get_liabilities()
except Exception as e:
    logger.warning(f"[orchestrator] fetch liabilities failed family={family_id}: {e}")
    liabilities = []
```

Graceful degradation is preserved (still returns empty fragment), but partial context is now visible in logs.

---

### Bug 6 (P2/P3) — Replace `Optional[T]` with `T | None`

Project standard (CLAUDE.md): use `str | None`, `list[str]` (PEP 604, Python 3.10+). Multiple agent files used `from typing import Optional` and `Optional[str]`.

**Fix:** replace across `orchestrator.py`, `pii_redactor.py`, `fallback_engine.py`:

```python
# Before
from typing import Optional
user_id: Optional[str] = None

# After
user_id: str | None = None
```

---

### Bug 7 — Frontend fixes

**`AppTabBar.vue` — unsafe cast:**
```typescript
// Before
const target = tabToRoute[name as string]

// After
if (typeof name !== 'string') return
const target = tabToRoute[name]
```

**`AIConfigPage.vue` — `aria-hidden` must be boolean:**
```html
<!-- Before -->
:aria-hidden="canSave ? 'true' : undefined"

<!-- After -->
:aria-hidden="canSave"
```

**`AIHubPage.vue` — `role="button"` needs keyboard handlers:**
```html
<!-- Before -->
<div role="button" tabindex="0" @click="...">

<!-- After -->
<div role="button" tabindex="0"
  @click="$router.push('/ai/report')"
  @keydown.enter="$router.push('/ai/report')"
  @keydown.space.prevent="$router.push('/ai/report')">
```

## Why This Works

The P0 bug was a classic "import resolves to None" trap: the orchestrator's broad `except Exception` on the import was intended to handle optional-dependency scenarios, but it also swallowed the `ImportError` from a missing name, leaving the feature permanently disabled. Exporting the singleton makes the import succeed when the config is present.

The P1 lock bug is a "declared but not used" concurrency primitive — a pattern that's easy to introduce when refactoring (the lock was added in a later pass but the acquisition was never wired in). The fix is straightforward, but the key insight is that `asyncio.Lock` must be acquired in the async context, not inside the executor thread.

The private import fix follows the principle that module boundaries should be enforced through public APIs. A leading underscore is a contract: "don't call this from outside." Adding `redact_text()` as a thin public wrapper costs nothing and makes the contract explicit.

## Prevention

1. **When exporting a singleton from a module, verify the import name matches the exported name** — a quick `python -c "from services.deerflow_adapter.adapter import deerflow_adapter"` would have caught this immediately.

2. **When declaring a concurrency primitive, add a comment at the declaration AND at the acquisition site** — if you can't find the acquisition site, the primitive isn't being used.

3. **Never import leading-underscore names across module boundaries** — if you need it externally, add a public wrapper. Ruff rule `PLC2701` (private name import) catches this.

4. **Always log in `except Exception` blocks that substitute defaults** — silent degradation is worse than noisy degradation for production debugging.

5. **For `asyncio.Lock` used to protect a `run_in_executor` call**: acquire the lock in the async layer (before the executor call), not inside the sync function running in the thread.

6. **When mocking a class instance in tests, configure all public methods that the code under test calls** — an unconfigured `MagicMock` method returns a `MagicMock`, which can cause surprising failures when the caller tries to unpack or index the return value.
