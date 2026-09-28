---
name: deerflow-agent-dev
description: >
  DeerFlow agent 模块开发 — Numina AI agent 的唯一执行路径。
  触发：agent 模块代码变更、skill 开发、MCP/工具注册、provider 配置、
  多租户隔离、harness 升级、stream_run 调度，或任何 server/apps/agent/ 下的工作。
---

# DeerFlow Agent 模块开发参考

Numina 的 agent 模块 (`server/apps/agent/`) 是基于 DeerFlow 的多租户 AI agent 微服务。
所有多步骤 AI 编排**必须**通过 DeerFlow harness 执行 — 不得自建 runtime、tool registry、
skill loader、memory manager 或 workflow engine。

## ⚠ 每次执行前：同步 DeerFlow 上游

DeerFlow 通过 git submodule 管理（路径: `.claude/skills/deerflow-agent-dev/references/deerflow`）。
**每次开发或 review 前**必须执行：

```bash
git submodule update --init --remote .claude/skills/deerflow-agent-dev/references/deerflow
```

**Why**: 确保参考最新稳定版 DeerFlow harness 组件，避免对照过时 API 开发。

同步后必须：
1. 阅读 `references/deerflow/CHANGELOG.md` 中标记 ⚠ 的 breaking changes
2. 对照兼容性检查清单验证项目现有 patch/monkey-patch 兼容性

**兼容性检查清单**（每次 submodule 更新后必过）：

| 检查项 | 验证方法 |
|--------|----------|
| `make_lead_agent()` 签名 | 对比上游 `agents/lead_agent/agent.py` |
| `create_chat_model()` provider 路由 | 对比上游 `models/factory.py` |
| `StreamEvent` 类型定义 | 对比上游 `client.py` dataclass |
| skill scanner 目录约定 | 确认 `{root}/public/{skill}/SKILL.md` 仍有效 |
| `sync_tool_patch.py` 5 个 patch | 逐一验证上游目标函数签名未变 |
| `extensions_config` API | 对比上游 `config/extensions_config.py` |
| `RunManager` / `StreamBridge` 接口 | 对比上游 `runtime/runs/manager.py` |

## 核心架构约束

### DeerFlow-only 执行

```
stream_agent_dispatch(family_id, ai_config, skill_config)
    ↓ EffectiveConfigBuilder.build()
    ↓ make_lead_agent() + astream()
    ↓ NDJSON events → SSE consumer → format_sse
```

**不得**: 自建 runtime、tool registry、skill loader、memory manager、orchestrator。
**可以**: 轻量单步 LLM 调用 (`suggest`, `input_polish`, title) 用 `core/llm.py`，绕过 DeerFlow。
**判断标准**: 不涉及 tool call、不需要多轮对话、不需要 checkpoint → 单步。如有疑问，走 DeerFlow。

### ContextVar 传播

DeerFlow `run_in_executor` **不传播** `contextvars`。`_run_in_executor_with_context` 解决。

受影响的 ContextVar：
- `sandbox_family_id` — 沙盒租户隔离
- `numina_active_skill_name` — 工具过滤
- `numina_extensions_config_path` — MCP 配置路径

**教训**: 工具返回成功但文件不存在 = ContextVar 未传播，不是工具 bug。

## 核心原则

不依赖 DeerFlow 版本的持久原则 — harness 升级后仍然适用。

**永不静默降级** — 初始化/adapter 构建的 `except Exception` 必须 log + re-raise（或至少设可见标志），不得返回 `None` 让功能隐形失效：
```python
try:
    adapter = build_adapter()
except Exception as e:
    logger.warning(f"Adapter init failed: {e}")
    raise  # 不要静默降级
```

**Thinking blocks 不得泄漏到用户可见字符串** — thinking 模型返回的 `content` 是 block list（`[{"type":"thinking",...}, {"type":"text",...}]`），任何字符串消费方（标题、suggestion、metadata）必须用 `_extract_text_from_content_blocks()`，不得直接 `str(content)`。须在**所有写入路径**同时应用，不只一处。
- 现有 helpers：`server/apps/agent/services/runtime/run_extras.py` — `_strip_thinking_from_text`、`_extract_text_from_content_blocks`
- 新增 title / suggestion 写入路径时必须检查此规则

**SSE stream proxy 用 `aiter_lines()`，不用 `aiter_text()`** — `aiter_text()` 不能可靠地上游流结束信号，导致前端 `reader.read()` 永远不返回 `done: true`，消息停留在 processing 状态。所有 SSE proxy 循环均用 `aiter_lines()`（参考 `ai_threads.py`、`dashboard_narrative.py`）。

**Generator yield 类型变更须同步更新所有 caller** — 改 `AsyncGenerator[X, None]` 的 yield 类型（如 `str` → `StreamChunk`）必须在同一 commit 内搜索并更新所有 `async for chunk in <gen>` 调用点；漏掉任何一个都会造成运行时类型错误。

## 多租户管理

### 按家庭隔离 (family-wall)

```
family_adapter_cache.get_family_adapter(family_id, ai_config, ...)
    ↓ LRU 缓存 (max 100 families)
    ↓ EffectiveConfigBuilder.build() 生成独立 config
    ↓ 写入临时 config.yaml + extensions_config.json
DeerFlowClient(config_path=temp_config, checkpointer=shared_checkpointer)
```

**每家庭差异点**: 模型配置、skill 开关、MCP 配置、web search、memory 路径、sandbox 路径均独立隔离。

**已知限制**:
- `DEERFLOW_CONCURRENCY` Semaphore(8) **全局**限制 — 单家庭可占满全部 slot
- Checkpointer 共享 SqliteSaver，按 thread_id 隔离 — 不验证 family_id 所有权，依赖 thread_id 不可猜测性

### AI 助手开关 (PolicyGuard)

```python
class CapabilityPolicy:
    ai_enabled: bool = True
    allowed_capabilities: list[str] = []  # empty = all allowed; 非空 = skill_id 白名单
    admin_only_capabilities: list[str] = []
    member_role: str  # "admin" | "member" | "child"
```

**门控链**: `ai_enabled=False` → 拒绝所有 → `skill_id ∉ allowed` → 拒绝特定功能 → `admin_only + !admin` → 拒绝非管理员

### MCP 租户管理

`sync_tool_patch.py` 共 5 个 patch（同步包装、ContextVar 传播、MCP 代理、工具过滤、跨线程锁修复）。MCP tool name 格式: `{server_name}_{tool_name}`。

→ patch 详解 + adapter 文件职责: [references/adapter-layer.md](references/adapter-layer.md)

### 联网搜索能力

- 每家庭可配置 `web_search_providers`（多 provider 支持降级）
- Skill 路由：`chat-search`（有 web_search） / `chat`（无 web_search）
- 工具进度通过 `tool_progress` SSE 事件前端展示

## 开发指南

### 新增一个 Agent App

1. 在 `services/runtime/worker.py` 添加 runner（或 `_SimpleAppConfig` 通用 runner）
2. 在 `run_agent` 的 `metadata["app"]` 分支中添加路由
3. 在 `sse_gateway.py` R1 allowlist 中注册（前端直连 vs `internal=True` — **锁步对**）
4. 在 `skills/builtin/public/<app>/SKILL.md` 定义 skill
5. 在 backend `RESERVED_NAMES` 中添加 skill ID 防冲突
6. 如需后端触发，在 `app/routers/gateway.py` 添加 internal endpoint

**完成标准**:
- [ ] `run_agent` 能路由到新 app 并成功 dispatch
- [ ] 前端 SSE 连接能收到首个 event（或正确返回鉴权错误）
- [ ] R1 allowlist 验证通过
- [ ] Skill scanner 能发现新 skill

→ 完整 app 注册表: [references/dispatch-apps.md](references/dispatch-apps.md)

### 新增/修改一个 Skill

```
skills/builtin/public/<skill-name>/SKILL.md
```

Frontmatter schema (DeerFlow-native):
```yaml
---
name: skill-name
description: 简短描述
trigger_phrases: [/trigger-phrase]
allowed-tools:
  - tool_name_1
  - server_name_tool_name_2  # MCP tools 用 prefixed name
thinking: true
max_tokens: 6000
plan_mode: false             # 启用 TodoList middleware
subagent_enabled: false      # 启用 subagent 委托
# 注意: 不要添加 mcp_tools 字段 — legacy，native filter 读 allowed-tools
---
```

**Scanner 要求**: `{root}/public/{skill}/SKILL.md` 三层结构。

**完成标准**:
- [ ] Skill scanner 能发现（路径符合三层结构）
- [ ] 前端 `useTaskResume` 的 skill_id 与 SKILL.md `name` 精确匹配
- [ ] `allowed-tools` 声明完整（含 MCP prefixed name）

### Bridge, don't fork

所有 DeerFlow 行为扩展走 `services/deerflow_adapter/` — 子类 + adapter 扩展，不 fork harness。能力不足时：adapter 扩展 → 检查上游 RFC → 升级版本。不得静默 fork。

→ 文件职责表: [references/adapter-layer.md](references/adapter-layer.md)

## 参考路径速查

| 需要了解 | 查阅 |
|----------|------|
| Harness 可复用组件 | [references/deerflow-components.md](references/deerflow-components.md) |
| 多模型供应商架构 | [references/provider-architecture.md](references/provider-architecture.md) |
| 调度 App 注册表 | [references/dispatch-apps.md](references/dispatch-apps.md) |
| Adapter 层文件职责 | [references/adapter-layer.md](references/adapter-layer.md) |
| 安全规则 | [references/security-rules.md](references/security-rules.md) |
| Code Review 检查清单 | [references/code-review-checklist.md](references/code-review-checklist.md) |
| 调试指南 | [references/debug-guide.md](references/debug-guide.md) |
| DeerFlow harness API | `server/apps/agent/deerflow_config/HARNESS_API.md` |
| 当前 harness 版本 | `server/apps/agent/deerflow_config/HARNESS_VERSION` |
| DeerFlow 上游文档 | [references/deerflow-docs-index.md](references/deerflow-docs-index.md) |
| 项目经验 & 踩坑 | [references/numina-agent-experience.md](references/numina-agent-experience.md) |
| DeerFlow 上游代码 | `references/deerflow/` |
