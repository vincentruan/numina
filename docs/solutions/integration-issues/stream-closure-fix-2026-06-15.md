# AI Chat Stream Closure Fix

## Problem

Frontend's `reader.read()` loop never returned `done: true`, causing the assistant message to stay in `processing` state indefinitely. The stream connection wasn't closing properly after the agent sent all events including `capability.end`.

## Root Cause

Backend's `chat_stream` proxy in `ai_chat.py` used `resp.aiter_text()` which yields raw text chunks. This method doesn't properly signal stream end to downstream consumers. The manual buffer splitting logic handled line boundaries but the HTTP connection wasn't being closed when the upstream agent stream ended.

## Fix

Changed from `resp.aiter_text()` to `resp.aiter_lines()`:

```python
# Before (broken)
async for chunk in resp.aiter_text():
    buffer += chunk
    while "\n" in buffer:
        line, buffer = buffer.split("\n", 1)
        if not line.strip():
            continue
        # process line
        yield f"{line}\n".encode()

# After (fixed)
async for line in resp.aiter_lines():
    if not line.strip():
        continue
    # process line
    yield f"{line}\n".encode()
```

## Why It Works

- `aiter_lines()` yields complete lines and properly detects stream end
- When the upstream agent's generator exits, `aiter_lines()` ends its iteration
- The backend generator exits, FastAPI's `StreamingResponse` closes the HTTP connection
- Frontend's `reader.read()` receives `done: true`, exits the loop
- Message phase transitions to `done` correctly

## Verification

Browser console logs after fix:

```
[AIChatPage] Starting stream read loop
[AIChatPage] Read chunk: {done: false, valueLen: 108}
[AIChatPage] Read chunk: {done: false, valueLen: 252}
...
[AIChatPage] Read chunk: {done: true, valueLen: undefined}
[AIChatPage] Stream done, exiting loop
[AIChatPage] Flushing parser
```

## Files Changed

- `server/apps/backend/app/routers/ai_chat.py` - switched to `aiter_lines()`, removed buffer variable

## Related Patterns

Other streaming endpoints in the backend use `aiter_lines()` (see `_ai_events_helper.py`). This pattern is preferred for NDJSON streams where each event is a complete line.