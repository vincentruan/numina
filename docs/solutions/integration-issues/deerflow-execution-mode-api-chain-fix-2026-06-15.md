# DeerFlow Execution Mode API Chain Fix

**Date:** 2026-06-15
**Severity:** P0 (Critical)
**Status:** Fixed

> **Update note (2026-07-20):** Layer 4 of the chain below (`orchestrator.stream_dispatch` on `orchestrator.py`) was **deleted** in the two-AI-apps unified-dispatch refactor (U8) — the `Orchestrator` class is gone; `is_plan_mode` / `subagent_enabled` now flow through `worker.run_agent(app)` → the per-app runner → `DeerFlowAdapter.typed_stream_dispatch` → `runnable_config`. Layers 5–7 (`agent_dispatch.py`, `chat_adapter.py`) survived and still carry these parameters. The 7-layer propagation *lesson* (trace a parameter through every layer of a multi-service chain before declaring the contract fixed) is durable; the specific `orchestrator.stream_dispatch` hop is historical. See [`two-ai-apps-unified-dispatch-stream-run.md`](../architecture-patterns/two-ai-apps-unified-dispatch-stream-run.md) for the current dispatch path.

---

## Problem

Frontend InputBox.vue sends `is_plan_mode` and `subagent_enabled` DeerFlow execution mode parameters, but backend ChatStreamRequest schema didn't include them, and the entire backend → agent service chain silently dropped these parameters, hardcoding to `deep_think` fallback.

## Impact

- DeerFlow execution modes (Flash/Thinking/Pro/Ultra) were non-functional
- `is_plan_mode` (multi-step task decomposition) was always `False`
- `subagent_enabled` (Ultra mode subagent coordination) was always `False`
- Frontend ModeSelector UI changes had no backend effect

## Root Cause

The API contract mismatch existed across multiple layers:

1. **Backend ChatStreamRequest** (ai_chat.py) — missing fields
2. **Backend agent_body** (ai_chat.py) — not passing to agent service
3. **Agent ChatStreamRequest** (chat.py) — missing fields
4. **Agent orchestrator.stream_dispatch** (orchestrator.py) — not passing to chat_adapter
5. **Agent AgentStreamRequest** (agent_stream.py) — missing fields
6. **Agent stream_agent_dispatch** (agent_dispatch.py) — not accepting or passing to runnable_config
7. **ChatAdapter.stream** (chat_adapter.py) — hardcoding to `deep_think`

## Solution

Extended each layer to accept and propagate the parameters:

### Layer 1: Backend ChatStreamRequest

```python
# server/apps/backend/app/routers/ai_chat.py
class ChatStreamRequest(BaseModel):
    # ... existing fields ...
    is_plan_mode: bool = False
    subagent_enabled: bool = False
```

### Layer 2: Backend agent_body

```python
# Both branches (agent_id and legacy)
agent_body = {
    # ... existing fields ...
    "is_plan_mode": body.is_plan_mode,
    "subagent_enabled": body.subagent_enabled,
}
```

### Layer 3: Agent ChatStreamRequest

```python
# server/apps/agent/routers/chat.py
class ChatStreamRequest(BaseModel):
    # ... existing fields ...
    is_plan_mode: bool = False
    subagent_enabled: bool = False
```

### Layer 4: Agent orchestrator.stream_dispatch

```python
# server/apps/agent/services/orchestrator.py
async def stream_dispatch(
    # ... existing params ...
    is_plan_mode: bool = False,
    subagent_enabled: bool = False,
) -> AsyncGenerator[str, None]:
```

### Layer 5: Agent AgentStreamRequest

```python
# server/apps/agent/routers/agent_stream.py
class AgentStreamRequest(BaseModel):
    # ... existing fields ...
    is_plan_mode: bool = False
    subagent_enabled: bool = False
```

### Layer 6: Agent stream_agent_dispatch

```python
# server/apps/agent/services/agent_dispatch.py
async def stream_agent_dispatch(
    # ... existing params ...
    is_plan_mode: bool = False,
    subagent_enabled: bool = False,
) -> AsyncGenerator[str, None]:
```

And in runnable_config:

```python
runnable_config = {
    "configurable": {
        # ... existing fields ...
        "is_plan_mode": is_plan_mode,
        "subagent_enabled": subagent_enabled,
    }
}
```

### Layer 7: ChatAdapter.stream

```python
# server/apps/agent/services/chat_adapter.py
async def stream(
    # ... existing params ...
    is_plan_mode: bool = False,
    subagent_enabled: bool = False,
) -> AsyncGenerator[StreamChunk, None]:
    # ...
    adapter = _create_family_adapter(
        # Use explicit params instead of deep_think fallback
        subagent_enabled=subagent_enabled,
        plan_mode=is_plan_mode,
        # ...
    )
```

## DeerFlow Reference

DeerFlow passes these parameters through `configurable` in runnable_config:

```python
# deer-flow-reference/backend/app/gateway/services.py
_CONTEXT_CONFIGURABLE_KEYS: frozenset[str] = frozenset({
    "is_plan_mode",
    "subagent_enabled",
    # ...
})
```

## Verification

```bash
uv run ruff check apps/backend/app/routers/ai_chat.py \
    apps/agent/routers/chat.py \
    apps/agent/routers/agent_stream.py \
    apps/agent/services/orchestrator.py \
    apps/agent/services/chat_adapter.py \
    apps/agent/services/agent_dispatch.py
# All checks passed!
```

## Files Modified

| File | Changes |
|------|---------|
| `server/apps/backend/app/routers/ai_chat.py` | Added is_plan_mode/subagent_enabled to ChatStreamRequest + agent_body |
| `server/apps/agent/routers/chat.py` | Added to ChatStreamRequest + stream_dispatch call |
| `server/apps/agent/routers/agent_stream.py` | Added to AgentStreamRequest + stream_agent_dispatch call |
| `server/apps/agent/services/orchestrator.py` | Extended stream_dispatch + _stream_dispatch_event_lines signatures |
| `server/apps/agent/services/chat_adapter.py` | Extended stream() signature + fixed adapter call |
| `server/apps/agent/services/agent_dispatch.py` | Extended stream_agent_dispatch signature + runnable_config |

## Testing

Manual verification via Chrome DevTools against DeerFlow demo:
- InputBox mode selector changes should now affect backend execution
- `is_plan_mode=True` enables multi-step task decomposition
- `subagent_enabled=True` enables Ultra mode subagent coordination

---

## Related

- Plan: `docs/solutions/ai-chat/deerflow-phase4-7-implementation-summary-2026-06-15.md`
- DeerFlow Reference: `/Users/vincentruan/geek_space/github/deer-flow-reference/backend/app/gateway/services.py`