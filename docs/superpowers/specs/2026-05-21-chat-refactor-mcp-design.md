# AI Chat 功能重构设计（基于 DeerFlow 2.0 + MCP）

## 概述

将 AI 问答（chat）从"严格私域约束"重构为"DeerFlow 标准能力 + 私域增强"。核心变化：删除 `chat/SKILL.md`，引入 MCP server 提供租户隔离的家庭数据访问，前端 deepThink/webSearch 开关控制 DeerFlow 能力。

## 设计原则

1. **DeerFlow 标准能力优先**：不通过 SKILL.md 约束 LLM 行为
2. **私域数据通过 MCP**：AI 按需调用 tools 查询家庭数据，不预取
3. **多层租户隔离**：URL 路径 + Session + Token + SQL WHERE 子句
4. **数据实时刷新**：每次 MCP tool 调用 = 实时查询，无缓存
5. **可扩展架构**：MCP 为未来多 capability 共享数据访问铺路

## 能力定位变化

| 维度 | 旧设计 | 新设计 |
|------|-------|-------|
| 性质 | 严格约束的私域问答 | DeerFlow 标准问答 + 私域增强 |
| Skill 文件 | `skills/builtin/chat/SKILL.md` | **删除** |
| Prompt 来源 | SKILL.md 提示词约束 | 独立 `prompts/chat/default_system_prompt.md` |
| 自定义 | 不支持 | 家庭可在 `WORKSPACE_ROOT/{family_id}/prompts/chat.md` 自定义 |
| 数据获取 | `_build_context()` 预取全量 | MCP tools 按需查询 |
| 路由触发 | trigger_phrases 自动匹配 | 仅显式 `/ai/chat` 调用 |
| 能力开关 | 无 | deepThink + webSearch 独立控制 |

## 整体架构

```
用户输入 → POST /api/v1/ai/chat/stream
       ↓ (deepThink, webSearch)
Backend 代理 → Agent POST /chat/ask/stream
       ↓
orchestrator.stream_dispatch_events(
    capability="chat",
    deep_think=deepThink,
    web_search=webSearch,
)
       ↓
横切关注点（auth/policy/audit/journal/PII）
       ↓
分支：capability == "chat"
       ↓
ChatAdapter.stream()
  ├── 加载 system_prompt（家庭自定义 → 默认）
  ├── 组装 MCP URL: http://backend:8000/mcp/{family_id}/sse
  ├── 创建 DeerFlowClient（注入 MCP server + system_prompt）
  └── 启用能力开关：
      ├── deepThink → thinking + subagent + plan_mode
      └── webSearch → register web search tool
       ↓
DeerFlow 流式调度，LLM 自主决策：
  - 调用 MCP tool 查询家庭数据
  - 调用 web search tool 联网
  - subagent/plan_mode 分解复杂任务
       ↓
NDJSON 事件流返回
```

## 组件设计

### 1. ChatAdapter（新增）

**位置**：`server/apps/agent/services/chat_adapter.py`

**职责**（精简）：
- System prompt 加载（家庭自定义 → 默认 fallback）
- MCP URL 组装（路径含 family_id）
- DeerFlow 配置生成（MCP 注入 + 能力开关）
- DeerFlow stream 调用

**不负责**（由 orchestrator 处理）：
- 认证、权限、审计
- Session journal、PII 脱敏
- 事件协议转换

```python
class ChatAdapter:
    def __init__(self, backend_base_url: str, internal_token: str) -> None: ...

    async def stream(
        self,
        family_id: str,
        question: str,
        thread_id: str,
        ai_config: dict,
        deep_think: bool = False,
        web_search: bool = False,
    ) -> AsyncGenerator[StreamChunk, None]: ...

    def _resolve_prompt(self, family_id: str) -> str:
        """Family override → default fallback"""

    def _fetch_family_prompt(self, family_id: str) -> str | None:
        """Fetch from backend /api/v1/internal/prompts/{family_id}/chat"""

    def _load_default_prompt(self) -> str:
        """Load from agent/prompts/chat/default_system_prompt.md"""
```

### 2. Orchestrator 改动

**位置**：`server/apps/agent/services/orchestrator.py`

```python
async def stream_dispatch_events(
    self,
    capability,
    family_id,
    ...,
    deep_think: bool = False,
    web_search: bool = False,
):
    # === 横切关注点（所有 capability 共用）===
    ai_config = await self._load_ai_config(family_id)
    policy_guard.check(...)
    session_journal.write_session_start(...)
    redacted_free_text = pii_redactor.redact_text(free_text)

    # === 分支：执行策略 ===
    if capability == "chat":
        # Chat: 通过 ChatAdapter，无 _build_context()
        async for chunk in self._chat_adapter.stream(
            family_id=family_id,
            question=redacted_free_text,
            thread_id=effective_thread_id,
            ai_config=ai_config,
            deep_think=deep_think,
            web_search=web_search,
        ):
            yield self._chunk_to_event(chunk, event_builder)
    else:
        # Skill-based: 原有逻辑
        skill_config = skill_loader.load_for_family(capability, family_id, ...)
        context = await self._build_context(client, family_id, free_text)
        adapter = _create_family_adapter(...)
        async for chunk in adapter.stream_events(...):
            yield self._chunk_to_event(chunk, event_builder)

    # === 横切关注点（继续）===
    session_journal.write_assistant_message(...)
    audit_logger.log(...)
```

### 3. System Prompt 文件管理

**默认提示词**：`server/apps/agent/prompts/chat/default_system_prompt.md`

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

**家庭自定义**：`WORKSPACE_ROOT/{family_id}/prompts/chat.md`（可选）

**加载策略**：
```python
def resolve_prompt(family_id) -> str:
    family_prompt = workspace.get_chat_prompt(family_id)  # 通过 Backend API
    return family_prompt or DEFAULT_PROMPT
```

### 4. MCP Server（新增，嵌入 Backend）

**位置**：`server/apps/backend/app/routers/mcp.py` + `server/apps/backend/app/services/mcp_session.py`

**URL 路径隔离**：
```
GET /mcp/{family_id}/sse
```

**租户隔离保障链**：

| 层 | 措施 |
|----|------|
| 连接层 | URL 路径含 family_id，建立连接时绑定 |
| Token 层 | `X-Internal-Token` 验证（Agent ↔ Backend 信任链） |
| Session 层 | `MCPSession(family_id)` 实例化时绑定，不可变 |
| Tool 参数层 | Tool schema **不暴露 family_id 字段**，LLM 无法越权 |
| 数据层 | 所有 SQL 查询强制 `WHERE family_id = ?` |
| 审计层 | 日志记录 `family_id, tool_name, args` |

### 5. MCP Tools（5 个，中粒度）

| Tool | 描述 | 返回 |
|------|------|------|
| `get_family_overview` | 净资产、总资产、总负债、配置占比、近期趋势 | JSON 摘要 |
| `get_assets` | 资产列表，支持 category/status 过滤 | 资产数组 |
| `get_liabilities` | 负债列表（贷款、信用卡等） | 负债数组 |
| `get_members` | 家庭成员列表 | 成员数组 |
| `get_recent_alerts` | 资产预警和处置建议 | 预警数组 |

**Tool 参数规则**：
- 不包含 `family_id` 字段（隔离由 session 保障）
- 支持过滤参数（如 category、status）
- 支持 limit（默认 10-20）

**Tool 实现复用**：
- `get_family_overview` 复用 `dashboard_service`
- `get_assets` 复用 `asset_service`
- `get_liabilities` 复用 `liability_service`
- `get_members` 复用 `family_service`
- `get_recent_alerts` 复用 `ai_asset_alert_service`

### 6. Backend 内部 API（新增）

**chat prompt 加载**：
```
GET /api/v1/internal/prompts/{family_id}/chat
Headers: X-Internal-Token
Response: { "content": str | null }
```

**实现**：
```python
@router.get("/prompts/{family_id}/chat")
def get_chat_prompt(family_id: int, x_internal_token: str = Header(...)):
    if x_internal_token != settings.INTERNAL_TOKEN:
        raise HTTPException(401)
    content = workspace.get_chat_prompt(str(family_id))
    return {"content": content}
```

### 7. Workspace 服务扩展

**位置**：`server/apps/backend/app/services/workspace.py`

```python
def chat_prompt_file(family_id: str) -> Path:
    return prompts_dir(family_id) / "chat.md"

def get_chat_prompt(family_id: str) -> str | None:
    f = chat_prompt_file(family_id)
    if f.exists():
        return _strip_frontmatter(f.read_text(encoding="utf-8"))
    return None

def save_chat_prompt(family_id: str, content: str) -> None:
    chat_prompt_file(family_id).write_text(content, encoding="utf-8")

def delete_chat_prompt(family_id: str) -> None:
    chat_prompt_file(family_id).unlink(missing_ok=True)

def _strip_frontmatter(content: str) -> str:
    """Strip YAML frontmatter, return body."""
    if not content.startswith("---"):
        return content.strip()
    end = content.find("---", 3)
    return content[end + 3:].strip() if end != -1 else content.strip()
```

### 8. DeerFlow 配置注入

`family_adapter_cache._generate_temp_config()` 接收 MCP URL 参数：

```python
def _generate_temp_config(family_id, ai_config, mcp_url=None, mcp_token=None, ...):
    config = {...}
    if mcp_url:
        config["mcp_servers"] = [
            {
                "name": "numina-family-data",
                "url": mcp_url,
                "transport": "sse",
                "headers": {"X-Internal-Token": mcp_token},
            }
        ]
    return config
```

### 9. 前端改动

**位置**：`frontend/apps/main/src/api/ai.ts`

```typescript
export async function sendChatMessageStream(
  question: string,
  deepThink: boolean,
  webSearch: boolean,         // 新增
  signal?: AbortSignal,
  sessionId?: string,
): Promise<ReadableStreamDefaultReader<Uint8Array>> {
  const body = JSON.stringify({
    question,
    deep_think: deepThink,
    web_search: webSearch,    // 新增
  })
  // ...
}
```

**AIChatPage.vue** 传递 webSearch：

```typescript
await sendChatMessageStream(
  question,
  deepThinkEnabled.value,
  webSearchEnabled.value,    // 新增
  abortController.signal,
  sessionId,
)
```

### 10. Backend 代理改动

`server/apps/backend/app/routers/ai.py` 增加 `web_search` 参数：

```python
class ChatStreamRequest(BaseModel):
    question: str
    deep_think: bool = False
    web_search: bool = False    # 新增

@router.post("/chat/stream")
async def chat_stream(body: ChatStreamRequest, ...):
    # 代理到 agent 时传递 web_search
    json_body = {
        "question": body.question,
        "deep_think": body.deep_think,
        "web_search": body.web_search,
    }
    # ...
```

### 11. Agent chat router 改动

`server/apps/agent/routers/chat.py` 增加 `web_search` 参数：

```python
class ChatStreamRequest(BaseModel):
    question: str
    deep_think: bool = False
    web_search: bool = False    # 新增

@router.post("/ask/stream")
async def ask_stream(body: ChatStreamRequest, ...):
    async def generate():
        async for chunk in orchestrator.stream_dispatch_events(
            capability="chat",
            family_id=x_family_id,
            user_id=x_user_id,
            thread_id=x_thread_id,
            free_text=body.question,
            deep_think=body.deep_think,
            web_search=body.web_search,    # 新增
        ):
            yield chunk
    return StreamingResponse(generate(), media_type="application/x-ndjson")
```

## 数据刷新与租户隔离总结

### 数据刷新

- **MCP tool 每次调用 = 实时 SQL 查询**，无缓存
- 跨天对话：每次 tool 调用都获取最新数据
- 用户在对话中修改资产：下次 tool 调用立即可见

### 租户隔离保障

| 层 | 保障 | 失败场景 |
|----|------|---------|
| URL 路径 | `/mcp/{family_id}/sse` | 路径篡改 → 路由解析失败 |
| Internal Token | `X-Internal-Token` 验证 | Token 错误 → 401 |
| MCP Session | `MCPSession(family_id)` 不可变 | Session 复用 → 各 session 独立 |
| Tool 参数 | 不暴露 family_id 字段 | LLM 越权 → schema 验证失败 |
| SQL 强制过滤 | `WHERE family_id = ?` | 缺失过滤 → 单元测试覆盖 |

### 跨家庭测试用例

```python
async def test_mcp_tenant_isolation():
    """连接 family A 的 MCP，无法访问 family B 的数据"""
    # 1. 创建 family A（5 个资产）和 family B（3 个资产）
    # 2. 连接 /mcp/{family_a_id}/sse
    # 3. 调用 get_assets() → 返回 5 个（仅 family A）
    # 4. 连接 /mcp/{family_b_id}/sse
    # 5. 调用 get_assets() → 返回 3 个（仅 family B）
    # 6. 尝试在 family A 连接上构造 SQL 注入访问 family B → 失败
```

## 文件清单

### 新增

- `server/apps/agent/services/chat_adapter.py` — ChatAdapter 实现
- `server/apps/agent/prompts/chat/default_system_prompt.md` — 默认系统提示词
- `server/apps/agent/prompts/chat/README.md` — 提示词约定说明
- `server/apps/backend/app/routers/mcp.py` — MCP SSE 端点
- `server/apps/backend/app/services/mcp_session.py` — MCP session 实现
- `server/apps/backend/app/services/mcp_tools.py` — MCP tool handlers

### 修改

- `server/apps/agent/services/orchestrator.py` — 添加 chat 分支
- `server/apps/agent/routers/chat.py` — 添加 web_search 参数
- `server/apps/agent/services/deerflow_adapter/family_adapter_cache.py` — 注入 MCP 配置
- `server/apps/backend/app/routers/ai.py` — chat 代理添加 web_search 参数
- `server/apps/backend/app/routers/ai_internal.py` — 添加 chat prompt 端点
- `server/apps/backend/app/services/workspace.py` — 添加 chat prompt 文件管理
- `server/apps/backend/app/main.py` — 注册 MCP 路由
- `frontend/apps/main/src/api/ai.ts` — sendChatMessageStream 添加 webSearch 参数
- `frontend/apps/main/src/pages/AIChatPage.vue` — 传递 webSearch 参数

### 删除

- `server/apps/agent/skills/builtin/chat/SKILL.md` — chat 不再作为 skill

## 演进路径

### 短期（本次实现）

- chat 使用 ChatAdapter + MCP
- 其他 capability（report、alerts 等）仍走原有 skill 机制 + `_build_context()`

### 中期（多 capability 成熟后）

- 评估迁移 report、liability 等 capability 到 MCP
- 删除 `_build_context()`
- 统一所有 capability 通过 MCP 访问数据

### 长期（生态扩展）

- 接入第三方 MCP server（银行流水、股票行情、汇率）
- MCP server 独立部署（性能扩展）

## 测试与验证

### 单元测试

- `MCPSession` tool handlers 强制 family_id 过滤
- ChatAdapter system_prompt 加载顺序（family → default）
- ChatAdapter MCP URL 组装正确性

### 集成测试

- 跨家庭隔离：family A token 调用 family B MCP → 拒绝
- LLM 无法越权：tool schema 不暴露 family_id
- 数据实时刷新：tool 间增加资产，下次调用能看到
- System prompt fallback：删除 family 自定义 → 使用默认

### E2E 测试

- 用户问"我有几辆车" → AI 调用 `get_assets(category="vehicle")` → 返回数量
- 用户问"今天天气" → AI 不调用 MCP，直接回答（或调用 web search）
- 用户开启 deepThink → 复杂问题触发 plan_mode
- 用户开启 webSearch → AI 可联网获取最新信息

## 实现优先级

1. **P0 - MCP Server 基础**
   - `mcp.py` SSE 端点（含租户隔离）
   - `mcp_session.py` session 管理
   - `mcp_tools.py` 5 个 tool handlers
   - 单元测试：tenant isolation

2. **P1 - ChatAdapter**
   - `chat_adapter.py` 实现
   - 默认 system_prompt 文件
   - 家庭自定义 prompt 加载

3. **P2 - Orchestrator 集成**
   - 添加 chat 分支
   - 移除 chat 对 `_build_context()` 的依赖
   - 删除 `chat/SKILL.md`

4. **P3 - 前端 webSearch 参数**
   - API 函数添加参数
   - AIChatPage 传递参数

5. **P4 - 集成测试**
   - 跨家庭隔离测试
   - E2E 流程测试
