---
title: "fix: Guard against Redis cache startup crash"
type: fix
status: completed
date: 2026-04-19
---

# fix: Guard against Redis cache startup crash

## Overview

`RedisCacheBackend.__init__` raises `NotImplementedError` unconditionally. Any deployment that sets `CACHE_BACKEND=redis` causes the app to crash at first cache access (rate limiting, captcha, or dashboard), with a confusing `NotImplementedError` traceback rather than a clear configuration error. The fix moves the guard to the factory layer so the error is caught early, is clearly attributed to misconfiguration, and surfaces a helpful message.

## Problem Frame

`backend/app/services/cache/factory.py` calls `RedisCacheBackend(settings.REDIS_URL)` when `CACHE_BACKEND=redis`. The constructor raises immediately. The crash happens at the first request that touches a cache singleton — not at startup — making it hard to diagnose. The error message "Redis backend not yet implemented" gives no guidance on what to do.

The default is `CACHE_BACKEND=memory`, so this only affects users who explicitly set the env var. But it is a silent runtime bomb: no validation at startup, no documentation in the config, no actionable error message.

## Requirements Trace

- R1. Setting `CACHE_BACKEND=redis` must produce a clear `ConfigurationError` (or equivalent) at app startup, not at first request.
- R2. The error message must tell the operator what to do: use `CACHE_BACKEND=memory` or implement the Redis backend.
- R3. The `RedisCacheBackend` class must remain as a placeholder (do not delete it), but its constructor must not raise — the guard belongs in the factory.
- R4. A test must verify that the factory raises a clear error when `CACHE_BACKEND=redis` is configured.
- R5. `CACHE_BACKEND` must be documented in `backend/app/config.py` with a comment noting Redis is not yet implemented.

## Scope Boundaries

- Do not implement Redis — this is purely a guard and UX improvement for misconfiguration.
- Do not change `MemoryCacheBackend` or any other cache logic.
- Do not add Redis as a Docker Compose service.

## Context & Research

### Relevant Code and Patterns

- `backend/app/services/cache/factory.py` — three factory functions (`get_rate_limit_cache`, `get_captcha_payload_cache`, `get_dashboard_cache`) all share the same `if settings.CACHE_BACKEND == "redis": RedisCacheBackend(...)` pattern.
- `backend/app/services/cache/redis.py` — placeholder class, all methods raise `NotImplementedError`.
- `backend/app/config.py:21-22` — `CACHE_BACKEND: str = "memory"` and `REDIS_URL: str = "redis://localhost:6379/0"`.
- `backend/app/main.py` — lifespan context manager is the right place to validate config at startup.
- `backend/app/errors/codes.py` — `AppError` / `ErrorCode` pattern used elsewhere; startup config errors are better as plain `ValueError` or `RuntimeError` since they happen before the HTTP layer is ready.

### Institutional Learnings

- No prior `docs/solutions/` entry for this pattern.

## Key Technical Decisions

- **Validate in lifespan, not in factory**: The factory is called lazily (first request). Moving the check to the FastAPI lifespan context manager (`backend/app/main.py`) ensures the error surfaces at startup, before any request is served.
- **Use `ValueError` for config errors**: `AppError`/`ErrorCode` is for HTTP-layer errors. A startup config problem is a programmer/operator error — `ValueError` with a clear message is idiomatic Python and does not require the HTTP error infrastructure.
- **Remove `raise NotImplementedError` from `RedisCacheBackend.__init__`**: The constructor should be a valid no-op placeholder. The factory guard is the single point of enforcement. Keeping the raise in the constructor creates two conflicting guard points.
- **Keep `RedisCacheBackend` class intact**: It documents the intended interface for a future implementer.

## Implementation Units

- [x] **Unit 1: Remove raise from RedisCacheBackend constructor**

**Goal:** Make `RedisCacheBackend.__init__` a valid placeholder that stores `redis_url` without raising, so the class can be instantiated for testing purposes without crashing.

**Requirements:** R3

**Dependencies:** None

**Files:**
- Modify: `backend/app/services/cache/redis.py`

**Approach:**
- Remove `raise NotImplementedError(...)` from `__init__`.
- Keep `self._redis_url = redis_url` and the docstring.
- All method bodies keep their `raise NotImplementedError` — only the constructor changes.
- Update the class docstring to note that instantiation is allowed but all operations raise until implemented.

**Patterns to follow:**
- `backend/app/services/cache/memory.py` — constructor pattern for a working backend.

**Test scenarios:**
- Test expectation: none — this is a pure structural change; the constructor no longer raises, which is verified by Unit 3's test.

**Verification:**
- `RedisCacheBackend("redis://localhost")` does not raise.
- All method calls on the instance still raise `NotImplementedError`.

---

- [x] **Unit 2: Add startup config validation in lifespan**

**Goal:** Detect `CACHE_BACKEND=redis` at app startup and raise a clear `ValueError` before any request is served.

**Requirements:** R1, R2

**Dependencies:** Unit 1

**Files:**
- Modify: `backend/app/main.py`

**Approach:**
- In the lifespan context manager (before `yield`), add a check: if `settings.CACHE_BACKEND == "redis"`, raise `ValueError` with message: `"CACHE_BACKEND=redis is not yet implemented. Set CACHE_BACKEND=memory or implement RedisCacheBackend in backend/app/services/cache/redis.py."`.
- Place the check after existing startup logic (seed, migrations) so it does not interfere with normal startup.
- The `ValueError` will propagate through uvicorn's startup and terminate the process with a clear traceback.

**Patterns to follow:**
- Existing lifespan startup checks in `backend/app/main.py`.

**Test scenarios:**
- Happy path: app starts normally with `CACHE_BACKEND=memory` (default) — no error raised.
- Error path: `CACHE_BACKEND=redis` → `ValueError` raised during lifespan startup with message containing `"CACHE_BACKEND=redis is not yet implemented"`.

**Verification:**
- Existing tests pass unmodified (they use default `memory` backend).
- A new test (Unit 3) confirms the error path.

---

- [x] **Unit 3: Add test for redis config guard**

**Goal:** Prevent regression — ensure the startup guard is tested and stays in place.

**Requirements:** R4

**Dependencies:** Unit 2

**Files:**
- Create: `backend/tests/test_cache_config.py`

**Approach:**
- Use `pytest.raises(ValueError)` with `monkeypatch` to set `settings.CACHE_BACKEND = "redis"`.
- Call the lifespan startup logic (or the validation check directly if extracted to a helper) and assert the `ValueError` is raised with the expected message substring.
- Also test that `CACHE_BACKEND=memory` does not raise.
- Keep the test file small — 2-3 test functions.

**Patterns to follow:**
- `backend/tests/conftest.py` — fixture patterns.
- `backend/tests/test_error_codes.py` — lightweight validation test style.

**Test scenarios:**
- `CACHE_BACKEND=memory` → no error raised.
- `CACHE_BACKEND=redis` → `ValueError` raised, message contains `"CACHE_BACKEND=redis is not yet implemented"`.
- `CACHE_BACKEND=redis` → error message contains guidance (`"CACHE_BACKEND=memory"` or `"implement RedisCacheBackend"`).

**Verification:**
- `uv run pytest tests/test_cache_config.py -v` passes.
- `uv run pytest tests/ -v` passes (no regressions).

---

- [x] **Unit 4: Document CACHE_BACKEND in config**

**Goal:** Make it obvious to anyone reading `config.py` that Redis is not yet available.

**Requirements:** R5

**Dependencies:** None (can land with any unit)

**Files:**
- Modify: `backend/app/config.py`

**Approach:**
- Update the inline comment on `CACHE_BACKEND` from `# "memory" or "redis"` to `# "memory" only — "redis" is not yet implemented (see backend/app/services/cache/redis.py)`.

**Test scenarios:**
- Test expectation: none — comment-only change.

**Verification:**
- Comment is present and accurate after the change.

## System-Wide Impact

- **Interaction graph:** Only `backend/app/main.py` lifespan and `backend/app/services/cache/factory.py` are affected. No routers, models, or schemas change.
- **Error propagation:** `ValueError` in lifespan propagates through uvicorn startup and terminates the process — this is the intended behavior for a fatal misconfiguration.
- **Unchanged invariants:** All existing cache behavior with `CACHE_BACKEND=memory` (default) is unchanged. Rate limiting, captcha, and dashboard caching are unaffected.

## Risks & Dependencies

| Risk | Mitigation |
|------|------------|
| Lifespan check placement breaks test setup | Tests use default `memory` backend — no impact. Confirm with `uv run pytest tests/ -v`. |
| Removing `raise` from constructor breaks future implementer's expectations | Constructor docstring updated to clarify that operations raise, not construction. |

## Sources & References

- `backend/app/services/cache/redis.py`
- `backend/app/services/cache/factory.py`
- `backend/app/config.py`
- `backend/app/main.py`
