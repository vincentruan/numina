---
name: agent-dev
description: >
  Numina agent 模块开发参考技能 — 基于 DeerFlow (bytedance/deer-flow) 的 AI agent 实现。
  涵盖 DeerFlow harness 集成、adapter 层扩展、多 app 调度、skill 系统、MCP 工具、
  沙盒隔离、流式传输等核心架构。
  触发场景：涉及 agent 模块开发、DeerFlow 集成、AI skill 开发、MCP 工具注册、
  agent 调试、stream_run 调度、checkpointer、sandbox、middleware、
  或任何 server/apps/agent/ 下的代码变更。
  关键词："agent", "deerflow", "skill", "MCP", "stream_run", "adapter",
  "智能体", "AI 调度", "沙盒", "工具注册", "harness", "checkpointer"。
  即使用户没有明确说 "agent"，只要涉及 AI 聊天/报告/解析/教练等能力的开发，
  都应该加载此技能。
---

# Agent 模块开发参考 (DeerFlow-Based)

Numina 的 agent 模块 (`server/apps/agent/`) 是一个基于 DeerFlow 的 AI agent 微服务。
所有多步骤 AI 编排**必须**通过 `DeerFlowAdapter` 执行 — 不得自建 runtime、tool registry、
skill loader、memory manager 或 workflow engine。

## 加载顺序

按以下顺序加载上下文，按需深入：

1. **本文件** — DeerFlow harness 能力总览 + 开发指南（已加载）
2. **[DeerFlow 文档索引](references/deerflow-docs-index.md)** — 按场景查阅 DeerFlow 上游文档
3. **[Numina 经验索引](references/numina-agent-experience.md)** — 项目已有的踩坑记录和架构决策
4. **DeerFlow 源码** — `references/deerflow/` 下的上游代码，仅在文档不足以回答时查阅
5. **项目代码** — `server/apps/agent/` 当前实现

## DeerFlow Harness 能力总览

DeerFlow (pinned at commit `6556d09d`, see `deerflow_config/HARNESS_VERSION`) 提供以下核心能力。
Numina 通过 adapter 层 (`services/deerflow_adapter/`) 集成这些能力，业务代码不直接调用 harness。

### 1. Agent 执行引擎

| 能力 | DeerFlow 组件 | Numina 集成点 |
|------|---------------|---------------|
| 多步编排 | `DeerFlowClient.stream()` | `adapter.typed_stream_dispatch()` |
| Lead Agent 图 | `make_lead_agent()` | 通过 config.yaml 配置 |
| ThreadPool 桥接 | N/A (同步 generator) | `_run_in_executor_with_context()` — 传播 ContextVar |
| 多模型支持 | config.yaml `models` | `family_adapter_cache` 按家庭生成临时 config |

### 2. Skill 系统

| 能力 | DeerFlow 组件 | Numina 用法 |
|------|---------------|-------------|
| Skill 加载 | `LocalSkillStorage` scanner | `skills/builtin/public/<name>/SKILL.md` 布局 |
| 工具过滤 | `filter_tools_by_skill_allowed_tools` | `sync_tool_patch._apply_active_skill_tool_filter` |
| Skill 前置元数据 | SKILL.md frontmatter | `allowed-tools`, `thinking`, `mcp_tools`, `plan_mode` |
| 内部 skill 隔离 | `_INTERNAL_ONLY_SKILLS` | `skill-creator`, `skill-installer` 不参与调度 |

**当前 5 个调度 app** (via `metadata["app"]`):

| App | Runner | Skill | 用途 |
|-----|--------|-------|------|
| `numina` | `_run_numina_agent` | chat / chat-search | 实时对话 |
| `asset-report` | `_run_asset_report_pipeline` | asset-report | 3 步资产报告 |
| `import-parse` | `_run_import_parse_agent` | import-parse | PDF/账单解析 |
| `finance-coach` | `_run_finance_coach_agent` | finance-coach | 理财建议 |
| `wish-advice` | `_run_wish_advice_agent` | wish-advice | 愿望储蓄建议 |

### 3. 工具 & MCP

| 能力 | DeerFlow 组件 | Numina 集成点 |
|------|---------------|---------------|
| MCP 客户端 | `MultiServerMCPClient` | `sync_tool_patch` 补丁（`tool_name_prefix=False`） |
| 沙盒工具 | `write_file`, `read_file`, `str_replace` | `NuminaLocalSandboxProvider` |
| 工具前缀 | `{server_name}_{tool}` | skill 过滤用 base name |

### 4. Memory & Checkpoint

| 能力 | DeerFlow 组件 | Numina 集成点 |
|------|---------------|---------------|
| 会话检查点 | `SqliteSaver` / Postgres | 共享 checkpointer (`_get_shared_checkpointer`) |
| 线程压缩 | `compact_thread_context` | `compact_service.py` 封装 |
| DeerMem | `storage_path` 配置 | `memory_config_bridge.py` 按家庭隔离 |
| Thread goal | `create_goal_evaluator_model` | `goal_evaluator.py`（用 `_create_lightweight_llm` 替代） |

### 5. Middleware

| 能力 | DeerFlow 组件 | Numina 用法 |
|------|---------------|-------------|
| TodoList | `TodoListMiddleware` | `todo_middleware.py` 子类，仅 plan_mode 加载 |
| Title 生成 | middleware chain | 须过滤 thinking blocks |

### 6. 流式传输

| 能力 | DeerFlow 组件 | Numina 用法 |
|------|---------------|-------------|
| SSE 格式 | LangGraph Platform wire format | `format_sse` (`messages`, `values`, `custom`, `end`, `error`) |
| StreamEvent | `type` + `data` | adapter 提取文本 + 转发 |
| 心跳 | 定时 sentinel | `SSE_HEARTBEAT_INTERVAL` (15s) |

## 核心架构约束

### Key Invariant: DeerFlow-only 执行

```
所有多步骤 AI 编排 → DeerFlowAdapter.typed_stream_dispatch
                     ↓
              DeerFlowClient.stream (ThreadPoolExecutor + copy_context)
                     ↓
              bridge.publish → sse_consumer → format_sse
```

**不得**: 自建 runtime、tool registry、skill loader、memory manager、orchestrator 或 workflow engine。
**可以**: 轻量单步 LLM 调用 (`suggest`, `input_polish`, title) 用 `core/llm.py` 直接调用，绕过 DeerFlow。
**判断标准**: 不涉及 tool call、不需要多轮对话、不需要 checkpoint 的 LLM 调用视为单步。如有疑问，走 DeerFlow。

**DeerFlow 能力不足时的升级路径**（按顺序尝试）：
1. 检查 adapter 层能否扩展（参见 §扩展 Adapter 层）
2. 检查 DeerFlow 上游是否有对应 RFC 或 plan（参见 `references/deerflow/backend/docs/rfc-*.md`）
3. 如果都不行，提出 HARNESS_VERSION 升级或向 DeerFlow 提 issue — **不得静默 fork**

### ContextVar 传播 (关键)

DeerFlow 的 `run_in_executor` **不传播** `contextvars`。Numina 通过
`_run_in_executor_with_context` (adapter.py) 解决：

```python
ctx = contextvars.copy_context()
return loop.run_in_executor(executor, lambda: ctx.run(func, *args))
```

受影响的 ContextVar：
- `sandbox_family_id` — 沙盒租户隔离
- `numina_active_skill_name` — 工具过滤
- `numina_extensions_config_path` — MCP 配置路径

**教训**: 工具返回成功但文件不存在 = ContextVar 未传播，不是工具 bug。

### 多租户隔离

```
family_adapter_cache.get_family_adapter(family_id, ai_config, ...)
    ↓ LRU 缓存 (max 100 families)
    ↓ 生成临时 config.yaml (注入 api_key, model_id, memory_path)
DeerFlowClient(config_path=temp_config, checkpointer=shared_checkpointer)
```

- 共享 checkpointer 按 `thread_id` 命名空间隔离
- `_CHECKPOINTER_LOCK` (asyncio.Lock) 序列化非流式调用
- `DEERFLOW_CONCURRENCY` Semaphore(8) 限制并发

### R1 Allowlist (前端调度门)

| 来源 | 允许的 app | 不允许的 app |
|------|-----------|-------------|
| 前端直接 `/runs/stream` | `numina` only | 其余 409 |
| 后端 internal gateway | 全部 (internal=True) | 未知 app → 400 |

worker 分支列表和 gateway allowlist 是**锁步对** — 扩一个必须扩另一个。

## 开发指南

### 新增一个 Agent App

1. 在 `services/runtime/worker.py` 添加 `_run_<app>_agent` runner 函数
2. 在 `services/runtime/worker.py` 的 `run_agent` 的 `metadata["app"]` 分支中添加路由（注意：Step 1 和 Step 3 是**锁步对** — worker 分支列表和 sse_gateway R1 allowlist 必须同步扩展）
3. 在 `sse_gateway.py` 的 R1 allowlist 中注册（决定前端能否直接触发）
4. 在 `skills/builtin/public/<app>/SKILL.md` 定义 skill（allowed-tools, thinking 等）
5. 在 backend `RESERVED_NAMES`（`apps/backend/app/routers/ai_skills.py`）中添加 skill ID 防自定义冲突。当前完整列表：`["chat", "asset-report", "import-parse", "finance-coach", "wish-advice", "dashboard-narrative", "literacy-weekly-report"]`
6. 在 `app/routers/gateway.py` 添加 internal trigger 端点（如果后端触发）

### 新增一个 Skill

```
skills/builtin/public/<skill-name>/SKILL.md
```

Frontmatter schema (DeerFlow-native):
```yaml
---
name: skill-name
description: 简短描述
trigger_phrases:
  - /trigger-phrase
allowed-tools:
  - tool_name_1
  - server_name_tool_name_2  # MCP tools 用 prefixed name
thinking: true               # 是否启用 extended thinking
max_tokens: 6000
plan_mode: false             # 是否启用 TodoList middleware
subagent_enabled: false      # 是否启用 subagent 委托
# 注意: 不要添加 mcp_tools 字段 — 它是 legacy，native filter 读 allowed-tools
---

## 适用场景
...prompt body (harness 自行加载)...
```

**注意**: scanner 要求 `{root}/public/{skill}/SKILL.md` 三层结构。

### 扩展 Adapter 层

所有 DeerFlow 行为扩展走 `services/deerflow_adapter/`:

| 文件 | 职责 |
|------|------|
| `adapter.py` | 主桥接 — typed_stream_dispatch, raw_stream_dispatch |
| `family_adapter_cache.py` | 按家庭 LRU 缓存 + temp config 生成 |
| `client_factory.py` | 构建 DeerFlowClient |
| `numina_deerflow_client.py` | Numina 子类（替代 monkey-patch） |
| `sync_tool_patch.py` | 同步包装、ContextVar 传播、MCP 代理、工具过滤 |
| `memory_config_bridge.py` | DeerMem 配置桥接 |
| `active_skill_context.py` | 当前 skill ContextVar |
| `original_user_content_context.py` | 原始用户内容 ContextVar |
| `patched_reasoning_chat.py` | Qwen/Anthropic extended thinking + reasoning_content 统一补丁 |

### 调试 DeerFlow 问题

| 症状 | 排查方向 | 参考 |
|------|----------|------|
| 工具返回成功但无效果 | ContextVar 未传播 | `f2-sandbox-contextvar-not-propagated-fix` |
| MCP 工具列表跨家庭泄漏 | extensions_config 环境变量竞争 | `extensions-config-contextvar-multifamily-fix` |
| Harness 静默降级 | 异常被吞 | `deerflow-harness-silent-fallback` solution |
| thinking 内容出现在标题 | 标题中间件未过滤 | `thinking-block-content-leaking` solution |
| Stream 提前关闭 | SSE 连接中断 | `stream-closure-fix` solution |
| MCP asyncio 死锁 | 跨线程 Lock | `mcp-cache-asyncio-lock-threading-deadlock` solution |
| 模型 endpoint 不匹配 | provider 配置错误 | `deerflow-glm5-thinking-mismatch` solution |

### DeerFlow 升级流程

当需要升级 `HARNESS_VERSION` 时：

1. **评估影响**: 对照本文件 §DeerFlow Harness 能力总览的 6 大能力域，逐一检查上游变更
2. **运行集成测试**: `cd server && uv run pytest tests/agent/ -v` — 特别关注 adapter/sandbox/MCP 相关用例
3. **检查 patch 兼容性**: `sync_tool_patch.py` 中的 monkey-patch 可能因上游方法签名变更而失效
4. **验证参考路径**: 确认 `references/deerflow-docs-index.md` 中引用的文档在新版本中仍存在
5. **回滚方案**: 如遇阻断性问题，将 `HARNESS_VERSION` 恢复到上一个已验证 commit

### 安全规则

1. 所有用户输入不可信 — 过滤 + 长度限制 + XML 包裹
2. PII redaction 强制 (`pii_redactor.redact()`)
3. 新 AI 路径须更新安全规则 + sim-test Area 11 对抗用例
4. 自定义 agent `allowed-tools` 强制声明
5. 系统 prompt 须有不可覆盖的安全前缀
6. 认证模型：内部端点 (backend→agent) 用 `X-Agent-Token` header；外部端点用 JWT cookie (`verify_family_token`)。新端点必须声明所属信任边界
7. Credential 管理：所有家庭 API key 使用 Fernet 加密 (`AI_ENCRYPTION_KEY`)，通过 backend 内部端点按需解密。新增 credential 类型须遵循相同的 encrypt-at-rest / decrypt-on-demand 模式
8. R1 allowlist 是安全边界：新 app 须决定是前端直连 (`numina`-like) 还是仅后端触发 (`internal=True`)，并在 `sse_gateway.py` 和 `worker.py` 同步注册（锁步对）

## 参考路径速查

| 需要了解 | 查阅 |
|----------|------|
| DeerFlow harness API | `server/apps/agent/deerflow_config/HARNESS_API.md` |
| 当前 harness 版本 | `server/apps/agent/deerflow_config/HARNESS_VERSION` |
| DeerFlow 上游文档 | `references/deerflow-docs-index.md` → `references/deerflow/backend/docs/` |
| 项目经验 & 踩坑 | `references/numina-agent-experience.md` |
| 项目解决方案库 | `docs/solutions/` (按类别) |
| 当前模块架构 | `server/apps/agent/CLAUDE.md` |
| DeerFlow 上游架构 | `references/deerflow/backend/docs/ARCHITECTURE.md` |
| DeerFlow 配置参考 | `references/deerflow/backend/docs/CONFIGURATION.md` |
| DeerFlow MCP 集成 | `references/deerflow/backend/docs/MCP_SERVER.md` |
| DeerFlow Skill 冲突 | `references/deerflow/docs/SKILL_NAME_CONFLICT_FIX.md` |
| 统一调度架构 | `docs/solutions/architecture-patterns/two-ai-apps-unified-dispatch-stream-run.md` |
| Adapter 解耦 | `docs/solutions/architecture-patterns/deerflow-adapter-decoupling-stream-bridge-subclass.md` |
