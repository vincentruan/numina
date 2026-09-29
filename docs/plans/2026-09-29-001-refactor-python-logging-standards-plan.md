---
artifact_contract: ce-unified-plan/v1
artifact_readiness: implementation-ready
execution: code
product_contract_source: ce-plan-bootstrap
plan_type: refactor
plan_depth: standard
created: 2026-09-29
---

# refactor: Python Logging Standards Alignment

## Summary

Align the Numina Python server codebase with a comprehensive set of logging standards: migrate ~132 modules from `logging.getLogger(__name__)` to the project's `get_logger(__name__)` convention, fix ~60+ exception logging patterns that lose traceback, convert ~95 f-string log calls to parameterized logging, and document the logging rules in `server/CLAUDE.md`. The core logging infrastructure (`packages/core/logging.py`) is already well-designed and does not need changes.

---

## Problem Frame

The project has a centralized logging configuration (`packages/core/logging.py`) with rotation, retention, and a `get_logger()` factory. However, the codebase diverges from the documented convention in three ways:

1. **~132 files** use `logging.getLogger(__name__)` directly instead of `get_logger(__name__)`, violating the rule in `packages/core/CLAUDE.md`.
2. **~60+ exception handlers** log only `str(e)` without preserving traceback, making production debugging harder.
3. **~95 log calls** use f-string interpolation instead of `logging`'s parameterized `%s` mechanism.

The infrastructure itself is solid: `setup_logging()` provides console + rotating file handlers, `RotatingFileHandler` with configurable mode/size/count, `cleanup_old_logs()` at startup, and a dedicated security logger. Docker services emit to both stdout and file. No sensitive data leaks were found.

---

## Requirements

| ID | Requirement |
|----|-------------|
| R1 | All modules use `get_logger(__name__)` from `packages.core.logging` — including `apps/` and `packages/` code. Never call `logging.getLogger()` directly for module loggers |
| R2 | Exception logging preserves traceback via `logger.exception()` or `logger.error(..., exc_info=True)` |
| R3 | Log calls use parameterized format (`logger.info("msg: %s", val)`) instead of f-strings (`logger.info(f"msg: {val}")`) |
| R4 | `server/CLAUDE.md` documents the logging conventions for future development |
| R5 | No behavior changes to `packages/core/logging.py` or the logging infrastructure |
| R6 | CLI scripts (`scripts/`, `reconcile/__main__.py`) retain `print()` — they are user-facing tools, not server code |

---

## Key Technical Decisions

### KTD1: `get_logger` is a thin wrapper — migration is convention-only

`get_logger(name)` is literally `return logging.getLogger(name)`. There is no behavioral difference today. The migration ensures that if `get_logger` gains future capabilities (context injection, filtering, etc.), all modules automatically benefit. It also enforces a single import path, making the codebase consistent.

### KTD2: Exception logging — prefer `logger.exception()` in `except` blocks

When an exception is caught and logged, use `logger.exception("context: %s", id)` which implicitly includes `exc_info=True`. When the exception is re-raised, `logger.exception()` + `raise` is the standard pattern. Avoid `logger.error("msg: %s", e)` which discards the stack trace.

### KTD3: Agent log format stays different

The agent service uses `%(asctime)s [%(levelname)s] %(name)s: %(message)s` (set in `agent/core/logging.py`) for backward compatibility. This plan does not unify log formats across services — each service's format is intentional.

### KTD4: `print()` in CLI scripts is acceptable

Scripts under `server/apps/backend/scripts/` and `reconcile/__main__.py` are one-off management tools with direct user output. `print()` is the correct choice there. This plan does not change them.

### KTD5: Inline `logging.getLogger(__name__)` inside functions should become module-level

`ai_internal.py` defines `logger = logging.getLogger(__name__)` at lines 741, 814, and 951 inside function bodies. These should become a single module-level declaration. The same pattern exists in `ai_task_service.py:424` and `scheduler_worker/jobs/__init__.py:351`.

---

## Implementation Units

### U1. Backend: Migrate `logging.getLogger` → `get_logger`

**Goal:** All backend modules (routers, services, middleware, reconcile, bootstrap, auth) use `get_logger(__name__)` from `packages.core.logging`.

**Requirements:** R1

**Dependencies:** None

**Files:** All files under `server/apps/backend/app/` and `server/packages/` that currently contain `logger = logging.getLogger(__name__)`. Approximately 85 files across:
- `server/apps/backend/app/routers/` (~35 files)
- `server/apps/backend/app/services/` (~15 files)
- `server/apps/backend/app/middleware/` (~3 files)
- `server/apps/backend/app/reconcile/` (~7 files)
- `server/apps/backend/app/bootstrap/` (~1 file)
- `server/apps/backend/app/auth/` (~1 file)
- `server/apps/backend/app/error_handlers.py`
- `server/apps/backend/app/main.py`
- `server/packages/core/` (2 files: `model_entry.py`, `system_config.py`)
- `server/packages/stream_bridge/` (3 files: `memory.py`, `factory.py`, `redis.py`)
- `server/packages/security/service_auth/` (1 file: `agent_token_verify.py`)
- `server/packages/domain/literacy/` (1 file: `service.py`)

**Approach:**

1. In each file, replace `import logging` + `logger = logging.getLogger(__name__)` with `from packages.core.logging import get_logger` + `logger = get_logger(__name__)`.
2. If the file already imports other symbols from `packages.core.logging` (e.g., `setup_logging`), add `get_logger` to the existing import.
3. If `import logging` is still needed for `logging.INFO`, `logging.DEBUG`, etc., keep it — only remove it if no other `logging.*` references remain.
4. Files that use `logging.getLogger("security")` or other named loggers should keep those calls — only migrate the `__name__` pattern.

**Patterns to follow:** The existing usage in `server/apps/scheduler_worker/main.py:15-18`:
```python
from packages.core.logging import get_logger, setup_logging
logger = get_logger(__name__)
```

**Test scenarios:**
- After migration, `grep -r 'logger = logging.getLogger(__name__)' server/apps/backend/app/ server/packages/` returns 0 results
- `uv run ruff check apps/backend/app/` passes (no unused imports)
- `uv run pytest tests/backend/test_logging_config.py -v` passes
- Existing test suite passes: `uv run pytest tests/backend/ -v`

**Verification:** Zero `logging.getLogger(__name__)` occurrences in backend app code. All existing tests pass.

---

### U2. Agent: Migrate `logging.getLogger` → `get_logger`

**Goal:** All agent modules use `get_logger(__name__)` from `packages.core.logging`.

**Requirements:** R1

**Dependencies:** None

**Files:** All files under `server/apps/agent/` that currently contain `logger = logging.getLogger(__name__)`. Approximately 47 files across:
- `server/apps/agent/routers/` (~6 files)
- `server/apps/agent/services/` (~10 files)
- `server/apps/agent/services/runtime/` (~5 files)
- `server/apps/agent/services/deerflow_adapter/` (~3 files)
- `server/apps/agent/app/` (~5 files, including `main.py`)
- `server/apps/agent/core/` (~2 files)

**Approach:**

Same migration pattern as U1. Special cases:
- `server/apps/agent/app/main.py` has inline `logging.getLogger(__name__)` calls at lines 40, 76, 210, 239, 262. These should use the module-level logger or a module-level `get_logger(__name__)` declaration.
- `server/apps/agent/services/audit_logger.py` uses `logging.getLogger("agent.audit")` — keep this (named logger, not `__name__`).
- `server/apps/agent/services/agent_dispatch.py` already uses `get_logger(__name__)` — no change needed.

**Patterns to follow:** Same as U1.

**Test scenarios:**
- After migration, `grep -r 'logger = logging.getLogger(__name__)' server/apps/agent/` returns 0 results (excluding tests)
- `uv run ruff check apps/agent/` passes
- `uv run pytest tests/agent/ -v` passes

**Verification:** Zero `logging.getLogger(__name__)` occurrences in agent code. All existing tests pass.

---

### U3. Fix exception logging — preserve traceback

**Goal:** All `except` blocks that log exceptions preserve the full traceback.

**Requirements:** R2

**Dependencies:** U1, U2 (so we migrate logger first, then fix patterns in the same files)

**Files:** Approximately 60+ locations across:

Backend:
- `server/apps/backend/app/routers/ai_chat.py:227` — `logger.error("调用 agent chat 失败: %s", type(e).__name__)`
- `server/apps/backend/app/routers/ai_chat.py:318` — `logger.error("[chat-stream] trigger failed: %s", type(e).__name__)`
- `server/apps/backend/app/routers/mcp_internal.py:65` — `logger.error("[mcp_sse] family=%s connection error: %s", ...)`
- `server/apps/backend/app/routers/import_report.py:449` — `logger.error("Agent parse failed: %s", e)`
- `server/apps/backend/app/routers/import_report.py:782` — `logger.error("Agent confirm-via-agent failed: %s", e)`
- `server/apps/backend/app/routers/files.py:72` — `logger.warning(f"本地文件删除失败: {e}")`
- `server/apps/backend/app/routers/files.py:95` — `logger.warning(f"远程文件删除失败 ...: {e}")`
- `server/apps/backend/app/routers/ai_suggest.py:58` — `logger.error(f"调用 agent suggest 失败: {e}")`
- `server/apps/backend/app/routers/ai_threads.py:86` — `logger.error(f"LangGraph proxy stream error ...: {e}")`
- `server/apps/backend/app/routers/ai_threads.py:119` — `logger.error(f"LangGraph proxy error ...: {e}")`
- `server/apps/backend/app/routers/ai_input_polish.py:82` — `logger.error(f"调用 agent input-polish 失败: {e}")`
- `server/apps/backend/app/main.py:350` — `logger.warning(f"自动快照生成失败: {e}")`
- `server/apps/backend/app/main.py:363` — `logger.warning(f"初始汇率获取失败: {e}")`

Agent:
- `server/apps/agent/app/routers/gateway.py:77,80` — `logger.error("[gateway] ... error: %s", e)`
- `server/apps/agent/services/runtime/lifespan.py:157` — `logger.error("Redis unavailable for StreamBridge (%s)", e)`

**Approach:**

For each location, apply one of:
1. If the exception is re-raised (e.g., `raise AppError(...) from e`): change to `logger.exception("context: %s", detail)` or add `exc_info=True`.
2. If the exception is caught and handled (not re-raised): use `logger.exception()` if the traceback is useful, or `logger.warning("context: %s", detail, exc_info=True)` for non-critical paths.
3. Where the current pattern logs only `type(e).__name__`, add the actual exception message and traceback context.

**Decision rule:** If the code path is a real failure that an operator would need to debug, use `logger.exception()`. If it's a non-critical warning (e.g., optional cleanup failed), use `logger.warning(..., exc_info=True)`.

**Patterns to follow:** The existing correct pattern in `error_handlers.py`:
```python
logger.exception("Unhandled exception on %s: %s", request.url.path, exc)
```

**Test scenarios:**
- For each changed file, the `except` block now either calls `logger.exception()` or passes `exc_info=True`
- Existing test suite still passes for both backend and agent
- Grep for `logger.error.*%s.*\be\b` (without `exc_info`) returns 0 results in the changed files

**Verification:** No exception-swallowing patterns remain. Existing tests pass.

---

### U4. Convert f-string log calls to parameterized format

**Goal:** All log calls use `logging`'s `%s` parameterization instead of f-strings.

**Requirements:** R3

**Dependencies:** U1, U2 (logger migration first)

**Files:** Approximately 95 locations, primarily in:

Backend:
- `server/apps/backend/app/routers/files.py:36,72,95`
- `server/apps/backend/app/main.py:211,279,281,283,285,350,363`
- `server/apps/backend/app/routers/ai_suggest.py:58`
- `server/apps/backend/app/routers/ai_threads.py:83,86,116,119`
- `server/apps/backend/app/reconcile/lock.py:63,175`
- `server/apps/backend/app/routers/ai_input_polish.py:82`
- `server/apps/backend/app/bootstrap/currencies.py:38`
- `server/apps/backend/app/reconcile/resources/file.py:130`

Scheduler Worker:
- `server/apps/scheduler_worker/main.py:52` — `logger.info(f"APScheduler started with {len(scheduler.get_jobs())} jobs")`

**Approach:**

For each f-string log call, convert:
```python
# Before
logger.info(f"APScheduler started with {len(scheduler.get_jobs())} jobs")
# After
logger.info("APScheduler started with %d jobs", len(scheduler.get_jobs()))
```

```python
# Before
logger.error(f"调用 agent suggest 失败: {e}")
# After (combined with U3 fix)
logger.exception("调用 agent suggest 失败")
```

Rules:
- `%s` for strings, `%d` for integers, `%.2f` for floats
- Keep the same log message content, only change the formatting mechanism
- When the f-string contains only `{e}` and the exception is being handled, this is also a U3 fix — use `logger.exception()` instead

**Patterns to follow:** Existing parameterized pattern:
```python
logger.info("Order processed: order_id=%s duration_ms=%d", order_id, duration_ms)
```

**Test scenarios:**
- `grep -r 'logger\.\(info\|debug\|warning\|error\|critical\)(f"' server/apps/ server/packages/` returns 0 results
- Existing test suite passes

**Verification:** Zero f-string log calls. Existing tests pass.

---

### U5. Unify agent `main.py` inline logger calls

**Goal:** Remove inline `logging.getLogger(__name__)` calls in `agent/app/main.py` and use a single module-level logger.

**Requirements:** R1

**Dependencies:** U2

**Files:**
- `server/apps/agent/app/main.py` — inline `logging.getLogger(__name__)` at lines 40, 76, 210, 239, 262
- `server/apps/backend/app/routers/ai_internal.py` — inline at lines 741, 814, 951
- `server/apps/backend/app/services/ai_task_service.py:424` — local logger inside function
- `server/apps/scheduler_worker/jobs/__init__.py:351` — local logger inside function

**Approach:**

In `agent/app/main.py`, replace all inline `logging.getLogger(__name__)` calls with a single module-level `logger = get_logger(__name__)`. The `setup_logging()` call at module level (line 65) should remain — it runs at import time which is correct for the agent.

In `ai_internal.py`, there are 3 inline `logger = logging.getLogger(__name__)` declarations (lines 741, 814, 951) inside function bodies. Remove all three and use the existing module-level logger.

In `ai_task_service.py:424` and `scheduler_worker/jobs/__init__.py:351`, move the local logger declaration to module level.

**Test scenarios:**
- No inline `logging.getLogger(__name__)` calls remain in any `main.py`
- Existing tests pass

**Verification:** No function-scoped logger declarations.

---

### U6. Document logging conventions in `server/CLAUDE.md`

**Goal:** Add a concise Logging section to `server/CLAUDE.md` that enforces the conventions for future development.

**Requirements:** R4

**Dependencies:** U1–U5

**Files:** `server/CLAUDE.md`

**Approach:**

Add a new `## Logging` section (or merge into `## Patterns`) covering:

1. Use `from packages.core.logging import get_logger; logger = get_logger(__name__)` — never call `logging.getLogger()` directly for module loggers
2. Choose log levels by semantics: DEBUG (dev detail), INFO (important events), WARNING (recoverable anomaly), ERROR (operation failed), CRITICAL (system failure)
3. Use parameterized logging: `logger.info("msg: %s", val)` — never f-strings
4. Exception logging must preserve traceback: `logger.exception()` or `logger.error(..., exc_info=True)` — never `logger.error("msg: %s", e)`
5. Log relevant context: `task_id`, `family_id`, `duration_ms`, `status` — but only what the event needs
6. Never log sensitive data: passwords, tokens, API keys, Authorization headers
7. Control log volume in high-frequency paths (loops, streaming, polling) — use DEBUG or sampling
8. File log rotation is handled by `setup_logging()` — `RotatingFileHandler` (size) or `TimedRotatingFileHandler` (time) based on `LOG_ROTATION_MODE`
9. Docker services log to stdout + file; rotation is managed by the Python handler
10. Do not use `print()` in server code — CLI scripts may use `print()`

Keep it short — constraints for future code, not a tutorial.

**Test expectation:** none — documentation change only

**Verification:** `server/CLAUDE.md` contains the Logging section with all 10 constraints.

---

## Scope Boundaries

### Not in Scope

- **Logging infrastructure changes** — `packages/core/logging.py` is well-designed. No changes to `setup_logging()`, `get_logger()`, rotation, or retention.
- **CLI script `print()` → `logger`** — `scripts/` and `reconcile/__main__.py` are management tools where `print()` is appropriate.
- **Agent log format unification** — The agent intentionally uses a different format. Not changing.
- **JSON/structured logging** — The project uses plain text logs. No migration to JSON format.
- **Adding log context to every log call** — This plan fixes the mechanical issues (convention, traceback, parameterization). Enriching every log call with more context is ongoing work, not a one-time migration.
- **Multi-process file contention** — All services run single-worker uvicorn in separate Docker containers. No contention risk.

### Deferred to Follow-Up Work

- Enriching high-frequency paths (e.g., `worker.py` heartbeat loops) with DEBUG-level sampling
- Adding `duration_ms` to external service call logs (agent → backend HTTP calls)
- Integrating `archive_old_logs()` into a scheduler job for automatic compression

---

## Risks & Dependencies

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Import breakage during migration | Low | Low | `get_logger` is in the same `packages.core.logging` module; import path is well-established |
| Ruff/CI failure from unused `import logging` | Medium | Low | Each U includes ruff check verification |
| Behavioral change in exception logging | Low | Low | `logger.exception()` adds traceback to the same log level; no semantic change |
| Large diff makes review hard | Medium | Medium | Each U is scoped to one concern; can be committed separately |

---

## System-Wide Impact

- **Backend (78 files):** Largest change. All routers, services, middleware affected.
- **Agent (47 files):** Second largest. All services, routers, core modules affected.
- **packages/ (7 files):** Shared packages — core, stream_bridge, security, domain.
- **Scheduler Worker (1 file):** Minor. Already uses `get_logger`.
- **packages/core (logging.py):** No changes to infrastructure itself.
- **Tests:** Existing tests should pass without modification. No new test files needed (this is a convention migration, not new behavior).
- **Docker/Deployment:** No changes. Log output paths, rotation, and format remain the same.
