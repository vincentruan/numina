---
title: "DeerFlow adapter decoupling — stream_bridge extraction and NuminaDeerFlowClient subclass"
date: "2026-08-21"
category: architecture-patterns
module: server/apps/agent
problem_type: architecture_pattern
component: service_object
severity: high
applies_when:
  - "Integrating with an upstream AI framework (DeerFlow/LangGraph) that needs project-specific extensions"
  - "Monkey-patching private methods of vendored classes creates fragility"
  - "Shared packages need to be consumed by multiple apps without circular dependencies"
tags:
  - deerflow
  - stream-bridge
  - subclass-pattern
  - decoupling
  - monorepo
  - monkey-patch-removal
---

# DeerFlow Adapter Decoupling — stream_bridge Extraction and NuminaDeerFlowClient Subclass

## Context

Numina's AI chat is built on top of DeerFlow (an upstream LangGraph-based AI framework). The integration layer (`DeerFlowAdapter`) lived in `server/apps/agent/` and had two architectural problems:

1. **Monkey-patching**: To support checkpoint-based retry, the adapter monkey-patched DeerFlow's private `_get_runnable_config()` method using `unittest.mock.patch`. This was fragile — the private method name could change in DeerFlow updates, patch scope could leak in concurrent scenarios, and having `unittest.mock` in production code was unusual.

2. **Coupled shared package**: The `stream_bridge` package (Redis-backed pub/sub for streaming SSE between agent and backend) previously lived under the `db` package (removed in this refactor), creating a false dependency — backend had to import from a `db` package to get stream functionality, even though stream_bridge had nothing to do with database models.

## Guidance

### 1. Replace monkey-patches with subclasses

When you need to extend behavior of a vendored/upstream class:

```python
# ❌ Monkey-patch — fragile, scope leaks, unittest.mock in production
from unittest.mock import patch

original_method = DeerFlowClient._get_runnable_config
def patched(self, thread_id, **overrides):
    config = original_method(self, thread_id, **overrides)
    if "checkpoint_id" in overrides:
        config["configurable"]["checkpoint_id"] = overrides["checkpoint_id"]
    return config

with patch.object(DeerFlowClient, "_get_runnable_config", patched):
    for event in client.stream(...):
        ...
```

```python
# ✅ Subclass — type-safe, scope-safe, maintainable
class NuminaDeerFlowClient(DeerFlowClient):
    def _get_runnable_config(self, thread_id: str, **overrides: Any) -> Any:
        config = super()._get_runnable_config(thread_id, **overrides)
        checkpoint_id = overrides.pop("checkpoint_id", None)
        if checkpoint_id is not None:
            config.setdefault("configurable", {})["checkpoint_id"] = checkpoint_id
        return config
```

Benefits of the subclass approach:
- **Type-safe**: IDE/mypy can check the override
- **Scope-safe**: Instance method, no global state mutation
- **Concurrency-safe**: No patch/unpatch race conditions
- **Maintainable**: Clear inheritance, no mock magic

### 2. Place shared packages by their own domain, not by consumer

```
# ❌ Misleading location — stream_bridge is not a DB concern (historical, removed)
server/packages/<domain>/<subpackage>/   # e.g. nested under an unrelated sibling

# ✅ Independent shared package at the packages root
server/packages/stream_bridge/
```

When a package is consumed by multiple apps (backend, agent, worker), it should live at the workspace packages level with its own identity — not nested under an unrelated sibling package. In Numina, the old location under the `db` package was removed; the package now lives at `server/packages/stream_bridge/`.

## Why This Matters

- **Monkey-patches in production** are a maintenance hazard: upstream updates can silently break them, and they're invisible to type checkers and linters.
- **Misplaced packages** create phantom dependencies: moving `stream_bridge` out of the `db` package removed the false implication that you need the DB package to use streams.
- **Subclassing is the right tool** when you control instantiation — the adapter creates the client, so it can use the subclass directly.

## When to Apply

- When you find `unittest.mock.patch` in production code (not tests)
- When a `packages/<domain>/` subpackage is imported by apps that don't use that domain's core functionality
- When upstream framework updates require manual re-patching

## Examples

**NuminaDeerFlowClient** (`server/apps/agent/services/deerflow_adapter/numina_deerflow_client.py`):
- Extends `DeerFlowClient._get_runnable_config()` to extract `checkpoint_id` from kwargs
- Used by `family_adapter_cache.py` and `client_factory.py` instead of the raw `DeerFlowClient`
- The adapter's `_produce()` function is simplified — no more patch context manager

**stream_bridge extraction** (`server/packages/stream_bridge/`):
- Contains `base.py`, `redis.py`, `memory.py`, `config.py`, `factory.py`
- Moved from the `db` package to its own top-level package
- Backend's `pyproject.toml` dependency changed from `numina-db` to `numina-stream-bridge`

## Related

- Previous adapter issues: `docs/solutions/integration-issues/deerflow-adapter-stream-type-mismatch-and-security-issues-2026-05-16.md`
- Checkpoint retry architecture: `docs/solutions/architecture-patterns/ai-chat-checkpoint-retry-architecture.md`
