---
title: T11 — MCP Cache Per-Family Race Fix
type: feat
date: 2026-11-02
topic: mcp-cache-per-family-race-t11
artifact_contract: ce-unified-plan/v1
execution: code
---

## Goal Capsule

- **Objective:** Eliminate the process-global `_last_reset_state` race in `_maybe_reset_mcp_cache()` so concurrent multi-family requests don't thrash the DeerFlow MCP tools cache, causing brief empty tool lists.
- **Authority:** Issue #171 (T11, part of #168).
- **Branch:** `vincentruan/p1-mcp-caller-bound-principal-t10` (alongside T10 finalization).
- **Open blockers:** None.

---

## Product Contract

### Summary

Replace the process-global `_last_reset_state` tuple with a per-family signature tracking dict protected by `threading.Lock`. Drop the explicit `reset_mcp_tools_cache()` call — let DeerFlow's `get_cached_mcp_tools()` handle staleness via its own `_is_cache_stale()` (which already uses the ContextVar-resolved config path). This eliminates:
1. The alternating-reset race between concurrent families.
2. The "briefly empty tool list" window caused by tearing down MCP sessions before `get_cached_mcp_tools()` re-initializes them.
3. Unnecessary `reset_extensions_config()` calls when the same family's config is unchanged.

### Problem Frame

`_maybe_reset_mcp_cache()` in `adapter.py:148-194` uses a single module-level variable `_last_reset_state: tuple[str | None, tuple | None] | None` to track the last reset's `(extensions_path, content_signature)`. Under concurrent multi-family requests:

1. **Family A** request: `_last_reset_state = None` → reset → set to `A_sig`
2. **Family B** request: `B_sig ≠ A_sig` → reset → set to `B_sig`
3. **Family A** again: `A_sig ≠ B_sig` → reset → set to `A_sig`
4. Repeat → **every request triggers a reset**, even when the same family's config is unchanged.

Each `reset_mcp_tools_cache()` tears down all MCP sessions (closing SSE connections) and sets `_mcp_tools_cache = None`, `_cache_initialized = False`. The next `get_cached_mcp_tools()` must re-initialize from scratch — during which the tool list is briefly empty.

Additionally, `reset_mcp_tools_cache()` is redundant because `get_cached_mcp_tools()` already checks `_is_cache_stale()` on every call, which detects config path/signature changes via the ContextVar-patched `ExtensionsConfig.resolve_config_path` (see `sync_tool_patch.py:425-471`).

### Key Decisions

- **D1. Per-family signature tracking.** Replace `_last_reset_state` (single tuple) with `_per_family_reset_state: dict[str, tuple | None]` keyed by `extensions_path`. Each family's config change is tracked independently. Governs R1, R2.
- **D2. Drop `reset_mcp_tools_cache()`.** Don't tear down the MCP tools cache eagerly. Let `get_cached_mcp_tools()` detect staleness via `_is_cache_stale()` (which reads the ContextVar-resolved path) and handle re-initialization under its own `_init_lock`. This eliminates the "briefly empty" window. Governs R3, R4.
- **D3. Keep `reset_extensions_config()` on config change.** `ExtensionsConfig` has a singleton cache (`_extensions_config` global) that must be cleared when the config changes for a family, so `initialize_mcp_tools()` picks up the new MCP server list. Governs R5.
- **D4. Service-level concurrency, not user behavior.** A user account belongs to exactly one family (many-to-one). "Family switch" refers to the shared agent process handling requests from different families in rapid succession — not a single user switching families. When the active family changes at the service level, `get_cached_mcp_tools()._is_cache_stale()` detects the different config path and re-initializes. This is unavoidable without per-family MCP caching (which requires DeerFlow changes — out of scope). **For individual users, this fix means zero resets for their requests** — they always hit the per-family cache. The "family switch" re-init only affects service-level metrics under high concurrency from many families.

### Requirements

- **R1.** Same family, unchanged config → `_maybe_reset_mcp_cache` skips all reset operations (no `reset_extensions_config`, no `reset_mcp_tools_cache`).
- **R2.** Same family, changed config (e.g., admin edits MCP servers) → `reset_extensions_config()` is called once to clear the stale singleton.
- **R3.** `_maybe_reset_mcp_cache` never calls `reset_mcp_tools_cache()`. The MCP tools cache lifecycle is managed solely by `get_cached_mcp_tools()._is_cache_stale()`.
- **R4.** No concurrent multi-family request triggers more resets than the number of actual config changes. Same-family repeated requests are zero-reset.
- **R5.** `ExtensionsConfig` singleton is cleared when a family's config content changes, so the next `initialize_mcp_tools()` loads the correct MCP server list.

### Key Flows

- **F1. Same family, repeated request (common case: interactive chat).**
  - Worker calls `_maybe_reset_mcp_cache(path_A)`.
  - Per-family tracking: `A_sig == state[path_A]` → skip (no reset call).
  - `get_cached_mcp_tools()`: `_is_cache_stale()` → path matches `_config_path`, sig matches → cache hit. No re-init.
  - **Result:** Zero resets, zero re-inits, instant tool availability.

- **F2. Service-level family interleaving (agent process handles A then B).**
  - This is NOT a user switching families — it's the shared agent process serving different families concurrently.
  - Worker calls `_maybe_reset_mcp_cache(path_B)`.
  - Per-family tracking: `path_B` not in `state` (or sig differs) → `reset_extensions_config()` → update `state[path_B]`.
  - `get_cached_mcp_tools()`: `_is_cache_stale()` → path differs from `_config_path` → re-init under `_init_lock`. MCP sessions torn down and rebuilt for family B.
  - **Result:** One `reset_extensions_config()` + one re-init (unavoidable for the global singleton). No "briefly empty" because `get_cached_mcp_tools()` waits for re-init under lock before returning. **This re-init is transparent to end users** — each family's request completes correctly; only service-level MCP session reuse is affected.

- **F3. Concurrent same-family requests.**
  - Thread 1 and Thread 2 both call `_maybe_reset_mcp_cache(path_A)` with same config.
  - Per-family tracking: both see `A_sig == state[path_A]` → both skip. No reset.
  - **Result:** Zero resets, zero contention. Previously, Thread 2 might have seen `A_sig ≠ B_sig` (from an interleaved family B) and triggered an unnecessary reset.

### Scope Boundaries

- **No per-family MCP caching.** DeerFlow's MCP tools cache remains a global singleton. Per-family MCP caching would require upstream changes to DeerFlow. This fix minimizes unnecessary resets; service-level family interleaving still triggers re-init, but this is transparent to individual users — each user belongs to one family, so their requests always hit the per-family tracking cache (zero resets).
- **No harness upgrade.** Approach A (upgrading the harness rev) is deferred. The per-family tracking approach is self-contained and doesn't depend on upstream changes.
- **`_maybe_reset_mcp_cache` is not removed.** It still serves a purpose: clearing the `ExtensionsConfig` singleton when a family's config changes. Without it, the singleton could serve stale MCP server configs.

### Dependencies / Assumptions

- `get_cached_mcp_tools()._is_cache_stale()` correctly detects config path changes via the ContextVar-patched `ExtensionsConfig.resolve_config_path` (`sync_tool_patch.py:425-471`). **Verified**: the patch reads `_extensions_config_path_context` ContextVar, which is set per-request by `agent_dispatch.py:541`.
- `reset_extensions_config()` is idempotent (sets `_extensions_config = None`). **Verified**: `deerflow/config/extensions_config.py`.
- `initialize_mcp_tools()` calls `ExtensionsConfig.from_file()` (not `get_extensions_config()`) to load the config. **Assumed** based on DeerFlow's architecture — to be verified during implementation.
- `_is_cache_stale()` is called under `_init_lock` inside `get_cached_mcp_tools()`. **Verified** from source.

### Sources / Research

- `server/apps/agent/services/deerflow_adapter/adapter.py:120-194` — `_last_reset_state`, `_maybe_reset_mcp_cache()`
- `server/apps/agent/services/agent_dispatch.py:532-541` — call site
- `server/apps/agent/services/deerflow_adapter/sync_tool_patch.py:425-471` — ContextVar patch for `ExtensionsConfig.resolve_config_path`
- `deerflow/mcp/cache.py` — `_mcp_tools_cache`, `get_cached_mcp_tools()`, `_is_cache_stale()`, `reset_mcp_tools_cache()`
- `deerflow/config/extensions_config.py` — `ExtensionsConfig` singleton, `reset_extensions_config()`

---

## Planning Contract

### Key Technical Decisions

- **KTD1. `_per_family_reset_state` dict replaces `_last_reset_state` tuple.** Module-level `_per_family_reset_state: dict[str, tuple | None] = {}` keyed by `extensions_path`. Values are `(content_signature | None)`. No `_mcp_cache_lock` needed — `reset_extensions_config()` is idempotent and `_init_lock` inside `get_cached_mcp_tools()` serializes re-initialization. Governs R1, R2.

- **KTD2. `_maybe_reset_mcp_cache` calls `reset_extensions_config()` but NOT `reset_mcp_tools_cache()`.** The former clears the parsed config singleton (cheap, necessary for correct MCP server resolution). The latter tears down MCP sessions and tools (expensive, causes "briefly empty", and is handled by `get_cached_mcp_tools()` staleness check). Governs R3, R5.

- **KTD3. Tests verify per-family behavior with concurrent threads.** Use `threading.Thread` + mock `reset_extensions_config` to verify: (a) same-family repeated calls → zero resets, (b) different-family calls → reset only for the new family, (c) config content change → reset once. No integration test (both services running) — unit-level coverage is sufficient. Governs R1-R5.

### Assumptions

- `_is_cache_stale()` inside `get_cached_mcp_tools()` correctly handles family switches by detecting the different config path from the ContextVar. **Verified from source**.
- `reset_extensions_config()` is safe to call without also calling `reset_mcp_tools_cache()` — the two caches are independent. **Verified from source**: `reset_extensions_config()` only clears `_extensions_config`; `reset_mcp_tools_cache()` clears `_mcp_tools_cache`, session pool, and config signature.
- The existing call site in `agent_dispatch.py:540` doesn't need changes — only `_maybe_reset_mcp_cache`'s internal behavior changes.

---

## Implementation Units

### U1. Replace `_last_reset_state` with per-family tracking + drop `reset_mcp_tools_cache()`

- **Goal:** Eliminate the process-global race and the "briefly empty tool list" window.
- **Requirements:** R1, R2, R3, R4, R5
- **Dependencies:** None
- **Files:**
  - `server/apps/agent/services/deerflow_adapter/adapter.py` — replace `_last_reset_state`, rewrite `_maybe_reset_mcp_cache`
- **Approach:**
  1. Remove `_last_reset_state: tuple[str | None, tuple | None] | None = None` (line 130).
  2. Add `_per_family_reset_state: dict[str, tuple | None] = {}` — per-family content signature tracking.
  3. Rewrite `_maybe_reset_mcp_cache(extensions_path)`:
     ```python
     def _maybe_reset_mcp_cache(extensions_path: str) -> None:
         """Reset MCP extensions config only when a family's config changed.

         T11: per-family signature tracking replaces the process-global
         ``_last_reset_state`` to prevent alternating resets under concurrent
         multi-family requests.

         Drops ``reset_mcp_tools_cache()`` — the MCP tools cache is managed by
         ``get_cached_mcp_tools()._is_cache_stale()`` which detects config
         changes via the ContextVar-resolved path (``sync_tool_patch.py``).
         Only ``reset_extensions_config()`` is called here to clear the parsed
         config singleton when a family's config changes.
         """
         try:
             from pathlib import Path
             from deerflow.config.extensions_config import reset_extensions_config
             from deerflow.mcp.cache import _get_config_signature
         except (ImportError, AttributeError):
             return

         sig = _get_config_signature(Path(extensions_path))

         # Fast path: same family, same config → skip.
         if _per_family_reset_state.get(extensions_path) == sig:
             return

         # Config changed for this family (or first time).
         reset_extensions_config()
         _per_family_reset_state[extensions_path] = sig
     ```
  4. Update the module-level comment block (lines 120-130) to document the new per-family tracking design and reference T11.
- **Patterns to follow:** The existing `_per_family_reset_state` dict pattern is similar to `_adapter_cache` in `family_adapter_cache.py` (module-level dict with per-key state).
- **Test scenarios:**
  - Same path, same sig: call `_maybe_reset_mcp_cache(path)` twice → `reset_extensions_config` called only on the first call.
  - Same path, changed sig (config edited): call with sig A, then sig B → `reset_extensions_config` called twice (once per change).
  - Different paths (family switch): call with path A, then path B → each path tracked independently, `reset_extensions_config` called once per new path.
  - Concurrent same-family: two threads call with same path/sig simultaneously → `reset_extensions_config` called at most once (fast path).
  - Concurrent different-family: two threads call with different paths simultaneously → each path's state is independent, no cross-family interference.
  - `reset_mcp_tools_cache()` is NOT called in any path.
- **Verification:** `pytest tests/agent/unit/test_mcp_cache_per_family.py -v` passes.

---

### U2. Add concurrent multi-family MCP cache test

- **Goal:** Verify that concurrent multi-family requests don't cause cache thrashing.
- **Requirements:** R4
- **Dependencies:** U1
- **Files:**
  - `server/tests/agent/unit/test_mcp_cache_per_family.py` — new test file
- **Approach:**
  1. Mock `_get_config_signature` to return controlled signatures.
  2. Mock `reset_extensions_config` to track call count.
  3. Mock `reset_mcp_tools_cache` to verify it's NEVER called.
  4. Test scenarios:
     - `test_same_family_no_repeated_reset`: same path/sig, 10 calls → `reset_extensions_config` called once.
     - `test_different_family_independent_tracking`: path A and path B with different sigs → each tracked independently.
     - `test_config_change_triggers_reset`: same path, sig changes → reset called again.
     - `test_concurrent_same_family`: 4 threads, same path/sig → reset called at most once.
     - `test_concurrent_different_families`: 4 threads, 2 families alternating → no family sees more resets than its own config changes.
     - `test_no_reset_mcp_tools_cache`: verify `reset_mcp_tools_cache` is never called in any scenario.
     - `test_import_error_graceful`: if `_get_config_signature` or `reset_extensions_config` is unavailable → function returns without error.
- **Patterns to follow:** `tests/agent/unit/test_family_adapter_cache.py` — existing test for the adapter LRU cache with thread safety.
- **Verification:** `pytest tests/agent/unit/test_mcp_cache_per_family.py -v` passes.

---

### U3. Commit T10 cleanup changes

- **Goal:** Commit the uncommitted T10-related changes (type annotation fixes + test refinements) before adding T11 changes.
- **Requirements:** N/A (housekeeping)
- **Dependencies:** None (can be done first)
- **Files:** All currently modified files (see `git status`)
- **Approach:**
  1. Review the uncommitted changes to confirm they're T10 cleanup (type annotations + test refinements).
  2. Commit with message: `fix(agent): T10 cleanup — type annotations + test refinements`
  3. Then implement U1 + U2 and commit as `fix(agent): T11 per-family MCP cache race fix`.
- **Verification:** `git log` shows both commits.

---

## Verification Contract

| Check | Command | Scope |
|-------|---------|-------|
| T11 unit tests | `cd server && uv run pytest tests/agent/unit/test_mcp_cache_per_family.py -v` | U1, U2 |
| Full agent unit suite | `cd server && uv run pytest tests/agent/unit/ -v` | All — no regressions |
| Agent integration tests | `cd server && uv run pytest tests/agent/integration/ -v` | All — no regressions |
| Lint | `cd server && uv run ruff check apps/agent/services/deerflow_adapter/adapter.py` | U1 |
| Typecheck | `cd server && uv run mypy --exclude vendor apps/agent/services/deerflow_adapter/adapter.py` | U1 |

---

## Definition of Done

- R1–R5 all have corresponding test scenarios that pass.
- All verification commands in the Verification Contract pass with zero failures.
- No existing tests regress — the full agent test suite passes.
- `_last_reset_state` module-level variable is removed.
- `_maybe_reset_mcp_cache` never calls `reset_mcp_tools_cache()`.
- Concurrent multi-family requests don't cause alternating resets (verified by test).
- T10 cleanup changes committed separately.
