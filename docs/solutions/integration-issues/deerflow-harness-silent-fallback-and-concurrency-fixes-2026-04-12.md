---
title: "DeerFlow harness integration fixes — silent fallback, locking, redaction (historical)"
date: "2026-04-12"
category: integration-issues
module: server/apps/agent
problem_type: integration_issue
component: assistant
severity: critical
root_cause: incomplete_setup
resolution_type: code_fix
tags:
  - deerflow
  - silent-exception
  - asyncio-lock
  - historical
---

# DeerFlow Harness Integration Fixes (Historical)

> **Status: Mostly historical (2026-07).** The `Orchestrator` class and its `dispatch()`/`stream_dispatch()` methods were deleted in the two-AI-apps unified-dispatch refactor. Dispatch now flows through `worker.run_agent(app)` → per-app runner → `DeerFlowAdapter.typed_stream_dispatch`. The engineering lessons below are durable and still apply.

## Problem

A review of Numina's DeerFlow AI agent harness found 7 issues: silent fallback swallowing exceptions, undeclared concurrency locks, cross-module private imports, dead config constants, missing error logging, inconsistent type annotations, and frontend accessibility issues. Six of the seven targeted code that was later deleted in the unified-dispatch refactor.

## Durable Lessons

1. **Never silently swallow initialization exceptions:**
   ```python
   # ❌ Silent fallback — feature permanently disabled, invisible
   try:
       adapter = import_adapter()
   except Exception:
       adapter = None  # ImportError swallowed → feature silently dead

   # ✅ Log and surface
   except Exception as e:
       logger.warning(f"Adapter init failed: {e}")
       raise  # or at minimum, set a visible flag
   ```

2. **`asyncio.Lock` is not thread-safe:** Acquire in the event loop (async context), not inside `run_in_executor`. Acquire BEFORE the executor call.

3. **Leading-underscore = private API:** Never import `_private_func()` across module boundaries. If you need it externally, add a public wrapper. Ruff rule `PLC2701` catches this.

4. **Dead constants mislead:** `_CAPABILITY_MAP` looked like it controlled dispatch but was never consulted. Dead code that resembles live configuration is worse than no code — future contributors update the map thinking it changes behavior.

5. **Always log in `except Exception` blocks that substitute defaults:**
   ```python
   # ❌ Silent degradation — outages invisible
   except Exception:
       data = []

   # ✅ Graceful degradation with visibility
   except Exception as e:
       logger.warning(f"Fetch failed family={family_id}: {e}")
       data = []
   ```

6. **Use PEP 604 union syntax** (`str | None`, not `Optional[str]`) for Python 3.10+.

## Related

- Current dispatch architecture: [`../architecture-patterns/two-ai-apps-unified-dispatch-stream-run.md`](../architecture-patterns/two-ai-apps-unified-dispatch-stream-run.md)
- MCP/ChatAdapter patterns: [`../architecture-patterns/mcp-chat-adapter-architecture-2026-05-21.md`](../architecture-patterns/mcp-chat-adapter-architecture-2026-05-21.md)
- Adapter decoupling: [`../architecture-patterns/deerflow-adapter-decoupling-stream-bridge-subclass.md`](../architecture-patterns/deerflow-adapter-decoupling-stream-bridge-subclass.md)
