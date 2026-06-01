# Web Search 多租户联网搜索设计

日期：2026-06-01
状态：已批准

## 概述

将联网搜索从 `config.yaml` 静态配置迁移到家庭租户级 DB 管理。支持 DeerFlow 原生 web_search 工具（优先）和 MCP 两种联网搜索通道，带限流熔断降级。

## 设计决策

| 决策 | 选择 | 原因 |
|------|------|------|
| 降级策略 | 优先级顺序降级（A） | 用户体验可预测 |
| 熔断实现 | 复用 AIProviderConfig 模式（C） | 减少代码重复 |
| 前端入口 | 独立页面 + MCP 类型标记（C） | 内置 provider 体验好，MCP 灵活扩展 |
| Provider 模板来源 | 代码注册表 + reconcile 校验 | 单一来源，自动发现新 provider |

## 架构总览

### 三层数据模型

| 层 | 存储 | 内容 |
|---|------|------|
| 模板层（静态） | `web_search_provider_registry.py` | DeerFlow 支持的所有内置 provider 元数据 |
| 实例层（DB） | `family_web_search_providers` 表 | 家庭启用的 provider 实例（api_key、优先级、熔断状态） |
| MCP 通道（DB） | `ai_mcp_servers` 表 `mcp_type` 字段 | 标记 `mcp_type='websearch'` 的 MCP server |

### 运行时数据流

```
用户点击智能体的"联网搜索"
   ↓
后端检查家庭是否启用 ≥1 个 web_search provider 或 websearch-MCP
   ↓ (否) 返回 errcode → 前端 toast "请先在设置→AI助手→联网搜索中启用至少一个搜索源"
   ↓ (是) 透传 web_search=True 给 agent
   ↓
agent._generate_temp_config 从内部 API 拉取家庭的 web_search providers（按 display_order）
   ↓
注入到临时 config.yaml 的 tools 段（含 api_key）
   ↓
DeerFlow 加载临时 config → web_search_tool 调用 Tavily/Brave/...
```

### 降级与熔断

- 主 provider 调用失败 → 写 `circuit_state=open`，按 `display_order` 切换到下一个
- 三态熔断（closed/open/half_open）和 `recovery_schedule` 字段复用 `AIProviderConfig` 的服务层代码
- Agent 端通过 `POST /api/v1/internal/ai/web-search/{provider_id}/circuit` 回报失败

### MCP-as-websearch 通道

- MCP 表新增 `mcp_type` 字段（默认 `'general'`，可选 `'websearch'`）
- 当家庭启用了 `mcp_type='websearch'` 的 MCP server，agent 系统提示词追加段落指引 LLM 调用 MCP 工具
- MCP 路径不走 DeerFlow 原生 web_search_tool

## 数据模型

### 新表 `family_web_search_providers`

```python
class FamilyWebSearchProvider(Base):
    __tablename__ = "family_web_search_providers"

    id: Mapped[int]                    # Snowflake
    family_id: Mapped[int]             # 租户隔离
    provider_name: Mapped[str]         # "tavily" | "ddg_search" | "exa" | "serper" | "firecrawl"
    display_name: Mapped[str | None]   # 用户自定义名称
    api_key_encrypted: Mapped[str | None]  # Fernet 加密（ddg_search 无需 api_key）
    is_enabled: Mapped[bool]           # 默认 False
    display_order: Mapped[int]         # 降级优先级
    max_results: Mapped[int]           # 默认 5
    # 熔断字段（复用 AIProviderConfig 模式）
    circuit_state: Mapped[str]         # closed | open | half_open
    circuit_reason: Mapped[str | None]
    recovery_schedule: Mapped[str | None]
    last_failure_type: Mapped[str | None]
    half_open_success_count: Mapped[int]
    half_open_failure_count: Mapped[int]
    half_open_window_start: Mapped[datetime | None]
    failure_count: Mapped[int]
    last_failure_at: Mapped[datetime | None]
    created_at: Mapped[datetime]
    updated_at: Mapped[datetime]
```

### `ai_mcp_servers` 表新增字段

```python
mcp_type: Mapped[str] = mapped_column(String(20), default="general")  # "general" | "websearch"
```

### Provider 注册表 `web_search_provider_registry.py`

```python
WEB_SEARCH_PROVIDER_REGISTRY = {
    "tavily": {
        "provider_class": "deerflow.community.tavily.tools:web_search_tool",
        "display_name": "Tavily Search",
        "requires_api_key": True,
        "config_fields": [
            {"key": "api_key", "label": "API Key", "type": "secret", "required": True},
            {"key": "max_results", "label": "最大结果数", "type": "number", "default": 5},
        ],
        "docs_url": "https://tavily.com",
        "note": "免费 1000 次/月",
    },
    "ddg_search": {
        "provider_class": "deerflow.community.ddg_search.tools:web_search_tool",
        "display_name": "DuckDuckGo",
        "requires_api_key": False,
        "config_fields": [
            {"key": "max_results", "label": "最大结果数", "type": "number", "default": 5},
        ],
        "docs_url": "https://duckduckgo.com",
        "note": "免费无限制，无需 API Key",
    },
    "exa": {
        "provider_class": "deerflow.community.exa.tools:web_search_tool",
        "display_name": "Exa Search",
        "requires_api_key": True,
        "config_fields": [
            {"key": "api_key", "label": "API Key", "type": "secret", "required": True},
            {"key": "max_results", "label": "最大结果数", "type": "number", "default": 5},
        ],
        "docs_url": "https://exa.ai",
        "note": "语义搜索，适合研究类查询",
    },
    "serper": {
        "provider_class": "deerflow.community.serper.tools:web_search_tool",
        "display_name": "Serper (Google)",
        "requires_api_key": True,
        "config_fields": [
            {"key": "api_key", "label": "API Key", "type": "secret", "required": True},
            {"key": "max_results", "label": "最大结果数", "type": "number", "default": 5},
        ],
        "docs_url": "https://serper.dev",
        "note": "Google 搜索结果，免费 2500 次",
    },
    "firecrawl": {
        "provider_class": "deerflow.community.firecrawl.tools:web_search_tool",
        "display_name": "Firecrawl",
        "requires_api_key": True,
        "config_fields": [
            {"key": "api_key", "label": "API Key", "type": "secret", "required": True},
            {"key": "max_results", "label": "最大结果数", "type": "number", "default": 5},
        ],
        "docs_url": "https://firecrawl.dev",
        "note": "网页抓取 + 搜索",
    },
}
```

启动时 reconcile 校验：扫描 `deerflow.community.*` 中所有 `web_search` 工具，与注册表对比，缺失项报警。

## API 设计

### 新增路由 `/api/v1/ai/web-search`

| Method | Path | 权限 | 说明 |
|--------|------|------|------|
| GET | `/templates` | adult | 返回注册表中所有 provider 模板 |
| GET | `` | adult | 列出家庭已配置的 providers |
| POST | `` | owner | 创建 provider 实例 |
| PUT | `/{id}` | owner | 更新配置 |
| DELETE | `/{id}` | owner | 删除 |
| POST | `/{id}/test` | owner | 测试连通性 |
| POST | `/{id}/enable` | owner | 启用（前置校验配置完整性） |
| POST | `/{id}/disable` | owner | 禁用 |
| GET | `/status` | adult | 联网搜索总开关状态 |

### Agent 内部接口变更

`GET /api/v1/internal/ai/config` 返回新增字段：

```json
{
  "web_search_providers": [
    {"provider_name": "tavily", "provider_class": "...", "api_key": "decrypted", "max_results": 5, "display_order": 1}
  ],
  "web_search_mcp_servers": [
    {"name": "brave-mcp", "url": "...", "transport": "sse"}
  ]
}
```

新增熔断回报接口：

```
POST /api/v1/internal/ai/web-search/{provider_id}/circuit
body: {"failure_type": "permanent_auth" | "transient_rate_limit" | "transient_timeout"}
```

## Agent 集成

### `_generate_temp_config` 改造

```python
# 注入 web_search providers
web_search_providers = ai_config.get("web_search_providers", [])
if web_search_providers:
    active = _select_active_provider(web_search_providers)  # 按 display_order，跳过 open 状态
    if active:
        for tool in config.get("tools", []):
            if tool.get("name") == "web_search":
                tool["use"] = active["provider_class"]
                tool["api_key"] = active["api_key"]
                tool["max_results"] = active.get("max_results", 5)
                break
else:
    # 无配置时移除 web_search 工具
    config["tools"] = [t for t in config.get("tools", []) if t.get("name") != "web_search"]
```

### MCP-as-websearch 提示词注入

```python
if web_search:
    websearch_mcps = [m for m in mcp_servers if m.get("mcp_type") == "websearch"]
    
    if websearch_mcps and not has_native_provider:
        guidance = (
            "## 联网搜索\n"
            "当用户问题需要联网获取实时信息时，调用以下 MCP 工具进行搜索：\n"
            + "\n".join(f"- mcp:{m['name']}.search(query)" for m in websearch_mcps)
        )
    elif has_native_provider:
        guidance = "## 联网搜索\n当问题涉及实时信息时，使用 web_search(query) 工具检索。"
    else:
        guidance = ""
    
    if guidance:
        messages.insert(0, {"role": "system", "content": guidance})
```

## 前端设计

### 设置 → AI助手 → 联网搜索（新页面）

- 顶部：总开关状态指示（"已启用 N 个搜索源" / "未配置"）
- 列表：所有注册表中的 provider 模板，卡片式展示
  - 未配置：灰色，显示"配置"按钮
  - 已配置未启用：显示"启用"按钮
  - 已启用：绿色状态，显示优先级序号
  - 熔断中：红色状态，显示恢复时间
- 底部提示：也可在 MCP 管理中添加 websearch 类型的 MCP server

### MCP 管理页面变更

- `MCPFormPage.vue` 新增 `mcp_type` 选择器（general / websearch）
- `MCPManagePage.vue` 列表中 websearch 类型显示特殊标记

### 智能体卡片联网搜索开关

点击时先调用 `GET /ai/web-search/status`，无启用 provider 则 toast 提示。

## 测试覆盖

- 单元：`test_web_search_provider_registry.py`、`test_web_search_circuit_service.py`、`test_generate_temp_config_with_web_search.py`
- 集成：`test_agent_dispatch_web_search_failover.py`（mock Tavily 401 → 自动切到下一个 provider）
- 路由：`test_ai_web_search_router.py`（CRUD + status + test 端点）

## 变更清单

### 后端

- 新增 `app/models/family_web_search_provider.py`
- 新增 `app/routers/ai_web_search.py`
- 新增 `app/services/web_search_provider_registry.py`
- 新增 `app/services/web_search_circuit_service.py`（复用 ai_provider_circuit 逻辑）
- 修改 `app/models/family_mcp_server.py` — 增加 `mcp_type` 字段
- 修改 `app/routers/ai_internal.py` — `/ai/config` 返回 web_search_providers
- 新增 Alembic migration

### Agent

- 修改 `services/deerflow_adapter/family_adapter_cache.py` — `_generate_temp_config` 注入 web_search
- 修改 `services/agent_dispatch.py` — web_search 提示词逻辑扩展
- 修改 `deerflow_config/base/config.yaml` — 移除 web_search 工具的静态 api_key（保留为模板占位）

### 前端

- 新增 `pages/WebSearchPage.vue`
- 新增 `pages/WebSearchFormPage.vue`
- 修改 `pages/MCPFormPage.vue` — 增加 mcp_type 选择
- 修改 `pages/MCPManagePage.vue` — websearch 类型标记
- 修改 `components/agent/AgentCard.vue` — 联网搜索开关前置检查

### 配置

- 修改 `docker-compose.yml` — 移除 `TAVILY_API_KEY` 环境变量（不再需要）
- `.env` 中 `TAVILY_API_KEY` 可删除
