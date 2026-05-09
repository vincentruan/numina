# AI Agent V2 Phase 1 Protocol Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the AI chat stream's `[THINK]` / `[TEXT]` prefix protocol with structured NDJSON events while preserving current chat behavior and preparing the surface for Capability and Tool UI phases.

**Architecture:** Introduce a small agent-side event model and `EventStreamBuilder` as the only stream serialization boundary. The agent emits NDJSON events, the backend proxies them and persists only final answer tokens, and the frontend parses line-delimited events into the existing phase/thinking/message state.

**Tech Stack:** Python 3.11 + FastAPI + Pydantic/pytest, Vue 3 + TypeScript + Vitest, Playwright for browser validation.

---

## Current Gap Summary

Current implementation after `c43a46f` has improved handoff and basic phase UI, but it is still V1.5 relative to `docs/design/AI_AGENT_INTERACTION_V2.md`:

- Protocol: `agent/routers/chat.py`, `backend/app/routers/ai_chat.py`, and `frontend/apps/main/src/pages/AIChatPage.vue` still depend on `[THINK]` / `[TEXT]` prefixes.
- Backend proxy: `/api/v1/ai/chat/stream` strips `[TEXT]` for persistence, so it is coupled to the old protocol and cannot persist structured events.
- Frontend parser: `AIChatPage.vue` hand-parses prefix boundaries, which is fragile when chunks split across prefix strings.
- Tool visibility: no `tool.call` / `tool.result` event path exists yet; Phase 1 should define event types and tolerate them, but not build full cards.
- Capability model: `/ai` still uses a static feature grid plus free input. This belongs to Phase 2, not Phase 1.
- Harness alignment: `orchestrator.stream_dispatch()` already prefers DeerFlow when `USE_DEERFLOW=true`, but fallback streaming still produces prefixed strings. Phase 1 must make both DeerFlow and fallback output go through one event boundary.

## File Structure

- Create `agent/services/stream_events.py`: event dataclasses/helpers and NDJSON serialization.
- Modify `agent/services/orchestrator.py`: add an event-streaming method that wraps existing text/thinking chunks into `StreamEvent` objects without changing policy, context, PII, or audit invariants.
- Modify `agent/routers/chat.py`: expose NDJSON from `/chat/ask/stream` with `application/x-ndjson`; remove prefix wrapping.
- Modify `agent/tests/unit/test_stream_events.py`: unit tests for event JSON shape, line delimiter, ordering, and UTF-8 content.
- Modify `agent/tests/integration/test_full_dispatch.py`: streaming endpoint expects NDJSON events instead of prefixed text.
- Modify `backend/app/routers/ai_chat.py`: proxy NDJSON unchanged and persist only `token.stream` events where `is_thinking=false`.
- Modify or add `backend/tests/test_ai_chat_sessions.py`: backend streaming persistence test for NDJSON token events.
- Modify `frontend/apps/main/src/types/agent-stream.ts`: shared TypeScript event types.
- Create `frontend/apps/main/src/composables/useAgentEventStream.ts`: parse incremental NDJSON chunks with a carry buffer.
- Modify `frontend/apps/main/src/api/ai.ts`: rename or add `sendChatEventStream()` while retaining a compatibility export only if needed by tests.
- Modify `frontend/apps/main/src/pages/AIChatPage.vue`: consume `AgentEvent` objects instead of prefix text, preserving current UI states.
- Modify `frontend/apps/main/tests/pages/AIChatPage.spec.ts`: parser/UI regression tests.
- Modify `tests/e2e/ai-chat-entry-flow.spec.ts`: keep request assertion, add visible phase/content assertion that works with NDJSON.

## Task 1: Agent Stream Event Model

**Files:**
- Create: `agent/services/stream_events.py`
- Test: `agent/tests/unit/test_stream_events.py`

- [ ] **Step 1: Write failing unit tests**

```python
# agent/tests/unit/test_stream_events.py
import json

from services.stream_events import EventStreamBuilder


def test_phase_event_serializes_as_one_ndjson_line():
    builder = EventStreamBuilder(capability_id="chat", task_id="task-1")

    line = builder.phase("connecting", {"model": "qwen"}).to_ndjson()

    assert line.endswith("\n")
    data = json.loads(line)
    assert data["id"] == "task-1-0001"
    assert data["type"] == "phase.connecting"
    assert data["capability_id"] == "chat"
    assert data["task_id"] == "task-1"
    assert data["phase"] == "connecting"
    assert data["metadata"] == {"model": "qwen"}


def test_token_event_preserves_chinese_and_thinking_flag():
    builder = EventStreamBuilder(capability_id="chat", task_id="task-1")

    data = json.loads(builder.token("净资产分析", is_thinking=False).to_ndjson())

    assert data["type"] == "token.stream"
    assert data["token"] == "净资产分析"
    assert data["is_thinking"] is False


def test_tool_events_have_stable_tool_id():
    builder = EventStreamBuilder(capability_id="chat", task_id="task-1")

    call = json.loads(
        builder.tool_call(
            tool_name="asset_search",
            arguments={"query": "房产"},
            display_name="资产查询",
            icon="search",
        ).to_ndjson()
    )

    assert call["type"] == "tool.call"
    assert call["tool"]["id"] == "task-1-tool-0001"
    assert call["tool"]["name"] == "asset_search"
    assert call["tool"]["display_name"] == "资产查询"
    assert call["tool"]["arguments"] == {"query": "房产"}
```

- [ ] **Step 2: Run test to verify failure**

Run from `agent/`:

```bash
uv run pytest tests/unit/test_stream_events.py -v
```

Expected: FAIL because `services.stream_events` does not exist.

- [ ] **Step 3: Implement event model**

```python
# agent/services/stream_events.py
"""Structured NDJSON stream events for Agent chat.

This is the protocol boundary between DeerFlow Harness output, backend proxying,
and frontend rendering. Keep it small and stable.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class StreamEvent:
    id: str
    type: str
    timestamp: float
    capability_id: str
    task_id: str
    payload: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "type": self.type,
            "timestamp": self.timestamp,
            "capability_id": self.capability_id,
            "task_id": self.task_id,
            **self.payload,
        }

    def to_ndjson(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, separators=(",", ":")) + "\n"


class EventStreamBuilder:
    def __init__(self, capability_id: str, task_id: str):
        self.capability_id = capability_id
        self.task_id = task_id
        self._event_id = 0
        self._tool_id = 0

    def _next_event_id(self) -> str:
        self._event_id += 1
        return f"{self.task_id}-{self._event_id:04d}"

    def _next_tool_id(self) -> str:
        self._tool_id += 1
        return f"{self.task_id}-tool-{self._tool_id:04d}"

    def _event(self, event_type: str, payload: dict[str, Any]) -> StreamEvent:
        return StreamEvent(
            id=self._next_event_id(),
            type=event_type,
            timestamp=time.time(),
            capability_id=self.capability_id,
            task_id=self.task_id,
            payload=payload,
        )

    def phase(self, phase: str, metadata: dict[str, Any] | None = None) -> StreamEvent:
        return self._event(
            f"phase.{phase}",
            {"phase": phase, "metadata": metadata or {}},
        )

    def token(self, token: str, is_thinking: bool) -> StreamEvent:
        return self._event(
            "token.stream",
            {"token": token, "is_thinking": is_thinking},
        )

    def tool_call(
        self,
        tool_name: str,
        arguments: dict[str, Any],
        display_name: str | None = None,
        icon: str | None = None,
    ) -> StreamEvent:
        return self._event(
            "tool.call",
            {
                "tool": {
                    "id": self._next_tool_id(),
                    "name": tool_name,
                    "display_name": display_name or tool_name,
                    "icon": icon or "tool",
                    "arguments": arguments,
                }
            },
        )

    def tool_result(
        self,
        tool_id: str,
        success: bool,
        execution_time_ms: int,
        data: Any | None = None,
        error: str | None = None,
    ) -> StreamEvent:
        return self._event(
            "tool.result",
            {
                "tool_id": tool_id,
                "result": {
                    "success": success,
                    "data": data,
                    "error": error,
                    "execution_time_ms": execution_time_ms,
                },
            },
        )

    def end(
        self,
        summary: str,
        tokens_used: int = 0,
        execution_time_ms: int = 0,
        tools_used: list[str] | None = None,
    ) -> StreamEvent:
        return self._event(
            "capability.end",
            {
                "result": {
                    "summary": summary,
                    "tokens_used": tokens_used,
                    "execution_time_ms": execution_time_ms,
                    "tools_used": tools_used or [],
                }
            },
        )

    def error(self, message: str, code: str = "stream_error") -> StreamEvent:
        return self._event(
            "capability.error",
            {"error": {"message": message, "code": code}},
        )
```

- [ ] **Step 4: Run unit tests**

Run from `agent/`:

```bash
uv run pytest tests/unit/test_stream_events.py -v
```

Expected: PASS.

## Task 2: Agent Route Emits NDJSON

**Files:**
- Modify: `agent/services/orchestrator.py`
- Modify: `agent/routers/chat.py`
- Modify: `agent/tests/integration/test_full_dispatch.py`

- [ ] **Step 1: Update integration test expectation**

Change `TestChatEndpoint.test_ask_stream_uses_orchestrator_stream_with_question` to patch `stream_dispatch_events` and assert NDJSON:

```python
async def _capture_stream_events(
    capability,
    family_id,
    task_id,
    user_id=None,
    thread_id=None,
    free_text=None,
    enable_thinking_override=None,
):
    captured["capability"] = capability
    captured["family_id"] = family_id
    captured["free_text"] = free_text
    captured["enable_thinking_override"] = enable_thinking_override
    from services.stream_events import EventStreamBuilder

    builder = EventStreamBuilder(capability, task_id)
    yield builder.phase("connecting").to_ndjson()
    yield builder.token("测试流式回答", is_thinking=False).to_ndjson()
    yield builder.end("测试流式回答").to_ndjson()


with patch(
    "services.orchestrator.Orchestrator.stream_dispatch_events",
    side_effect=_capture_stream_events,
):
    resp = client.post(
        "/chat/ask/stream",
        json={"question": "我的净资产是多少？"},
        headers={"X-Family-Id": _FAMILY_ID, "X-Agent-Token": _TOKEN},
    )

assert resp.status_code == 200
lines = [json.loads(line) for line in resp.text.splitlines()]
assert [line["type"] for line in lines] == [
    "phase.connecting",
    "token.stream",
    "capability.end",
]
assert lines[1]["token"] == "测试流式回答"
```

- [ ] **Step 2: Run test to verify failure**

Run from `agent/`:

```bash
uv run pytest tests/integration/test_full_dispatch.py::TestChatEndpoint::test_ask_stream_uses_orchestrator_stream_with_question -v
```

Expected: FAIL because `stream_dispatch_events` is not implemented and route still wraps prefixes.

- [ ] **Step 3: Add event stream wrapper to orchestrator**

Add this method to `Orchestrator` without removing the existing `stream_dispatch()` yet:

```python
async def stream_dispatch_events(
    self,
    capability: str,
    family_id: str,
    task_id: str,
    user_id: str | None = None,
    thread_id: str | None = None,
    free_text: str | None = None,
    enable_thinking_override: bool | None = None,
) -> AsyncGenerator[str, None]:
    """Stream structured NDJSON events. Keeps policy/context/PII in stream_dispatch."""
    from services.stream_events import EventStreamBuilder

    builder = EventStreamBuilder(capability_id=capability, task_id=task_id)
    started = time.monotonic()
    text_parts: list[str] = []

    yield builder.phase("connecting").to_ndjson()
    if enable_thinking_override:
        yield builder.phase("thinking").to_ndjson()

    try:
        async for chunk in self.stream_dispatch(
            capability=capability,
            family_id=family_id,
            task_id=task_id,
            user_id=user_id,
            thread_id=thread_id,
            free_text=free_text,
            enable_thinking_override=enable_thinking_override,
        ):
            if chunk.startswith("[THINK]"):
                yield builder.token(chunk[7:], is_thinking=True).to_ndjson()
                continue
            if chunk.startswith("[TEXT]"):
                token = chunk[6:]
                text_parts.append(token)
                yield builder.phase("answering").to_ndjson()
                yield builder.token(token, is_thinking=False).to_ndjson()
                continue
            text_parts.append(chunk)
            yield builder.phase("answering").to_ndjson()
            yield builder.token(chunk, is_thinking=False).to_ndjson()

        elapsed_ms = int((time.monotonic() - started) * 1000)
        yield builder.end("".join(text_parts), execution_time_ms=elapsed_ms).to_ndjson()
    except Exception as exc:
        logger.error("[orchestrator] stream_dispatch_events failed: %s", type(exc).__name__)
        yield builder.error("暂时无法完成分析，请稍后重试。").to_ndjson()
```

This wrapper is intentionally transitional. Later Phase 4 should make DeerFlow emit structured events directly and reduce the prefix adapter surface.

- [ ] **Step 4: Update chat route media type and generator**

In `agent/routers/chat.py`, replace the current `generate()` body:

```python
async def generate():
    task_id = str(uuid.uuid4())
    async for event_line in orchestrator.stream_dispatch_events(
        capability="chat",
        family_id=x_family_id,
        task_id=task_id,
        user_id=x_user_id,
        thread_id=x_thread_id,
        free_text=body.question,
        enable_thinking_override=body.deep_think,
    ):
        yield event_line

return StreamingResponse(generate(), media_type="application/x-ndjson; charset=utf-8")
```

- [ ] **Step 5: Run agent tests**

Run from `agent/`:

```bash
uv run pytest tests/unit/test_stream_events.py tests/integration/test_full_dispatch.py -v
uv run ruff check services/stream_events.py services/orchestrator.py routers/chat.py tests/unit/test_stream_events.py tests/integration/test_full_dispatch.py
```

Expected: PASS.

## Task 3: Backend Proxy and Persistence for NDJSON

**Files:**
- Modify: `backend/app/routers/ai_chat.py`
- Modify: `backend/tests/test_ai_chat_sessions.py`

- [ ] **Step 1: Add backend streaming persistence test**

Add a test that stubs the agent response as NDJSON and verifies only non-thinking answer tokens are saved:

```python
async def _fake_aiter_text():
    yield '{"type":"phase.connecting","phase":"connecting"}\n'
    yield '{"type":"token.stream","token":"内部思考","is_thinking":true}\n'
    yield '{"type":"token.stream","token":"最终回答","is_thinking":false}\n'
    yield '{"type":"capability.end","result":{"summary":"最终回答"}}\n'
```

Expected persisted assistant message content: `最终回答`.

- [ ] **Step 2: Run backend test to verify failure**

Run from `backend/`:

```bash
uv run pytest tests/test_ai_chat_sessions.py -v -k stream
```

Expected: FAIL because backend still strips `[TEXT]`.

- [ ] **Step 3: Parse NDJSON in proxy**

In `backend/app/routers/ai_chat.py`, import `json` and replace answer collection logic:

```python
buffer = ""
async for chunk in resp.aiter_text():
    buffer += chunk
    while "\n" in buffer:
        line, buffer = buffer.split("\n", 1)
        if not line.strip():
            continue
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            logger.warning("chat_stream received invalid NDJSON line")
            continue
        if event.get("type") == "token.stream" and event.get("is_thinking") is False:
            answer_chunks.append(str(event.get("token", "")))
        yield (line + "\n").encode("utf-8")
```

On exception, yield a structured error event:

```python
yield (
    '{"type":"capability.error","error":{"message":"抱歉，AI 服务暂时不可用。","code":"backend_proxy_error"}}\n'
).encode("utf-8")
```

Return:

```python
return StreamingResponse(proxy_stream(), media_type="application/x-ndjson; charset=utf-8")
```

- [ ] **Step 4: Run backend tests and lint**

Run from `backend/`:

```bash
uv run pytest tests/test_ai_chat_sessions.py -v -k stream
uv run ruff check app/routers/ai_chat.py tests/test_ai_chat_sessions.py
```

Expected: PASS.

## Task 4: Frontend NDJSON Parser

**Files:**
- Create: `frontend/apps/main/src/types/agent-stream.ts`
- Create: `frontend/apps/main/src/composables/useAgentEventStream.ts`
- Test: `frontend/apps/main/tests/composables/useAgentEventStream.spec.ts`

- [ ] **Step 1: Write parser tests**

```ts
import { describe, expect, it } from 'vitest'
import { createAgentEventParser } from '../../src/composables/useAgentEventStream'

describe('createAgentEventParser', () => {
  it('parses complete and split NDJSON lines', () => {
    const events: unknown[] = []
    const parser = createAgentEventParser((event) => events.push(event))

    parser.push('{"type":"phase.connecting","phase":"connecting"}\n{"type":"token.stream"')
    parser.push(',"token":"净资产","is_thinking":false}\n')
    parser.flush()

    expect(events).toEqual([
      { type: 'phase.connecting', phase: 'connecting' },
      { type: 'token.stream', token: '净资产', is_thinking: false },
    ])
  })
})
```

- [ ] **Step 2: Run test to verify failure**

Run from `frontend/apps/main/`:

```bash
npm run test:run -- tests/composables/useAgentEventStream.spec.ts
```

Expected: FAIL because parser does not exist.

- [ ] **Step 3: Add event types**

```ts
// frontend/apps/main/src/types/agent-stream.ts
export type AgentEventType =
  | 'phase.connecting'
  | 'phase.thinking'
  | 'phase.answering'
  | 'tool.call'
  | 'tool.result'
  | 'token.stream'
  | 'capability.end'
  | 'capability.error'

export interface AgentEvent {
  id?: string
  type: AgentEventType
  timestamp?: number
  capability_id?: string
  task_id?: string
  phase?: 'connecting' | 'thinking' | 'answering'
  metadata?: Record<string, unknown>
  token?: string
  is_thinking?: boolean
  tool?: {
    id: string
    name: string
    display_name: string
    icon: string
    arguments: Record<string, unknown>
  }
  tool_id?: string
  result?: {
    summary?: string
    tokens_used?: number
    execution_time_ms?: number
    tools_used?: string[]
    success?: boolean
    data?: unknown
    error?: string
  }
  error?: {
    message: string
    code: string
  }
}
```

- [ ] **Step 4: Add parser composable**

```ts
// frontend/apps/main/src/composables/useAgentEventStream.ts
import type { AgentEvent } from '@/types/agent-stream'

export function createAgentEventParser(onEvent: (event: AgentEvent) => void) {
  let buffer = ''

  function parseLine(line: string) {
    const trimmed = line.trim()
    if (!trimmed) return
    onEvent(JSON.parse(trimmed) as AgentEvent)
  }

  return {
    push(chunk: string) {
      buffer += chunk
      let newline = buffer.indexOf('\n')
      while (newline >= 0) {
        parseLine(buffer.slice(0, newline))
        buffer = buffer.slice(newline + 1)
        newline = buffer.indexOf('\n')
      }
    },
    flush() {
      if (buffer.trim()) parseLine(buffer)
      buffer = ''
    },
  }
}
```

- [ ] **Step 5: Run parser tests**

Run from `frontend/apps/main/`:

```bash
npm run test:run -- tests/composables/useAgentEventStream.spec.ts
```

Expected: PASS.

## Task 5: Frontend Chat Consumes Events

**Files:**
- Modify: `frontend/apps/main/src/api/ai.ts`
- Modify: `frontend/apps/main/src/pages/AIChatPage.vue`
- Modify: `frontend/apps/main/tests/pages/AIChatPage.spec.ts`

- [ ] **Step 1: Add API helper**

```ts
export function sendChatEventStream(
  question: string,
  deepThink: boolean,
  signal?: AbortSignal,
): Promise<ReadableStreamDefaultReader<Uint8Array>> {
  return fetch('/api/v1/ai/chat/stream', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    credentials: 'include',
    body: JSON.stringify({ question, deep_think: deepThink }),
    signal,
  }).then((res) => {
    if (!res.ok) throw new Error(`${res.status}`)
    if (!res.body) throw new Error('No response body')
    return res.body.getReader()
  })
}
```

- [ ] **Step 2: Replace prefix parsing in `AIChatPage.vue`**

Use `createAgentEventParser` and a local handler:

```ts
function handleAgentEvent(event: AgentEvent) {
  const msg = messages.value[msgIdx]
  if (event.type === 'phase.connecting') msg.phase = 'connecting'
  if (event.type === 'phase.thinking') msg.phase = 'thinking'
  if (event.type === 'phase.answering') msg.phase = 'answering'
  if (event.type === 'token.stream' && event.is_thinking) {
    thinkRaw += event.token ?? ''
    msg.thinkContent = renderMarkdown(thinkRaw)
  }
  if (event.type === 'token.stream' && !event.is_thinking) {
    if (!thinkingDone && deepThink.value) {
      thinkingDone = true
      if (thinkTimer) {
        clearInterval(thinkTimer)
        thinkTimer = null
      }
      msg.thinkDone = true
      msg.thinkOpen = false
      msg.thinkSeconds = Math.round((Date.now() - thinkStart) / 1000)
    }
    textRaw += event.token ?? ''
    msg.content = textRaw
    msg.renderedContent = renderMarkdown(textRaw)
  }
  if (event.type === 'capability.error') {
    msg.phase = 'error'
    msg.content = event.error?.message ?? t('toast.aiChatError')
    msg.renderedContent = renderMarkdown(msg.content)
  }
}
```

Then stream loop:

```ts
const reader = await sendChatEventStream(q, deepThink.value, abortController.signal)
const parser = createAgentEventParser(handleAgentEvent)
while (true) {
  const { done, value } = await reader.read()
  if (done) break
  parser.push(decoder.decode(value, { stream: true }))
  await scrollToBottom()
}
parser.flush()
messages.value[msgIdx].phase = textRaw ? 'done' : 'error'
```

- [ ] **Step 3: Add or update component test**

Mock `sendChatEventStream()` to return chunks:

```ts
[
  '{"type":"phase.connecting","phase":"connecting"}\n',
  '{"type":"phase.thinking","phase":"thinking"}\n',
  '{"type":"token.stream","token":"分析中","is_thinking":true}\n',
  '{"type":"phase.answering","phase":"answering"}\n',
  '{"type":"token.stream","token":"最终回答","is_thinking":false}\n',
  '{"type":"capability.end","result":{"summary":"最终回答"}}\n',
]
```

Assert that the assistant bubble contains `最终回答` and the thinking block contains `分析中`.

- [ ] **Step 4: Run frontend tests**

Run from `frontend/apps/main/`:

```bash
npm run test:run -- tests/composables/useAgentEventStream.spec.ts tests/pages/AIChatPage.spec.ts tests/pages/AIHubPage.spec.ts
npm run typecheck
```

Expected: PASS.

## Task 6: End-to-End Validation

**Files:**
- Modify: `tests/e2e/ai-chat-entry-flow.spec.ts`

- [ ] **Step 1: Update E2E expectations only if needed**

Keep the current request assertion:

```ts
request.url().includes('/api/v1/ai/chat/stream')
```

Add a stable assertion that does not depend on full model completion:

```ts
await expect(page.getByText(/正在连接模型|深度思考中|组织回答中/)).toBeVisible({ timeout: 10_000 })
```

- [ ] **Step 2: Run Docker/browser verification**

Use the established dev Docker flow:

```bash
BASE_URL=http://localhost/api/v1 ./tests/data/seed-data.sh --reset-passwords
cd tests
npx playwright test e2e/ai-chat-entry-flow.spec.ts --project=chromium
```

Expected: PASS with `demouser / DemoPass123`.

- [ ] **Step 3: Capture service logs for protocol evidence**

Run from repo root:

```bash
docker compose -f docker-compose.yml -f docker-compose.dev.yml logs --tail=220 backend
docker compose -f docker-compose.yml -f docker-compose.dev.yml logs --tail=220 agent
```

Expected evidence:

- Backend receives `POST /api/v1/ai/chat/stream`.
- Backend calls agent `POST /chat/ask/stream`.
- Agent returns 200.
- No log entry shows prefix parsing errors or old `[TEXT]` fallback.

## Final Verification

Run the focused gates required by module CLAUDE files:

From `agent/`:

```bash
uv run pytest tests/unit/test_stream_events.py tests/integration/test_full_dispatch.py -v
uv run ruff check services/stream_events.py services/orchestrator.py routers/chat.py tests/unit/test_stream_events.py tests/integration/test_full_dispatch.py
```

From `backend/`:

```bash
uv run pytest tests/test_ai_chat_sessions.py -v -k stream
uv run ruff check app/routers/ai_chat.py tests/test_ai_chat_sessions.py
```

From `frontend/apps/main/`:

```bash
npm run test:run -- tests/composables/useAgentEventStream.spec.ts tests/pages/AIChatPage.spec.ts tests/pages/AIHubPage.spec.ts
npm run typecheck
```

From `tests/`:

```bash
npx playwright test e2e/ai-chat-entry-flow.spec.ts --project=chromium
```

## Out of Scope for Phase 1

- Full Capability Registry implementation and `/ai` Capability Grid.
- ToolCallCard and ToolResultCard visual components.
- Removing Direct LLM fallback entirely.
- Rewriting DeerFlow adapter internals to emit native Harness events.
- Database schema changes for event history.

## Self-Review

- Spec coverage: Phase 1 covers NDJSON event stream, phase feedback, backend proxying, frontend parsing, and a typed event surface for later tool/capability phases.
- Deferred items: Capability Registry, Tool UI, and Harness native events are explicitly deferred to Phases 2-4.
- DeerFlow best practice: this plan adds a single protocol boundary and avoids another independent frontend-only stream grammar; it preserves existing policy, PII redaction, context loading, and audit logging paths.
