# DeerFlow 2.0 Phase 2-3 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Complete the DeerFlow 2.0 progressive alignment by migrating non-chat capabilities to MCP on-demand data access, adding LLM-generated follow-up suggestions to chat, and exposing family-scoped dynamic capabilities.

**Architecture:** Inject the same `numina-family-data` MCP server used by chat into all non-chat capabilities via the orchestrator, eliminating pre-fetched `_build_context()`. Add a fire-and-forget `_generate_suggestions()` post-stream LLM call (same pattern as `_generate_title()`) that includes results in `capability.end`. Expose `list_capabilities_for_family()` via a new query parameter on the existing `/capabilities` endpoint.

**Tech Stack:** Python 3.12+ / FastAPI / DeerFlow 2.0 harness / Vue 3 + TypeScript / Vite / Vant 4

---

## File Structure

| File | Responsibility | Task |
|------|---------------|------|
| `server/apps/agent/services/orchestrator.py` | Inject MCP servers in non-chat dispatch; add `_generate_suggestions()` | 1, 3 |
| `server/apps/agent/services/stream_events.py` | Add `suggestions` field to `capability.end` event | 2 |
| `server/apps/agent/routers/capabilities.py` | Add family-scoped `GET /capabilities?family_id=` | 5 |
| `server/apps/agent/tests/unit/test_mcp_injection.py` | Test MCP injection for non-chat capabilities | 1 |
| `server/apps/agent/tests/unit/test_suggestions.py` | Test suggestions generation and event structure | 3 |
| `frontend/apps/main/src/types/agent-stream.ts` | Add `suggestions` to `AgentEvent` type | 4 |
| `frontend/apps/main/src/composables/useAITask.ts` | Handle `suggestions` from `capability.end` | 4 |
| `frontend/apps/main/src/pages/AIChatPage.vue` | Wire LLM-generated suggestions into chat chips | 4 |

---

## Task 1: Inject MCP server into non-chat capability dispatch

**Files:**
- Modify: `server/apps/agent/services/orchestrator.py:529-531`
- Create: `server/apps/agent/tests/unit/test_mcp_injection.py`

- [ ] **Step 1: Write the failing test**

Create `server/apps/agent/tests/unit/test_mcp_injection.py`:

```python
"""Test that non-chat capabilities receive MCP server injection."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from apps.agent.services.orchestrator import Orchestrator


@pytest.fixture
def orchestrator():
    o = Orchestrator.__new__(Orchestrator)
    o._chat_adapter = MagicMock()
    return o


def test_mcp_server_config_for_non_chat():
    """Non-chat capabilities should receive numina-family-data MCP server config."""
    o = Orchestrator.__new__(Orchestrator)
    config = o._build_mcp_servers("family-123", user_id="user-456")
    assert len(config) == 1
    assert config[0]["name"] == "numina-family-data"
    assert "family-123" in config[0]["url"]
    assert config[0]["transport"] == "sse"
    assert config[0]["headers"]["X-Family-Id"] == "family-123"
    assert config[0]["headers"]["X-Caller-User-Id"] == "user-456"


def test_mcp_server_config_without_user_id():
    """MCP config omits X-Caller-User-Id when user_id is None."""
    o = Orchestrator.__new__(Orchestrator)
    config = o._build_mcp_servers("family-123", user_id=None)
    assert "X-Caller-User-Id" not in config[0]["headers"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /Volumes/LexarSSDNQ790/geek_space/github/numina/server && uv run pytest apps/agent/tests/unit/test_mcp_injection.py -v 2>&1 | tail -10`
Expected: FAIL — `AttributeError: 'Orchestrator' has no method '_build_mcp_servers'`

- [ ] **Step 3: Add `_build_mcp_servers()` helper to orchestrator**

In `server/apps/agent/services/orchestrator.py`, add the method after `_build_context()` (around line 873):

```python
    def _build_mcp_servers(
        self,
        family_id: str,
        user_id: str | None = None,
    ) -> list[dict]:
        """Build MCP server config for DeerFlow adapter injection.

        Same server as ChatAdapter uses — numina-family-data via SSE.
        """
        headers: dict[str, str] = {
            "X-Agent-Token": settings.AGENT_INTERNAL_TOKEN,
            "X-Family-Id": family_id,
        }
        if user_id:
            headers["X-Caller-User-Id"] = user_id
        return [
            {
                "name": "numina-family-data",
                "url": f"{settings.BACKEND_BASE_URL}/api/v1/internal/mcp/{family_id}/sse",
                "transport": "sse",
                "headers": headers,
            }
        ]
```

- [ ] **Step 4: Inject MCP servers in the non-chat dispatch branch**

In `orchestrator.py`, modify the adapter creation at line ~531. Change from:

```python
adapter = _create_family_adapter(family_id, selected_provider, timeout_seconds=max(selected_provider.get("timeout_seconds", 60), 240), subagent_enabled=skill_config.subagent_enabled, plan_mode=skill_config.plan_mode)
```

To:

```python
mcp_servers = self._build_mcp_servers(family_id, user_id=user_id)
adapter = _create_family_adapter(family_id, selected_provider, timeout_seconds=max(selected_provider.get("timeout_seconds", 60), 240), subagent_enabled=skill_config.subagent_enabled, plan_mode=skill_config.plan_mode, mcp_servers=mcp_servers)
```

- [ ] **Step 5: Keep `_build_context()` as fallback — pass minimal context when MCP is available**

Change line ~492 from:

```python
context = await self._build_context(client, family_id, free_text=free_text)
redacted_context = pii_redactor.redact(context)
```

To:

```python
context = FamilyContext(family_id=family_id, free_text=free_text)
redacted_context = pii_redactor.redact(context)
```

This passes only `family_id` and `free_text` — the DeerFlow agent will use MCP tools to fetch data on demand. The `_build_context()` method is retained for potential fallback use.

- [ ] **Step 6: Run tests**

Run: `cd /Volumes/LexarSSDNQ790/geek_space/github/numina/server && uv run pytest apps/agent/tests/unit/test_mcp_injection.py apps/agent/tests/ -v -x 2>&1 | tail -20`
Expected: All tests pass

- [ ] **Step 7: Commit**

```bash
git add server/apps/agent/services/orchestrator.py server/apps/agent/tests/unit/test_mcp_injection.py
git commit -m "feat(agent): inject MCP server into non-chat capabilities for on-demand data access"
```

---

## Task 2: Add `suggestions` field to `capability.end` event

**Files:**
- Modify: `server/apps/agent/services/stream_events.py:108-125`

- [ ] **Step 1: Write the failing test**

Create `server/apps/agent/tests/unit/test_stream_events_suggestions.py`:

```python
"""Test that capability.end can include suggestions."""

from apps.agent.services.stream_events import EventStreamBuilder


def test_end_event_includes_suggestions():
    """capability.end should include suggestions when provided."""
    builder = EventStreamBuilder(capability_id="chat", task_id="t1")
    event = builder.end("summary text", suggestions=["查看详情", "分析趋势"])
    data = event.to_dict()
    assert data["result"]["suggestions"] == ["查看详情", "分析趋势"]


def test_end_event_omits_suggestions_when_none():
    """capability.end should omit suggestions field when not provided."""
    builder = EventStreamBuilder(capability_id="chat", task_id="t1")
    event = builder.end("summary text")
    data = event.to_dict()
    assert "suggestions" not in data["result"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /Volumes/LexarSSDNQ790/geek_space/github/numina/server && uv run pytest apps/agent/tests/unit/test_stream_events_suggestions.py -v 2>&1 | tail -10`
Expected: FAIL — `end()` does not accept `suggestions` kwarg

- [ ] **Step 3: Add `suggestions` parameter to `EventStreamBuilder.end()`**

In `server/apps/agent/services/stream_events.py`, modify the `end()` method (lines 108-125):

```python
    def end(
        self,
        summary: str,
        tokens_used: int = 0,
        execution_time_ms: int = 0,
        tools_used: list[str] | None = None,
        suggestions: list[str] | None = None,
    ) -> StreamEvent:
        result: dict = {
            "summary": summary,
            "tokens_used": tokens_used,
            "execution_time_ms": execution_time_ms,
            "tools_used": tools_used or [],
        }
        if suggestions:
            result["suggestions"] = suggestions
        return self._event("capability.end", {"result": result})
```

- [ ] **Step 4: Run tests**

Run: `cd /Volumes/LexarSSDNQ790/geek_space/github/numina/server && uv run pytest apps/agent/tests/unit/test_stream_events_suggestions.py apps/agent/tests/ -v -x 2>&1 | tail -20`
Expected: All tests pass

- [ ] **Step 5: Commit**

```bash
git add server/apps/agent/services/stream_events.py server/apps/agent/tests/unit/test_stream_events_suggestions.py
git commit -m "feat(agent): add suggestions field to capability.end event"
```

---

## Task 3: Add fire-and-forget `_generate_suggestions()` for chat

**Files:**
- Modify: `server/apps/agent/services/orchestrator.py`
- Create: `server/apps/agent/tests/unit/test_suggestions.py`

- [ ] **Step 1: Write the failing test**

Create `server/apps/agent/tests/unit/test_suggestions.py`:

```python
"""Test LLM-based suggestion generation."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from apps.agent.services.orchestrator import Orchestrator


@pytest.fixture
def orchestrator():
    o = Orchestrator.__new__(Orchestrator)
    return o


@pytest.mark.asyncio
async def test_generate_suggestions_returns_list():
    """_generate_suggestions should return a list of suggestion strings."""
    o = Orchestrator.__new__(Orchestrator)
    ai_config = {
        "ai_provider": "openai",
        "api_key": "test-key",
        "ai_model_id": "gpt-4",
        "ai_base_url": None,
    }
    with patch("apps.agent.core.llm.LLMClient") as mock_llm_cls:
        mock_llm = AsyncMock()
        mock_llm.complete.return_value = "查看资产配置\n分析净资产趋势\n对比上月变化"
        mock_llm_cls.return_value = mock_llm
        result = await o._generate_suggestions(
            answer_text="您的净资产为100万元，房产占比60%。",
            ai_config=ai_config,
        )
    assert isinstance(result, list)
    assert len(result) == 3
    assert "查看资产配置" in result


@pytest.mark.asyncio
async def test_generate_suggestions_handles_llm_failure():
    """_generate_suggestions should return empty list on LLM failure."""
    o = Orchestrator.__new__(Orchestrator)
    ai_config = {
        "ai_provider": "openai",
        "api_key": "test-key",
        "ai_model_id": "gpt-4",
        "ai_base_url": None,
    }
    with patch("apps.agent.core.llm.LLMClient") as mock_llm_cls:
        mock_llm = AsyncMock()
        mock_llm.complete.side_effect = Exception("timeout")
        mock_llm_cls.return_value = mock_llm
        result = await o._generate_suggestions(
            answer_text="test answer",
            ai_config=ai_config,
        )
    assert result == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /Volumes/LexarSSDNQ790/geek_space/github/numina/server && uv run pytest apps/agent/tests/unit/test_suggestions.py -v 2>&1 | tail -10`
Expected: FAIL — `Orchestrator has no method '_generate_suggestions'`

- [ ] **Step 3: Add `_generate_suggestions()` to orchestrator**

In `server/apps/agent/services/orchestrator.py`, add after `_generate_title()` (around line 823):

```python
    async def _generate_suggestions(
        self,
        *,
        answer_text: str,
        ai_config: dict,
        max_suggestions: int = 3,
    ) -> list[str]:
        """Generate follow-up suggestion chips via LLM.

        Returns a list of short follow-up questions the user might ask next.
        Returns empty list on any failure (fire-and-forget friendly).
        """
        try:
            from apps.agent.core.llm import LLMClient
            provider = ai_config.get("ai_provider", "")
            api_key = ai_config.get("api_key", "")
            model_id = ai_config.get("ai_model_id", "")
            base_url = ai_config.get("ai_base_url", "") or None
            if not (provider and api_key and model_id):
                return []
            llm = LLMClient(provider=provider, api_key=api_key, model_id=model_id, base_url=base_url)
            prompt = (
                f"基于以下AI回答，生成{max_suggestions}个用户可能想继续问的简短后续问题。"
                f"每行一个问题，不超过15个字，不要编号：\n\n{answer_text[:500]}"
            )
            raw = await llm.complete(prompt, max_tokens=100)
            lines = [line.strip() for line in raw.strip().splitlines() if line.strip()]
            return lines[:max_suggestions]
        except Exception as e:
            logger.warning("[orchestrator] suggestions generation failed: %s", e)
            return []
```

- [ ] **Step 4: Wire suggestions into the chat branch's `capability.end` event**

In the chat branch of `_stream_dispatch_event_lines()` (around lines 480-490), find where `builder.end()` is called for chat. Change:

```python
yield builder.end("".join(answer_parts), execution_time_ms=elapsed_ms).to_ndjson()
```

To:

```python
suggestions = await self._generate_suggestions(
    answer_text="".join(answer_parts),
    ai_config=selected_provider,
)
yield builder.end(
    "".join(answer_parts),
    execution_time_ms=elapsed_ms,
    suggestions=suggestions if suggestions else None,
).to_ndjson()
```

Note: This is a simple async call at the end of the stream, not fire-and-forget. Since it's a short LLM call (~100 tokens), the latency is acceptable (~0.5-1s) and avoids the complexity of a separate event channel. If latency proves problematic, it can be moved to fire-and-forget in a follow-up.

- [ ] **Step 5: Run tests**

Run: `cd /Volumes/LexarSSDNQ790/geek_space/github/numina/server && uv run pytest apps/agent/tests/unit/test_suggestions.py apps/agent/tests/ -v -x 2>&1 | tail -20`
Expected: All tests pass

- [ ] **Step 6: Commit**

```bash
git add server/apps/agent/services/orchestrator.py server/apps/agent/tests/unit/test_suggestions.py
git commit -m "feat(agent): add LLM-generated follow-up suggestions to chat capability.end"
```

---

## Task 4: Frontend — receive and display LLM-generated suggestions

**Files:**
- Modify: `frontend/apps/main/src/types/agent-stream.ts`
- Modify: `frontend/apps/main/src/composables/useAITask.ts:222-224`
- Modify: `frontend/apps/main/src/pages/AIChatPage.vue`

- [ ] **Step 1: Add `suggestions` to `AgentEvent` type**

In `frontend/apps/main/src/types/agent-stream.ts`, find the `AgentEvent` interface and add:

```typescript
export interface AgentEvent {
  id?: string
  type: AgentEventType
  timestamp?: number
  capability_id?: string
  task_id?: string
  // token.stream fields
  token?: string
  is_thinking?: boolean
  // tool.call fields
  tool?: { id: string; name: string; display_name?: string; icon?: string; tool_type?: string }
  // tool.result fields
  tool_id?: string
  result?: { success?: boolean; summary?: string; suggestions?: string[] }
  // tool.progress fields
  progress_message?: string
  // capability.error fields
  code?: string
  error?: { code?: string; message?: string }
  message?: string
}
```

If `result` already has a type, just add `suggestions?: string[]` to it.

- [ ] **Step 2: Add `suggestions` ref and handle in `useAITask.ts`**

In `frontend/apps/main/src/composables/useAITask.ts`, add a new ref after `currentToolLabel` (line ~64):

```typescript
const suggestions = ref<string[]>([])
```

Then update the `capability.end` handler (lines 222-224):

```typescript
case 'capability.end':
  if (event.result?.suggestions?.length) {
    suggestions.value = event.result.suggestions
  }
  break
```

Reset `suggestions.value = []` in `startStream()` (where other state is reset, around line 365).

Add `suggestions` to the return object (line ~556):

```typescript
return {
  status,
  phase,
  thinkContent,
  thinkDone,
  thinkSeconds,
  answerContent,
  elapsedSeconds,
  taskId,
  sessionId,
  isConsoleOpen,
  queuePosition,
  errorCode,
  toolSteps,
  currentToolLabel,
  suggestions,
  startStream,
  cancelTask,
}
```

- [ ] **Step 3: Wire LLM suggestions into AIChatPage.vue `suggestionChipsFor()`**

In `frontend/apps/main/src/pages/AIChatPage.vue`, the `suggestionChipsFor()` function (line ~1500) currently uses a static template pool. Modify it to prefer LLM-generated suggestions when available.

The chat page does not use `useAITask` (it has its own stream management via `useChatStream` or direct message handling). Instead, the LLM suggestions arrive via the NDJSON stream that the chat page already consumes. Find where `capability.end` is handled in the chat stream consumer and store `result.suggestions` on the last assistant message.

Look for where messages are managed and add a `suggestions?: string[]` field to the `Message` type if not already present. When `capability.end` arrives with suggestions, assign them to the last assistant message:

```typescript
// In the stream event handler for capability.end:
if (event.result?.suggestions?.length) {
  const lastMsg = messages.value[messages.value.length - 1]
  if (lastMsg?.role === 'assistant') {
    lastMsg.suggestions = event.result.suggestions
  }
}
```

Then update `suggestionChipsFor()` to prefer LLM suggestions:

```typescript
function suggestionChipsFor(msg: Message): string[] {
  // Prefer LLM-generated suggestions if available
  if (msg.suggestions?.length) {
    return msg.suggestions.slice(0, 3)
  }
  // Fallback to template-based suggestions
  const pool = [
    t('aiChat.chipFollowupReason'),
    t('aiChat.chipFollowupAction'),
    t('aiChat.chipFollowupExample'),
    t('aiChat.chipFollowupCompare'),
    t('aiChat.chipFollowupTrend'),
  ]
  const seed = (msg.content || '').length % pool.length
  return [...pool.slice(seed), ...pool.slice(0, seed)].slice(0, 3)
}
```

- [ ] **Step 4: Run typecheck**

Run: `cd /Volumes/LexarSSDNQ790/geek_space/github/numina/frontend/apps/main && pnpm typecheck 2>&1 | tail -10`
Expected: No errors

- [ ] **Step 5: Commit**

```bash
git add frontend/apps/main/src/types/agent-stream.ts frontend/apps/main/src/composables/useAITask.ts frontend/apps/main/src/pages/AIChatPage.vue
git commit -m "feat(frontend): display LLM-generated suggestions from capability.end event"
```

---

## Task 5: Expose family-scoped capabilities endpoint

**Files:**
- Modify: `server/apps/agent/routers/capabilities.py`
- Create: `server/apps/agent/tests/unit/test_capabilities_family.py`

- [ ] **Step 1: Write the failing test**

Create `server/apps/agent/tests/unit/test_capabilities_family.py`:

```python
"""Test family-scoped capabilities endpoint."""

from unittest.mock import patch, MagicMock

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client():
    from apps.agent.app.main import app
    return TestClient(app)


def test_capabilities_with_family_id(client):
    """GET /capabilities?family_id=xxx should call list_capabilities_for_family."""
    with patch("apps.agent.routers.capabilities.capability_registry") as mock_reg:
        mock_reg.list_capabilities_for_family = MagicMock(return_value=[])
        resp = client.get(
            "/capabilities",
            params={"family_id": "fam-123"},
            headers={"X-Agent-Token": "test-token"},
        )
    assert resp.status_code == 200
    mock_reg.list_capabilities_for_family.assert_called_once_with("fam-123")


def test_capabilities_without_family_id(client):
    """GET /capabilities (no family_id) should call list_capabilities as before."""
    with patch("apps.agent.routers.capabilities.capability_registry") as mock_reg:
        mock_reg.list_capabilities = MagicMock(return_value=[])
        resp = client.get(
            "/capabilities",
            headers={"X-Agent-Token": "test-token"},
        )
    assert resp.status_code == 200
    mock_reg.list_capabilities.assert_called_once()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /Volumes/LexarSSDNQ790/geek_space/github/numina/server && uv run pytest apps/agent/tests/unit/test_capabilities_family.py -v 2>&1 | tail -10`
Expected: FAIL — endpoint doesn't accept `family_id` query parameter (or `list_capabilities_for_family` not called)

- [ ] **Step 3: Update the capabilities router**

In `server/apps/agent/routers/capabilities.py`, modify the endpoint to accept optional `family_id`:

```python
from typing import Annotated

from fastapi import APIRouter, Header, HTTPException, Query

from apps.agent.app.config import settings
from apps.agent.schemas.capability import CapabilityDefinition
from apps.agent.services.capability_registry import capability_registry

router = APIRouter(prefix="/capabilities", tags=["capabilities"])


@router.get("", response_model=list[CapabilityDefinition])
async def list_capabilities(
    x_agent_token: str = Header(..., alias="X-Agent-Token"),
    family_id: str | None = Query(None),
) -> list[CapabilityDefinition]:
    if x_agent_token != settings.AGENT_INTERNAL_TOKEN:
        raise HTTPException(status_code=401, detail="invalid token")
    if family_id:
        return await capability_registry.list_capabilities_for_family(family_id)
    return capability_registry.list_capabilities()
```

Note: `list_capabilities_for_family` is async (it calls backend HTTP). Make the endpoint `async def` if not already.

- [ ] **Step 4: Run tests**

Run: `cd /Volumes/LexarSSDNQ790/geek_space/github/numina/server && uv run pytest apps/agent/tests/unit/test_capabilities_family.py apps/agent/tests/ -v -x 2>&1 | tail -10`
Expected: All tests pass

- [ ] **Step 5: Commit**

```bash
git add server/apps/agent/routers/capabilities.py server/apps/agent/tests/unit/test_capabilities_family.py
git commit -m "feat(agent): add family_id query param to capabilities endpoint for per-family filtering"
```

---

## Self-Review

**Spec coverage check:**

| Spec Unit | Task |
|-----------|------|
| U2.2 (MCP for all capabilities) | Task 1 — injects `numina-family-data` MCP server into non-chat dispatch |
| U3.2 (Suggestions API) | Tasks 2, 3, 4 — backend generation + event transport + frontend display |
| U3.3 (Dynamic capabilities) | Task 5 — family-scoped endpoint |

**Placeholder scan:** No TBD, TODO, or "implement later" found.

**Type consistency:** `suggestions: list[str] | None` used consistently across `EventStreamBuilder.end()`, `_generate_suggestions()` return type, `AgentEvent.result.suggestions`, and `useAITask.suggestions` ref.

**Notes on scope decisions:**

- **U2.2 keeps `_build_context()` defined** — it's retained as a documented fallback method. If MCP on-demand fetch degrades quality for a capability, the orchestrator can be toggled back to pre-fetch per-capability.
- **U3.2 uses inline async (not fire-and-forget)** — since suggestions need to be in the `capability.end` event, they must complete before the event is emitted. The LLM call is ~100 tokens so latency is <1s. If this proves too slow, a follow-up can split into a separate `suggestions.ready` event.
- **U3.3 does NOT change the frontend** — the AIHubPage currently hardcodes capability cards. Making it dynamic requires a frontend UI refactor that's out of scope for this DeerFlow alignment plan. The backend endpoint is ready for when the frontend is updated.
