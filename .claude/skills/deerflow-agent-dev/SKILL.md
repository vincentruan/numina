---
name: deerflow-agent-dev
description: >
  Numina agent 模块开发参考 — 基于 DeerFlow (bytedance/deer-flow) 的 AI agent 实现。
  涵盖 DeerFlow harness 集成、多模型供应商抽象（限流/降级/负载切换）、AI 助手开关、
  MCP/联网搜索/skill 等租户管理能力、按家庭租户维度的 client 管理差异。
  触发场景：涉及 agent 模块开发、DeerFlow 框架升级、AI skill 开发、MCP 工具注册、
  agent 调试、stream_run 调度、checkpointer、sandbox、middleware、
  多供应商切换、policy guard、harness 升级，或任何 server/apps/agent/ 下的代码变更。
  关键词："agent", "deerflow", "harness", "多供应商", "provider", "MCP", "联网搜索",
  "web_search", "skill", "stream_run", "adapter", "智能体", "AI 调度", "沙盒", "工具注册",
  "checkpointer", "多租户", "family", "policy", "熔断", "降级"。
  即使用户没有明确说 "agent"，只要涉及 AI 聊天/报告/解析/教练等能力的开发，
  都应该加载此技能。
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
1. 检查 `HARNESS_VERSION` 是否有变化
2. 阅读 `references/deerflow/CHANGELOG.md` 中标记 ⚠ 的 breaking changes
3. 对照下方 §DeerFlow Harness 可复用组件 验证项目现有 patch/monkey-patch 兼容性
4. 特别注意 `sync_tool_patch.py` 中的 monkey-patch 是否因上游签名变更而失效
5. 注意 `make_lead_agent()` / `create_chat_model()` / `StreamEvent` 接口变更

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

## DeerFlow Harness 可复用组件

优先复用 harness 包中的成熟组件，不自建等价功能。

| 组件 | 路径 (submodule 内) | 用法 |
|------|---------------------|------|
| `DeerFlowClient` | `backend/packages/harness/deerflow/client.py` | 同步 generator stream()，ThreadPoolExecutor 桥接 |
| `StreamBridge` | `runtime/stream_bridge/` | 跨进程事件分发（Redis Streams / in-memory） |
| `RunManager` | `runtime/runs/manager.py` | Run 生命周期管理（lease, orphan recovery） |
| `make_lead_agent()` | `agents/lead_agent/agent.py` | 构建 LangGraph agent 图 |
| `create_chat_model()` | `models/factory.py` | 供应商 class 路由 + base_url 规范化 |
| Checkpoint providers | `runtime/checkpointer/` | SQLite / Postgres 持久化 |
| `ExtensionsConfig` | `config/extensions_config.py` | Skill enable/disable + atomic write |
| Skill storage | `skills/storage.py` | LocalSkillStorage scanner |
| `MultiServerMCPClient` | `mcp/` | MCP server 连接管理 |
| Sandbox | `sandbox/` | write_file / read_file / str_replace |
| Trace context | `trace_context.py` | 分布式 trace id 绑定 |

**不自建原则**: 如果 harness 已有等价实现 → 直接复用。能力不足时按顺序尝试：
1. 扩展 adapter 层（`services/deerflow_adapter/`）
2. 检查上游 RFC / plan（`references/deerflow/backend/docs/rfc-*.md`）
3. 升级 `HARNESS_VERSION` 或向 DeerFlow 提 issue — **不得静默 fork**

## 多模型供应商抽象

### 架构层次

```
DB ai_providers 行 (per family, Fernet-encrypted)
    ↓ EffectiveConfigBuilder.build()
    ↓ packages/core/model_entry.build_model_entry()
    ↓ 生成 DeerFlow models[0] entry
    ↓ create_chat_model() 路由到正确的 LangChain class
```

### Provider Class Map (`_PROVIDER_CLASS_MAP`)

| Provider key | LangChain class | Notes |
|-------------|-----------------|-------|
| `anthropic` | `langchain_anthropic:ChatAnthropic` | 原生 Messages API |
| `openai` | `langchain_openai:ChatOpenAI` | gpt-5*, o-series |
| `openai_compatible` | `langchain_openai:ChatOpenAI` | GLM/Qwen/DashScope/Novita/vLLM |
| `gemini` | `langchain_google_genai:ChatGoogleGenerativeAI` | 不支持 thinking |

### Thinking 路由 (`_THINKING_CLASS_OVERRIDES`)

| 类型 | Class | 触发条件 |
|------|-------|----------|
| `deepseek` | `PatchedChatDeepSeek` | `extra_body.thinking.{type: enabled\|disabled}` |
| `reasoning` | `PatchedChatReasoning` | Qwen/GLM/QwQ via DashScope — `extra_body.enable_thinking` |
| `anthropic` | `PatchedChatAnthropic` | `thinking.budget_tokens` (fraction of max_tokens) |

### max_tokens 解析优先级

1. `ai_provider['max_tokens']` — DB 用户设置
2. `system-config.yaml` prefix-matched default
3. `None` — SDK / vendor defaults

### 熔断 & 降级

- **三态 FSM 熔断器**（per provider）：closed → open → half-open
- **Cascade retry**: 主 provider 失败 → fallback provider
- **Web search circuit**: `report_web_search_circuit()` 报告搜索 provider 故障
- 故障分类：`transient_timeout`, `transient_rate_limit`, `transient_network`, `permanent_auth`, `transient_server`

## 多租户管理

### 按家庭 Client 管理 (family_adapter_cache)

```
family_adapter_cache.get_family_adapter(family_id, ai_config, ...)
    ↓ LRU 缓存 (max 100 families)
    ↓ EffectiveConfigBuilder.build() 生成独立 config
    ↓ 写入临时 config.yaml + extensions_config.json
DeerFlowClient(config_path=temp_config, checkpointer=shared_checkpointer)
```

**每家庭差异点**：
- **模型配置**: 不同 family 可用不同 provider/model/api_key
- **Skill 开关**: extensions_config 按 family 独立控制 skill enable/disable
- **MCP 配置**: extensions_config.json 按 family 生成，防止工具列表跨家庭泄漏
- **Web search**: web_search_providers 按 family 配置
- **Memory 路径**: `{AGENT_DATA_DIR}/{family_id}/agent/memory/` 隔离
- **Sandbox 路径**: `{DEER_FLOW_HOME}/users/{family_id}/...` 隔离
- **并发控制**: `DEERFLOW_CONCURRENCY` Semaphore(8) **全局**限制（非 per-family）。单家庭可占满全部 slot 导致其他家庭被阻塞 — 已知限制，如需公平性需额外实现 per-family 限流
- **Checkpointer**: 共享 SqliteSaver，按 thread_id 命名空间隔离。thread_id 由前端/后端生成（UUID4, 不可预测），但 checkpointer 读取**不验证** family_id 所有权 — 依赖 thread_id 不可猜测性作为隔离保障

### AI 助手开关 (PolicyGuard)

```python
# schemas/policy.py
class CapabilityPolicy:
    ai_enabled: bool = True
    allowed_capabilities: list[str] = []  # empty = all allowed; 非空 = skill_id 白名单
    admin_only_capabilities: list[str] = []
    member_role: str  # "admin" | "member" | "child"

# policy_guard.py — 纯内存检查，不访问 DB/网络
policy_guard.check(policy, skill_id) → PolicyDecision(allowed, reason)
```

**门控链**: `ai_enabled=False` → 拒绝所有 AI → `skill_id ∉ allowed` → 拒绝特定功能 → `admin_only + !admin` → 拒绝非管理员

### Skill 租户管理

每家庭可独立控制 skill enable/disable（通过 `extensions_config.json`）：
- DeerFlow `ExtensionsConfig` 管理 skill 开关
- `set_raw_skill_enabled()` 原子更新
- `_INTERNAL_ONLY_SKILLS`（skill-creator, skill-installer, skill-reviewer）不参与调度

### MCP 租户管理

- `sync_tool_patch.py` 共 5 个 patch（入口 `apply_sync_tool_patches()`）：
  1. `_patched_get_available_tools`: 同步包装 + active skill 工具过滤
  2. `_apply_original_user_content_patch`: 原始用户内容 ContextVar 传播
  3. `_apply_extensions_config_path_patch`: extensions_config 路径 ContextVar 传播
  4. `_apply_mcp_httpx_factory_patch`: httpx client factory 注入（跨线程安全）
  5. `_apply_mcp_cache_threading_lock_patch`: asyncio.Lock → threading.Lock（防死锁）
- MCP tool name 格式: `{server_name}_{tool_name}`（skill allowed-tools 用 prefixed name）
- `extensions_config.json` 按 family 维度生成，防止跨家庭泄漏

### 联网搜索能力

- 每家庭可配置 `web_search_providers`（多 provider 支持降级）
- 通过 `EffectiveConfigBuilder` 注入 `tools.web_search` 配置
- Skill 路由：
  - `chat-search` skill: 有 web_search 能力时
  - `chat` skill: 无 web_search 时
- 工具进度通过 `tool_progress` SSE 事件前端展示

## 当前 8 个调度 App

### Custom Runner Apps (独立 runner 函数)

| App | Runner | Skill | 用途 |
|-----|--------|-------|------|
| `numina` | `_run_numina_agent` | chat / chat-search | 实时对话 |
| `asset-report` | `_run_asset_report_agent` | asset-report | 3 步资产报告 |
| `import-parse` | `_run_import_parse_agent` | import-parse | PDF/账单解析 |
| `finance-coach` | `_run_finance_coach_agent` | finance-coach | 理财建议 |
| `wish-advice` | `_run_wish_advice_agent` | wish-advice | 愿望储蓄建议 |

### Config-Driven Apps (`_SimpleAppConfig` + `_run_simple_app` 通用 runner)

| App | Skill | 用途 |
|-----|-------|------|
| `dashboard-narrative` | dashboard-narrative | 仪表盘 AI 叙事 |
| `literacy-weekly-report` | literacy-weekly-report | 启蒙周报 |
| `learning-tutor` | learning-tutor | AI 学习辅导 |

## 开发指南

### 新增一个 Agent App

1. 在 `services/runtime/worker.py` 添加 `_run_<app>_agent` runner（或 `_SimpleAppConfig` 通用 runner）
2. 在 `run_agent` 的 `metadata["app"]` 分支中添加路由
3. 在 `sse_gateway.py` R1 allowlist 中注册（前端直连 vs `internal=True` 后端触发 — **锁步对**）
4. 在 `skills/builtin/public/<app>/SKILL.md` 定义 skill
5. 在 backend `RESERVED_NAMES` 中添加 skill ID 防冲突
6. 如需后端触发，在 `app/routers/gateway.py` 添加 internal endpoint

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

### 扩展 Adapter 层

所有 DeerFlow 行为扩展走 `services/deerflow_adapter/`:

| 文件 | 职责 |
|------|------|
| `adapter.py` | 主桥接 — typed_stream_dispatch, raw_stream_dispatch |
| `family_adapter_cache.py` | 按家庭 LRU 缓存 + EffectiveConfigBuilder 临时 config |
| `client_factory.py` | 构建 DeerFlowClient |
| `numina_deerflow_client.py` | Numina 子类（替代 monkey-patch） |
| `sync_tool_patch.py` | 5 个运行时 patch — 同步包装、ContextVar 传播、MCP 代理、工具过滤（详见 §MCP 租户管理） |
| `memory_config_bridge.py` | DeerMem 配置桥接 |
| `active_skill_context.py` | 当前 skill ContextVar |
| `original_user_content_context.py` | 原始用户内容 ContextVar |
| `patched_reasoning_chat.py` | Qwen/Anthropic extended thinking + reasoning_content 统一补丁 |
| `patched_anthropic.py` | Anthropic thinking block 捕获 + reasoning_content 复制 |
| `exceptions.py` | DeerFlowError / SkillNotFoundError / TimeoutError |

## 核心架构约束

### Key Invariant: DeerFlow-only 执行

```
stream_agent_dispatch(family_id, ai_config, skill_config)
    ↓ EffectiveConfigBuilder.build()
    ↓ make_lead_agent() + astream()
    ↓ NDJSON events → SSE consumer → format_sse
```

**不得**: 自建 runtime、tool registry、skill loader、memory manager、orchestrator。
**可以**: 轻量单步 LLM 调用 (`suggest`, `input_polish`, title) 用 `core/llm.py`，绕过 DeerFlow。
**判断标准**: 不涉及 tool call、不需要多轮对话、不需要 checkpoint → 单步。如有疑问，走 DeerFlow。

### ContextVar 传播 (关键)

DeerFlow `run_in_executor` **不传播** `contextvars`。`_run_in_executor_with_context` 解决：

受影响的 ContextVar：
- `sandbox_family_id` — 沙盒租户隔离
- `numina_active_skill_name` — 工具过滤
- `numina_extensions_config_path` — MCP 配置路径

**教训**: 工具返回成功但文件不存在 = ContextVar 未传播，不是工具 bug。

### 安全规则

1. 所有用户输入不可信 — 过滤 + 长度限制 + XML 包裹
2. PII redaction 强制 (`pii_redactor.redact()`)
3. 新 AI 路径须更新安全规则 + sim-test Area 11 对抗用例
4. 自定义 agent `allowed-tools` 强制声明
5. 系统 prompt 须有不可覆盖的安全前缀
6. **认证 & 信任模型**: 三层信任边界 —
   - **外部端点**: JWT cookie (`verify_family_token`) — 认证 + family 级别授权
   - **内部端点** (backend→agent): `X-Agent-Token` — 仅认证调用方服务身份，**不做 family scope 校验**；family 级授权由调用方 backend 在执行前完成（owner/admin 检查）
   - **信任链**: agent gateway 信任 backend 已做 family authz，backend 信任 JWT 已做 user auth
7. **Credential 两层 Fernet 加密**:
   - `AI_ENCRYPTION_KEY`: 加密 `ai_providers` 表中的 API key（encrypt-at-rest, decrypt-on-demand, 生产环境强制配置）
   - `STORAGE_ENCRYPTION_KEY`: 加密 per-family DeerFlow 临时 config.yaml / extensions_config.json（`packages/storage/config_crypto.py`），回退到 `SECRET_KEY` SHA256 派生（有 warning）
   - 新增敏感字段时必须确认使用正确的 key 层级
8. **R1 allowlist 安全边界**:
   - **前端直连** (R1 强制校验): worker 分支 + sse_gateway start_run 锁步对同步注册
   - **内部触发** (`internal=True`, `X-Agent-Token` 认证): **绕过 R1 app 检查** — 前提是后端触发端点已执行 owner/ai_enabled/concurrency 门控
   - 新增 app 时必须明确选择: (A) 仅 `internal=True` 触发（R1 绕过, 后端门控）, 或 (B) 允许前端直连（R1 强制校验）

## Code Review 检查清单

Review agent 模块代码时，重点关注：

**Invariants**:
- [ ] PII redaction: `pii_redactor.redact()` 在传给 LLM 前调用
- [ ] Policy guard: `policy_guard.check()` 不被绕过
- [ ] Audit logging: `audit_logger.log_call()` 在 finally 块中；`output_summary` 写入前须经 `pii_redactor.redact_text()` 处理，防止 LLM 输出回传 PII 到审计日志
- [ ] DeerFlow-only: 多步骤调用不走 `core/llm.py`
- [ ] ContextVar 传播: `_run_in_executor_with_context` 正确使用
- [ ] R1 allowlist: worker 分支 + gateway 锁步对同步
- [ ] Family 隔离: temp config / memory / sandbox / MCP 无跨家庭泄漏

**DeerFlow 升级兼容**:
- [ ] `make_lead_agent()` 签名未变
- [ ] `create_chat_model()` provider 路由正确
- [ ] `sync_tool_patch.py` 的 5 个 patch 目标函数签名兼容（见 §MCP 租户管理 完整列表）
- [ ] `extensions_config` API 无变更
- [ ] `RunManager` / `StreamBridge` 接口无破坏性变更

## 加载顺序

按以下顺序加载上下文，按需深入：

1. **本文件** — DeerFlow harness 能力 + 多租户架构 + 开发指南（已加载）
2. **[DeerFlow 文档索引](references/deerflow-docs-index.md)** — 按场景查阅上游文档
3. **[Numina 经验索引](references/numina-agent-experience.md)** — 项目踩坑记录和架构决策
4. **DeerFlow 源码** — `references/deerflow/` 上游代码，仅在文档不足时查阅
5. **项目代码** — `server/apps/agent/` 当前实现

## 调试指南

| 症状 | 排查方向 |
|------|----------|
| 工具返回成功但无效果 | ContextVar 未传播 |
| MCP 工具列表跨家庭泄漏 | extensions_config 环境变量竞争 |
| Harness 静默降级 | 异常被吞 |
| thinking 内容出现在标题 | 标题中间件未过滤 thinking blocks |
| Stream 提前关闭 | SSE 连接中断 |
| MCP asyncio 死锁 | 跨线程 Lock（asyncio.Lock vs threading.Lock） |
| 模型 endpoint 不匹配 | provider 配置错误 |
| 429 / rate limit | 熔断器状态检查 + cascade fallback |

## 参考路径速查

| 需要了解 | 查阅 |
|----------|------|
| DeerFlow harness API | `server/apps/agent/deerflow_config/HARNESS_API.md` |
| 当前 harness 版本 | `server/apps/agent/deerflow_config/HARNESS_VERSION` |
| DeerFlow 上游文档 | `references/deerflow-docs-index.md` |
| 项目经验 & 踩坑 | `references/numina-agent-experience.md` |
| 项目解决方案库 | `docs/solutions/` |
| 当前模块架构 | `server/apps/agent/CLAUDE.md` |
| DeerFlow 上游架构 | `references/deerflow/backend/docs/ARCHITECTURE.md` |
| DeerFlow 配置参考 | `references/deerflow/backend/docs/CONFIGURATION.md` |
| DeerFlow MCP 集成 | `references/deerflow/backend/docs/MCP_SERVER.md` |
| 统一调度架构 | `docs/solutions/architecture-patterns/two-ai-apps-unified-dispatch-stream-run.md` |
| Adapter 解耦 | `docs/solutions/architecture-patterns/deerflow-adapter-decoupling-stream-bridge-subclass.md` |
| 三态熔断器 | `docs/solutions/architecture-patterns/three-state-circuit-breaker-with-cascade-retry-2026-05-20.md` |
