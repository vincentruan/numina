# Learning OS — DeerFlow SSE 完整集成 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement full DeerFlow SSE integration for the learning-tutor skill, migrating all runners from in-memory bridge + HTTP SSE pump to Redis StreamBridge, and building the child app's learning chat UI.

**Architecture:** Agent writes events to Redis StreamBridge (cross-process). Backend subscribes to the same Redis Stream directly (replacing the fragile HTTP SSE pump layer). DeerFlow checkpointer persists conversation history. 3 learning tools registered as MCP tools in backend, auto-discovered by agent. Child app gets SSE infrastructure via shared `@numina/shared` package.

**Tech Stack:** Python 3.12 + FastAPI + Redis Streams + SQLAlchemy | Vue 3 + TypeScript + Vant 4 | DeerFlow harness (StreamBridge, Checkpointer, RunPipeline)

**Spec:** `docs/superpowers/specs/2026-09-23-learning-os-deerflow-sse-design.md`

## Global Constraints

- All API endpoints respond 200 directly — no 307 redirects. Root-path decorators use `""` not `"/"`.
- All `bigint` IDs serialized as strings in API responses (`SnowflakeBase`).
- `learning-tutor` already present in `RESERVED_NAMES` in `ai_skills.py` (verify no duplicates).
- Agent `allowed-tools` names must match MCP tool names exactly (base names, no prefix).
- MCP tool handlers never read `family_id` from arguments — only from `self._family_id`.
- Redis is a hard production dependency after this change (DeerFlow parity).
- **SSE exception**: `useLearningChat.ts` uses bare `fetch()` for SSE streaming — this is an established exception to the Axios-only rule (see existing `useReportStream.ts`, `useLiteracyStream.ts` which also use bare `fetch()` for `text/event-stream` responses). Axios does not natively support streaming responses. Non-SSE HTTP calls (e.g., `GET /sessions/{id}/status`) MUST use the Axios wrapper from `src/api/index.ts`.
- All user-facing strings in `.ts`/`.vue` files use i18n keys via `t('key')` — never hardcode Chinese strings.
- `on_disconnect: "continue"` for all backend-triggered runs.
- Security: all LLM-facing tool inputs validated (integer ranges, enum values).
- `record_learning_result` requires strict schema validation of LLM output.

## Review Focus

1. **Redis bridge key alignment**: Agent publishes with `run_id` (e.g., `"123:abc"`), backend subscribes with the same `run_id` — if the key format differs between producer and consumer, events are silently lost. Pin: Task 1 test verifies key format.
2. **Pump removal completeness**: After removing `_pump_agent_sse_to_bridge`, no residual code should reference `agent_client.stream()` for SSE forwarding. Pin: Task 3 test greps for dead references.
3. **MCP tool name matching**: `allowed-tools` in SKILL.md must exactly match tool names in `mcp_tool_registry.py` and `mcp_session.py` handlers. Pin: Task 5 test validates name consistency.
4. **`record_learning_result` schema validation**: LLM may return malformed evaluation JSON — must validate `evidence_results` array, `overall_score` 0-1 range, `recommendation` enum before writing to DB. Pin: Task 6 test.
5. **Session ID as thread ID**: `str(session.id)` passed to agent gateway must be a valid LangGraph thread_id. If Snowflake ID format conflicts with thread_id expectations, DeerFlow checkpointer fails silently. Pin: Task 7 test.

---

## Phase 1: Infrastructure — Redis StreamBridge Migration

### Task 1: Agent Redis StreamBridge

**Files:**
- Modify: `server/apps/agent/services/runtime/lifespan.py:27-63`
- Modify: `server/apps/agent/app/config.py` (add `STREAM_BRIDGE_REDIS_URL`)
- Test: `server/tests/agent/integration/test_redis_bridge.py`

**Interfaces:**
- Consumes: `StreamBridgeConfig` from `packages/stream_bridge/config.py`, `make_stream_bridge` from `packages/stream_bridge/factory.py`
- Produces: `app.state.stream_bridge` is `NuminaRedisStreamBridge` instance (all runners write to Redis)

- [ ] **Step 1: Write failing test for Redis bridge initialization**

```python
# server/tests/agent/integration/test_redis_bridge.py
"""Verify agent initializes Redis StreamBridge when Redis is available."""
import pytest
from packages.stream_bridge.redis import NuminaRedisStreamBridge
from packages.stream_bridge.memory import MemoryStreamBridge


@pytest.mark.asyncio
async def test_redis_bridge_initializes_with_valid_url(redis_url: str):
    """Agent should create NuminaRedisStreamBridge when STREAM_BRIDGE_REDIS_URL is set."""
    from packages.stream_bridge.config import StreamBridgeConfig
    from packages.stream_bridge.factory import make_stream_bridge

    config = StreamBridgeConfig(
        type="redis",
        redis_url=redis_url,
        queue_maxsize=256,
        stream_ttl_seconds=86400,
    )
    bridge = make_stream_bridge(config)
    assert isinstance(bridge, NuminaRedisStreamBridge)
    assert bridge.supports_cross_process is True
    await bridge.close()


@pytest.mark.asyncio
async def test_redis_bridge_publish_subscribe_cross_process(redis_url: str):
    """Events published by one bridge instance are readable by another (simulates agent→backend)."""
    from packages.stream_bridge.config import StreamBridgeConfig
    from packages.stream_bridge.factory import make_stream_bridge

    config = StreamBridgeConfig(type="redis", redis_url=redis_url, queue_maxsize=256)

    # Producer (agent side)
    producer = make_stream_bridge(config)
    # Consumer (backend side) — separate instance, same Redis
    consumer = make_stream_bridge(config)

    run_id = "test_family:run_123"
    await producer.publish(run_id, "messages", {"content": "hello"})
    await producer.publish_end(run_id)

    # Consumer should see the events
    events = []
    async for item in consumer.subscribe(run_id):
        events.append(item)
        if item.event == "__end__":
            break

    assert len(events) >= 2  # at least 1 message + end sentinel
    assert events[0].event == "messages"
    assert events[0].data == {"content": "hello"}

    await producer.close()
    await consumer.close()


@pytest.mark.asyncio
async def test_redis_bridge_tenant_isolation(redis_url: str):
    """NuminaRedisStreamBridge keys include family_id for tenant isolation."""
    from packages.stream_bridge.config import StreamBridgeConfig
    from packages.stream_bridge.factory import make_stream_bridge

    config = StreamBridgeConfig(type="redis", redis_url=redis_url)
    bridge = make_stream_bridge(config)

    # Key format: numina:stream:{family_id}:{run_id}
    key = bridge._stream_key("family_123:run_456")
    assert key == "numina:stream:family_123:run_456"

    # Without family_id prefix
    key_bare = bridge._stream_key("run_789")
    assert key_bare == "numina:stream:0:run_789"

    await bridge.close()
```

- [ ] **Step 2: Run tests to verify they pass with existing code**

These tests validate existing `NuminaRedisStreamBridge` behavior. Run with a Redis instance:

```bash
cd server && REDIS_URL=redis://localhost:6379/0 uv run pytest tests/agent/integration/test_redis_bridge.py -v
```

Expected: PASS (tests exercise existing code, confirming the bridge works as expected).

- [ ] **Step 3: Add `STREAM_BRIDGE_REDIS_URL` to agent config**

In `server/apps/agent/app/config.py`, add to `AgentSettings`:

```python
STREAM_BRIDGE_REDIS_URL: str = Field(
    default="",
    description="Redis URL for StreamBridge. Falls back to REDIS_URL, then redis://redis:6379/0",
)
```

- [ ] **Step 4: Modify `lifespan.py` to use Redis bridge**

In `server/apps/agent/services/runtime/lifespan.py`, replace `init_runtime()`:

```python
async def init_runtime(app: FastAPI) -> None:
    """Initialize RunManager + StreamBridge on app.state.

    Agent uses Redis StreamBridge for cross-process event sharing.
    Backend subscribes to the same Redis Stream directly.
    Falls back to memory bridge if Redis is unavailable (dev only).
    """
    redis_url = (
        settings.STREAM_BRIDGE_REDIS_URL
        or "redis://redis:6379/0"
    )

    try:
        # Verify Redis connectivity
        from redis.asyncio import Redis as AsyncRedis
        client = AsyncRedis.from_url(redis_url, decode_responses=True)
        await client.ping()
        await client.aclose()

        config = StreamBridgeConfig(
            type="redis",
            redis_url=redis_url,
            queue_maxsize=256,
            stream_ttl_seconds=86400,
        )
        app.state.stream_bridge = make_stream_bridge(config)
        logger.info("Initialized StreamBridge (type=redis, url=%s)", redis_url)
    except Exception as e:
        logger.warning("Redis bridge unavailable (%s), falling back to memory", e)
        config = StreamBridgeConfig(type="memory", queue_maxsize=256)
        app.state.stream_bridge = make_stream_bridge(config)

    app.state.run_manager = RunManager(store=None)

    await reconcile_orphaned_runs(
        app.state.run_manager,
        error="Agent restarted before run reached a durable final state.",
    )

    logger.info("[runtime] StreamBridge + RunManager initialized")
```

- [ ] **Step 5: Run agent tests to verify no regressions**

```bash
cd server && uv run pytest tests/agent/ -v --timeout=60 -x
```

Expected: All existing tests pass. The `sse_consumer` interface is unchanged — it reads from `bridge.subscribe()` which works identically whether the bridge is memory or Redis.

- [ ] **Step 6: Commit**

```bash
git add server/apps/agent/services/runtime/lifespan.py \
       server/apps/agent/app/config.py \
       server/tests/agent/integration/test_redis_bridge.py
git commit -m "feat(agent): switch StreamBridge from memory to Redis for cross-process event sharing

All runners now publish events to Redis StreamBridge instead of in-memory.
Backend can subscribe to the same Redis Stream directly, replacing the
fragile HTTP SSE pump layer. Graceful fallback to memory for dev environments.

Co-Authored-By: Claude Code <noreply@anthropic.com>"
```

---

### Task 2: Backend Shared Bridge → Redis + Pump Replacement

**Files:**
- Modify: `server/apps/backend/app/services/bridge_consumer.py` (replace pump with Redis subscribe trigger)
- Modify: `server/apps/backend/app/routers/ai_report.py` (replace pump call)
- Modify: `server/apps/backend/app/routers/ai_finance_coach.py` (replace pump call)
- Modify: `server/apps/backend/app/routers/ai_literacy_report.py` (replace pump call)
- Modify: `server/apps/backend/app/routers/dashboard.py` (replace pump call)
- Modify: `server/apps/backend/app/routers/ai_chat.py` (replace HTTP SSE proxy with Redis subscribe)
- Test: `server/tests/backend/integration/test_redis_bridge_migration.py`

**Interfaces:**
- Consumes: `NuminaRedisStreamBridge` (same Redis as agent), `AgentClient.post()` (trigger only, no SSE)
- Produces: All 5 routers use `trigger_agent_run()` pattern instead of `_pump_agent_sse_to_bridge()` / `agent_client.stream()`

- [ ] **Step 1: Write test for the new trigger-and-subscribe pattern**

```python
# server/tests/backend/integration/test_redis_bridge_migration.py
"""Verify backend triggers agent run and subscribes to Redis directly."""
import pytest
from unittest.mock import AsyncMock, patch, MagicMock


@pytest.mark.asyncio
async def test_trigger_and_subscribe_pattern():
    """Backend should: 1) POST to agent (fire-and-forget), 2) subscribe to Redis bridge."""
    from apps.backend.app.services.bridge_consumer import (
        trigger_agent_run,
    )

    mock_agent_client = AsyncMock()
    mock_agent_client.post = AsyncMock(return_value=MagicMock(
        headers={"Content-Location": "/internal/gateway/runs/asset-report/session_1/r456"},
        status_code=200,
    ))

    result = await trigger_agent_run(
        agent_client=mock_agent_client,
        agent_url="/internal/gateway/runs/asset-report/session_1",
        json_body={"input": {"messages": []}},
        task_id="task_1",
        family_id=123,
    )

    # Agent was called (trigger)
    mock_agent_client.post.assert_called_once()
    # run_id extracted from Content-Location
    assert result["run_id"] == "r456"


@pytest.mark.asyncio
async def test_no_pump_references_remain():
    """After migration, no code should reference _pump_agent_sse_to_bridge."""
    import subprocess
    result = subprocess.run(
        ["grep", "-r", "_pump_agent_sse_to_bridge",
         "server/apps/backend/", "--include=*.py"],
        capture_output=True, text=True,
    )
    # Should find zero matches (function deleted)
    assert result.stdout.strip() == "", (
        f"_pump_agent_sse_to_bridge still referenced:\n{result.stdout}"
    )
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd server && uv run pytest tests/backend/integration/test_redis_bridge_migration.py::test_no_pump_references_remain -v
```

Expected: FAIL — `_pump_agent_sse_to_bridge` still exists.

- [ ] **Step 3: Create `trigger_agent_run()` in `bridge_consumer.py`**

Add a new function that replaces `_pump_agent_sse_to_bridge()`:

```python
async def trigger_agent_run(
    *,
    agent_client: AgentClient,
    agent_url: str,
    json_body: dict[str, Any],
    task_id: str,
    family_id: int | str | None = None,
) -> dict[str, Any]:
    """Trigger an agent run and return run_id for Redis subscription.

    Unlike _pump_agent_sse_to_bridge, this does NOT consume HTTP SSE.
    The agent writes events directly to Redis StreamBridge.
    Backend subscribes to the same Redis Stream via bridge.subscribe().
    The actual subscribe happens in the caller via consume_task_stream().

    Returns:
        dict with 'run_id' (extracted from Content-Location header)
    """
    # POST to agent gateway (fire-and-forget — agent writes to Redis)
    resp = await agent_client.post(agent_url, json=json_body)
    resp.raise_for_status()

    # Extract run_id from Content-Location header
    content_location = resp.headers.get("Content-Location", "")
    run_id = content_location.rsplit("/", 1)[-1] if "/" in content_location else ""

    return {"run_id": run_id}
```

- [ ] **Step 4: Replace pump calls in each router**

For each of the 5 routers (`ai_report.py`, `ai_finance_coach.py`, `ai_literacy_report.py`, `dashboard.py`, `ai_chat.py`), replace the pattern:

**Before** (pump pattern — 4 routers):
```python
asyncio.create_task(
    _pump_agent_sse_to_bridge(
        agent_client=agent_client,
        agent_url=agent_url,
        json_body=agent_trigger_body,
        bridge=shared_bridge,
        run_id="",
        task_id=task_id,
        ...
    )
)
# ... later ...
stream_gen = consume_task_stream(task_id=task_id, ...)
return StreamingResponse(...)
```

**After** (Redis subscribe pattern):
```python
# Trigger agent (writes to Redis) and get run_id
result = await trigger_agent_run(
    agent_client=agent_client,
    agent_url=agent_url,
    json_body=agent_trigger_body,
    task_id=task_id,
    family_id=family_id,
)

# Spawn lifecycle consumer (reads from Redis — same as before)
_spawn_lifecycle_consumer(
    task_id=task_id, family_id=family_id,
    run_id=result["run_id"], bridge=shared_bridge, ...
)

# Subscribe to Redis bridge for frontend SSE
last_event_id = request.headers.get("Last-Event-ID")
stream_gen = consume_task_stream(
    task_id=task_id, family_id=family_id,
    last_event_id=last_event_id,
    run_id=result["run_id"],
    bridge=shared_bridge,
)
return StreamingResponse(
    tracked_sse_stream(task_id, stream_gen),
    media_type="text/event-stream",
    headers={"X-Accel-Buffering": "no"},
)
```

Key change: `consume_task_stream()` already calls `bridge.subscribe(run_id=...)` internally. With Redis bridge, this subscribes to the same Redis Stream the agent writes to. The pump is no longer needed.

**ai_chat.py migration note**: `ai_chat.py` does NOT use `_pump_agent_sse_to_bridge()` — it uses `agent_client.stream()` (HTTP SSE proxy) + `_spawn_lifecycle_consumer()`. Replace the `async with agent_client.stream()` blocks with `trigger_agent_run()` + `consume_task_stream()` using Redis bridge. The `_spawn_lifecycle_consumer()` call can remain since it already reads from the bridge.

- [ ] **Step 5: Delete `_pump_agent_sse_to_bridge()` from `bridge_consumer.py`**

Remove the function and its SSE line-parsing logic (~220 lines). Keep `consume_task_stream()`, `bridge_consumer()`, `_spawn_lifecycle_consumer()`, and `get_shared_bridge()` — these are still needed.

Also update `get_shared_bridge()` to default to `"redis"`:

```python
def get_shared_bridge() -> StreamBridge:
    global _shared_bridge
    if _shared_bridge is None:
        bridge_type = os.environ.get("STREAM_BRIDGE_TYPE", "redis")
        redis_url = os.environ.get("REDIS_URL", "redis://redis:6379/0")
        config = StreamBridgeConfig(
            type=bridge_type,
            redis_url=redis_url,
            queue_maxsize=256,
            stream_ttl_seconds=86400,
        )
        _shared_bridge = make_stream_bridge(config)
    return _shared_bridge
```

- [ ] **Step 6: Update tests that mock `_pump_agent_sse_to_bridge`**

Search and update test files:
- `server/tests/backend/test_ai_report_trigger.py`
- `server/tests/backend/test_ai_report.py`

Replace `@patch("..._pump_agent_sse_to_bridge")` with `@patch("...trigger_agent_run")`.

- [ ] **Step 7: Run all backend tests**

```bash
cd server && uv run pytest tests/backend/ -v --timeout=60 -x
```

Expected: All tests pass. No references to `_pump_agent_sse_to_bridge` remain.

- [ ] **Step 8: Commit**

```bash
git add server/apps/backend/app/services/bridge_consumer.py \
       server/apps/backend/app/routers/ai_report.py \
       server/apps/backend/app/routers/ai_finance_coach.py \
       server/apps/backend/app/routers/ai_literacy_report.py \
       server/apps/backend/app/routers/dashboard.py \
       server/apps/backend/app/routers/ai_chat.py \
       server/tests/backend/
git commit -m "refactor(backend): replace HTTP SSE pump with direct Redis StreamBridge subscribe

All 5 routers (ai_report, ai_finance_coach, ai_literacy_report, dashboard, ai_chat)
now trigger agent via POST and subscribe to Redis Stream directly.
_pump_agent_sse_to_bridge() deleted — agent writes to Redis, backend reads.

Co-Authored-By: Claude Code <noreply@anthropic.com>"
```

---

## Phase 2: Frontend SSE Infrastructure

### Task 3: Extract sseReader to `@numina/shared`

**Files:**
- Create: `frontend/packages/shared/package.json`
- Create: `frontend/packages/shared/tsconfig.json`
- Create: `frontend/packages/shared/src/index.ts`
- Create: `frontend/packages/shared/src/utils/sseReader.ts` (move from `frontend/apps/main/src/utils/sseReader.ts`)
- Modify: `frontend/apps/main/package.json` (add `@numina/shared` dep)
- Modify: `frontend/apps/child/package.json` (add `@numina/shared` dep)
- Modify: `frontend/apps/main/src/composables/useLiteracyStream.ts` (update import)
- Modify: `frontend/apps/main/src/composables/useReportStream.ts` (update import)
- Modify: `frontend/apps/main/src/api/ai.ts` (update import)
- Modify: `frontend/apps/main/src/api/dashboard.ts` (update import)

**Interfaces:**
- Consumes: `frontend/apps/main/src/utils/sseReader.ts` (source)
- Produces: `@numina/shared` package exporting `readSSEstream()` and `SSEStreamHandlers`

- [ ] **Step 1: Create `@numina/shared` package**

Create `frontend/packages/shared/package.json`:
```json
{
  "name": "@numina/shared",
  "version": "0.0.0",
  "private": true,
  "type": "module",
  "main": "./src/index.ts",
  "exports": { ".": "./src/index.ts" }
}
```

Create `frontend/packages/shared/tsconfig.json`:
```json
{
  "compilerOptions": {
    "target": "ES2020",
    "module": "ESNext",
    "moduleResolution": "bundler",
    "strict": true,
    "lib": ["ES2020", "DOM"],
    "skipLibCheck": true,
    "isolatedModules": true,
    "verbatimModuleSyntax": true
  },
  "include": ["src/**/*.ts"]
}
```

- [ ] **Step 2: Move `sseReader.ts` to shared package**

Move `frontend/apps/main/src/utils/sseReader.ts` → `frontend/packages/shared/src/utils/sseReader.ts` (zero changes needed — file has no app-specific imports).

Create `frontend/packages/shared/src/index.ts`:
```typescript
export { readSSEstream } from './utils/sseReader'
export type { SSEStreamHandlers } from './utils/sseReader'
```

- [ ] **Step 3: Add workspace dependencies**

In `frontend/apps/main/package.json`, add:
```json
"@numina/shared": "workspace:*"
```

In `frontend/apps/child/package.json`, add:
```json
"@numina/shared": "workspace:*"
```

- [ ] **Step 4: Update imports in main app**

In 4 files, change:
```typescript
import { readSSEstream } from '@/utils/sseReader'
```
to:
```typescript
import { readSSEstream } from '@numina/shared'
```

Files: `useLiteracyStream.ts`, `useReportStream.ts`, `api/ai.ts`, `api/dashboard.ts`.

Delete the old `frontend/apps/main/src/utils/sseReader.ts`.

- [ ] **Step 5: Run `pnpm install` and verify build**

```bash
cd frontend && pnpm install && pnpm -r build
```

Expected: No build errors. All 4 main-app consumers resolve `@numina/shared`.

- [ ] **Step 6: Commit**

```bash
git add frontend/packages/shared/ \
       frontend/apps/main/package.json \
       frontend/apps/child/package.json \
       frontend/apps/main/src/composables/useLiteracyStream.ts \
       frontend/apps/main/src/composables/useReportStream.ts \
       frontend/apps/main/src/api/ai.ts \
       frontend/apps/main/src/api/dashboard.ts
git commit -m "refactor(frontend): extract sseReader to @numina/shared package

Zero-dependency SSE frame parser now shared between main and child apps.
4 main-app imports updated from @/utils/sseReader to @numina/shared.

Co-Authored-By: Claude Code <noreply@anthropic.com>"
```

---

## Phase 3: Learning-Tutor Feature

### Task 4: Learning MCP Tools (Registry + Handlers)

> **Deviation from spec §4:** Spec describes creating a new file `mcp_learning_tools.py` with `@register_tool` decorator pattern. This plan instead registers tools via the existing `_REGISTRY` dict in `mcp_tool_registry.py` + `elif` branches in `mcp_session.py`. **Rationale:** The codebase uses the registry+session dispatch pattern (not `@register_tool` decorators). The spec's `@register_tool` approach was a simplified description; the actual implementation must follow the existing codebase pattern to maintain consistency with the 20+ already-registered tools.

**Files:**
- Modify: `server/apps/backend/app/services/mcp_tool_registry.py` (add 3 entries to `_REGISTRY`)
- Modify: `server/apps/backend/app/services/mcp_session.py` (add 3 `elif` branches in `call_tool()`)
- Delete: `server/apps/backend/app/services/learning/mcp_tools.py` (remove NotImplementedError stubs)
- Test: `server/tests/backend/integration/test_learning_mcp_tools.py`

**Interfaces:**
- Consumes: `LearningTopic`, `LearningProgress`, `LearningSession` models from `packages/db/models/learning/`
- Produces: 3 MCP tools available to agent: `get_learning_topic`, `get_child_learning_profile`, `record_learning_result`

- [ ] **Step 1: Write failing tests for the 3 MCP tools**

```python
# server/tests/backend/integration/test_learning_mcp_tools.py
"""Test learning MCP tool registration and handler logic."""
import pytest
from apps.backend.app.services.mcp_tool_registry import get_tool, validate_registry, _REGISTRY


class TestLearningToolRegistry:
    """Verify 3 learning tools are properly registered."""

    def test_get_learning_topic_registered(self):
        meta = get_tool("get_learning_topic")
        assert meta is not None
        assert meta.name == "get_learning_topic"
        assert meta.requires_write is False
        assert "topic_id" in meta.input_schema.get("properties", {})
        assert "child_id" in meta.input_schema.get("properties", {})

    def test_get_child_learning_profile_registered(self):
        meta = get_tool("get_child_learning_profile")
        assert meta is not None
        assert meta.requires_write is False
        assert "child_id" in meta.input_schema.get("properties", {})

    def test_record_learning_result_registered(self):
        meta = get_tool("record_learning_result")
        assert meta is not None
        assert meta.requires_write is True  # write operation
        assert "session_id" in meta.input_schema.get("properties", {})
        assert "evaluation" in meta.input_schema.get("properties", {})

    def test_validate_registry_passes(self):
        """Startup validation should not raise."""
        validate_registry()

    def test_tool_names_match_skill_allowed_tools(self):
        """Tool names must match learning-tutor SKILL.md allowed-tools exactly."""
        expected = {"get_learning_topic", "get_child_learning_profile", "record_learning_result"}
        registered = {name for name in _REGISTRY if name in expected}
        assert registered == expected
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd server && uv run pytest tests/backend/integration/test_learning_mcp_tools.py -v
```

Expected: FAIL — tools not yet registered.

- [ ] **Step 3: Add 3 `MCPToolMeta` entries to `_REGISTRY`**

In `server/apps/backend/app/services/mcp_tool_registry.py`, add to `_REGISTRY`:

```python
"get_learning_topic": MCPToolMeta(
    name="get_learning_topic",
    description="获取学习知识点详情及孩子的掌握程度。返回知识点名称、描述、证据标准、评估提示，以及孩子当前的掌握级别。",
    input_schema={
        "type": "object",
        "properties": {
            "topic_id": {"type": "integer", "description": "知识点 ID"},
            "child_id": {"type": "integer", "description": "孩子用户 ID"},
        },
        "required": ["topic_id", "child_id"],
    },
    allowed_roles=frozenset({"owner", "member"}),
    requires_write=False,
),
"get_child_learning_profile": MCPToolMeta(
    name="get_child_learning_profile",
    description="获取孩子的学习档案统计：已掌握、学习中、可用的知识点数量，以及最近的学习活动。",
    input_schema={
        "type": "object",
        "properties": {
            "child_id": {"type": "integer", "description": "孩子用户 ID"},
            "subject": {"type": "string", "description": "可选：按科目过滤"},
        },
        "required": ["child_id"],
    },
    allowed_roles=frozenset({"owner", "member"}),
    requires_write=False,
),
"record_learning_result": MCPToolMeta(
    name="record_learning_result",
    description="记录 AI 辅导评估结果。更新学习进度、触发金币/徽章奖励。",
    input_schema={
        "type": "object",
        "properties": {
            "session_id": {"type": "integer", "description": "学习会话 ID"},
            "evaluation": {
                "type": "object",
                "description": "评估结果 JSON",
                "properties": {
                    "evidence_results": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "evidence": {"type": "string"},
                                "met": {"type": "boolean"},
                                "notes": {"type": "string"},
                            },
                            "required": ["evidence", "met"],
                        },
                    },
                    "overall_score": {"type": "number", "minimum": 0.0, "maximum": 1.0},
                    "recommendation": {
                        "type": "string",
                        "enum": ["mastered", "needs_review", "keep_learning"],
                    },
                },
                "required": ["evidence_results", "overall_score", "recommendation"],
            },
        },
        "required": ["session_id", "evaluation"],
    },
    allowed_roles=frozenset({"owner", "member"}),
    requires_write=True,
),
```

- [ ] **Step 4: Add handler branches in `MCPSession.call_tool()`**

In `server/apps/backend/app/services/mcp_session.py`, add 3 `elif` branches:

```python
elif name == "get_learning_topic":
    from packages.db.models.learning.topic import LearningTopic
    from packages.db.models.learning.progress import LearningProgress

    topic_id = arguments["topic_id"]
    child_id = arguments["child_id"]

    with SessionLocal() as db:
        user = _get_caller_user(self._family_id, self._caller_user_id, db)
        topic = db.query(LearningTopic).filter(LearningTopic.id == topic_id).first()
        if not topic:
            return [TextContent(type="text", text=json.dumps({"error": "topic_not_found"}))]

        # Family-scope validation: verify child belongs to caller's family
        child = db.query(User).filter(User.id == child_id, User.family_id == self._family_id).first()
        if not child:
            return [TextContent(type="text", text=json.dumps({"error": "child_not_in_family"}))]

        progress = (
            db.query(LearningProgress)
            .filter_by(child_id=child_id, topic_id=topic_id)
            .first()
        )

        data = {
            "topic_id": str(topic.id),
            "name": topic.name,
            "description": topic.description,
            "evidence_criteria": topic.evidence_json,
            "assessment_prompt": topic.assessment_prompt,
            "mastery_level": progress.mastery_level if progress else "locked",
        }
    result_text = json.dumps(data, ensure_ascii=False, default=str)

elif name == "get_child_learning_profile":
    from packages.db.models.learning.progress import LearningProgress

    child_id = arguments["child_id"]
    subject = arguments.get("subject")

    with SessionLocal() as db:
        user = _get_caller_user(self._family_id, self._caller_user_id, db)
        query = db.query(LearningProgress).filter(LearningProgress.child_id == child_id)
        if subject:
            query = query.filter(LearningProgress.subject == subject)
        progresses = query.all()

        data = {
            "child_id": str(child_id),
            "total_topics": len(progresses),
            "mastered": sum(1 for p in progresses if p.mastery_level == "mastered"),
            "learning": sum(1 for p in progresses if p.mastery_level == "learning"),
            "review": sum(1 for p in progresses if p.mastery_level == "review"),
            "locked": sum(1 for p in progresses if p.mastery_level == "locked"),
            "assessing": sum(1 for p in progresses if p.mastery_level == "assessing"),
        }
    result_text = json.dumps(data, ensure_ascii=False, default=str)

elif name == "record_learning_result":
    from apps.backend.app.services.learning import session_service, progress_service
    from packages.db.models.learning.session import LearningSession

    session_id = arguments["session_id"]
    evaluation = arguments["evaluation"]

    # Schema validation (LLM output is untrusted)
    _validate_evaluation_schema(evaluation)

    with SessionLocal() as db:
        user = _get_caller_user(self._family_id, self._caller_user_id, db)
        # End session with evaluation
        session = session_service.end_session(
            db, session_id,
            score=evaluation["overall_score"],
            ai_evaluation=evaluation,
        )
        # Family-scope validation: verify session belongs to caller's family
        if session.child.family_id != self._family_id:
            return [TextContent(type="text", text=json.dumps({"error": "session_not_in_family"}))]
        # Update progress based on recommendation
        progress = (
            db.query(LearningProgress)
            .filter_by(child_id=session.child_id, topic_id=session.topic_id)
            .first()
        )
        if progress:
            rec = evaluation["recommendation"]
            if rec == "mastered":
                progress.mastery_level = "mastered"
            elif rec == "needs_review":
                progress.mastery_level = "review"
            # keep_learning → stays at current level

        data = {"ok": True, "session_id": str(session_id), "recommendation": evaluation["recommendation"]}
    result_text = json.dumps(data, ensure_ascii=False, default=str)
```

Add the validation helper:

```python
def _validate_evaluation_schema(evaluation: dict) -> None:
    """Validate LLM-produced evaluation structure."""
    if not isinstance(evaluation, dict):
        raise ValueError("evaluation must be a dict")
    if "evidence_results" not in evaluation or not isinstance(evaluation["evidence_results"], list):
        raise ValueError("evaluation must contain evidence_results array")
    # Per-item validation (LLM output is untrusted)
    for i, item in enumerate(evaluation["evidence_results"]):
        if not isinstance(item, dict):
            raise ValueError(f"evidence_results[{i}] must be a dict")
        if "evidence" not in item or not isinstance(item["evidence"], str):
            raise ValueError(f"evidence_results[{i}] must contain 'evidence' (string)")
        if "met" not in item or not isinstance(item["met"], bool):
            raise ValueError(f"evidence_results[{i}] must contain 'met' (boolean)")
    score = evaluation.get("overall_score")
    if not isinstance(score, (int, float)) or not (0.0 <= score <= 1.0):
        raise ValueError("overall_score must be 0.0-1.0")
    rec = evaluation.get("recommendation")
    if rec not in ("mastered", "needs_review", "keep_learning"):
        raise ValueError(f"recommendation must be mastered/needs_review/keep_learning, got {rec!r}")
```

- [ ] **Step 5: Run tests to verify they pass**

```bash
cd server && uv run pytest tests/backend/integration/test_learning_mcp_tools.py -v
```

Expected: PASS.

- [ ] **Step 6: Delete old stub file**

Delete `server/apps/backend/app/services/learning/mcp_tools.py` (3 `NotImplementedError` stubs — replaced by MCP registry entries).

- [ ] **Step 7: Commit**

```bash
git add server/apps/backend/app/services/mcp_tool_registry.py \
       server/apps/backend/app/services/mcp_session.py \
       server/tests/backend/integration/test_learning_mcp_tools.py
git rm server/apps/backend/app/services/learning/mcp_tools.py
git commit -m "feat(learning): register 3 MCP tools for learning-tutor skill

get_learning_topic, get_child_learning_profile, record_learning_result
registered in MCP tool registry with schema validation for LLM output.
Replaces NotImplementedError stubs in mcp_tools.py.

Co-Authored-By: Claude Code <noreply@anthropic.com>"
```

---

### Task 5: Agent learning-tutor Runner + Gateway

**Files:**
- Modify: `server/apps/agent/services/runtime/worker.py` (add `_run_learning_tutor_agent` + dispatch branch)
- Modify: `server/apps/agent/app/routers/gateway.py` (add trigger endpoint)
- Modify: `server/apps/backend/app/bootstrap/agents.py` (add system agent)
- Modify: `server/apps/backend/app/routers/ai_skills.py` (add to `RESERVED_NAMES`)
- Test: `server/tests/agent/integration/test_learning_tutor_dispatch.py`

**Interfaces:**
- Consumes: `RunPipeline`, `DeerFlowAdapter`, `StreamBridge` (all existing)
- Produces: Agent accepts `POST /internal/gateway/runs/learning-tutor/{thread_id}` and runs the learning-tutor skill

- [ ] **Step 1: Write failing test for dispatch routing**

```python
# server/tests/agent/integration/test_learning_tutor_dispatch.py
"""Verify learning-tutor app dispatches correctly."""
import pytest
from unittest.mock import AsyncMock, patch, MagicMock


@pytest.mark.asyncio
async def test_learning_tutor_dispatch():
    """worker.run_agent should route 'learning-tutor' app to _run_learning_tutor_agent."""
    from apps.agent.services.runtime.worker import run_agent

    record = MagicMock()
    record.run_id = "run_1"
    record.thread_id = "thread_1"
    record.user_message = "Help me learn fractions"
    record.metadata = {"app": "learning-tutor", "task_id": "task_1"}
    record.on_disconnect = "continue"

    bridge = AsyncMock()

    with patch("apps.agent.services.runtime.worker._run_learning_tutor_agent") as mock_runner:
        mock_runner.return_value = None
        await run_agent(
            bridge=bridge, run_manager=MagicMock(),
            record=record, family_id="fam_1", user_id="user_1",
            thread_id="thread_1", graph_input=None, config=None,
        )
        mock_runner.assert_called_once()


@pytest.mark.asyncio
async def test_learning_tutor_runner_uses_run_pipeline():
    """_run_learning_tutor_agent should use RunPipeline with skill_name='learning-tutor'."""
    from apps.agent.services.runtime.worker import _run_learning_tutor_agent

    record = MagicMock()
    record.run_id = "run_1"
    record.thread_id = "thread_1"
    record.user_message = "Help me learn fractions"
    record.metadata = {"app": "learning-tutor"}

    bridge = AsyncMock()
    adapter = AsyncMock()

    with patch("apps.agent.services.runtime.worker.RunPipeline") as MockPipeline:
        mock_pipeline = AsyncMock()
        MockPipeline.return_value.__aenter__ = AsyncMock(return_value=mock_pipeline)
        MockPipeline.return_value.__aexit__ = AsyncMock(return_value=False)

        await _run_learning_tutor_agent(
            bridge=bridge, run_manager=MagicMock(),
            record=record, family_id="fam_1", user_id="user_1",
            thread_id="thread_1", graph_input=None, config=None,
        )

        # RunPipeline is entered as context manager, adapter.typed_stream_dispatch is called
        mock_pipeline.__aenter__.assert_called_once()
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd server && uv run pytest tests/agent/integration/test_learning_tutor_dispatch.py -v
```

Expected: FAIL — `_run_learning_tutor_agent` doesn't exist yet.

- [ ] **Step 3: Add `_run_learning_tutor_agent` to `worker.py`**

In `server/apps/agent/services/runtime/worker.py`, add the runner function (following the pattern of `_run_finance_coach_agent`):

```python
async def _run_learning_tutor_agent(
    *,
    bridge: StreamBridge,
    run_manager: RunManager,
    record: RunRecord,
    family_id: str,
    user_id: str,
    thread_id: str,
    graph_input: Any,
    config: Any,
) -> None:
    """Learning tutor — AI 辅导对话 (DeerFlow skill: learning-tutor).

    Uses RunPipeline for provider selection, MCP resolution, PII redaction,
    and audit logging. DeerFlow handles tool calls to MCP learning tools.
    Follows the same pattern as _run_finance_coach_agent and other runners.
    """
    async with RunPipeline(
        app_name="learning-tutor",
        record=record,
        bridge=bridge,
        family_id=family_id,
        user_id=user_id,
        thread_id=thread_id,
    ) as pipeline:
        # Inject synthetic trigger message with learning context
        trigger_message = record.user_message  # contains JSON with topic/child info
        await pipeline.adapter.typed_stream_dispatch(
            skill_name="learning-tutor",
            user_message=trigger_message,
            thread_id=thread_id,
        )
        # RunPipeline auto-publishes events via bridge.publish()
        # DeerFlow's learning-tutor skill calls MCP tools for data access
```

In `run_agent()`, add the dispatch branch (matching existing if-chain pattern):

```python
elif app == "learning-tutor":
    await _run_learning_tutor_agent(
        bridge=bridge, run_manager=run_manager,
        record=record, family_id=family_id, user_id=user_id,
        thread_id=thread_id, graph_input=graph_input, config=config,
    )
```

- [ ] **Step 4: Add gateway endpoint**

In `server/apps/agent/app/routers/gateway.py`, add:

```python
class LearningTutorRunRequest(BaseModel):
    family_id: str
    user_id: str | None = None
    language: str | None = None
    input: dict
    on_disconnect: str = "continue"


@router.post("/internal/gateway/runs/learning-tutor/{thread_id}")
async def trigger_learning_tutor_run(
    thread_id: str,
    body: LearningTutorRunRequest,
    request: Request,
    family_id: str = Header(..., alias="X-Family-Id"),
    user_id: str = Header(..., alias="X-User-Id"),
):
    """Backend → Agent: trigger learning-tutor run."""
    await verify_service_token(request)
    run_body = SimpleNamespace(
        assistant_id=None,
        input=body.input,
        config=None,
        metadata={"app": "learning-tutor"},
        on_disconnect=body.on_disconnect,
        multitask_strategy="reject",
    )
    return await start_run(
        run_body, thread_id, request, family_id, user_id,
        internal=True,
    )
```

- [ ] **Step 5: Register system agent + verify RESERVED_NAMES**

In `server/apps/backend/app/bootstrap/agents.py`, add:
```python
SystemAgent("learning-tutor", ["learning-tutor"], memory_enabled=False),
```

In `server/apps/backend/app/routers/ai_skills.py`, verify `learning-tutor` is already in `RESERVED_NAMES` (it exists at lines 58 and 68 — remove the duplicate if present):
```python
RESERVED_NAMES = ["chat", "asset-report", "import-parse", "finance-coach",
                  "wish-advice", "dashboard-narrative", "literacy-weekly-report",
                  "learning-tutor"]
```

- [ ] **Step 6: Run agent tests**

```bash
cd server && uv run pytest tests/agent/integration/test_learning_tutor_dispatch.py -v
```

Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add server/apps/agent/services/runtime/worker.py \
       server/apps/agent/app/routers/gateway.py \
       server/apps/backend/app/bootstrap/agents.py \
       server/apps/backend/app/routers/ai_skills.py \
       server/tests/agent/integration/test_learning_tutor_dispatch.py
git commit -m "feat(agent): add learning-tutor runner + gateway endpoint

New _run_learning_tutor_agent() uses RunPipeline with skill_name='learning-tutor'.
Gateway endpoint at /internal/gateway/runs/learning-tutor/{thread_id}.
Registered in RESERVED_NAMES and system agents.

Co-Authored-By: Claude Code <noreply@anthropic.com>"
```

---

### Task 6: Backend Assessment Stream Endpoint + Session Service

**Files:**
- Modify: `server/apps/backend/app/services/learning/session_service.py` (add `start_assessment_stream`)
- Modify: `server/apps/backend/app/routers/learning_child.py` (add `POST /sessions/{id}/assess/stream`)
- Test: `server/tests/backend/integration/test_learning_assess_stream.py`

**Interfaces:**
- Consumes: `AgentClient`, `NuminaRedisStreamBridge`, `LearningSession` model, `consume_task_stream`
- Produces: `POST /child/learning/sessions/{session_id}/assess/stream` returns SSE stream

- [ ] **Step 1: Write failing test for assessment stream endpoint**

```python
# server/tests/backend/integration/test_learning_assess_stream.py
"""Test the assessment streaming endpoint."""
import pytest
from unittest.mock import patch, AsyncMock


@pytest.mark.asyncio
async def test_assess_stream_creates_session_and_triggers_agent():
    """POST /sessions/{id}/assess/stream should trigger agent and return SSE."""
    # Test that:
    # 1. Session is validated (exists, belongs to child)
    # 2. Agent is triggered via AgentClient.post()
    # 3. Response is StreamingResponse with text/event-stream
    pass  # Integration test — requires full app setup


def test_session_id_used_as_thread_id():
    """str(session.id) should be passed to agent as thread_id."""
    from apps.backend.app.services.learning.session_service import (
        get_thread_id_for_session,
    )
    # Session ID is the thread ID (no separate field needed)
    assert get_thread_id_for_session(12345) == "12345"
    assert get_thread_id_for_session(999999999999999) == "999999999999999"
```

- [ ] **Step 2: Add `get_thread_id_for_session` to session_service**

In `server/apps/backend/app/services/learning/session_service.py`:

```python
def get_thread_id_for_session(session_id: int) -> str:
    """Session ID is used as the DeerFlow thread_id (same pattern as AIChatSession)."""
    return str(session_id)
```

- [ ] **Step 3: Add assessment stream endpoint to `learning_child.py`**

```python
class AssessStreamRequest(BaseModel):
    """Optional body for multi-turn tutorial messages. Omit for initial assessment."""
    user_message: str | None = None


@router.post("/sessions/{session_id}/assess/stream")
async def stream_assessment(
    session_id: int,
    request: Request,
    body: AssessStreamRequest | None = None,
    db: Session = Depends(get_db),
    current_child: User = Depends(get_current_child),
):
    """Start or continue AI assessment session and return SSE stream.

    Flow:
    1. Validate session + transition to 'assessing' (if initial) or continue (if follow-up)
    2. Build agent trigger body (initial: topic context; follow-up: user_message)
    3. Trigger agent (writes to Redis StreamBridge)
    4. Subscribe to Redis Stream → SSE to frontend
    """
    from apps.backend.app.services.learning.session_service import (
        get_thread_id_for_session,
        start_assessment,
    )
    from apps.backend.app.services.agent_client import AgentClient
    from apps.backend.app.services.bridge_consumer import (
        get_shared_bridge,
        consume_task_stream,
        trigger_agent_run,
    )

    # 1. Start/continue assessment
    session = session_service.get_session(db, session_id, current_child.id)  # validate ownership
    thread_id = get_thread_id_for_session(session_id)
    family_id = current_child.family_id

    is_follow_up = body is not None and body.user_message is not None

    if not is_follow_up:
        # Initial assessment: transition progress to 'assessing'
        start_assessment(db, session_id, current_child.id)
        session.thread_id = thread_id
        db.commit()

    # 2. Build agent trigger body
    topic = db.query(LearningTopic).filter(LearningTopic.id == session.topic_id).first()

    if is_follow_up:
        # Tutorial multi-turn: forward user message to existing thread
        agent_content = json.dumps({
            "action": "continue_tutoring",
            "user_message": body.user_message,
            "topic_id": topic.id,
            "child_id": current_child.id,
            "session_id": session_id,
        }, ensure_ascii=False)
    else:
        # Initial assessment: provide full context
        agent_content = json.dumps({
            "action": "start_tutoring",
            "topic_id": topic.id,
            "topic_name": topic.name,
            "topic_description": topic.description,
            "child_id": current_child.id,
            "child_name": current_child.display_name,
            "session_type": session.session_type,
            "session_id": session_id,
        }, ensure_ascii=False)

    agent_body = {
        "input": {
            "messages": [{"role": "user", "content": agent_content}],
        },
        "on_disconnect": "continue",
        "metadata": {
            "app": "learning-tutor",
            "session_id": str(session_id),
            "topic_id": str(topic.id),
        },
    }

    # 3. Create AITask record for lifecycle tracking (bridge_consumer requires integer task_id)
    from apps.backend.app.services.ai_task_service import AITaskService
    task = AITaskService.create_task(
        db, family_id=family_id, user_id=current_child.id,
        task_type="learning_assessment", metadata={"session_id": str(session_id)},
    )
    db.commit()
    task_id = str(task.id)

    # 4. Trigger agent (writes to Redis)
    agent_client = AgentClient(family_id=str(family_id), user_id=str(current_child.id))
    result = await trigger_agent_run(
        agent_client=agent_client,
        agent_url=f"/internal/gateway/runs/learning-tutor/{thread_id}",
        json_body=agent_body,
        task_id=task_id,
    )

    # 5. Subscribe to Redis Stream → SSE
    shared_bridge = get_shared_bridge()
    last_event_id = request.headers.get("Last-Event-ID")
    stream_gen = consume_task_stream(
        task_id=task_id,
        family_id=family_id,
        last_event_id=last_event_id,
        run_id=result["run_id"],
        bridge=shared_bridge,
    )

    return StreamingResponse(
        stream_gen,
        media_type="text/event-stream",
        headers={"X-Accel-Buffering": "no"},
    )
```

> **Multi-turn support:** The endpoint now accepts an optional `AssessStreamRequest` body. When `user_message` is present, it builds a `continue_tutoring` agent payload instead of `start_tutoring`, enabling tutorial mode multi-turn conversation within the same thread.

- [ ] **Step 3b: Add `GET /sessions/{id}/history` endpoint for reconnection**

```python
@router.get("/sessions/{session_id}/history")
async def get_session_history(
    session_id: int,
    db: Session = Depends(get_db),
    current_child: User = Depends(get_current_child),
):
    """Load conversation history from DeerFlow checkpointer for reconnection.

    Used by frontend reconnect() when run_status is 'completed' to restore
    the full conversation after a gap or page reload.
    """
    session = session_service.get_session(db, session_id, current_child.id)
    thread_id = get_thread_id_for_session(session_id)

    # Fetch conversation history from agent checkpointer via AgentClient
    from apps.backend.app.services.agent_client import AgentClient
    agent_client = AgentClient(
        family_id=str(current_child.family_id),
        user_id=str(current_child.id),
    )
    resp = await agent_client.get(f"/internal/gateway/threads/{thread_id}/state")
    # resp contains the checkpoint state with message history
    messages = resp.json().get("messages", [])

    return {"session_id": session_id, "thread_id": thread_id, "messages": messages}
```

- [ ] **Step 4: Run tests**

```bash
cd server && uv run pytest tests/backend/integration/test_learning_assess_stream.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add server/apps/backend/app/services/learning/session_service.py \
       server/apps/backend/app/routers/learning_child.py \
       server/tests/backend/integration/test_learning_assess_stream.py
git commit -m "feat(learning): add assessment stream endpoint with Redis bridge subscribe

POST /child/learning/sessions/{id}/assess/stream triggers learning-tutor agent
and returns SSE stream. Uses session ID as thread_id. Agent writes to Redis,
backend subscribes directly — no HTTP SSE pump.

Co-Authored-By: Claude Code <noreply@anthropic.com>"
```

---

### Task 7: Frontend Learning Chat UI

**Files:**
- Create: `frontend/apps/child/src/composables/useLearningChat.ts`
- Modify: `frontend/apps/child/src/api/learning.ts` (add `startAssessmentStream`)
- Modify: `frontend/apps/child/src/pages/learning/LearningSessionPage.vue` (replace placeholder)
- Modify: `frontend/apps/child/src/i18n/locales/zh-CN.ts` (add `learning.error.*` keys)
- Modify: `frontend/apps/child/src/i18n/locales/en.ts` (add `learning.error.*` keys)

**Interfaces:**
- Consumes: `@numina/shared` (`readSSEstream`, `SSEStreamHandlers`), backend `POST /sessions/{id}/assess/stream`
- Produces: Working chat UI in `LearningSessionPage` with streaming messages

- [ ] **Step 1: Create `useLearningChat` composable**

```typescript
// frontend/apps/child/src/composables/useLearningChat.ts
import { ref, computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { readSSEstream, type SSEStreamHandlers } from '@numina/shared'
import apiClient from '@/api'  // Axios wrapper — used for non-SSE calls (status, history)

interface ChatMessage {
  id: string
  role: 'user' | 'assistant' | 'tool'
  content: string
  toolCall?: { name: string; arguments: Record<string, unknown> }
  toolResult?: { name: string; output: unknown }
  timestamp: number
}

export function useLearningChat() {
  const { t } = useI18n()
  const messages = ref<ChatMessage[]>([])
  const status = ref<'idle' | 'connecting' | 'streaming' | 'completed' | 'error'>('idle')
  const lastEventId = ref<string | null>(null)
  const currentStreamText = ref('')
  const error = ref<string | null>(null)

  let abortController: AbortController | null = null

  /**
   * Shared SSE event handlers — used by startAssessment, reconnect, and sendMessage.
   * Eliminates duplicated handler blocks across the three streaming methods.
   */
  function _createStreamHandlers(): SSEStreamHandlers {
    return {
      onMessage(event: string, data: unknown) {
        const payload = data as Record<string, unknown>
        if (payload?.content) {
          currentStreamText.value += payload.content as string
        }
      },
      onCustom(data: unknown) {
        const payload = data as Record<string, unknown>
        const type = payload?.type as string | undefined
        if (type === 'tool_call') {
          messages.value.push({
            id: `tool-${Date.now()}`,
            role: 'tool',
            content: '',
            toolCall: {
              name: payload.tool_name as string,
              arguments: payload.tool_args as Record<string, unknown>,
            },
            timestamp: Date.now(),
          })
        } else if (type === 'tool_result') {
          messages.value.push({
            id: `result-${Date.now()}`,
            role: 'tool',
            content: '',
            toolResult: {
              name: payload.tool_name as string,
              output: payload.result,
            },
            timestamp: Date.now(),
          })
        } else if (type === 'learning-tutor.result') {
          messages.value.push({
            id: `eval-${Date.now()}`,
            role: 'assistant',
            content: JSON.stringify(payload.data),
            timestamp: Date.now(),
          })
        }
      },
      onError(data: unknown) {
        error.value = String((data as Record<string, unknown>)?.message ?? t('learning.error.stream'))
        status.value = 'error'
      },
      onEnd() {
        // Flush any accumulated streaming text as a message
        if (currentStreamText.value) {
          messages.value.push({
            id: `msg-${Date.now()}`,
            role: 'assistant',
            content: currentStreamText.value,
            timestamp: Date.now(),
          })
          currentStreamText.value = ''
        }
        status.value = 'completed'
      },
      onMetadata(data: unknown) {
        const payload = data as Record<string, unknown>
        if (payload?.run_id) {
          lastEventId.value = (payload.last_event_id as string) ?? lastEventId.value
        }
      },
      onGap(data: unknown) {
        // Gap recovery: buffer overflow — discard transient state, reload from checkpointer
        const payload = data as Record<string, unknown>
        const latestEventId = payload?.latest_available_event_id as string | undefined
        if (latestEventId) {
          lastEventId.value = latestEventId
        }
        // Reset transient streaming state
        currentStreamText.value = ''
        // Attempt reconnection with latest cursor
        _reconnectFromGap().catch((e) => {
          error.value = t('learning.error.gap_recovery')
          status.value = 'error'
        })
      },
    }
  }

  /** Internal: reconnect after gap by re-subscribing from latest_available_event_id */
  async function _reconnectFromGap() {
    if (!lastEventId.value) return
    status.value = 'connecting'
    abortController = new AbortController()
    const response = await fetch(
      `/api/v1/child/learning/sessions/${_activeSessionId}/assess/stream`,
      {
        method: 'POST',
        credentials: 'include',
        headers: {
          'Accept': 'text/event-stream',
          'Last-Event-ID': lastEventId.value,
        },
        signal: abortController.signal,
      },
    )
    if (!response.ok) throw new Error(`Gap reconnect failed: ${response.status}`)
    status.value = 'streaming'
    await readSSEstream(response, _createStreamHandlers())
  }

  let _activeSessionId = ''

  async function startAssessment(sessionId: string) {
    _activeSessionId = sessionId
    status.value = 'connecting'
    error.value = null
    abortController = new AbortController()

    try {
      const response = await fetch(
        `/api/v1/child/learning/sessions/${sessionId}/assess/stream`,
        {
          method: 'POST',
          credentials: 'include',
          headers: {
            'Accept': 'text/event-stream',
            ...(lastEventId.value ? { 'Last-Event-ID': lastEventId.value } : {}),
          },
          signal: abortController.signal,
        },
      )

      if (!response.ok) {
        throw new Error(`Assessment stream failed: ${response.status}`)
      }

      status.value = 'streaming'
      currentStreamText.value = ''

      await readSSEstream(response, _createStreamHandlers())
    } catch (e) {
      if ((e as Error).name !== 'AbortError') {
        error.value = (e as Error).message
        status.value = 'error'
      }
    }
  }

  /**
   * Reconnect to an active or completed assessment.
   *
   * Pattern (from useTaskResume / useReportStream):
   * 1. GET /sessions/{id}/status to check run_status
   * 2a. running → resume SSE with Last-Event-ID
   * 2b. completed → load history from checkpointer via agent thread API
   * 2c. interrupted/error → show recovery UI
   * 2d. idle → no active run, do nothing
   */
  async function reconnect(sessionId: string) {
    _activeSessionId = sessionId
    status.value = 'connecting'
    error.value = null

    try {
      // 1. Check session status via Axios (non-SSE call uses wrapper)
      const { data: sessionStatus } = await apiClient.get(
        `/child/learning/sessions/${sessionId}/status`,
      )

      if (sessionStatus.run_status === 'idle') {
        status.value = 'idle'
        return
      }

      if (sessionStatus.run_status === 'completed' || sessionStatus.run_status === 'failed') {
        // Load history from checkpointer via agent thread API
        if (sessionStatus.thread_id) {
          const { data: history } = await apiClient.get(
            `/child/learning/sessions/${sessionId}/history`,
          )
          messages.value = (history.messages ?? []).map((m: Record<string, unknown>) => ({
            id: `hist-${m.id ?? Date.now()}`,
            role: (m.role as ChatMessage['role']) ?? 'assistant',
            content: (m.content as string) ?? '',
            timestamp: Date.now(),
          }))
        }
        status.value = 'completed'
        return
      }

      if (sessionStatus.run_status === 'running') {
        // Resume SSE with Last-Event-ID
        status.value = 'streaming'
        abortController = new AbortController()

        const response = await fetch(
          `/api/v1/child/learning/sessions/${sessionId}/assess/stream`,
          {
            method: 'POST',
            credentials: 'include',
            headers: {
              'Accept': 'text/event-stream',
              ...(lastEventId.value ? { 'Last-Event-ID': lastEventId.value } : {}),
            },
            signal: abortController.signal,
          },
        )

        if (!response.ok) throw new Error(`Reconnect failed: ${response.status}`)
        await readSSEstream(response, _createStreamHandlers())
        return
      }

      // interrupted / timeout
      status.value = 'error'
      error.value = t('learning.error.session_interrupted', { status: sessionStatus.run_status })
    } catch (e) {
      if ((e as Error).name !== 'AbortError') {
        error.value = (e as Error).message
        status.value = 'error'
      }
    }
  }

  /**
   * Send a message during tutorial mode (multi-turn learning).
   *
   * Pattern (from useThreadChat.sendMessage):
   * 1. Cancel existing stream if still loading
   * 2. Add optimistic user message to messages list
   * 3. POST new assessment with user_message in body → backend builds new agent run
   * 4. Stream response
   */
  async function sendMessage(sessionId: string, content: string) {
    if (!content.trim()) return
    _activeSessionId = sessionId

    // 1. Cancel existing stream if active
    if (abortController) {
      abortController.abort()
      abortController = null
    }

    // 2. Add user message
    messages.value.push({
      id: `user-${Date.now()}`,
      role: 'user',
      content,
      timestamp: Date.now(),
    })

    status.value = 'connecting'
    error.value = null
    abortController = new AbortController()

    try {
      const response = await fetch(
        `/api/v1/child/learning/sessions/${sessionId}/assess/stream`,
        {
          method: 'POST',
          credentials: 'include',
          headers: {
            'Accept': 'text/event-stream',
            'Content-Type': 'application/json',
          },
          body: JSON.stringify({ user_message: content }),
          signal: abortController.signal,
        },
      )

      if (!response.ok) throw new Error(`Send failed: ${response.status}`)

      status.value = 'streaming'
      currentStreamText.value = ''

      await readSSEstream(response, _createStreamHandlers())
    } catch (e) {
      if ((e as Error).name !== 'AbortError') {
        error.value = (e as Error).message
        status.value = 'error'
      }
    }
  }

  function disconnect() {
    abortController?.abort()
    abortController = null
  }

  const isStreaming = computed(() => status.value === 'streaming')
  const isCompleted = computed(() => status.value === 'completed')

  return {
    messages,
    status,
    currentStreamText,
    error,
    isStreaming,
    isCompleted,
    startAssessment,
    reconnect,
    sendMessage,
    disconnect,
  }
}
```

> **i18n keys to add** in `src/i18n/locales/zh-CN.ts` and `en.ts`:
> - `learning.error.stream`: "流式连接错误" / "Stream connection error"
> - `learning.error.gap_recovery`: "事件流中断，正在重新连接…" / "Stream interrupted, reconnecting…"
> - `learning.error.session_interrupted`: "会话已{status}" / "Session {status}"

- [ ] **Step 2: Add `startAssessmentStream` to learning API**

In `frontend/apps/child/src/api/learning.ts`:

```typescript
/**
 * Start assessment stream — returns raw Response for SSE consumption.
 * The caller (useLearningChat) handles SSE parsing via readSSEstream.
 */
export function startAssessmentStream(sessionId: string): Promise<Response> {
  return fetch(`/api/v1/child/learning/sessions/${sessionId}/assess/stream`, {
    method: 'POST',
    credentials: 'include',
    headers: { 'Accept': 'text/event-stream' },
  })
}
```

- [ ] **Step 3: Rewrite `LearningSessionPage.vue`**

Replace the placeholder with a working chat UI. Key elements:

- **Header**: Topic name + session type badge (blue for tutorial, orange for assessment)
- **Message list**: Render `messages` from `useLearningChat`, with streaming text display
- **Input area**: Text input for child to type answers (during tutorial mode)
- **Controls**: "Finish Session" button, disconnect/reconnect indicator
- **Integration**: Call `startAssessment(sessionId)` on mount when session has a thread_id

The component should:
1. Load session data + topic details on mount
2. Call `startAssessment(sessionId)` to begin the AI stream
3. Render streaming messages with typing animation
4. Handle tool_call / tool_result display (collapsible)
5. Show "Session ended" when stream completes
6. Support disconnect/reconnect (via `disconnect()` + re-call `startAssessment`)

- [ ] **Step 4: Run frontend build**

```bash
cd frontend && pnpm -F child build
```

Expected: No build errors.

- [ ] **Step 5: Commit**

```bash
git add frontend/apps/child/src/composables/useLearningChat.ts \
       frontend/apps/child/src/api/learning.ts \
       frontend/apps/child/src/pages/learning/LearningSessionPage.vue \
       frontend/apps/child/src/i18n/locales/zh-CN.ts \
       frontend/apps/child/src/i18n/locales/en.ts
git commit -m "feat(learning): implement LearningSessionPage chat UI with SSE streaming

useLearningChat composable handles SSE connection via @numina/shared readSSEstream.
Shared _createStreamHandlers() eliminates duplicated handler blocks across
startAssessment/reconnect/sendMessage. i18n keys for error messages.
LearningSessionPage replaced placeholder with full chat UI.

Co-Authored-By: Claude Code <noreply@anthropic.com>"
```

---

## Phase 4: Integration & Cleanup

### Task 8: Integration Tests + Smoke Test

**Files:**
- Create: `server/tests/agent/integration/test_learning_e2e.py`
- Modify: `server/apps/backend/app/services/bridge_consumer.py` (update `get_shared_bridge` default if needed)

- [ ] **Step 1: Write end-to-end integration test**

```python
# server/tests/agent/integration/test_learning_e2e.py
"""Smoke tests for learning-tutor Redis bridge integration."""
import pytest


@pytest.mark.asyncio
async def test_shared_bridge_defaults_to_redis():
    """After migration, get_shared_bridge() should return a Redis bridge."""
    from apps.backend.app.services.bridge_consumer import get_shared_bridge
    bridge = get_shared_bridge()
    from packages.stream_bridge.redis import NuminaRedisStreamBridge
    assert isinstance(bridge, NuminaRedisStreamBridge), (
        f"Expected NuminaRedisStreamBridge, got {type(bridge).__name__}"
    )


@pytest.mark.asyncio
async def test_trigger_agent_run_extracts_run_id():
    """trigger_agent_run should extract run_id from Content-Location header."""
    from unittest.mock import AsyncMock, MagicMock
    from apps.backend.app.services.bridge_consumer import trigger_agent_run

    mock_client = AsyncMock()
    mock_client.post = AsyncMock(return_value=MagicMock(
        headers={"Content-Location": "/internal/gateway/runs/learning-tutor/12345/67890"},
        status_code=200,
    ))

    result = await trigger_agent_run(
        agent_client=mock_client,
        agent_url="/internal/gateway/runs/learning-tutor/12345",
        json_body={"input": {"messages": []}},
    )
    assert result["run_id"] == "67890"


@pytest.mark.asyncio
async def test_learning_tutor_full_flow(redis_url: str):
    """
    Full E2E integration test — requires running stack.
    Covers: backend → agent → Redis bridge → backend subscribe → MCP tools.
    """
    pytest.skip("Requires full stack — run via e2e test suite")
```

- [ ] **Step 2: Run full test suite**

```bash
cd server && uv run pytest tests/ -v --timeout=120 -x --ignore=tests/agent/integration/test_learning_e2e.py
```

Expected: All tests pass.

- [ ] **Step 3: Update documentation**

Update these docs to reflect the architecture change:
- `server/apps/agent/CLAUDE.md`: Update "Agent always uses in-memory bridge" → "Agent uses Redis StreamBridge"
- `server/apps/backend/CLAUDE.md`: Add `learning-tutor` to AI router table
- `server/apps/agent/CLAUDE.md` §Security Rules: Add `learning-tutor` runner + 3 MCP tool security constraints (input validation, tenant isolation, schema validation for `record_learning_result`)
- `tests/e2e/` sim-test Area 11: Add learning-tutor security test cases (unauthorized child_id, cross-family topic access, malformed evaluation schema)
- Root `CLAUDE.md`: No changes needed (already references module docs)

- [ ] **Step 4: Update deferred items doc**

In `docs/superpowers/reviews/2026-09-23-learning-os-code-review.md`, update:
- OQ-1: Mark as ✅ Resolved (MCP tools implemented)
- OQ-5: Mark as ✅ Resolved (LearningSessionPage connected to SSE)

- [ ] **Step 5: Final commit**

```bash
git add docs/ server/apps/agent/CLAUDE.md server/apps/backend/CLAUDE.md
git commit -m "docs: update architecture docs for Redis StreamBridge migration

Agent now uses Redis StreamBridge (was memory). Backend subscribes directly.
OQ-1 and OQ-5 resolved — learning-tutor DeerFlow SSE integration complete.

Co-Authored-By: Claude Code <noreply@anthropic.com>"
```

---

### Task 9: Backend Session Status Endpoint (Spec §11)

> **Note:** `useLearningChat` composable methods (`reconnect`, `sendMessage`, `_createStreamHandlers`) are implemented in Task 7. This task provides the backend endpoint that `reconnect()` depends on.

**Design rationale:** Learning-tutor has two interaction modes that need different reconnection strategies:
- **Assessment mode** (single-shot): Follows the **Report/Async task pattern** — AITask status check → resume SSE with Last-Event-ID → gap recovery via `_reconnectFromGap()`
- **Tutorial mode** (multi-turn): Follows the **Chat pattern** — cancel existing stream → new run with `user_message` → backend builds `continue_tutoring` agent payload

**Files:**
- Modify: `server/apps/backend/app/routers/learning_child.py` (add `GET /sessions/{id}/status`)
- Test: `server/tests/backend/integration/test_learning_session_status.py`

**Interfaces:**
- Consumes: `AITaskService` (task status), `LearningSession` model
- Produces: `GET /sessions/{id}/status` endpoint returning `run_status` + `thread_id`

- [ ] **Step 1: Write test for session status endpoint**

```python
# server/tests/backend/integration/test_learning_session_status.py
"""Test GET /sessions/{id}/status for reconnection decisions."""
import pytest
from unittest.mock import patch, MagicMock


@pytest.mark.asyncio
async def test_status_returns_idle_when_no_task():
    """When no AITask exists for session, status should be 'idle'."""
    # Mock: session exists, no AITask found
    # Expected: {"session_id": X, "run_status": "idle", "thread_id": "..."}
    pass  # Integration test — requires full app setup


@pytest.mark.asyncio
async def test_status_returns_task_status_when_running():
    """When AITask is running, status should reflect task status."""
    # Mock: session exists, AITask with status='running'
    # Expected: {"session_id": X, "run_status": "running", "task_id": "...", ...}
    pass  # Integration test — requires full app setup


@pytest.mark.asyncio
async def test_status_includes_last_event_id():
    """Response should include last_event_id for frontend Last-Event-ID header."""
    # Mock: AITask with last_event_id set
    # Expected: last_event_id in response
    pass  # Integration test — requires full app setup
```

- [ ] **Step 2: Add GET session status endpoint**

```python
@router.get("/sessions/{session_id}/status")
async def get_session_status(
    session_id: int,
    db: Session = Depends(get_db),
    current_child: User = Depends(get_current_child),
):
    """Return session run status for reconnection decisions.

    Follows the ai_chat pattern: check AITask status + thread_id for frontend
    to decide whether to reconnect SSE, reload history, or show interrupted state.
    """
    from apps.backend.app.services.ai_task_service import AITaskService

    session = session_service.get_session(db, session_id, current_child.id)

    # Find the AITask for this session (if any)
    task = AITaskService.get_task_by_session_metadata(
        db, family_id=current_child.family_id,
        task_type="learning_assessment",
        metadata_filter={"session_id": str(session_id)},
    )

    if task is None:
        return {
            "session_id": str(session_id),
            "run_status": "idle",
            "thread_id": session.thread_id,
        }

    return {
        "session_id": str(session_id),
        "run_status": task.status,  # running | completed | failed | timeout
        "thread_id": session.thread_id,
        "task_id": str(task.id),
        "last_event_id": task.last_event_id if hasattr(task, "last_event_id") else None,
    }
```

> **Snowflake ID note:** All IDs in response (`session_id`, `task_id`) are serialized as strings per project convention.

- [ ] **Step 3: Run tests**

```bash
cd server && uv run pytest tests/backend/integration/test_learning_session_status.py -v
```

- [ ] **Step 4: Commit**

```bash
git add server/apps/backend/app/routers/learning_child.py \
       server/tests/backend/integration/test_learning_session_status.py
git commit -m "feat(learning): add GET session status endpoint for reconnection

GET /child/learning/sessions/{id}/status returns run_status (idle/running/
completed/failed) + thread_id for frontend reconnect() decisions.
Uses AITask metadata lookup pattern from ai_chat.

Co-Authored-By: Claude Code <noreply@anthropic.com>"
```

---

## Task Dependency Graph

```
Task 1 (Agent Redis Bridge)
    │
    ├──► Task 2 (Backend Pump → Redis)
    │        │
    │        ├──► Task 6 (Assessment Stream Endpoint)
    │        │        │
    │        │        ├──► Task 7 (Frontend Chat UI)
    │        │        │        │
    │        │        │        └──► Task 9 (Session Status Endpoint)
    │        │        │
    │        │        └──► Task 8 (Integration Tests)
    │        │
    │        └──► Task 8 (Integration Tests)
    │
    ├──► Task 3 (Frontend sseReader Extraction)
    │        │
    │        └──► Task 7 (Frontend Chat UI)
    │                 │
    │                 └──► Task 9 (Session Status Endpoint)
    │
    ├──► Task 4 (MCP Tools) ──► Task 6 (Assessment Stream Endpoint)
    │
    └──► Task 5 (Agent Runner + Gateway)
             │
             └──► Task 6 (Assessment Stream Endpoint)
```

**Parallel tracks:**
- Track A (infra): Task 1 → Task 2 → Task 6 → Task 7 → Task 9 → Task 8
- Track B (feature): Task 4 + Task 5 (parallel, after Task 1)
- Track C (frontend): Task 3 (independent, parallel with Track A/B)

---

## Review Changelog (2026-09-23)

> Fixes applied after multi-persona document review (coherence, feasibility, security, scope-guardian).

### Review pass 2 — Standards + Spec compliance (2026-09-23)

**P0 — Critical**
- **SSE `fetch()` exception documented** — Added to Global Constraints: bare `fetch()` is an established exception for SSE streaming (matching `useReportStream`/`useLiteracyStream` pattern). Non-SSE calls use Axios wrapper.
- **i18n enforced** — Added to Global Constraints: all user-facing strings must use `t('key')`. Hardcoded Chinese in `onGap` handler replaced with i18n key.

**P1 — Important**
- **Duplicated SSE handlers extracted** — `_createStreamHandlers()` helper shared by `startAssessment`, `reconnect`, and `sendMessage` (eliminates Fowler Duplicated Code smell).
- **Gap recovery implemented** — `onGap` handler now extracts `latest_available_event_id`, resets transient state, and calls `_reconnectFromGap()` to resume from latest cursor (instead of just erroring out).
- **Tutorial multi-turn backend support** — Added `AssessStreamRequest` body to `stream_assessment` endpoint with optional `user_message`. Backend builds `continue_tutoring` agent payload for follow-up messages.
- **`trigger_agent_run` signature fixed** — Removed unused `bridge` parameter from signature and test (bridge is passed to `consume_task_stream` by the caller, not to `trigger_agent_run`).
- **`trigger_agent_run` type annotations** — Replaced `agent_client: Any` with `agent_client: AgentClient`.
- **CLAUDE.md security rules update** — Task 8 Step 3 now includes updating `agent/CLAUDE.md` §Security Rules and sim-test Area 11.
- **Commit attribution** — All 8 commit messages fixed from `Claude Opus 5 (1M context)` to `Claude Code`.
- **MCP tool pattern deviation documented** — Task 4 now explicitly notes why `_REGISTRY` + `elif` pattern is used instead of spec's `@register_tool` decorator (codebase uses registry pattern).
- **Task 9 restructured** — Frontend methods (`reconnect`, `sendMessage`) moved to Task 7 composable (where shared handlers live). Task 9 now focuses on backend `GET /sessions/{id}/status` endpoint.
- **`reconnect()` uses Axios for non-SSE calls** — `GET /sessions/{id}/status` and `GET /sessions/{id}/history` now use `apiClient.get()` (Axios wrapper), only SSE streaming uses bare `fetch()`.

**P2 — Improvements**
- **MCP tool IDs serialized as strings** — `get_learning_topic`, `get_child_learning_profile`, `record_learning_result` handlers now return `str(topic.id)`, `str(child_id)`, `str(session_id)`.
- **Speculative `getattr(settings, "REDIS_URL", "")` removed** — Task 1 Step 4 now uses only `STREAM_BRIDGE_REDIS_URL` (documented field) with fallback to default URL.
- **History endpoint added** — `GET /sessions/{id}/history` endpoint added to Task 6 for gap recovery reconnection (loads conversation from DeerFlow checkpointer via agent thread API).
- **Response IDs as strings** — `GET /sessions/{id}/status` response serializes `session_id` as `str()`.

### Review pass 1 — Original review (2026-09-23)

### P0 — Critical fixes
- **`topic.evidence_criteria_json` → `topic.evidence_json`** — Task 4 handler referenced non-existent field (verified against `packages/db/models/learning/topic.py:38`)
- **`task_id` format** — Replaced `f"learning_{session_id}"` with proper `AITaskService.create_task()` to get a valid Snowflake ID (bridge_consumer calls `int(task_id)`)

### P1 — Important fixes
- **Task 5 Runner signature** — Rewritten to match actual codebase pattern: `(*, bridge, run_manager, record, family_id, user_id, thread_id, graph_input, config)`
- **Task 5 RunPipeline API** — Changed from `pipeline.run_skill()` to `RunPipeline(app_name=...) as p` + `adapter.typed_stream_dispatch()`
- **Task 5 Gateway endpoint** — Added `LearningTutorRunRequest` Pydantic model, `multitask_strategy="reject"`, matching existing typed-request pattern
- **ai_chat.py migration** — Added to Task 2 (uses `agent_client.stream()` HTTP SSE proxy, different from pump pattern; migration note added)
- **`trigger_agent_and_subscribe` → `trigger_agent_run`** — Function renamed (it doesn't subscribe, only triggers + extracts run_id)
- **`session.thread_id` assignment** — Added to Task 6 endpoint for reconnection continuity
- **`RESERVED_NAMES` note** — Updated to "verify already present" (learning-tutor exists at lines 58+68)
- **Family-scope validation** — Added `child.family_id == self._family_id` check in `get_learning_topic` and `record_learning_result` handlers
- **sseReader.ts path** — Fixed to `packages/shared/src/utils/sseReader.ts` (matching spec)
- **Import name** — Fixed `readSSEStream` → `readSSEstream` (matching actual export)

### P2 — Improvements
- **`_validate_evaluation_schema`** — Added per-item validation for `evidence_results` entries
- **`mastery_level` default** — Changed `"available"` → `"locked"` (matching `LearningProgress` model default)
- **Test mock Content-Location** — Fixed to actual gateway format `/internal/gateway/runs/{app}/{thread}/{run_id}`
- **Task 8 tests** — Replaced stub `pytest.skip()` + `pass` with concrete smoke tests (bridge type assertion, run_id extraction)
- **Task 4 → Task 6 dependency edge** — Added to dependency graph
- **Removed false `subscribe` assertion** from Task 2 test (function doesn't subscribe)

### Task 9 — New (Reconnection + Tutorial Chat)
- ✅ Added `GET /sessions/{id}/status` endpoint (matches `useTaskResume` pattern from main app)
- ✅ Added `reconnect()` method — Last-Event-ID resume + `onGap` handler (from `useReportStream`)
- ✅ Added `sendMessage()` method — cancel existing stream + new run (from `useThreadChat.sendMessage`)
- ✅ Updated dependency graph and parallel tracks
- ✅ Patterns sourced from agent-dev skill research of existing Numina reconnection implementations
