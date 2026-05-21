---
title: "MCP Chat Adapter Architecture — AI 问答、工程逻辑、Skill 能力分层设计"
date: "2026-05-21"
category: architecture-patterns
module: agent/chat
problem_type: architecture_pattern
component: assistant
severity: high
related_components:
  - service_object
  - database
applies_when:
  - "Adding a new AI chat capability that needs runtime data access via MCP tools"
  - "Separating chat-specific logic from a general-purpose orchestrator"
  - "Designing MCP SSE endpoints where connections outlive FastAPI dependency scope"
  - "Enforcing tenant isolation when family_id is frozen at session construction"
tags:
  - mcp
  - sse
  - chat-adapter
  - deerflow
  - tenant-isolation
  - db-session-lifecycle
  - orchestrator
  - system-prompt
---

# MCP Chat Adapter Architecture — AI 问答、工程逻辑、Skill 能力分层设计

## Context

Numina's AI chat originally relied on DeerFlow for all interactions, building a static context dump upfront via `_build_context()` and passing it to the LLM in a single prompt. This created tight coupling: the chat layer had no clean way to inject runtime family data (assets, liabilities, members) without either embedding everything upfront or building fragile workarounds.

The refactoring introduced MCP (Model Context Protocol) as a runtime data access layer, letting the LLM pull structured family data on demand during a conversation. This required separating chat concerns into three distinct layers — each with its own design patterns and pitfalls.

Prior sessions on the `feat/ai-interaction-polish` branch (session history) revealed that DeerFlow's global config singleton is not thread-safe for multi-tenant use. The workaround — serializing streaming behind `_init_lock` while setting `DEER_FLOW_CONFIG_PATH` + calling `reload_app_config()` — was discovered through multiple failed approaches (fixing skills paths alone, passing explicit model names, reloading config without the lock).

## Guidance

### 一、问答能力 (Q&A Capability)

**Encapsulate chat-specific logic in a ChatAdapter** that owns three responsibilities:

1. **Prompt resolution** — family override → default fallback:

```python
# server/apps/agent/services/chat_adapter.py
def _resolve_prompt(self, family_id: str) -> str:
    family_prompt = workspace.get_chat_prompt(family_id)
    if family_prompt:
        return family_prompt
    return self._default_prompt  # from prompts/chat/default_system_prompt.md
```

2. **MCP URL construction** — builds the SSE endpoint URL with safe family_id validation:

```python
def _mcp_url(self, family_id: str) -> str:
    if not re.match(r"^[a-zA-Z0-9_-]+$", family_id):
        raise ValueError("invalid family_id")
    return f"{self._backend_base}/api/v1/internal/mcp/{family_id}/sse"
```

3. **DeerFlow stream delegation** — wraps system prompt in XML tags and delegates to DeerFlow adapter.

**Use XML tags for system prompt privilege separation.** DeerFlow has no native system role. Without structural separation, user messages could bleed into system instructions:

```
<system_instructions>
{system_prompt}
</system_instructions>

<user_question>
{user_message}
</user_question>
```

**Append web search guidance conditionally.** DeerFlow has no native `web_search` tool. Rather than silently ignoring the flag, append explicit guidance:

```python
if web_search:
    prompt += "\n\n你可以使用网络搜索来获取最新的金融市场信息。"
else:
    prompt += "\n\n请仅基于提供的家庭数据回答，不要引用外部信息。"
```

**Store prompts as markdown with YAML frontmatter.** Default at `server/apps/agent/prompts/chat/default_system_prompt.md`, family overrides at `WORKSPACE_ROOT/{family_id}/prompts/chat.md`. The `_strip_frontmatter()` helper removes metadata before injection.

### 二、工程逻辑 (Engineering Logic)

**MCP SSE dual-endpoint pattern: share one transport instance.** The MCP protocol requires GET `/sse` (opens stream) and POST `/messages` (sends tool requests) to share a single `SseServerTransport`. The transport embeds a `session_id` in the URL it returns; POST bodies route to the correct SSE session via that param:

```python
# server/apps/backend/app/routers/mcp_internal.py
_transport = None  # module-level singleton

def _get_transport():
    global _transport
    if _transport is None:
        from mcp.server.sse import SseServerTransport
        _transport = SseServerTransport(endpoint="/api/v1/internal/mcp/messages")
    return _transport
```

A common mistake (caught in review as Critical #1): returning a canned `{"status": "accepted"}` from POST `/messages`. This silently breaks all tool calls — the LLM receives no data but no error either.

**Use per-call DB sessions in MCP tools, not FastAPI DI sessions.** SSE connections are long-lived and outlive FastAPI's request/response lifecycle. The DI session would be closed before tool calls execute:

```python
# WRONG — DI session closed before tool calls run
class MCPSession:
    def __init__(self, db: Session):
        self.db = db  # will be closed

# CORRECT — fresh session per tool call
class MCPSession:
    async def call_tool(self, name: str, arguments: dict):
        with SessionLocal() as db:
            return await self._execute_tool(name, arguments, db)
```

This issue (Critical #2) was silent in dev but would fail under load with connection pool timeouts.

**Freeze tenant identity at construction via `__slots__`.** `family_id` is set once and never accepted as a tool argument — prevents prompt injection from making the LLM pass a different tenant's ID:

```python
class MCPSession:
    __slots__ = ("_family_id", "server")

    def __init__(self, family_id: str):
        self._family_id = family_id  # frozen, immutable
```

**Validate family_id path against the auth token.** The SSE endpoint compares `X-Family-Id` header against URL path `family_id`:

```python
@router.get("/{family_id}/sse")
async def mcp_sse(
    family_id: str,
    x_family_id: str | None = Header(None, alias="X-Family-Id"),
):
    if x_family_id and x_family_id != family_id:
        raise HTTPException(status_code=403, detail="family_id mismatch")
```

**Sanitize MCP tool errors.** Raw Python tracebacks must never reach the LLM:

```python
except Exception:
    logger.exception("MCP tool %s failed for family %s", tool_name, self._family_id)
    return {"error": "查询失败，请稍后重试"}
```

**Chat branch must run session lifecycle hooks before streaming.** The orchestrator's chat branch must call `write_session_start` and `_upsert_session` before delegating to `ChatAdapter.stream()`:

```python
if capability == "chat":
    session_started = True
    await self.write_session_start(session_id, ...)
    await self._upsert_session(session_id, ...)
    async for chunk in self._chat_adapter.stream(...):
        yield chunk
```

Skipping these (Important #7) causes sessions to be missing from history queries.

**Extend the family adapter cache key to include MCP config.** A 5-tuple key prevents a cached non-MCP adapter from serving an MCP-enabled call:

```python
mcp_hash = hashlib.sha1(
    json.dumps(mcp_servers, sort_keys=True).encode()
).hexdigest() if mcp_servers else ""

cache_key = (family_id, config_id, subagent_enabled, plan_mode, mcp_hash)
```

### 三、Skill 能力 (Skill Capability)

**Chat is a fixed capability, not a DeerFlow skill.** The `chat/SKILL.md` was deleted. DeerFlow skills are intent-routed, dispatched via `stream_dispatch`, and defined by `SKILL.md` files — used for structured tasks (asset analysis, report generation). Chat is a conversational capability with its own adapter:

| Dimension | DeerFlow Skill | Fixed Capability (Chat) |
|-----------|---------------|------------------------|
| Routing | intent-matched via capability registry | direct adapter call |
| Config | `SKILL.md` file | `default_system_prompt.md` + workspace override |
| Data access | context built upfront | MCP runtime tools |
| Dispatch | `stream_dispatch()` | `ChatAdapter.stream()` |

**`create_family_adapter()` accepts optional `mcp_servers` param.** When MCP is enabled, the adapter factory writes the config into the DeerFlow YAML:

```python
def create_family_adapter(
    family_id: str, ai_config: dict,
    subagent_enabled: bool = False, plan_mode: bool = False,
    mcp_servers: list[dict] | None = None,  # new param
) -> DeerFlowAdapter:
    ...
```

For non-MCP calls, `mcp_servers=None` and the config is written without the key — backward compatible.

## Why This Matters

The dual-endpoint transport singleton is not optional — MCP's session routing depends on it. A per-request transport instance creates a new session namespace on every GET, making POST routing impossible.

The per-call DB session issue is silent in development (connections stay open longer) but fails under load or with connection pool timeouts in production.

The `__slots__` tenant isolation is the last line of defense against prompt injection targeting multi-tenant data. If the LLM can pass `family_id` as a tool argument, a crafted prompt could exfiltrate another family's financial data.

Treating chat as a DeerFlow skill routes it through skill dispatch, adding unnecessary overhead (skill loading, intent matching, SKILL.md parsing) and creating a confusing abstraction — chat doesn't have "skills" in the DeerFlow sense, it has a conversation loop.

Prior session history shows DeerFlow's global config singleton is not thread-safe — concurrent family requests corrupt the config. The lock + env var + reload workaround was discovered only after multiple failed approaches (session history).

## When to Apply

- Any FastAPI endpoint that opens a long-lived connection (SSE, WebSocket)
- Any MCP server implementation in a multi-tenant context
- Any tool-calling pattern where the LLM supplies arguments that could include identity or authorization claims
- Any adapter or service that is cached and may have configuration-dependent behavior
- When adding a new AI capability: decide upfront whether it is fixed (direct adapter) or skill-based (DeerFlow dispatch)

## Examples

**Orchestrator dispatch — before (chat treated as skill):**

```python
# All capabilities routed through skill dispatch
async for chunk in self.stream_dispatch(capability, message, session_id):
    yield chunk
```

**Orchestrator dispatch — after (chat is fixed capability):**

```python
if capability == "chat":
    session_started = True
    await self.write_session_start(session_id, ...)
    await self._upsert_session(session_id, ...)
    async for chunk in self._chat_adapter.stream(
        family_id, message, web_search=web_search
    ):
        yield chunk
else:
    async for chunk in self.stream_dispatch(capability, message, session_id):
        yield chunk
```

**System prompt — before (flat concatenation):**

```python
full_prompt = system_instructions + "\n\n" + user_message
```

**System prompt — after (XML-tagged separation):**

```python
full_prompt = f"""<system_instructions>
{system_prompt}
</system_instructions>

<user_question>
{user_message}
</user_question>"""
```

**MCP tool — before (DI session, raw errors, family_id in args):**

```python
class MCPSession:
    def __init__(self, db: Session, family_id: str):
        self.db = db

    async def get_assets(self, arguments: dict):
        fid = arguments["family_id"]  # from LLM — prompt injection risk
        return asset_service.get_by_family(self.db, fid)
```

**MCP tool — after (per-call session, sanitized errors, frozen family_id):**

```python
class MCPSession:
    __slots__ = ("_family_id", "server")

    def __init__(self, family_id: str):
        self._family_id = family_id

    async def get_assets(self, arguments: dict):
        with SessionLocal() as db:
            try:
                return asset_service.get_by_family(db, self._family_id)
            except Exception:
                logger.exception("get_assets failed")
                return {"error": "查询失败，请稍后重试"}
```

## Related

- [DeerFlow Adapter Stream Type Mismatch and Security Issues](../integration-issues/deerflow-adapter-stream-type-mismatch-and-security-issues-2026-05-16.md) — stream contract (`AsyncGenerator[str, None]`) and security fixes (path traversal, SSRF) that apply to any adapter layer
- [DeerFlow Harness Silent Fallback and Concurrency Fixes](../integration-issues/deerflow-harness-silent-fallback-and-concurrency-fixes-2026-04-12.md) — prior orchestrator/adapter integration history; the ChatAdapter pattern supersedes the singleton-export workaround
- [Extraction Failure Samples](../test-failures/2026-05-19-extraction-failure-samples.md) — establishes that `SkillConfig.prompt` is dead data and DeerFlow loads SKILL.md independently
