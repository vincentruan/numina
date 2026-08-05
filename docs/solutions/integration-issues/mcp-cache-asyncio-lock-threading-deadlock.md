---
date: 2026-08-05
module: agent
problem_type: integration_issue
component: deerflow_adapter
severity: high
root_cause: logic_error
resolution_type: code_fix
symptoms:
  - "MCP tools: 0 on every agent run — DeerFlow MCP tools fail to load"
  - "/ai/chat reports 'MCP tools unavailable' — cannot query family data"
  - "RuntimeError: There is no current event loop in thread 'deerflow_N' in agent logs"
tags:
  - asyncio-lock
  - threading
  - event-loop
  - mcp-cache
  - monkey-patch
applies_when:
  - "Module-level asyncio.Lock accessed from worker threads with separate event loops"
  - "DeerFlow ThreadPoolExecutor dispatches to worker threads that access cached async resources"
---

# DeerFlow MCP Cache asyncio.Lock Threading Deadlock

## Problem
DeerFlow's MCP tool cache uses `_initialization_lock = asyncio.Lock()` created at module import time, bound to the main thread's event loop. Worker threads (`deerflow_N`) access this lock via `asyncio.run()` which creates a new event loop — cross-thread `create_future()` raises `RuntimeError`. Result: **MCP tools: 0** on every agent run.

## Symptoms
- Agent logs show `MCP tools: 0` on every run
- `/ai/chat` reports "MCP tools unavailable" — cannot query family data
- `/ai/report` works (different code path)
- `RuntimeError: There is no current event loop in thread 'deerflow_N'` in agent logs

## What Didn't Work
- The upstream `except RuntimeError` retry at `cache.py:177` — it catches the initial `get_event_loop()` failure but retries with `asyncio.run()` which also fails at `initialize_mcp_tools` line 125 (`async with _initialization_lock`) for the same cross-thread reason
- Restarting the agent process — the module-level lock re-initializes bound to the same main-thread loop, and worker threads hit the same deadlock

## Solution
Monkey-patch `deerflow.mcp.cache.get_cached_mcp_tools` to replace the broken `asyncio.Lock` with a `threading.Lock` + `asyncio.run()` combination that works correctly in any thread.

**Before** (upstream DeerFlow library `deerflow/mcp/cache.py` in site-packages):
```python
_initialization_lock = asyncio.Lock()  # Bound to main thread's loop at import time

async def initialize_mcp_tools():
    async with _initialization_lock:  # Cross-thread RuntimeError
        ...
```

**After** (`server/apps/agent/services/deerflow_adapter/sync_tool_patch.py`):
```python
def _apply_mcp_cache_threading_lock_patch() -> None:
    import deerflow.mcp.cache as _cache_mod
    import asyncio as _asyncio
    import threading as _threading

    _lazy_init_thread_lock = _threading.Lock()

    def _patched_get_cached_mcp_tools():
        if _cache_mod._cache_initialized and not _cache_mod._is_cache_stale():
            return _cache_mod._mcp_tools_cache or []

        if not _lazy_init_thread_lock.acquire(blocking=False):
            _lazy_init_thread_lock.acquire()  # Wait for other thread
            _lazy_init_thread_lock.release()
            return _cache_mod._mcp_tools_cache or []
        try:
            if _cache_mod._cache_initialized:
                return _cache_mod._mcp_tools_cache or []
            from deerflow.mcp.tools import get_mcp_tools
            _cache_mod._mcp_tools_cache = _asyncio.run(get_mcp_tools())
            _cache_mod._cache_initialized = True
        finally:
            _lazy_init_thread_lock.release()
        return _cache_mod._mcp_tools_cache or []

    _cache_mod.get_cached_mcp_tools = _patched_get_cached_mcp_tools
```

## Why This Works
`threading.Lock` is not bound to any event loop — it works across any thread. `asyncio.run()` creates a fresh event loop scoped to the call, avoiding the cross-thread loop access that `asyncio.Lock` requires. The double-check pattern after acquiring the lock prevents redundant initialization when multiple worker threads race to initialize simultaneously.

## Prevention
- **Never create `asyncio.Lock()` / `asyncio.Event()` / `asyncio.Semaphore()` at module import time** when the code may be called from worker threads with separate event loops. Use `threading.Lock` for cross-thread synchronization.
- **Test MCP tool loading in multi-threaded scenarios** — the bug only manifests when DeerFlow's ThreadPoolExecutor dispatches to a worker thread, not in single-threaded test harnesses.
