# AI Chat Streaming Issues Fix Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix the P0 issue where `agent_id=null` requests to the Backend `/ai/chat/stream` proxy route to a deleted endpoint and return 404. All other issues from the test report (disconnect detection, server-side cancel, Pro/Ultra timeout) are already implemented.

**Architecture:** A single change in `server/apps/backend/app/routers/ai_chat.py` to auto-fallback to the 数鸣 system agent (`NUMINA_AGENT_ID = 100000000000005`) when `agent_id` is null, instead of routing to the deleted legacy `/chat/ask/stream` endpoint.

**Tech Stack:** FastAPI (Python 3.12+), httpx

## Global Constraints

- All API endpoints must respond with 200 directly — no 307 redirects (`redirect_slashes=False`, router decorators use `""` not `"/"`)
- Error messages in Chinese for HTTP exceptions
- Pydantic v2 only
- No speculative code — don't add features beyond what was asked
- Import `NUMINA_AGENT_ID` from `apps.backend.app.constants.system_ids` (already exists)
- The `is_plan_mode` and `subagent_enabled` fields from `ChatStreamRequest` must be forwarded to Agent as-is (match DeerFlow 4-mode spec)
- The `session.start` SSE event must still be emitted before the proxy stream begins

---

## Pre-Flight Verification: Issues Already Fixed

The following issues from the test report are **already implemented** — no code changes needed. This was confirmed by reading the current code.

### ✅ P0: Disconnect detection (3 locations)

| File | Line | Status |
|------|------|--------|
| `server/apps/agent/routers/runs.py` | 217 | `request.is_disconnected()` in `_sse_generator()` loop |
| `server/apps/agent/services/agent_dispatch.py` | 668 | `cancellation_event.is_set()` in `astream` loop |
| `server/apps/backend/app/routers/ai_chat.py` | 395, 403 | `request.is_disconnected()` in `proxy_stream()` loops |

All three streaming paths check for client disconnect and break/return gracefully.

### ✅ P1: Server-side cancel in cancelStream

| File | Line | Status |
|------|------|--------|
| `frontend/apps/main/src/composables/ai-chat/useThreadChat.ts` | 334 | `client.runs.cancel(currentThreadId, 'agent').catch(() => {})` |

Fire-and-forget server-side cancel on abort.

### ✅ P0: Pro/Ultra timeout

The 15s timeout was a curl test tool limitation. Backend `AgentClient.stream()` uses `httpx.Timeout(read=300.0)` — 300 seconds for streaming reads. Frontend `STREAM_TIMEOUT_MS` is 120 seconds. Both are adequate for long responses.

### ✅ P2: MCP server configuration

No code change needed — requires admin to configure MCP servers for the test family in the backend admin UI.

---

## Task 1: Add agent_id auto-fallback when null

**Problem:** In `chat_stream()`, when `body.agent_id` is `None`, the proxy_stream() closure routes to the legacy agent endpoint `/chat/ask/stream` (line 346), which has been removed from the Agent service. This causes a 404.

**Fix:** When `body.agent_id` is `None`, automatically use the 数鸣 system agent ID (`NUMINA_AGENT_ID = 100000000000005`) instead of the legacy path. This is the only code change needed.

**Files:**
- Modify: `server/apps/backend/app/routers/ai_chat.py:328` — Replace the `if body.agent_id: ... else:` branching logic with a single path that always uses `runs.py`.

### Step 1: Import NUMINA_AGENT_ID

**File:** `server/apps/backend/app/routers/ai_chat.py` — Add import at top of file

```python
from apps.backend.app.constants.system_ids import NUMINA_AGENT_ID
```

### Step 2: Replace agent_id routing logic

**File:** `server/apps/backend/app/routers/ai_chat.py` — Around lines 325-355

Replace the `if body.agent_id: / else:` branching (lines 328-355) with a unified path that uses a resolved `agent_id`:

**Current code (lines 325-355):**
```python
        # Route to the appropriate agent endpoint.
        # When agent_id is present, proxy to runs.py (LangGraph SSE format).
        # Otherwise use the legacy chat_adapter path (NDJSON format).
        if body.agent_id:
            # runs.py expects LangGraph-style input with assistant_id and messages
            agent_url = f"/api/threads/{session_id}/runs/stream"
            request_json = {
                "assistant_id": body.agent_id,
                "input": {
                    "messages": [{"role": "user", "content": body.question}],
                },
                "metadata": {
                    "deep_think": body.deep_think,
                    "web_search": body.web_search,
                    "reasoning_effort": body.reasoning_effort,
                    "source": body.source,
                    "is_plan_mode": body.is_plan_mode,
                    "subagent_enabled": body.subagent_enabled,
                },
            }
        else:
            agent_url = "/chat/ask/stream"
            request_json = {
                "question": body.question,
                "deep_think": body.deep_think,
                "web_search": body.web_search,
                "reasoning_effort": body.reasoning_effort,
                "source": body.source,
                "is_plan_mode": body.is_plan_mode,
                "subagent_enabled": body.subagent_enabled,
            }
```

**New code:**
```python
        # Route to the runs.py endpoint (LangGraph SSE format).
        # When agent_id is absent, fall back to the 数鸣 system agent (NUMINA_AGENT_ID).
        agent_id = body.agent_id or str(NUMINA_AGENT_ID)
        agent_url = f"/api/threads/{session_id}/runs/stream"
        request_json = {
            "assistant_id": agent_id,
            "input": {
                "messages": [{"role": "user", "content": body.question}],
            },
            "metadata": {
                "deep_think": body.deep_think,
                "web_search": body.web_search,
                "reasoning_effort": body.reasoning_effort,
                "source": body.source,
                "is_plan_mode": body.is_plan_mode,
                "subagent_enabled": body.subagent_enabled,
            },
        }
```

### Step 3: Remove the legacy NDJSON parsing path

**File:** `server/apps/backend/app/routers/ai_chat.py` — Around lines 365-420

Now that every request goes through the runs.py path, the `if body.agent_id: / else:` branching inside the proxy_stream generator (line 365) is also dead code. Replace the entire SSE passthrough + legacy NDJSON path with just the SSE passthrough:

**Current code (lines 364-421):**
```python
                if body.agent_id:
                    # runs.py returns SSE directly — passthrough with SSE-aware parsing
                    sse_buffer: list[str] = []
                    async for line in resp.aiter_lines():
                        if not line.strip() and sse_buffer:
                            # Complete SSE event — forward it
                            full_event = "\n".join(sse_buffer) + "\n\n"
                            yield full_event.encode()

                            # Parse event type and data for answer token collection
                            event_type = ""
                            data_text = ""
                            for ev_line in sse_buffer:
                                if ev_line.startswith("event: "):
                                    event_type = ev_line[7:]
                                elif ev_line.startswith("data: "):
                                    data_text = ev_line[6:]

                            if event_type == "messages" and data_text:
                                try:
                                    msg_data = json.loads(data_text)
                                    if isinstance(msg_data, dict) and msg_data.get("type") == "ai" and msg_data.get("content"):
                                        answer_chunks.append(msg_data["content"])
                                except json.JSONDecodeError:
                                    pass

                            sse_buffer = []
                        elif line.strip():
                            sse_buffer.append(line)

                        if await request.is_disconnected():
                            logger.info("chat_stream client disconnected session=%s", session_id)
                            break
                else:
                    # Legacy NDJSON path — convert each NDJSON line to SSE
                    async for line in resp.aiter_lines():
                        if not line.strip():
                            continue
                        if await request.is_disconnected():
                            logger.info("chat_stream client disconnected session=%s", session_id)
                            break
                        # Collect answer tokens for persistence using NDJSON parsing
                        token = _collect_answer_token_from_event(line)
                        if token is not None:
                            answer_chunks.append(token)
                        if use_sse:
                            try:
                                event_data = json.loads(line)
                                event_type = event_data.get("type", "custom")
                                sse_type = _SSE_TYPE_MAP.get(event_type, "custom")
                                payload = json.dumps(event_data, ensure_ascii=False, separators=(",", ":"))
                                yield f"event: {sse_type}\ndata: {payload}\n\n".encode()
                            except json.JSONDecodeError:
                                yield f"event: custom\ndata: {line.strip()}\n\n".encode()
                        else:
                            yield f"{line}\n".encode()
```

**New code (replace the entire block):**
```python
                # runs.py returns SSE directly — passthrough with SSE-aware parsing
                sse_buffer: list[str] = []
                async for line in resp.aiter_lines():
                    if not line.strip() and sse_buffer:
                        # Complete SSE event — forward it
                        full_event = "\n".join(sse_buffer) + "\n\n"
                        yield full_event.encode()

                        # Parse event type and data for answer token collection
                        event_type = ""
                        data_text = ""
                        for ev_line in sse_buffer:
                            if ev_line.startswith("event: "):
                                event_type = ev_line[7:]
                            elif ev_line.startswith("data: "):
                                data_text = ev_line[6:]

                        if event_type == "messages" and data_text:
                            try:
                                msg_data = json.loads(data_text)
                                if isinstance(msg_data, dict) and msg_data.get("type") == "ai" and msg_data.get("content"):
                                    answer_chunks.append(msg_data["content"])
                            except json.JSONDecodeError:
                                pass

                        sse_buffer = []
                    elif line.strip():
                        sse_buffer.append(line)

                    if await request.is_disconnected():
                        logger.info("chat_stream client disconnected session=%s", session_id)
                        break
```

**Also remove the unused `_collect_answer_token_from_event` helper** (lines 212-223) if it's no longer referenced anywhere after this change. Check with grep.

### Step 4: Remove unused helpers (after verifying)

**File:** `server/apps/backend/app/routers/ai_chat.py`

After removing the legacy NDJSON path, check if `_collect_answer_token_from_event` (line 212) is still called anywhere. If not, remove it. Also check if the `_SSE_TYPE_MAP` constant (line 52) is still needed — it was only used by the NDJSON→SSE conversion path.

Run: `grep -n "_collect_answer_token_from_event\|_SSE_TYPE_MAP" apps/backend/app/routers/ai_chat.py`

If both are only referenced in the deleted code block, remove them.

### Step 5: Run tests

```bash
cd server
uv run pytest apps/backend/tests/ -v --tb=short 2>&1 | tail -30
uv run mypy apps/backend/app/routers/ai_chat.py 2>&1
uv run ruff check apps/backend/app/routers/ai_chat.py 2>&1
```

### Step 6: Update test report

After the fix, update the test report at `docs/reports/2026-06-23-ai-chat-streaming-verification-report.md`:

- Mark Issue 1 (P0 - no agent_id path broken) as **已修复**
- Change the 开放问答 (无 agent_id) test results from ❌ to ✅ expected (should now route to 数鸣 agent)

### Step 7: Commit

```bash
cd server
git add apps/backend/app/routers/ai_chat.py apps/backend/tests/
git commit -m "fix: auto-fallback to 数鸣 agent when agent_id is null

When agent_id is not provided in /ai/chat/stream requests, the proxy
was routing to the deleted /chat/ask/stream endpoint (404). Now falls
back to NUMINA_AGENT_ID (100000000000005, 数鸣) so all requests go
through runs.py and the legacy NDJSON path is fully removed."
```

---

## Files to Modify (Complete List)

| File | Change |
|------|--------|
| `server/apps/backend/app/routers/ai_chat.py` | Add `NUMINA_AGENT_ID` import; replace `if/else` routing with unified `agent_id` fallback; remove legacy NDJSON parsing branch; clean up unused helpers |

## Files NOT to Modify

- `server/apps/agent/routers/runs.py` — Already has disconnect detection
- `server/apps/agent/services/agent_dispatch.py` — Already has cancellation_event
- `frontend/apps/main/src/composables/ai-chat/useThreadChat.ts` — Already has server-side cancel
- `frontend/apps/main/src/composables/ai-chat/__tests__/useThreadChat.spec.ts` — Tests pass
- `server/apps/backend/app/constants/system_ids.py` — `NUMINA_AGENT_ID` already defined
