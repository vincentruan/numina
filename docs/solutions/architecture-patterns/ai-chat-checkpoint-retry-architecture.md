---
title: "AI Chat checkpoint-based retry — fork from failure point instead of restarting conversation"
date: "2026-08-21"
category: architecture-patterns
module: frontend/apps/main
problem_type: architecture_pattern
component: frontend_stimulus
severity: high
applies_when:
  - "AI chat sessions need retry-on-failure without losing prior conversation context"
  - "LangGraph checkpointers are available for state restoration"
  - "Frontend needs to regenerate the last assistant response without duplicating earlier messages"
tags:
  - ai-chat
  - checkpoint
  - retry
  - langgraph
  - deerflow
  - sse
  - title-preservation
---

# AI Chat Checkpoint-Based Retry Architecture

## Context

When an AI chat response fails mid-stream (LLM timeout, circuit breaker trip, network error), the user needs to retry — regenerate the last assistant message without losing the conversation before it. Simply re-sending the message creates a new LangGraph run from the head checkpoint, which duplicates prior messages and loses the original thread state.

The solution is **checkpoint forking**: save the checkpoint ID before the failed message, then retry from that checkpoint. LangGraph's checkpointer loads the state from the checkpoint, and the new run replaces (not appends to) the failed branch.

## Guidance

### Architecture

```
User sends message
  → LangGraph creates run, saves checkpoint_A (before AI responds)
  → AI starts streaming
  → Error occurs mid-stream
  → Frontend shows retry button with checkpoint_A

User clicks retry
  → Frontend sends retryPrepare { checkpoint_id: checkpoint_A }
  → Backend forks from checkpoint_A (not head)
  → New run starts from checkpoint_A's state
  → Checkpoint_B saved (new branch from A)
```

### Key implementation points

1. **Checkpoint ID flows through DeerFlow client** — `NuminaDeerFlowClient` subclass extracts `checkpoint_id` from kwargs and includes it in the `RunnableConfig.configurable` dict for the checkpointer.

2. **Frontend tracks the latest checkpoint** — extracted from SSE `values` events during streaming. On retry, the frontend passes `checkpoint_id` from the last successful `values` event.

3. **Title preservation** — on follow-up turns, the checkpoint carries a stale fallback title from the first run. The adapter must NOT forward this stale title to the frontend. Fix: drop fallback titles from `values` events entirely. The frontend already has a temp title from `handleStartChat`, and the LLM title arrives via `bridge.publish` after the first stream.

4. **No version pagination** — earlier iterations used client-side version pagination to track message history. This was removed in favor of the shared checkpoint scan utility, which reads checkpoint metadata directly from the checkpointer.

### Follow-up title bug (specific pitfall)

On follow-up turns (not the first message), the checkpoint still carries the stale fallback title from the first run. The old code replaced the fallback with `context.free_text` (the current turn's user message), which **overwrote the first-turn LLM title with the follow-up text**.

Fix: drop the fallback title from the `values` event entirely on ALL turns. DeerFlow parity — title is generated only on the first exchange.

```python
# ✅ Drop fallback title from values event — don't replace it
raw_title = event_data.get("title")
if raw_title and isinstance(raw_title, str):
    if _is_fallback_title(raw_title):
        event_data = {k: v for k, v in event_data.items() if k != "title"}
```

## Why This Matters

- **User experience**: Retry produces a clean regeneration, not a conversation with duplicated messages.
- **Title stability**: Session titles don't change on follow-up turns or retries.
- **State consistency**: LangGraph's checkpointer handles the forking — no custom state management needed.

## When to Apply

- Any AI chat system built on LangGraph/LangChain with a checkpointer
- When retry semantics need to preserve prior conversation context
- When title generation is decoupled from the streaming response

## Related

- DeerFlow adapter decoupling: `docs/solutions/architecture-patterns/deerflow-adapter-decoupling-stream-bridge-subclass.md`
- Circuit breaker (failure trigger for retry): `docs/solutions/architecture-patterns/three-state-circuit-breaker-with-cascade-retry-2026-05-20.md`
