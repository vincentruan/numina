# AI Chat 重构 + MCP 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将 AI 问答（chat）从 SKILL-based 严格私域问答重构为 DeerFlow 标准能力 + MCP 私域数据访问，通过多层租户隔离保障家庭数据安全。

**Architecture:** ChatAdapter 封装 chat 专属逻辑（system_prompt 加载、MCP URL 组装、能力开关），从 Orchestrator 的 chat 分支调用，复用横切关注点（auth/policy/audit/journal/PII）。Backend 嵌入 MCP server 提供 5 个家庭数据查询 tool，URL 路径携带 family_id 实现租户隔离。

**Tech Stack:** Python 3.12 + FastAPI + SSE + Anthropic MCP SDK (`mcp` Python package) + DeerFlow harness + Vue 3 + TypeScript

**Reference Spec:** [`docs/superpowers/specs/2026-05-21-chat-refactor-mcp-design.md`](../specs/2026-05-21-chat-refactor-mcp-design.md)

---

## File Structure

### Backend (新增/修改)

| 文件 | 操作 | 职责 |
|------|------|------|
| `server/apps/backend/app/services/mcp_session.py` | 新增 | MCPSession 类：family_id 绑定 + 5 个 tool handler |
| `server/apps/backend/app/routers/mcp_internal.py` | 新增 | SSE 端点 `/internal/mcp/{family_id}/sse` |
| `server/apps/backend/app/routers/ai_internal.py` | 修改 | 添加 `GET /internal/prompts/{family_id}/chat` 端点 |
| `server/apps/backend/app/services/workspace.py` | 修改 | 添加 `chat_prompt_file` / `get_chat_prompt` / `save/delete_chat_prompt` |
| `server/apps/backend/app/routers/ai_chat.py` | 修改 | `ChatStreamRequest` 添加 `web_search`；代理时透传 |
| `server/apps/backend/app/main.py` | 修改 | 注册 `mcp_internal` 路由 |
| `server/apps/backend/pyproject.toml` | 修改 | 添加 `mcp` Python SDK 依赖 |

### Agent (新增/修改)

| 文件 | 操作 | 职责 |
|------|------|------|
| `server/apps/agent/services/chat_adapter.py` | 新增 | ChatAdapter：system_prompt 加载 + MCP URL 组装 + DeerFlow stream 调用 |
| `server/apps/agent/prompts/chat/default_system_prompt.md` | 新增 | chat 默认 system prompt |
| `server/apps/agent/services/orchestrator.py` | 修改 | `stream_dispatch_events` 添加 chat 分支 + `web_search` 参数 |
| `server/apps/agent/services/deerflow_adapter/family_adapter_cache.py` | 修改 | `_generate_temp_config` 接收 `mcp_servers` 参数 |
| `server/apps/agent/routers/chat.py` | 修改 | `ChatStreamRequest` 添加 `web_search`；传递给 orchestrator |
| `server/apps/agent/app/config.py` | 修改 | 添加 `BACKEND_BASE_URL` 用于 MCP URL 拼接（如未存在） |
| `server/apps/agent/skills/builtin/chat/SKILL.md` | 删除 | chat 不再作为 skill 管理 |

### Frontend (修改)

| 文件 | 操作 | 职责 |
|------|------|------|
| `frontend/apps/main/src/api/ai.ts` | 修改 | `sendChatMessageStream` 添加 `webSearch` 参数 |
| `frontend/apps/main/src/pages/AIChatPage.vue` | 修改 | 添加 webSearch 开关 UI + 传参 |
| `frontend/apps/main/src/i18n/locales/zh-CN.ts` | 修改 | 添加 `chat.webSearchToggle` 等 i18n key |
| `frontend/apps/main/src/i18n/locales/en-US.ts` | 修改 | 同步英文翻译 |

### Tests

| 文件 | 操作 |
|------|------|
| `server/tests/backend/unit/test_mcp_session.py` | 新增 |
| `server/tests/backend/unit/test_workspace_chat_prompt.py` | 新增 |
| `server/tests/backend/integration/test_mcp_sse.py` | 新增 |
| `server/tests/agent/unit/test_chat_adapter.py` | 新增 |
| `server/tests/agent/integration/test_chat_orchestrator_branch.py` | 新增 |

---

## Task 1: 添加 MCP SDK 依赖

**Files:**
- Modify: `server/apps/backend/pyproject.toml`

- [ ] **Step 1: 添加 mcp 依赖**

在 `[project.dependencies]` 节中加入官方 Anthropic MCP Python SDK：

```toml
"mcp>=1.0.0,<2.0.0",
```

- [ ] **Step 2: 安装依赖**

```bash
cd server/apps/backend
uv sync
```

Expected: `Resolved N packages`，无错误。

- [ ] **Step 3: 验证 import**

```bash
cd server/apps/backend
uv run python -c "from mcp.server import Server; from mcp.server.sse import SseServerTransport; print('ok')"
```

Expected: 输出 `ok`。

- [ ] **Step 4: Commit**

```bash
git add server/apps/backend/pyproject.toml server/apps/backend/uv.lock
git commit -m "deps(backend): add mcp Python SDK for internal MCP server"
```

---

## Task 2: Workspace 服务扩展 chat prompt 文件管理

**Files:**
- Modify: `server/apps/backend/app/services/workspace.py`
- Test: `server/tests/backend/unit/test_workspace_chat_prompt.py`

- [ ] **Step 1: 写失败测试**

Create `server/tests/backend/unit/test_workspace_chat_prompt.py`:

```python
"""Unit tests for workspace.py chat prompt management."""
import os
import tempfile
from pathlib import Path

import pytest

from apps.backend.app.services import workspace


@pytest.fixture
def temp_workspace(monkeypatch):
    """Override WORKSPACE_ROOT to a temp dir for isolation."""
    with tempfile.TemporaryDirectory() as tmp:
        from apps.backend.app.config import settings as s
        monkeypatch.setattr(s, "WORKSPACE_ROOT", tmp)
        yield tmp


def test_get_chat_prompt_returns_none_when_missing(temp_workspace):
    assert workspace.get_chat_prompt("100") is None


def test_save_then_get_chat_prompt_round_trip(temp_workspace):
    content = "你是家庭资产助手。"
    workspace.save_chat_prompt("100", content)
    assert workspace.get_chat_prompt("100") == content


def test_get_chat_prompt_strips_yaml_frontmatter(temp_workspace):
    content = "---\nname: chat\n---\n\n你是家庭资产助手。"
    workspace.save_chat_prompt("100", content)
    body = workspace.get_chat_prompt("100")
    assert body is not None
    assert "你是家庭资产助手。" in body
    assert "name: chat" not in body


def test_delete_chat_prompt_removes_file(temp_workspace):
    workspace.save_chat_prompt("100", "test")
    workspace.delete_chat_prompt("100")
    assert workspace.get_chat_prompt("100") is None


def test_delete_chat_prompt_is_noop_when_missing(temp_workspace):
    workspace.delete_chat_prompt("100")  # should not raise


def test_chat_prompt_isolated_per_family(temp_workspace):
    workspace.save_chat_prompt("100", "family A prompt")
    workspace.save_chat_prompt("200", "family B prompt")
    assert workspace.get_chat_prompt("100") == "family A prompt"
    assert workspace.get_chat_prompt("200") == "family B prompt"
```

- [ ] **Step 2: 运行测试验证失败**

```bash
cd server && uv run pytest tests/backend/unit/test_workspace_chat_prompt.py -v
```

Expected: FAIL — `AttributeError: module 'workspace' has no attribute 'get_chat_prompt'`.

- [ ] **Step 3: 在 workspace.py 添加函数**

Append to `server/apps/backend/app/services/workspace.py`:

```python
def chat_prompt_file(family_id: str) -> Path:
    """Return the path to the family's chat prompt override file."""
    return prompts_dir(family_id) / "chat.md"


def get_chat_prompt(family_id: str) -> str | None:
    """Return family's chat prompt override content (body only, no frontmatter), or None."""
    f = chat_prompt_file(family_id)
    if not f.exists():
        return None
    return _strip_frontmatter(f.read_text(encoding="utf-8"))


def save_chat_prompt(family_id: str, content: str) -> None:
    """Write family's chat prompt override file."""
    chat_prompt_file(family_id).write_text(content, encoding="utf-8")


def delete_chat_prompt(family_id: str) -> None:
    """Remove family's chat prompt override file (no-op if absent)."""
    chat_prompt_file(family_id).unlink(missing_ok=True)


def _strip_frontmatter(content: str) -> str:
    """Strip YAML frontmatter from a markdown string, return body only."""
    if not content.startswith("---"):
        return content.strip()
    end = content.find("---", 3)
    if end == -1:
        return content.strip()
    return content[end + 3 :].strip()
```

- [ ] **Step 4: 运行测试验证通过**

```bash
cd server && uv run pytest tests/backend/unit/test_workspace_chat_prompt.py -v
```

Expected: 6 passed.

- [ ] **Step 5: Commit**

```bash
git add server/apps/backend/app/services/workspace.py server/tests/backend/unit/test_workspace_chat_prompt.py
git commit -m "feat(backend): add chat prompt file management to workspace service"
```

---

## Task 3: Backend 内部 API 暴露 chat prompt

**Files:**
- Modify: `server/apps/backend/app/routers/ai_internal.py`

- [ ] **Step 1: 写失败测试**

Create `server/tests/backend/integration/test_internal_chat_prompt_api.py`:

```python
"""Integration test for GET /internal/prompts/{family_id}/chat."""
import tempfile

import pytest
from fastapi.testclient import TestClient

from apps.backend.app.config import settings
from apps.backend.app.main import app
from apps.backend.app.services import workspace


@pytest.fixture
def client(monkeypatch):
    with tempfile.TemporaryDirectory() as tmp:
        monkeypatch.setattr(settings, "WORKSPACE_ROOT", tmp)
        monkeypatch.setattr(settings, "AGENT_INTERNAL_TOKEN", "test-token")
        yield TestClient(app)


def test_get_chat_prompt_returns_null_when_no_override(client):
    resp = client.get(
        "/api/v1/internal/prompts/100/chat",
        headers={"X-Family-Id": "100", "X-Agent-Token": "test-token"},
    )
    assert resp.status_code == 200
    assert resp.json() == {"content": None}


def test_get_chat_prompt_returns_family_override(client):
    workspace.save_chat_prompt("100", "family A custom prompt")
    resp = client.get(
        "/api/v1/internal/prompts/100/chat",
        headers={"X-Family-Id": "100", "X-Agent-Token": "test-token"},
    )
    assert resp.status_code == 200
    assert resp.json() == {"content": "family A custom prompt"}


def test_get_chat_prompt_rejects_invalid_token(client):
    resp = client.get(
        "/api/v1/internal/prompts/100/chat",
        headers={"X-Family-Id": "100", "X-Agent-Token": "wrong-token"},
    )
    assert resp.status_code == 401
```

- [ ] **Step 2: 运行测试验证失败**

```bash
cd server && uv run pytest tests/backend/integration/test_internal_chat_prompt_api.py -v
```

Expected: FAIL — `404 Not Found` on the endpoint.

- [ ] **Step 3: 添加内部端点**

在 `server/apps/backend/app/routers/ai_internal.py` 文件末尾追加：

```python
@router.get("/prompts/{family_id}/chat")
def internal_get_chat_prompt(
    family_id_path: str,
    family_id: str = Depends(verify_agent_token),
):
    """Return family's custom chat system prompt (or null if not set)."""
    # Path family_id_path is informational; auth-derived family_id is authoritative
    from apps.backend.app.services import workspace
    content = workspace.get_chat_prompt(family_id)
    return {"content": content}
```

注意：`verify_agent_token` 从 header 提取 family_id 作为唯一权威来源；path 参数仅用于 URL 一致性。如果 path 和 header 不匹配应拒绝：

```python
@router.get("/prompts/{family_id_path}/chat")
def internal_get_chat_prompt(
    family_id_path: str,
    family_id: str = Depends(verify_agent_token),
):
    if family_id_path != str(family_id):
        raise HTTPException(status_code=403, detail="family_id mismatch")
    from apps.backend.app.services import workspace
    content = workspace.get_chat_prompt(family_id)
    return {"content": content}
```

- [ ] **Step 4: 运行测试验证通过**

```bash
cd server && uv run pytest tests/backend/integration/test_internal_chat_prompt_api.py -v
```

Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
git add server/apps/backend/app/routers/ai_internal.py server/tests/backend/integration/test_internal_chat_prompt_api.py
git commit -m "feat(backend): add internal endpoint for chat prompt override fetch"
```

---

## Task 4: MCP Session 实现（核心隔离层）

**Files:**
- Create: `server/apps/backend/app/services/mcp_session.py`
- Test: `server/tests/backend/unit/test_mcp_session.py`

- [ ] **Step 1: 写失败测试（租户隔离用例）**

Create `server/tests/backend/unit/test_mcp_session.py`:

```python
"""Unit tests for MCPSession — verifies family_id-bound tool isolation."""
import json
from unittest.mock import MagicMock, patch

import pytest

from apps.backend.app.services.mcp_session import MCPSession


@pytest.fixture
def mock_db():
    return MagicMock()


def test_session_binds_family_id_at_construction(mock_db):
    session = MCPSession(family_id="100", db=mock_db)
    assert session.family_id == "100"


def test_session_family_id_is_immutable(mock_db):
    session = MCPSession(family_id="100", db=mock_db)
    with pytest.raises(AttributeError):
        session.family_id = "200"


@pytest.mark.asyncio
async def test_list_tools_returns_five_tools(mock_db):
    session = MCPSession(family_id="100", db=mock_db)
    tools = await session.list_tools()
    names = {t.name for t in tools}
    assert names == {
        "get_family_overview",
        "get_assets",
        "get_liabilities",
        "get_members",
        "get_recent_alerts",
    }


@pytest.mark.asyncio
async def test_no_tool_exposes_family_id_parameter(mock_db):
    session = MCPSession(family_id="100", db=mock_db)
    tools = await session.list_tools()
    for tool in tools:
        schema = tool.inputSchema
        props = schema.get("properties", {}) if isinstance(schema, dict) else {}
        assert "family_id" not in props, f"Tool {tool.name} must not expose family_id"


@pytest.mark.asyncio
async def test_get_family_overview_uses_bound_family_id(mock_db):
    session = MCPSession(family_id="100", db=mock_db)
    with patch("apps.backend.app.services.mcp_session.dashboard_service") as ds:
        ds.get_overview.return_value = {"net_worth": 1000000}
        result = await session.call_tool("get_family_overview", {})
        # _get_mock_user is called with family_id=100, db
        # then dashboard_service.get_overview(db, user)
        ds.get_overview.assert_called_once()
        # Verify result is JSON-serializable text content
        assert "net_worth" in result[0].text


@pytest.mark.asyncio
async def test_get_assets_ignores_caller_family_id_arg(mock_db):
    """Critical: even if LLM somehow sends family_id, it must be ignored."""
    session = MCPSession(family_id="100", db=mock_db)
    with patch("apps.backend.app.services.mcp_session.asset_service") as asv:
        asv.list_assets_for_family.return_value = []
        # Attacker-style call with extra family_id arg
        await session.call_tool("get_assets", {"family_id": "999"})
        # Verify it was called with the bound family_id (100), not the arg (999)
        args, kwargs = asv.list_assets_for_family.call_args
        assert "100" in (args + tuple(kwargs.values())) or kwargs.get("family_id") == "100"
```

- [ ] **Step 2: 运行测试验证失败**

```bash
cd server && uv run pytest tests/backend/unit/test_mcp_session.py -v
```

Expected: FAIL — `ModuleNotFoundError: No module named 'apps.backend.app.services.mcp_session'`.

- [ ] **Step 3: 实现 MCPSession**

Create `server/apps/backend/app/services/mcp_session.py`:

```python
"""MCP Session — family_id-bound tool registry for AI Chat data access.

Tenant isolation guarantees:
- family_id is set at __init__ and frozen via __slots__
- All tool handlers ignore any family_id in tool args
- All SQL queries enforce WHERE family_id = self._family_id at service layer
"""
import json
import logging
from typing import Any

from mcp.server import Server
from mcp.types import TextContent, Tool
from sqlalchemy.orm import Session

from apps.backend.app.models.user import User
from apps.backend.app.services import dashboard as dashboard_service
from apps.backend.app.services import asset as asset_service
from apps.backend.app.services import liability as liability_service
from apps.backend.app.services import family as family_service

logger = logging.getLogger(__name__)


def _get_owner_user(family_id: str, db: Session) -> User:
    """Return the family's owner user for service-layer authorization."""
    user = (
        db.query(User)
        .filter(User.family_id == family_id, User.role == "owner", User.is_active.is_(True))
        .first()
    )
    if not user:
        user = (
            db.query(User)
            .filter(User.family_id == family_id, User.is_active.is_(True))
            .first()
        )
    if not user:
        raise RuntimeError(f"No active member found for family={family_id}")
    return user


class MCPSession:
    """Per-connection MCP session bound to a single family_id.

    Tenant isolation:
    - family_id is captured at construction and frozen via __slots__
    - Tool handlers NEVER read family_id from tool args — only from self
    - All data queries route through service layer which enforces family scope
    """

    __slots__ = ("_family_id", "_db", "_server")

    def __init__(self, family_id: str, db: Session) -> None:
        self._family_id = family_id
        self._db = db
        self._server = Server(f"numina-family-{family_id}")
        self._register_tools()

    @property
    def family_id(self) -> str:
        return self._family_id

    @property
    def server(self) -> Server:
        return self._server

    def _register_tools(self) -> None:
        server = self._server

        @server.list_tools()
        async def _list_tools() -> list[Tool]:
            return await self.list_tools()

        @server.call_tool()
        async def _call_tool(name: str, arguments: dict[str, Any]) -> list[TextContent]:
            return await self.call_tool(name, arguments)

    async def list_tools(self) -> list[Tool]:
        return [
            Tool(
                name="get_family_overview",
                description="获取家庭财务总览：净资产、总资产、总负债、配置占比、近期变化。",
                inputSchema={"type": "object", "properties": {}, "required": []},
            ),
            Tool(
                name="get_assets",
                description="查询家庭资产列表。支持按类别过滤、限制条数。",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "category": {"type": "string", "description": "资产类别（可选）"},
                        "limit": {"type": "integer", "default": 20, "minimum": 1, "maximum": 100},
                    },
                    "required": [],
                },
            ),
            Tool(
                name="get_liabilities",
                description="查询家庭负债列表（贷款、信用卡等）。",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "limit": {"type": "integer", "default": 20, "minimum": 1, "maximum": 100},
                    },
                    "required": [],
                },
            ),
            Tool(
                name="get_members",
                description="查询家庭成员列表。",
                inputSchema={"type": "object", "properties": {}, "required": []},
            ),
            Tool(
                name="get_recent_alerts",
                description="查询家庭最近的资产预警和处置建议。",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "limit": {"type": "integer", "default": 10, "minimum": 1, "maximum": 50},
                    },
                    "required": [],
                },
            ),
        ]

    async def call_tool(self, name: str, arguments: dict[str, Any]) -> list[TextContent]:
        # SECURITY: ignore any family_id in arguments — always use bound self._family_id
        user = _get_owner_user(self._family_id, self._db)
        try:
            if name == "get_family_overview":
                data = dashboard_service.get_overview(self._db, user)
            elif name == "get_assets":
                category = arguments.get("category")
                limit = int(arguments.get("limit", 20))
                data = asset_service.list_assets_for_family(
                    self._db, self._family_id, category=category, limit=limit
                )
            elif name == "get_liabilities":
                limit = int(arguments.get("limit", 20))
                data = liability_service.list_liabilities_for_family(
                    self._db, self._family_id, limit=limit
                )
            elif name == "get_members":
                data = family_service.list_members(self._db, self._family_id)
            elif name == "get_recent_alerts":
                limit = int(arguments.get("limit", 10))
                data = dashboard_service.get_recent_alerts(self._db, user, limit=limit)
            else:
                raise ValueError(f"Unknown tool: {name}")
            logger.info(
                "[mcp_session] family=%s tool=%s args=%s ok",
                self._family_id, name, arguments,
            )
            return [TextContent(type="text", text=json.dumps(data, ensure_ascii=False, default=str))]
        except Exception as e:
            logger.error(
                "[mcp_session] family=%s tool=%s failed: %s",
                self._family_id, name, e,
            )
            return [TextContent(type="text", text=json.dumps({"error": str(e)}, ensure_ascii=False))]
```

注意：`list_assets_for_family` / `list_liabilities_for_family` / `list_members` / `get_recent_alerts` 可能不存在；下一步会检查并补齐。

- [ ] **Step 4: 验证 service 层函数存在**

```bash
cd server && grep -n "def list_assets_for_family\|def list_liabilities_for_family\|def list_members\|def get_recent_alerts" apps/backend/app/services/*.py
```

如果某函数不存在，在对应 service 文件中添加最简实现（仅 family_id 过滤），例如在 `asset.py`：

```python
def list_assets_for_family(
    db: Session,
    family_id: str,
    category: str | None = None,
    limit: int = 20,
) -> list[dict]:
    from apps.backend.app.models.asset import Asset
    from apps.backend.app.models.user import User
    q = (
        db.query(Asset)
        .join(User, Asset.owner_id == User.id)
        .filter(User.family_id == family_id, Asset.is_archived.is_(False))
    )
    if category:
        q = q.filter(Asset.category == category)
    rows = q.limit(limit).all()
    return [
        {
            "id": str(a.id),
            "name": a.name,
            "category": a.category,
            "current_value": float(a.current_value or 0),
        }
        for a in rows
    ]
```

对 `liability.py` / `family.py` / `dashboard.py` 同理。

- [ ] **Step 5: 运行测试验证通过**

```bash
cd server && uv run pytest tests/backend/unit/test_mcp_session.py -v
```

Expected: 6 passed.

- [ ] **Step 6: Commit**

```bash
git add server/apps/backend/app/services/mcp_session.py server/tests/backend/unit/test_mcp_session.py server/apps/backend/app/services/asset.py server/apps/backend/app/services/liability.py server/apps/backend/app/services/family.py server/apps/backend/app/services/dashboard.py
git commit -m "feat(backend): add MCPSession with family_id-bound 5 tools

Tenant isolation: family_id captured at __init__, never read from tool args.
All tool handlers route through service layer with family_id scope."
```

---

## Task 5: MCP SSE 端点（路由层 + 注册）

**Files:**
- Create: `server/apps/backend/app/routers/mcp_internal.py`
- Modify: `server/apps/backend/app/main.py`
- Test: `server/tests/backend/integration/test_mcp_sse.py`

- [ ] **Step 1: 写失败测试**

Create `server/tests/backend/integration/test_mcp_sse.py`:

```python
"""Integration tests for the internal MCP SSE endpoint.

Verifies:
1. URL path includes family_id
2. X-Agent-Token authentication
3. Tenant isolation: connecting as family A cannot see family B's data
"""
import pytest
from fastapi.testclient import TestClient

from apps.backend.app.config import settings
from apps.backend.app.main import app


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setattr(settings, "AGENT_INTERNAL_TOKEN", "test-token")
    return TestClient(app)


def test_mcp_sse_endpoint_rejects_missing_token(client):
    resp = client.get("/api/v1/internal/mcp/100/sse")
    # SSE requires GET; auth failure = 401
    assert resp.status_code == 401


def test_mcp_sse_endpoint_rejects_invalid_token(client):
    resp = client.get(
        "/api/v1/internal/mcp/100/sse",
        headers={"X-Agent-Token": "wrong"},
    )
    assert resp.status_code == 401


def test_mcp_sse_endpoint_accepts_valid_token(client):
    """Endpoint should at least open with valid auth (200 then SSE stream)."""
    # Use stream=True; SSE doesn't return until first event
    with client.stream(
        "GET",
        "/api/v1/internal/mcp/100/sse",
        headers={"X-Agent-Token": "test-token"},
        timeout=2.0,
    ) as resp:
        assert resp.status_code == 200
        assert "text/event-stream" in resp.headers.get("content-type", "")
```

- [ ] **Step 2: 运行测试验证失败**

```bash
cd server && uv run pytest tests/backend/integration/test_mcp_sse.py -v
```

Expected: FAIL — endpoints return 404.

- [ ] **Step 3: 实现 SSE 端点**

Create `server/apps/backend/app/routers/mcp_internal.py`:

```python
"""Internal MCP SSE endpoint — agent → backend tool calls for family data.

Tenant isolation:
- URL path: /internal/mcp/{family_id}/sse — family_id captured here
- Auth: X-Agent-Token shared secret
- Session: MCPSession(family_id) bound to URL path's family_id
"""
import logging

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from apps.backend.app.config import settings
from apps.backend.app.database import get_db
from apps.backend.app.services.mcp_session import MCPSession

router = APIRouter(prefix="/internal/mcp", tags=["internal-mcp"])
logger = logging.getLogger(__name__)


def _verify_token(token: str | None) -> None:
    if not settings.AGENT_INTERNAL_TOKEN:
        raise HTTPException(status_code=503, detail="agent token not configured")
    if not token or token != settings.AGENT_INTERNAL_TOKEN:
        raise HTTPException(status_code=401, detail="invalid agent token")


@router.get("/{family_id}/sse")
async def mcp_sse(
    family_id: str,
    request: Request,
    x_agent_token: str | None = Header(None, alias="X-Agent-Token"),
    db: Session = Depends(get_db),
):
    """SSE endpoint that speaks MCP protocol for the given family_id."""
    _verify_token(x_agent_token)

    from mcp.server.sse import SseServerTransport

    session = MCPSession(family_id=family_id, db=db)
    transport = SseServerTransport(f"/api/v1/internal/mcp/{family_id}/messages")

    async def event_generator():
        try:
            async with transport.connect_sse(
                request.scope, request.receive, request._send
            ) as streams:
                read_stream, write_stream = streams
                init_opts = session.server.create_initialization_options()
                await session.server.run(read_stream, write_stream, init_opts)
        except Exception as e:
            logger.error("[mcp_sse] family=%s connection error: %s", family_id, e)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive"},
    )


@router.post("/{family_id}/messages")
async def mcp_messages(
    family_id: str,
    request: Request,
    x_agent_token: str | None = Header(None, alias="X-Agent-Token"),
):
    """Inbound messages channel for the SSE transport — must match SSE family_id."""
    _verify_token(x_agent_token)
    # The actual handling is delegated to the SSE transport via the session
    # bound on the GET endpoint; this stub returns 202 to satisfy the protocol.
    return {"status": "accepted"}
```

注意：MCP SDK 的 `SseServerTransport` 接口具体使用方式参考 [MCP Python SDK 文档](https://github.com/modelcontextprotocol/python-sdk)，若 API 不同需调整。任务执行时通过 `mcp__plugin_context7_context7__query-docs` 查询最新文档。

- [ ] **Step 4: 注册路由**

Modify `server/apps/backend/app/main.py` — 在 `ai_chat_router` 注册附近添加：

```python
from apps.backend.app.routers import mcp_internal  # noqa: F401
# ...
app.include_router(mcp_internal.router, prefix="/api/v1")
```

- [ ] **Step 5: 运行测试验证通过**

```bash
cd server && uv run pytest tests/backend/integration/test_mcp_sse.py -v
```

Expected: 3 passed。如果第 3 个测试因 SSE 长连接挂起，可改为只断言 status_code 后立即关闭流。

- [ ] **Step 6: Commit**

```bash
git add server/apps/backend/app/routers/mcp_internal.py server/apps/backend/app/main.py server/tests/backend/integration/test_mcp_sse.py
git commit -m "feat(backend): add internal MCP SSE endpoint with family_id URL isolation"
```

---

## Task 6: Agent ChatAdapter — system prompt 加载

**Files:**
- Create: `server/apps/agent/prompts/chat/default_system_prompt.md`
- Create: `server/apps/agent/services/chat_adapter.py`
- Test: `server/tests/agent/unit/test_chat_adapter.py`

- [ ] **Step 1: 创建默认 system prompt 文件**

Create `server/apps/agent/prompts/chat/default_system_prompt.md`:

```markdown
---
name: chat-default-system-prompt
version: 1.0
description: Default system prompt for Numina chat assistant
---

你是 Numina 家庭资产助手。

## 你的能力

- 回答关于用户家庭资产、负债、净资产、配置等问题
- 通过工具查询家庭的实时财务数据
- 回答通用知识问题
- 联网搜索最新信息（如果用户启用了联网）

## 使用工具

- 用户问到家庭财务相关问题时，主动调用工具获取数据
- 基于工具返回的数据给出分析和建议
- 如果数据不足，如实告知

## 回答风格

- 简洁、专业、友好
- 使用观察性语言：「当前」「显示」「建议关注」
- 不提供投资建议或推荐金融产品
- 不对未来收益做确定性承诺
```

- [ ] **Step 2: 写失败测试**

Create `server/tests/agent/unit/test_chat_adapter.py`:

```python
"""Unit tests for ChatAdapter — system prompt loading + MCP URL composition."""
from unittest.mock import AsyncMock, patch

import pytest

from apps.agent.services.chat_adapter import ChatAdapter


@pytest.fixture
def adapter():
    return ChatAdapter(
        backend_base_url="http://backend:8000",
        internal_token="test-token",
    )


def test_default_prompt_loaded_from_file(adapter):
    prompt = adapter._load_default_prompt()
    assert "Numina 家庭资产助手" in prompt
    # frontmatter must be stripped
    assert "---" not in prompt.splitlines()[0]


@pytest.mark.asyncio
async def test_resolve_prompt_uses_family_override_when_present(adapter):
    with patch.object(adapter, "_fetch_family_prompt", new=AsyncMock(return_value="family custom")):
        result = await adapter._resolve_prompt("100")
        assert result == "family custom"


@pytest.mark.asyncio
async def test_resolve_prompt_falls_back_to_default_when_no_override(adapter):
    with patch.object(adapter, "_fetch_family_prompt", new=AsyncMock(return_value=None)):
        result = await adapter._resolve_prompt("100")
        assert "Numina 家庭资产助手" in result


@pytest.mark.asyncio
async def test_resolve_prompt_falls_back_on_fetch_error(adapter):
    with patch.object(adapter, "_fetch_family_prompt", new=AsyncMock(side_effect=Exception("net err"))):
        result = await adapter._resolve_prompt("100")
        assert "Numina 家庭资产助手" in result


def test_mcp_url_contains_family_id(adapter):
    url = adapter._mcp_url("100")
    assert url == "http://backend:8000/api/v1/internal/mcp/100/sse"


def test_mcp_url_rejects_unsafe_family_id(adapter):
    with pytest.raises(ValueError):
        adapter._mcp_url("../etc/passwd")
```

- [ ] **Step 3: 运行测试验证失败**

```bash
cd server && uv run pytest tests/agent/unit/test_chat_adapter.py -v
```

Expected: FAIL — `ModuleNotFoundError`.

- [ ] **Step 4: 实现 ChatAdapter（仅 prompt + URL 部分）**

Create `server/apps/agent/services/chat_adapter.py`:

```python
"""ChatAdapter — encapsulates chat-specific concerns.

Responsibilities:
- Load chat system prompt (family override → default fallback)
- Compose MCP SSE URL with family_id in path
- Stream events via DeerFlow with MCP server injected

Does NOT handle:
- Auth, policy, audit, journal, PII (orchestrator's responsibility)
"""
import logging
import re
from collections.abc import AsyncGenerator
from pathlib import Path
from typing import Any

import httpx

from apps.agent.services.deerflow_adapter.adapter import StreamChunk

logger = logging.getLogger(__name__)

_SAFE_ID_PATTERN = re.compile(r"^[A-Za-z0-9_\-]+$")
_PROMPT_DIR = Path(__file__).resolve().parent.parent / "prompts" / "chat"


class ChatAdapter:
    def __init__(self, backend_base_url: str, internal_token: str) -> None:
        self._backend_base_url = backend_base_url.rstrip("/")
        self._internal_token = internal_token

    def _mcp_url(self, family_id: str) -> str:
        if not _SAFE_ID_PATTERN.match(family_id):
            raise ValueError(f"Invalid family_id: {family_id!r}")
        return f"{self._backend_base_url}/api/v1/internal/mcp/{family_id}/sse"

    def _load_default_prompt(self) -> str:
        path = _PROMPT_DIR / "default_system_prompt.md"
        raw = path.read_text(encoding="utf-8")
        return _strip_frontmatter(raw)

    async def _fetch_family_prompt(self, family_id: str) -> str | None:
        url = f"{self._backend_base_url}/api/v1/internal/prompts/{family_id}/chat"
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(
                url,
                headers={
                    "X-Agent-Token": self._internal_token,
                    "X-Family-Id": family_id,
                },
            )
            resp.raise_for_status()
            data = resp.json()
            return data.get("content")

    async def _resolve_prompt(self, family_id: str) -> str:
        try:
            override = await self._fetch_family_prompt(family_id)
            if override:
                return override
        except Exception as e:
            logger.warning("[chat_adapter] fetch family prompt failed family=%s: %s", family_id, e)
        return self._load_default_prompt()

    async def stream(
        self,
        family_id: str,
        question: str,
        thread_id: str,
        ai_config: dict[str, Any],
        deep_think: bool = False,
        web_search: bool = False,
    ) -> AsyncGenerator[StreamChunk, None]:
        """Implemented in Task 8 — orchestrator integration."""
        raise NotImplementedError("stream() implemented in Task 8")


def _strip_frontmatter(content: str) -> str:
    if not content.startswith("---"):
        return content.strip()
    end = content.find("---", 3)
    if end == -1:
        return content.strip()
    return content[end + 3 :].strip()
```

- [ ] **Step 5: 运行测试验证通过**

```bash
cd server && uv run pytest tests/agent/unit/test_chat_adapter.py -v
```

Expected: 6 passed.

- [ ] **Step 6: Commit**

```bash
git add server/apps/agent/services/chat_adapter.py server/apps/agent/prompts/chat/default_system_prompt.md server/tests/agent/unit/test_chat_adapter.py
git commit -m "feat(agent): add ChatAdapter scaffold with prompt loading and MCP URL composition"
```

---

## Task 7: family_adapter_cache 支持 MCP 注入

**Files:**
- Modify: `server/apps/agent/services/deerflow_adapter/family_adapter_cache.py`
- Test: 扩展 `server/tests/agent/unit/test_family_adapter_cache.py`（如不存在则创建最小测试）

- [ ] **Step 1: 写失败测试**

Append to `server/tests/agent/unit/test_family_adapter_cache.py` (创建文件如不存在):

```python
"""Unit tests for _generate_temp_config — verifies MCP server injection."""
import tempfile
from pathlib import Path

import yaml

from apps.agent.services.deerflow_adapter.family_adapter_cache import _generate_temp_config


def _base_config_dir() -> str:
    """Return agent's deerflow_config directory absolute path."""
    return str(Path(__file__).resolve().parents[3] / "apps" / "agent" / "deerflow_config")


def test_temp_config_includes_mcp_servers_when_provided():
    ai_config = {
        "api_key": "sk-x",
        "ai_model_id": "gpt-4",
        "ai_provider": "openai",
    }
    mcp_servers = [
        {
            "name": "numina-family-data",
            "url": "http://backend:8000/api/v1/internal/mcp/100/sse",
            "transport": "sse",
            "headers": {"X-Agent-Token": "secret"},
        }
    ]
    path = _generate_temp_config(
        _base_config_dir(),
        ai_config,
        family_id="100",
        mcp_servers=mcp_servers,
    )
    with open(path, encoding="utf-8") as f:
        cfg = yaml.safe_load(f)
    assert cfg.get("mcp_servers") == mcp_servers


def test_temp_config_omits_mcp_servers_when_not_provided():
    ai_config = {
        "api_key": "sk-x",
        "ai_model_id": "gpt-4",
        "ai_provider": "openai",
    }
    path = _generate_temp_config(_base_config_dir(), ai_config, family_id="100")
    with open(path, encoding="utf-8") as f:
        cfg = yaml.safe_load(f)
    assert "mcp_servers" not in cfg
```

- [ ] **Step 2: 运行测试验证失败**

```bash
cd server && uv run pytest tests/agent/unit/test_family_adapter_cache.py -v
```

Expected: FAIL — `_generate_temp_config` 不接受 `mcp_servers` kwarg。

- [ ] **Step 3: 修改 _generate_temp_config 签名**

In `server/apps/agent/services/deerflow_adapter/family_adapter_cache.py`, modify signature and body:

```python
def _generate_temp_config(
    base_config_dir: str,
    ai_config: dict[str, Any],
    family_id: str = "",
    mcp_servers: list[dict[str, Any]] | None = None,
) -> Path:
    # ... existing body up to before `# 写入临时文件` ...

    # MCP server injection (chat capability + future capabilities)
    if mcp_servers:
        config["mcp_servers"] = mcp_servers

    # ... existing write code ...
```

同样修改 `get_family_adapter` 接收 `mcp_servers` 并传入：

```python
def get_family_adapter(
    family_id: str,
    ai_config: dict[str, Any],
    base_config_dir: str | None = None,
    timeout_seconds: int = 120,
    subagent_enabled: bool = False,
    plan_mode: bool = False,
    mcp_servers: list[dict[str, Any]] | None = None,
) -> tuple[DeerFlowClient, Path]:
    # ...
    cache_key: tuple[str, str, bool, bool, str] = (
        family_id, config_id, subagent_enabled, plan_mode,
        _mcp_cache_key(mcp_servers),
    )
    # ...
    temp_config_path = _generate_temp_config(
        base_config_dir, ai_config, family_id=family_id, mcp_servers=mcp_servers,
    )
    # ...
```

并添加辅助：

```python
def _mcp_cache_key(mcp_servers: list[dict[str, Any]] | None) -> str:
    """Stable cache key fragment for mcp_servers list."""
    if not mcp_servers:
        return ""
    import hashlib
    import json
    blob = json.dumps(mcp_servers, sort_keys=True, ensure_ascii=False)
    return hashlib.sha1(blob.encode("utf-8")).hexdigest()[:8]
```

并更新缓存类型注解：

```python
_adapter_cache: OrderedDict[
    tuple[str, str, bool, bool, str],
    tuple[DeerFlowClient, Path] | None,
] = OrderedDict()
```

并更新 `invalidate_family_adapter` 和 `invalidate_family_adapter_cache` 的索引检查（任何包含 family_id 的 key）— 这部分代码已写为 `k[0] == family_id`，所以仍正确，仅 key 长度多一项。

- [ ] **Step 4: 同步修改 adapter 调用方**

In `server/apps/agent/services/deerflow_adapter/adapter.py`, `create_family_adapter`:

```python
def create_family_adapter(
    family_id: str,
    ai_config: dict[str, Any],
    timeout_seconds: int = 120,
    subagent_enabled: bool = False,
    plan_mode: bool = False,
    mcp_servers: list[dict[str, Any]] | None = None,
):
    client, _ = get_family_adapter(
        family_id, ai_config, timeout_seconds=timeout_seconds,
        subagent_enabled=subagent_enabled, plan_mode=plan_mode,
        mcp_servers=mcp_servers,
    )
    return DeerFlowAdapter(client, timeout_seconds=timeout_seconds)
```

- [ ] **Step 5: 运行测试验证通过**

```bash
cd server && uv run pytest tests/agent/unit/test_family_adapter_cache.py -v
```

Expected: 2 passed.

- [ ] **Step 6: 回归测试现有 orchestrator 单测**

```bash
cd server && uv run pytest tests/agent/unit/test_capability_registry.py tests/agent/unit/ -v 2>&1 | tail -30
```

Expected: 现有测试全通过（参数仅为可选 kwarg，向后兼容）。

- [ ] **Step 7: Commit**

```bash
git add server/apps/agent/services/deerflow_adapter/family_adapter_cache.py server/apps/agent/services/deerflow_adapter/adapter.py server/tests/agent/unit/test_family_adapter_cache.py
git commit -m "feat(agent): _generate_temp_config accepts mcp_servers for DeerFlow injection"
```

---

## Task 8: ChatAdapter.stream() 完整实现

**Files:**
- Modify: `server/apps/agent/services/chat_adapter.py`
- Test: 扩展 `server/tests/agent/unit/test_chat_adapter.py`

- [ ] **Step 1: 写失败测试**

Append to `server/tests/agent/unit/test_chat_adapter.py`:

```python
@pytest.mark.asyncio
async def test_stream_injects_mcp_server_into_adapter():
    """Adapter.stream() must call create_family_adapter with mcp_servers list."""
    from apps.agent.services.deerflow_adapter.adapter import StreamChunk

    adapter = ChatAdapter("http://backend:8000", "secret-token")

    captured: dict = {}

    def fake_create(*args, **kwargs):
        captured["kwargs"] = kwargs
        mock_adapter = AsyncMock()

        async def fake_stream(*a, **kw):
            yield StreamChunk(type="text", content="hello")
        mock_adapter.stream_dispatch = fake_stream
        return mock_adapter

    with (
        patch("apps.agent.services.chat_adapter._create_family_adapter", side_effect=fake_create),
        patch.object(adapter, "_resolve_prompt", new=AsyncMock(return_value="sys")),
    ):
        chunks: list = []
        async for c in adapter.stream(
            family_id="100",
            question="hi",
            thread_id="t1",
            ai_config={"api_key": "k", "ai_model_id": "m", "ai_provider": "openai"},
            deep_think=False,
            web_search=False,
        ):
            chunks.append(c)

    assert len(chunks) == 1 and chunks[0].content == "hello"
    mcp_servers = captured["kwargs"].get("mcp_servers")
    assert mcp_servers and mcp_servers[0]["url"].endswith("/internal/mcp/100/sse")
    assert mcp_servers[0]["headers"]["X-Agent-Token"] == "secret-token"


@pytest.mark.asyncio
async def test_stream_deep_think_enables_subagent_and_plan_mode():
    adapter = ChatAdapter("http://backend:8000", "secret-token")
    captured: dict = {}

    def fake_create(*args, **kwargs):
        captured["kwargs"] = kwargs
        mock_adapter = AsyncMock()

        async def fake_stream(*a, **kw):
            yield  # generator with no items
        mock_adapter.stream_dispatch = fake_stream
        return mock_adapter

    with (
        patch("apps.agent.services.chat_adapter._create_family_adapter", side_effect=fake_create),
        patch.object(adapter, "_resolve_prompt", new=AsyncMock(return_value="sys")),
    ):
        async for _ in adapter.stream(
            family_id="100",
            question="hi",
            thread_id="t1",
            ai_config={"api_key": "k", "ai_model_id": "m", "ai_provider": "openai"},
            deep_think=True,
            web_search=False,
        ):
            break

    kw = captured["kwargs"]
    assert kw.get("subagent_enabled") is True
    assert kw.get("plan_mode") is True
```

- [ ] **Step 2: 运行测试验证失败**

```bash
cd server && uv run pytest tests/agent/unit/test_chat_adapter.py -v
```

Expected: 2 new tests fail with `NotImplementedError`.

- [ ] **Step 3: 实现 stream()**

Replace the stub in `server/apps/agent/services/chat_adapter.py`:

```python
from apps.agent.services.deerflow_adapter.adapter import (
    create_family_adapter as _create_family_adapter,
)
from apps.agent.schemas.context import FamilyContext


class ChatAdapter:
    # ... existing __init__ and helpers unchanged ...

    async def stream(
        self,
        family_id: str,
        question: str,
        thread_id: str,
        ai_config: dict[str, Any],
        deep_think: bool = False,
        web_search: bool = False,
        enable_thinking: bool = False,
    ) -> AsyncGenerator[StreamChunk, None]:
        system_prompt = await self._resolve_prompt(family_id)
        mcp_servers = [
            {
                "name": "numina-family-data",
                "url": self._mcp_url(family_id),
                "transport": "sse",
                "headers": {"X-Agent-Token": self._internal_token},
            }
        ]

        adapter = _create_family_adapter(
            family_id=family_id,
            ai_config=ai_config,
            timeout_seconds=int(ai_config.get("timeout_seconds", 60)),
            subagent_enabled=deep_think,
            plan_mode=deep_think,
            mcp_servers=mcp_servers,
        )

        # Empty FamilyContext — chat does NOT pre-fetch; data comes via MCP
        context = FamilyContext(family_id=family_id, free_text=question)
        # Inject system_prompt and web_search via context's extra slot (next step covers harness wiring)
        extra: dict[str, Any] = {
            "system_prompt": system_prompt,
            "web_search": web_search,
        }
        async for chunk in adapter.stream_dispatch(
            "chat",
            context,
            thread_id,
            enable_thinking=enable_thinking or deep_think,
            extra=extra,
        ):
            yield chunk
```

注意：`stream_dispatch` 当前可能不接受 `extra` 参数。需要在 `adapter.py` 的 `stream_dispatch` 签名追加 `extra: dict | None = None` 并向下传到 DeerFlowClient。如果 DeerFlow 不直接支持 extra，可将 `system_prompt` 注入到 `context.free_text` 之前作为 system 角色消息，或通过 DeerFlow 的 `system_message` 参数。具体接入方式参考 `deerflow_config/HARNESS_API.md`。

- [ ] **Step 4: 适配 stream_dispatch 接收 extra**

In `server/apps/agent/services/deerflow_adapter/adapter.py`, `stream_dispatch`:

```python
async def stream_dispatch(
    self,
    skill_name: str,
    context: "RedactedContext | FamilyContext",
    thread_id: str,
    enable_thinking: bool = False,
    extra: dict[str, Any] | None = None,
) -> AsyncGenerator[StreamChunk, None]:
    # ...
    # Pass system_prompt / web_search to underlying DeerFlowClient.stream_chat()
    # via additional kwargs supported by harness API.
    extra = extra or {}
    # ... existing call updated to forward extra fields ...
```

具体 harness API 见 `deerflow_config/HARNESS_API.md`。如果 DeerFlow 不支持运行时 system_prompt 注入，则在 `_generate_temp_config` 中把 system_prompt 写入 `config["system_prompt"]` 字段，并在 ChatAdapter 中将 system_prompt 通过 ai_config 传入（因为每次 stream 都生成 temp_config）。

- [ ] **Step 5: 运行测试验证通过**

```bash
cd server && uv run pytest tests/agent/unit/test_chat_adapter.py -v
```

Expected: 8 passed.

- [ ] **Step 6: Commit**

```bash
git add server/apps/agent/services/chat_adapter.py server/apps/agent/services/deerflow_adapter/adapter.py server/tests/agent/unit/test_chat_adapter.py
git commit -m "feat(agent): implement ChatAdapter.stream with MCP + deep_think wiring"
```

---

## Task 9: Orchestrator 添加 chat 分支

**Files:**
- Modify: `server/apps/agent/services/orchestrator.py`
- Test: `server/tests/agent/integration/test_chat_orchestrator_branch.py`

- [ ] **Step 1: 写失败测试**

Create `server/tests/agent/integration/test_chat_orchestrator_branch.py`:

```python
"""Integration test: orchestrator dispatches chat via ChatAdapter, not _build_context."""
from unittest.mock import AsyncMock, patch

import pytest

from apps.agent.services.deerflow_adapter.adapter import StreamChunk
from apps.agent.services.orchestrator import orchestrator


@pytest.mark.asyncio
async def test_chat_branch_uses_chat_adapter_not_build_context(monkeypatch):
    """chat capability must skip _build_context and route via ChatAdapter."""
    chat_called = {"called": False, "web_search": None}

    async def fake_chat_stream(**kwargs):
        chat_called["called"] = True
        chat_called["web_search"] = kwargs.get("web_search")
        yield StreamChunk(type="text", content="answer")

    build_context_called = {"called": False}

    async def fake_build_context(*args, **kwargs):
        build_context_called["called"] = True
        from apps.agent.schemas.context import FamilyContext
        return FamilyContext(family_id="100")

    monkeypatch.setattr(orchestrator._chat_adapter, "stream", fake_chat_stream)
    monkeypatch.setattr(orchestrator, "_build_context", fake_build_context)

    # Minimal stub config so the pipeline can proceed
    with patch("apps.agent.services.orchestrator.BackendClient") as bc_cls:
        bc = bc_cls.return_value
        bc.get_family_ai_configs = AsyncMock(return_value={
            "ai_enabled": True,
            "allowed_capabilities": ["chat"],
            "admin_only_capabilities": [],
            "member_role": "admin",
            "providers": [{
                "config_id": "cfg1",
                "ai_model_id": "gpt-4",
                "ai_provider": "openai",
                "api_key": "k",
                "model_1_capabilities": ["text_generation"],
            }],
        })
        bc.reset_circuit_success = AsyncMock()

        chunks = []
        async for line in orchestrator.stream_dispatch_events(
            capability="chat",
            family_id="100",
            task_id="t-1",
            user_id="u-1",
            thread_id="th-1",
            free_text="hi",
            enable_thinking_override=False,
            web_search=True,
        ):
            chunks.append(line)

    assert chat_called["called"] is True
    assert chat_called["web_search"] is True
    assert build_context_called["called"] is False
```

- [ ] **Step 2: 运行测试验证失败**

```bash
cd server && uv run pytest tests/agent/integration/test_chat_orchestrator_branch.py -v
```

Expected: FAIL — `web_search` kwarg unknown / `_chat_adapter` 不存在。

- [ ] **Step 3: 修改 Orchestrator**

In `server/apps/agent/services/orchestrator.py`:

1. 在文件顶部导入并实例化 ChatAdapter：

```python
from apps.agent.services.chat_adapter import ChatAdapter
```

2. 在 `Orchestrator.__init__` 添加（或加 module-level 单例）：

```python
class Orchestrator:
    def __init__(self) -> None:
        self._chat_adapter = ChatAdapter(
            backend_base_url=settings.BACKEND_BASE_URL,
            internal_token=settings.AGENT_INTERNAL_TOKEN,
        )
```

并在文件末尾 `orchestrator = Orchestrator()` 保持。

3. 修改 `stream_dispatch_events` 和 `_stream_dispatch_event_lines` 签名追加 `web_search`：

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
    web_search: bool = False,
) -> AsyncGenerator[str, None]:
    try:
        async for event_line in self._stream_dispatch_event_lines(
            capability=capability,
            family_id=family_id,
            task_id=task_id,
            user_id=user_id,
            thread_id=thread_id,
            free_text=free_text,
            enable_thinking_override=enable_thinking_override,
            web_search=web_search,
        ):
            yield event_line
    except Exception as e:
        logger.error("[orchestrator] stream_dispatch_events failed: %s", e)
        builder = EventStreamBuilder(capability, task_id)
        yield builder.error("暂时无法完成分析，请稍后重试。").to_ndjson()
```

4. 在 `_stream_dispatch_event_lines` 中，找到 `context = await self._build_context(...)` 这一行，将其与后续的 DeerFlow 调度块替换为分支逻辑：

```python
# After policy_guard check and journal write_session_start:
if capability == "chat":
    # Chat: skip _build_context; data flows through MCP at runtime
    redacted_free_text = pii_redactor.redact_text(free_text or "")[0]
    # Session start was already written; write user message
    if redacted_free_text:
        session_journal.write_user_message(
            family_id=family_id,
            session_id=effective_thread_id,
            user_id=user_id,
            content=redacted_free_text,
        )
    try:
        async for chunk in self._chat_adapter.stream(
            family_id=family_id,
            question=redacted_free_text,
            thread_id=effective_thread_id,
            ai_config=selected_provider,
            deep_think=bool(enable_thinking_override),
            web_search=web_search,
            enable_thinking=enable_thinking,
        ):
            async for event_line in self._chunk_to_event_lines(
                builder, chunk, answer_parts, family_id, effective_thread_id
            ):
                yield event_line
        elapsed_ms = int(time.monotonic() * 1000) - start_ms
        yield builder.end("".join(answer_parts), execution_time_ms=elapsed_ms).to_ndjson()
        if config_id:
            _fire_and_forget(client.reset_circuit_success(config_id))
        return
    except DeerFlowTimeoutError:
        success = False
        error_type = "DeerFlowTimeoutError"
        yield builder.error("AI 响应超时，请稍后重试。", code="deerflow_timeout").to_ndjson()
        return
    except Exception as e:
        logger.error("[orchestrator] chat stream failed: %s", e)
        success = False
        error_type = type(e).__name__
        if config_id:
            _fire_and_forget(client.report_circuit_event(config_id, 500))
        yield builder.error("AI 服务暂时不可用，请稍后重试。", code="deerflow_error").to_ndjson()
        return

# else: existing skill-based path (unchanged)
context = await self._build_context(client, family_id, free_text=free_text)
redacted_context = pii_redactor.redact(context)
# ... rest of existing code ...
```

注意：journal/session_started 设置需要在分支之前完成；保留 finally 块统一处理 write_session_end + audit。

- [ ] **Step 4: Agent config 添加 BACKEND_BASE_URL**

如果 `server/apps/agent/app/config.py` 尚无 `BACKEND_BASE_URL`，添加：

```python
class AgentSettings(BaseSettings):
    # ...
    BACKEND_BASE_URL: str = "http://backend:8000"
```

- [ ] **Step 5: 运行测试验证通过**

```bash
cd server && uv run pytest tests/agent/integration/test_chat_orchestrator_branch.py -v
```

Expected: 1 passed.

- [ ] **Step 6: 跑全套 agent 测试确保无回归**

```bash
cd server && uv run pytest tests/agent/ -v 2>&1 | tail -40
```

Expected: 所有原有测试通过。

- [ ] **Step 7: Commit**

```bash
git add server/apps/agent/services/orchestrator.py server/apps/agent/app/config.py server/tests/agent/integration/test_chat_orchestrator_branch.py
git commit -m "feat(agent): orchestrator routes chat through ChatAdapter, skips _build_context"
```

---

## Task 10: Agent chat router 接收 web_search

**Files:**
- Modify: `server/apps/agent/routers/chat.py`

- [ ] **Step 1: 写失败测试**

Append or create `server/tests/agent/unit/test_chat_router.py`:

```python
"""Unit test: chat router forwards web_search to orchestrator."""
from unittest.mock import patch

from fastapi.testclient import TestClient

from apps.agent.app.main import app
from apps.agent.app.config import settings


def test_ask_stream_forwards_web_search(monkeypatch):
    monkeypatch.setattr(settings, "AGENT_INTERNAL_TOKEN", "tok")
    captured = {}

    async def fake_stream(**kwargs):
        captured.update(kwargs)
        yield b'{"type":"capability.end"}\n'

    with patch("apps.agent.routers.chat.orchestrator.stream_dispatch_events", new=fake_stream):
        client = TestClient(app)
        resp = client.post(
            "/chat/ask/stream",
            json={"question": "hi", "deep_think": True, "web_search": True},
            headers={
                "X-Family-Id": "100",
                "X-Agent-Token": "tok",
                "X-User-Id": "u1",
                "X-Thread-Id": "t1",
            },
        )
        assert resp.status_code == 200
    assert captured.get("web_search") is True
    assert captured.get("enable_thinking_override") is True
```

- [ ] **Step 2: 运行测试验证失败**

```bash
cd server && uv run pytest tests/agent/unit/test_chat_router.py -v
```

Expected: FAIL — `web_search` not in `ChatStreamRequest`.

- [ ] **Step 3: 修改 chat router**

In `server/apps/agent/routers/chat.py`:

```python
class ChatStreamRequest(BaseModel):
    question: str
    deep_think: bool = False
    web_search: bool = False


@router.post("/ask/stream")
async def ask_stream(
    body: ChatStreamRequest,
    x_family_id: str = Header(..., alias="X-Family-Id"),
    x_agent_token: str = Header(..., alias="X-Agent-Token"),
    x_user_id: str = Header(None, alias="X-User-Id"),
    x_thread_id: str = Header(None, alias="X-Thread-Id"),
):
    if x_agent_token != settings.AGENT_INTERNAL_TOKEN:
        raise HTTPException(status_code=401, detail="invalid token")

    async def generate():
        task_id = str(uuid.uuid4())
        event_builder = EventStreamBuilder(capability_id="chat", task_id=task_id)
        try:
            async for event_line in orchestrator.stream_dispatch_events(
                capability="chat",
                family_id=x_family_id,
                task_id=task_id,
                user_id=x_user_id,
                thread_id=x_thread_id,
                free_text=body.question,
                enable_thinking_override=body.deep_think,
                web_search=body.web_search,
            ):
                yield event_line
        except Exception as e:
            logger.error(f"[chat/stream] unhandled error: {e}")
            yield event_builder.error(
                "抱歉，AI 服务暂时不可用，请稍后重试。",
                code="chat_stream_error",
            ).to_ndjson()

    return StreamingResponse(generate(), media_type="application/x-ndjson; charset=utf-8")
```

- [ ] **Step 4: 运行测试验证通过**

```bash
cd server && uv run pytest tests/agent/unit/test_chat_router.py -v
```

Expected: 1 passed.

- [ ] **Step 5: Commit**

```bash
git add server/apps/agent/routers/chat.py server/tests/agent/unit/test_chat_router.py
git commit -m "feat(agent): chat router accepts and forwards web_search parameter"
```

---

## Task 11: Backend chat 代理透传 web_search

**Files:**
- Modify: `server/apps/backend/app/routers/ai_chat.py`

- [ ] **Step 1: 写失败测试**

Create `server/tests/backend/integration/test_chat_proxy_web_search.py`:

```python
"""Integration: backend /api/v1/ai/chat/stream forwards web_search to agent."""
from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient

from apps.backend.app.main import app


def test_chat_stream_forwards_web_search(monkeypatch, db_session, current_user_fixture):
    captured = {}

    class FakeStream:
        async def __aenter__(self):
            return self
        async def __aexit__(self, *args):
            pass
        async def aiter_text(self):
            yield ""

    async def fake_post(*args, **kwargs):
        captured["json"] = kwargs.get("json")
        return FakeStream()

    with patch("apps.backend.app.routers.ai_chat.httpx.AsyncClient") as client_cls:
        client_cls.return_value.__aenter__ = AsyncMock(return_value=client_cls.return_value)
        client_cls.return_value.__aexit__ = AsyncMock(return_value=False)
        client_cls.return_value.stream = lambda *a, **kw: (captured.setdefault("json", kw.get("json")) or FakeStream())

        client = TestClient(app)
        # ... auth setup via fixtures ...
        resp = client.post(
            "/api/v1/ai/chat/stream",
            json={"question": "hi", "deep_think": True, "web_search": True},
        )
    assert captured.get("json", {}).get("web_search") is True
```

注意：完整的 backend 集成测试需要 auth fixture；如果工程没有现成 fixture，可以改为单元测试只覆盖 `proxy_stream` 内部 `client.stream(json=...)` 调用，跳过 auth 路径。

- [ ] **Step 2: 运行测试验证失败**

Expected: FAIL — `web_search` not in `ChatStreamRequest`.

- [ ] **Step 3: 修改 ai_chat.py**

```python
class ChatStreamRequest(BaseModel):
    question: str
    deep_think: bool = False
    web_search: bool = False
    session_id: str | None = None
    # validator unchanged
```

并修改 `proxy_stream` 中的 agent 调用：

```python
client.stream(
    "POST",
    f"{settings.AGENT_BASE_URL}/chat/ask/stream",
    json={
        "question": body.question,
        "deep_think": body.deep_think,
        "web_search": body.web_search,
    },
    headers={...},
    timeout=None,
)
```

- [ ] **Step 4: 运行测试验证通过**

```bash
cd server && uv run pytest tests/backend/integration/test_chat_proxy_web_search.py -v
```

Expected: 1 passed。

- [ ] **Step 5: Commit**

```bash
git add server/apps/backend/app/routers/ai_chat.py server/tests/backend/integration/test_chat_proxy_web_search.py
git commit -m "feat(backend): chat proxy forwards web_search to agent"
```

---

## Task 12: 前端 sendChatMessageStream 接收 webSearch 参数

**Files:**
- Modify: `frontend/apps/main/src/api/ai.ts`

- [ ] **Step 1: 添加 webSearch 参数**

In `frontend/apps/main/src/api/ai.ts`, replace `sendChatMessageStream`:

```typescript
export async function sendChatMessageStream(
  question: string,
  deepThink: boolean,
  webSearch: boolean,
  signal?: AbortSignal,
  sessionId?: string,
): Promise<ReadableStreamDefaultReader<Uint8Array>> {
  const headers: Record<string, string> = { 'Content-Type': 'application/json' }
  if (sessionId) headers['X-Thread-Id'] = sessionId
  const body = JSON.stringify({ question, deep_think: deepThink, web_search: webSearch })

  let res = await fetch('/api/v1/ai/chat/stream', {
    method: 'POST',
    headers,
    credentials: 'include',
    body,
    signal,
  })

  if (res.status === 401) {
    try {
      await refreshTokenIfNeeded()
    } catch {
      throw new Error('401')
    }
    res = await fetch('/api/v1/ai/chat/stream', {
      method: 'POST',
      headers,
      credentials: 'include',
      body,
      signal,
    })
  }

  if (!res.ok) throw new Error(`${res.status}`)
  if (!res.body) throw new Error('streaming_not_supported')
  return res.body.getReader()
}
```

- [ ] **Step 2: 跑类型检查**

```bash
cd frontend/apps/main && npm run typecheck
```

Expected: FAIL — `AIChatPage.vue` 调用处少传 `webSearch`。这是预期的，会在 Task 13 修复。

- [ ] **Step 3: Commit**

```bash
git add frontend/apps/main/src/api/ai.ts
git commit -m "feat(frontend): sendChatMessageStream accepts webSearch parameter"
```

---

## Task 13: 前端 AIChatPage 添加 webSearch 开关 UI

**Files:**
- Modify: `frontend/apps/main/src/pages/AIChatPage.vue`
- Modify: `frontend/apps/main/src/i18n/locales/zh-CN.ts`
- Modify: `frontend/apps/main/src/i18n/locales/en-US.ts`

- [ ] **Step 1: 添加 i18n keys**

In `frontend/apps/main/src/i18n/locales/zh-CN.ts`, find the `chat` namespace and add:

```ts
chat: {
  // ... existing keys ...
  webSearchToggle: '联网搜索',
  webSearchHint: '允许 AI 联网获取最新信息',
}
```

In `frontend/apps/main/src/i18n/locales/en-US.ts`:

```ts
chat: {
  // ...
  webSearchToggle: 'Web search',
  webSearchHint: 'Allow AI to fetch fresh info from the web',
}
```

- [ ] **Step 2: 找到 AIChatPage 中 deepThink 开关位置**

```bash
grep -n "deepThink\|deep_think" frontend/apps/main/src/pages/AIChatPage.vue
```

记录开关 UI 块的行号。

- [ ] **Step 3: 添加 webSearch ref + UI**

In `frontend/apps/main/src/pages/AIChatPage.vue`:

```vue
<script setup lang="ts">
// ... existing imports ...
const deepThinkEnabled = ref(false)
const webSearchEnabled = ref(false)
// ...
</script>

<template>
  <!-- ... existing deepThink switch ... -->
  <div class="toggle-row">
    <span class="toggle-label">{{ t('chat.webSearchToggle') }}</span>
    <van-switch v-model="webSearchEnabled" size="20px" />
  </div>
</template>
```

- [ ] **Step 4: 传递 webSearchEnabled 到 sendChatMessageStream**

找到 `sendChatMessageStream` 调用位置（应该在 `submitQuestion` 或类似处理函数中）：

```ts
const reader = await sendChatMessageStream(
  question,
  deepThinkEnabled.value,
  webSearchEnabled.value,
  abortController.signal,
  sessionId,
)
```

- [ ] **Step 5: 类型检查通过**

```bash
cd frontend/apps/main && npm run typecheck
```

Expected: 0 errors.

- [ ] **Step 6: 跑前端测试**

```bash
cd frontend/apps/main && npm run test:run 2>&1 | tail -20
```

Expected: 通过（或与原 baseline 一致）。

- [ ] **Step 7: Commit**

```bash
git add frontend/apps/main/src/pages/AIChatPage.vue frontend/apps/main/src/i18n/locales/zh-CN.ts frontend/apps/main/src/i18n/locales/en-US.ts
git commit -m "feat(frontend): add web search toggle to AIChatPage with i18n"
```

---

## Task 14: 删除 chat SKILL.md + 从 CapabilityRegistry 中确认 chat 不在 builtin 列表

**Files:**
- Delete: `server/apps/agent/skills/builtin/chat/SKILL.md`
- Delete: `server/apps/agent/skills/builtin/chat/` (空目录)
- Verify: `server/apps/agent/services/capability_registry.py` (chat 应在 FIXED_CAPABILITY_DEFS)

- [ ] **Step 1: 验证 chat 在 FIXED 列表**

```bash
grep -n "FIXED_CAPABILITY_DEFS\|chat" server/apps/agent/services/capability_registry.py | head -20
```

确认 chat 已属于 fixed capability（之前已重构）。如果不在 FIXED_CAPABILITY_DEFS，则添加。

- [ ] **Step 2: 删除文件**

```bash
rm server/apps/agent/skills/builtin/chat/SKILL.md
rmdir server/apps/agent/skills/builtin/chat 2>/dev/null || true
```

- [ ] **Step 3: 跑 capability registry 测试**

```bash
cd server && uv run pytest tests/agent/unit/test_capability_registry.py -v
```

Expected: 全部通过 — chat 应作为 fixed capability 出现，不受 SKILL.md 删除影响。

- [ ] **Step 4: 跑全套 agent 测试**

```bash
cd server && uv run pytest tests/agent/ 2>&1 | tail -10
```

Expected: 全通过。

- [ ] **Step 5: Commit**

```bash
git add -A server/apps/agent/skills/builtin/chat/
git commit -m "chore(agent): delete chat SKILL.md (chat is now fixed capability via ChatAdapter)"
```

---

## Task 15: 端到端跨家庭隔离集成测试

**Files:**
- Create: `server/tests/backend/integration/test_mcp_tenant_isolation_e2e.py`

- [ ] **Step 1: 写跨家庭隔离测试**

Create `server/tests/backend/integration/test_mcp_tenant_isolation_e2e.py`:

```python
"""End-to-end tenant isolation test:
Family A connects to MCP and cannot see family B's data.
"""
import pytest
from sqlalchemy.orm import Session

from apps.backend.app.services.mcp_session import MCPSession


@pytest.mark.asyncio
async def test_family_a_session_cannot_see_family_b_assets(
    db_session: Session, seed_two_families_with_assets
):
    family_a_id, family_b_id = seed_two_families_with_assets
    # family A has 5 assets, family B has 3 assets (per fixture)

    session_a = MCPSession(family_id=family_a_id, db=db_session)
    result = await session_a.call_tool("get_assets", {})
    import json
    data = json.loads(result[0].text)
    assert len(data) == 5

    session_b = MCPSession(family_id=family_b_id, db=db_session)
    result = await session_b.call_tool("get_assets", {})
    data = json.loads(result[0].text)
    assert len(data) == 3


@pytest.mark.asyncio
async def test_llm_cannot_escalate_via_family_id_arg(db_session, seed_two_families_with_assets):
    """Even if LLM tries to pass family_id=B from family A session, it must be ignored."""
    family_a_id, family_b_id = seed_two_families_with_assets

    session_a = MCPSession(family_id=family_a_id, db=db_session)
    # Adversarial call: try to pass family_b_id as arg
    result = await session_a.call_tool("get_assets", {"family_id": family_b_id})
    import json
    data = json.loads(result[0].text)
    # Must still return family A's 5 assets — argument ignored
    assert len(data) == 5
```

并实现 fixture `seed_two_families_with_assets` 在 `conftest.py`，使用现有 Family/User/Asset 模型创建两个家庭并 commit。

- [ ] **Step 2: 运行测试**

```bash
cd server && uv run pytest tests/backend/integration/test_mcp_tenant_isolation_e2e.py -v
```

Expected: 2 passed。

- [ ] **Step 3: Commit**

```bash
git add server/tests/backend/integration/test_mcp_tenant_isolation_e2e.py
git commit -m "test(backend): add e2e tenant isolation for MCP family data access"
```

---

## Task 16: 最终验证 + 手动端到端测试

- [ ] **Step 1: 跑全套测试**

```bash
cd server && uv run pytest tests/ -v 2>&1 | tail -30
cd frontend/apps/main && npm run typecheck && npm run test:run 2>&1 | tail -20
```

Expected: 后端全部通过；前端 typecheck 0 errors；前端测试通过。

- [ ] **Step 2: 后端 lint 检查**

```bash
cd server/apps/backend && uv run ruff check . 2>&1 | tail -10
cd server/apps/agent && uv run ruff check . 2>&1 | tail -10
```

Expected: 无 error。

- [ ] **Step 3: 类型检查**

```bash
cd server/apps/backend && uv run mypy app/ 2>&1 | tail -10
cd server/apps/agent && uv run mypy . --exclude vendor 2>&1 | tail -10
```

Expected: 无新增 error（与基线一致）。

- [ ] **Step 4: 手动 Docker 环境验证**

```bash
docker-compose up -d --build
docker-compose logs -f backend agent 2>&1 | head -50
```

- [ ] **Step 5: 浏览器测试场景**

打开 http://localhost:8080，登录测试家庭账号，进入 AI Chat 页面：

1. **私域问题**：「我有几辆车？」
   - Expected: AI 调用 MCP `get_assets(category="vehicle")`，返回正确数量
2. **公域问题**：「今天上海天气如何？」
   - Expected: AI 不调用 MCP；若 webSearch 开启则联网，否则诚实回答无法获取实时天气
3. **deepThink 开启**：「分析下我家资产配置是否合理」
   - Expected: AI 触发 plan_mode + subagent，分多步思考
4. **跨家庭隔离**：切到家庭 B 账号，重复问题 1
   - Expected: 看到家庭 B 自己的数据，不会看到家庭 A 的数据

记录每个场景的实际输出。

- [ ] **Step 6: 创建最终 commit + summary**

```bash
git log --oneline main..HEAD
git push origin fix/ai-history-session-display
```

---

## Self-Review

**1. Spec coverage check** — 对照 `docs/superpowers/specs/2026-05-21-chat-refactor-mcp-design.md` 11 节内容：

| Spec 节 | Plan 覆盖 |
|---------|----------|
| ChatAdapter | Task 6 + Task 8 |
| Orchestrator chat 分支 | Task 9 |
| System Prompt 文件 | Task 6 (创建文件) + Task 3 (Backend 内部 API) |
| MCP Server | Task 4 + Task 5 |
| MCP Tools (5个) | Task 4 |
| Backend 内部 API | Task 3 |
| Workspace 扩展 | Task 2 |
| DeerFlow 配置注入 | Task 7 |
| 前端改动 | Task 12 + Task 13 |
| Backend 代理 | Task 11 |
| Agent chat router | Task 10 |
| 删除 chat/SKILL.md | Task 14 |
| 测试 | Task 4/5/6/8/9/15 单元 + 集成 + e2e |

✅ 全部覆盖。

**2. Placeholder scan** — 无 "TBD"/"TODO"/"implement later"。所有代码块为完整可执行片段。少数处对未确认的 DeerFlow harness API 使用方式（`extra=` 参数、`system_prompt` 注入）已明示"具体接入方式参考 HARNESS_API.md"并给出 fallback 方案（注入到 ai_config 或 temp_config），这是已知未知的合规处理。

**3. Type consistency** — `ChatAdapter.stream` 签名在 Task 6/8/9 一致；`_generate_temp_config` 的 `mcp_servers` 参数在 Task 7/8 一致；`web_search` 参数从前端 → backend → agent → orchestrator → ChatAdapter 全链路命名一致（前端 camelCase `webSearch`，传输/后端 snake_case `web_search`）。

**4. 已知风险**：
- DeerFlow `mcp_servers` 配置项是否被 harness 识别需要在 Task 7 之前通过 `mcp__plugin_context7_context7__query-docs` 或阅读 `HARNESS_API.md` 确认。
- MCP Python SDK 的 `SseServerTransport.connect_sse` API 形态需要在 Task 5 实现时验证。
- 若任一不匹配，需更新对应任务的代码片段——不会改变任务结构或顺序。

**5. 运行顺序**：Tasks 1→16 严格按序执行。Task 7 之前不可执行 Task 8/9，因为 ChatAdapter.stream 依赖 family_adapter_cache 的 MCP 注入能力。Task 14 必须在 Task 9 之后，避免在 chat 分支尚未生效时移除 SKILL.md 导致 capability_registry 加载失败。
