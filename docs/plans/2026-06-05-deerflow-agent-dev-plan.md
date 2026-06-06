# DeerFlow Agent 开发规划

> 调研日期: 2026-06-05  
> 分支: feat/deerflow-agent  
> 项目路径: /Volumes/LexarSSDNQ790/geek_space/github/numina_dev_space/numina-deerflow

---

## 一、当前架构总结

### 1.1 整体架构

```
┌─────────────────────────────────────────────────────────────────┐
│                        Frontend (Vue/TS)                        │
└────────────────────────┬────────────────────────────────────────┘
                         │ HTTP / SSE
┌────────────────────────▼────────────────────────────────────────┐
│                    Backend (FastAPI)                            │
│  - JWT 认证 / 家庭隔离                                          │
│  - 资产 / 负债 / 仪表盘数据 CRUD                                │
│  - AI 配置管理 (provider, API key 加密存储)                      │
│  - MCP SSE Server (numina-family-data)                          │
└──────────┬──────────────────────────────┬───────────────────────┘
           │ X-Agent-Token + X-Family-Id  │ HTTP (session metadata)
┌──────────▼──────────────────────────────▼───────────────────────┐
│                   Agent Service (FastAPI :8001)                  │
│                                                                  │
│  ┌────────────────────────────────────────────────────────────┐  │
│  │  Routers (14 个): report, alerts, chat, disposal, etc.    │  │
│  └───────────────────────────┬────────────────────────────────┘  │
│                              │                                   │
│  ┌───────────────────────────▼────────────────────────────────┐  │
│  │                    Orchestrator                             │  │
│  │  PolicyGuard → BackendClient → PIIRedactor → DeerFlow     │  │
│  │  → AuditLogger                                              │  │
│  └───────────────────────────┬────────────────────────────────┘  │
│                              │                                   │
│  ┌───────────────────────────▼────────────────────────────────┐  │
│  │              DeerFlow Adapter Layer                         │  │
│  │  ┌──────────────────┐  ┌────────────────────────────────┐  │  │
│  │  │ adapter.py       │  │ family_adapter_cache.py        │  │  │
│  │  │ - dispatch()     │  │ - LRU cache (100 families)     │  │  │
│  │  │ - stream_dispatch│  │ - temp config generation       │  │  │
│  │  │                  │  │ - multi-provider support       │  │  │
│  │  └──────────────────┘  │ - checkpointer management      │  │  │
│  │                         └────────────────────────────────┘  │  │
│  │  ┌──────────────────┐  ┌────────────────────────────────┐  │  │
│  │  │ skill_loader.py  │  │ client_factory.py              │  │  │
│  │  │ - SKILL.md 加载  │  │ - DeerFlowClient singleton     │  │  │
│  │  │ - family override│  │                                │  │  │
│  │  └──────────────────┘  └────────────────────────────────┘  │  │
│  └───────────────────────────┬────────────────────────────────┘  │
│                              │                                   │
│  ┌───────────────────────────▼────────────────────────────────┐  │
│  │              Agent-First Path (新增)                        │  │
│  │  agent_dispatch.py → EffectiveConfigBuilder → make_lead_  │  │
│  │  agent() → astream() → NDJSON                              │  │
│  └────────────────────────────────────────────────────────────┘  │
│                                                                  │
│  支撑组件:                                                       │
│  - PII Redactor (脱敏) / Policy Guard (权限)                     │
│  - Audit Logger (审计) / Session Journal (会话日志)              │
│  - Stream Events (NDJSON) / Output Mapper (响应格式化)           │
│  - Chat Adapter (MCP 注入 + 系统提示)                            │
└──────────────────────────────────────────────────────────────────┘
                           │
            ┌──────────────┴──────────────┐
            │  DeerFlow Harness (vendored) │
            │  - LangGraph 图执行          │
            │  - Skill / Tool / MCP / Mem  │
            │  - Checkpointer (SQLite)     │
            │  - Planning / Subagent       │
            └─────────────────────────────┘
```

### 1.2 两条执行路径

项目目前存在 **两条并行执行路径**：

| 特性 | Legacy Orchestrator 路径 | Agent-First 路径 |
|------|-------------------------|------------------|
| 入口 | `routers/*.py` → `orchestrator.dispatch()` | `routers/agent_stream.py` → `agent_dispatch.stream_agent_dispatch()` |
| 配置生成 | `family_adapter_cache._generate_temp_config()` | `EffectiveConfigBuilder.build()` |
| DeerFlow 调用 | `DeerFlowAdapter.dispatch()` / `stream_dispatch()` | `make_lead_agent()` → `astream()` |
| 流协议 | text/plain 或 NDJSON | NDJSON only |
| 技能加载 | `skill_loader.py` 从文件读取 | `EffectiveConfigBuilder` symlink + DeerFlow 自动发现 |
| Checkpointer | `reload_app_config()` + env var 切换 | `RunnableConfig` 注入 `AppConfig` |

### 1.3 关键技术决策

1. **DeerFlow 为唯一执行路径** — `fallback_engine.py` 已是空壳，无 LLM 回退
2. **家庭级配置隔离** — 每家庭独立 temp config、独立 memory.json、thread_id 命名空间
3. **PII 脱敏强制** — 所有 LLM 调用前经过 `pii_redactor.redact()`
4. **审计不可绕过** — `finally` 块保证每条请求都有审计日志
5. **Provider 熔断级联** — 支持多 provider 自动切换（closed/half_open/open 三态）
6. **Provider 深度思考适配** — 自动映射 DeepSeek/OpenAI/Anthropic 的思考参数

---

## 二、已完成功能清单

### 2.1 核心基础设施

| 功能 | 状态 | 说明 |
|------|------|------|
| DeerFlow Harness Vendor | ✅ | `scripts/vendor-deerflow.sh` 从参考仓库复制 |
| 家庭级 Adapter 缓存 | ✅ | LRU 100 条目，`(family_id, config_id, subagent, plan_mode, mcp_hash)` 五元组 key |
| 动态配置生成 | ✅ | `_generate_temp_config()` 注入 api_key/model_id/base_url/web_search_providers |
| 多 Provider 支持 | ✅ | DeepSeek / OpenAI / OpenAI-compatible / Anthropic，自动选择模型类 |
| 深度思考适配 | ✅ | 各 provider 的 thinking 参数自动映射 |
| Checkpointer 共享 | ✅ | 全局单例 `AsyncSqliteSaver`，thread_id 命名空间隔离 |
| 并发控制 | ✅ | `asyncio.Semaphore(8)` + `_CHECKPOINTER_LOCK` 序列化 SQLite 写入 |
| PII Redactor | ✅ | 结构化 + 文本脱敏 |
| Policy Guard | ✅ | AI 开关 + 能力白名单 + admin_only + 角色校验 |
| Audit Logger | ✅ | JSONL 格式，30 天轮转 |
| Session Journal | ✅ | JSONL 追加写，session 生命周期管理 |
| Session Store | ✅ | 通过 HTTP 代理到 backend 持久化 |
| NDJSON Stream Events | ✅ | `EventStreamBuilder` 完整事件协议 |
| Output Mapper | ✅ | DeerFlow 输出 → `AgentResponse` 结构化映射 |
| 错误分类 | ✅ | `permanent_auth` / `transient_server` / `transient_timeout` 等 |
| Provider 熔断级联 | ✅ | half_open 10% 探测，transient 自动切换到下一 provider |

### 2.2 Agent-First 路径

| 功能 | 状态 | 说明 |
|------|------|------|
| `agent_dispatch.py` | ✅ | 新入口：BackendClient → EffectiveConfigBuilder → RunnableConfig → make_lead_agent → astream |
| `EffectiveConfigBuilder` | ✅ | 无全局单例突变，每次请求独立配置 |
| `make_lead_agent()` 集成 | ✅ | DeerFlow 2.0 的 `make_lead_agent` 通过 `RunnableConfig` 注入 |
| Agent 配置获取 | ✅ | `BackendClient.get_agent_config(agent_id)` + 自动回退到 numina |
| 技能范围解析 | ✅ | `_resolve_skills()` 实现 R5/R6/R15 + U9 规则 |
| MCP 服务器注入 | ✅ | SSE 握手 URL 构建 + auth headers (X-Agent-Token, X-Family-Id, X-Caller-User-Id) |
| extensions_config.json | ✅ | MCP 工具加载配置生成 |

### 2.3 路由与 API

| 端点 | 协议 | 状态 |
|------|------|------|
| `/report/generate` | text/plain | ✅ |
| `/report/generate/stream` | NDJSON | ✅ |
| `/alerts/aging` | text/plain | ✅ |
| `/alerts/stream` | NDJSON | ✅ |
| `/liability/analyze` | text/plain | ✅ |
| `/liability/stream` | NDJSON | ✅ |
| `/disposal/scan` | text/plain | ✅ |
| `/disposal/stream` | NDJSON | ✅ |
| `/allocation/drift` | text/plain | ✅ |
| `/allocation/stream` | NDJSON | ✅ |
| `/chat/ask` | text/plain | ✅ |
| `/chat/ask/stream` | NDJSON | ✅ |
| `/spending-leak` | text/plain | ✅ |
| `/spending-leak/stream` | NDJSON | ✅ |
| `/suggest/asset` | text/plain | ✅ |
| `/time-machine/interpret` | text/plain | ✅ |
| `/time-machine/stream` | NDJSON | ✅ |
| `/import/parse` | text/plain | ✅ |
| `/agent/{agent_id}/stream` | NDJSON | ✅ Agent-First |
| `/internal/gateway/*` | HTTP proxy | ✅ |
| `/capabilities` | JSON | ✅ |
| `/sessions` | JSON | ✅ |
| `/model-test` | JSON | ✅ |

### 2.4 Skills（13 个）

| Skill | 目录 | thinking | planning | MCP 工具 |
|-------|------|----------|----------|----------|
| `chat` | builtin | ✅ | - | - |
| `chat-search` | builtin | ✅ | - | web_search, web_fetch |
| `report` | builtin | - | - | numina-family-data (5 tools) |
| `alerts` | builtin | - | - | - |
| `allocation` | builtin | - | - | - |
| `disposal` | builtin | - | - | - |
| `liability` | builtin | - | - | - |
| `spending_leak` | builtin | - | - | - |
| `family-asset-checkup` | builtin | - | - | - |
| `family-liability-review` | builtin | - | - | - |
| `fixed-asset-followup` | builtin | - | - | - |
| `family-finance-insight-planner` | builtin | - | ✅ (max 5 steps) | - |
| `skill-creator` | builtin | ✅ | - | - |
| `skill-installer` | builtin | ✅ | - | web_search |

### 2.5 配置管理

| 配置项 | 说明 |
|--------|------|
| `deerflow_config/base/config.yaml` | 基础模板（models 由 adapter 动态注入） |
| `deerflow_config/dev/config.yaml` | 开发 overlay（更短超时、更低 memory 阈值） |
| `deerflow_config/prod/config.yaml` | 生产 overlay（限制 allowed_fact_categories） |
| `deerflow_config/agents/family-finance-agent/profile.yaml` | Agent profile（身份 + skill 组 + 系统提示后缀） |

---

## 三、待开发功能清单（按优先级排列）

### P0 — 关键缺失（影响核心可用性）

#### 3.1 统一两条执行路径
- **问题**: Legacy Orchestrator 和 Agent-First 并行存在，配置生成、技能加载、checkpointer 管理逻辑重复
- **影响**: 维护成本高、行为不一致风险、bug 难以定位
- **建议**: 以 Agent-First 路径为最终方向，逐步迁移 legacy routers 到 `agent_dispatch.py`

#### 3.2 `assets` 和 `members` 上下文始终为空
- **位置**: `orchestrator._build_context()` hardcodes `assets=[]`, `members=[]`
- **影响**: report、alerts 等涉及资产和成员的 skill 无法获取完整数据
- **建议**: 在 backend 新增 `/api/v1/internal/assets` 和 `/api/v1/internal/members` 端点，在 `_build_context()` 中并发拉取

#### 3.3 Scheduler 零任务
- **位置**: `scheduler.py` 所有 job 注册被注释
- **影响**: 定时任务（如每日资产体检报告、到期预警）无法自动执行
- **建议**: 启用至少 1-2 个核心定时任务，验证 APScheduler 与 DeerFlow 集成的兼容性

### P1 — 重要功能（影响产品体验）

#### 3.4 Agent-First 路径缺少重试/级联逻辑
- **现状**: `agent_dispatch.py` 没有实现 `_select_provider_with_retry` 重试机制
- **影响**: 当首选 provider 失败时，Agent-First 路径直接报错，不会切换到备用 provider
- **建议**: 从 `orchestrator.py` 提取重试逻辑为共享模块

#### 3.5 流式事件缺少 `plan_update` 类型
- **现状**: `EventStreamBuilder.plan_update()` 已实现，但 `agent_dispatch.py` 的 `astream()` 循环没有处理 `todos` 事件
- **影响**: 用户看不到 TodoList 规划步骤
- **建议**: 在 `astream()` 事件分发中增加 `values` 类型的 `todos` 处理

#### 3.6 Web Search 在 Agent-First 路径中未完整实现
- **现状**: `agent_dispatch.py` 仅注入 system guidance，没有处理 web_search providers/MCP 的级联
- **影响**: 启用联网搜索时可能不生效
- **建议**: 在 `EffectiveConfigBuilder` 中注入 web_search tool 配置

#### 3.7 Token 计量缺失
- **现状**: `EventStreamBuilder.end()` 的 `tokens_used` 硬编码为 0
- **影响**: 无法追踪 AI 使用量、无法做账单/配额管理
- **建议**: 从 DeerFlow/LangGraph 的 usage metadata 中提取 token 数

#### 3.8 Vision 理解能力未接入 DeerFlow
- **现状**: `import_parse` capability 标记 `task_type="vision"`，但 `orchestrator._build_context()` 不传递图片数据
- **影响**: 票据/账单 OCR 解析能力不完整
- **建议**: 在 `FamilyContext` 中增加 `images` 字段，adapter 中传递多模态消息

### P2 — 优化与增强

#### 3.9 自定义 Skill 的运行时安装
- **现状**: `skill-installer` 已存在，但缺少完整的安装/启用/卸载生命周期
- **建议**: 增加 skill 安装状态管理、依赖校验、冲突检测

#### 3.10 多轮对话上下文压缩优化
- **现状**: `deerflow_config/base/config.yaml` 配置了 summarization（40 条消息或 6000 tokens 触发）
- **建议**: 验证压缩效果，针对财务场景优化 `summary_prompt`

#### 3.11 审计日志增强
- **现状**: 审计日志记录基本字段（capability、success、duration、error_type）
- **建议**: 增加 provider_name、model_id、token_usage、circuit_state 等字段

#### 3.12 Temp 配置清理健壮性
- **现状**: `family_adapter_cache.py` 用 `tempfile.mkdtemp()` 创建临时目录，崩溃时留下孤儿目录
- **建议**: 增加启动时清理过期目录的逻辑（基于文件修改时间 > 24h）

#### 3.13 DeerFlow Harness 版本管理
- **现状**: `HARNESS_VERSION` 记录了 commit SHA `329a181`，但 vendor 脚本需要手动运行
- **建议**: 增加 CI 检查 vendored harness 版本是否匹配期望 SHA

#### 3.14 前端 Agent Stream 集成
- **现状**: `agent_stream.py` 后端端点已就绪，但需要前端配合
- **建议**: 确认前端已有 NDJSON 事件消费能力，验证 UI 渲染

---

## 四、关键技术决策建议

### Dec-1: 统一执行路径的方向

**推荐**: 以 Agent-First (`agent_dispatch.py` + `EffectiveConfigBuilder`) 为最终方向

**理由**:
- Agent-First 不使用 `reload_app_config()` 全局单例突变，避免了并发配置污染
- `EffectiveConfigBuilder` 每次请求独立构建配置，无 TOCTOU 竞争
- `RunnableConfig` 注入模式更符合 LangGraph 2.0 的设计哲学
- Legacy 路径的 `_generate_temp_config()` 需要 `_init_lock` 序列化，限制了并发度

**迁移策略**: 保持 backward compatibility，先将 legacy routers 的 dispatch 调用替换为 `agent_dispatch.stream_agent_dispatch()`

### Dec-2: Checkpointer 策略

**推荐**: 保持全局共享 `AsyncSqliteSaver` + thread_id 命名空间隔离

**理由**:
- 已验证 DeerFlow 通过 thread_id 做状态隔离
- 多 SQLite 文件方案增加管理复杂度且无必要
- 若后续扩展到 Postgres 集群，DeerFlow `init_engine(backend="postgres")` 已支持

**注意**: `_CHECKPOINTER_LOCK` 序列化所有非流式写入。若并发压力增大，考虑改用 WAL mode 或迁移到 Postgres。

### Dec-3: Skill 加载机制

**推荐**: 统一使用 `EffectiveConfigBuilder._materialize_skills()` symlink 方案

**理由**:
- symlink 方案让 DeerFlow 从单一目录发现所有 skill，符合 DeerFlow 设计
- Legacy `skill_loader.py` 的 HTTP fetch 模式增加了 backend 依赖链
- `EffectiveConfigBuilder` 同时支持 builtin 和 tenant custom skills

### Dec-4: PII 脱敏边界

**推荐**: 保持当前 `PIIRedactor` 在 agent 层的脱敏策略，不将原始数据传给 DeerFlow

**理由**:
- 符合金融科技合规要求（数据最小化原则）
- DeerFlow 的 memory 和 checkpointer 存储的是脱敏后的数据
- 审计日志记录的是脱敏后的 summary

**注意**: 需定期 review `PIIRedactor` 的规则列表，确保覆盖新增的 PII 类型

### Dec-5: 流式协议选择

**推荐**: 新能力统一使用 NDJSON 协议

**理由**:
- NDJSON 支持丰富的事件类型（phase/token/tool.call/tool.result/plan.update/error）
- 前端可据此渲染 thinking 动画、tool 调用状态、规划步骤等
- Legacy text/plain 协议无法传递结构化事件

### Dec-6: 子 Agent 和规划模式

**现状**: `subagent_enabled` 和 `plan_mode` 作为 init-time 参数传入 `DeerFlowClient`
- `family-finance-insight-planner` skill 启用 `planning: enabled: true, max_steps: 5`
- 其他 skill 默认关闭

**推荐**: 保持按 skill 按需开启，不要全局启用

**理由**:
- 子 Agent 和规划模式增加延迟和 token 消耗
- 仅对复杂深度研究任务（如综合财务规划）有意义
- 简单问答场景不需要

---

## 五、风险与注意事项

| 风险 | 影响 | 缓解措施 |
|------|------|----------|
| DeerFlow Harness 上游更新 | vendor 版本落后可能导致 API 不兼容 | 定期同步，CI 检查版本匹配 |
| SQLite 并发写入限制 | `_CHECKPOINTER_LOCK` 限制并发度 | 监控 QPS，超阈值时迁移 Postgres |
| Temp 配置目录泄漏 | 进程崩溃后孤儿目录积累 | 启动时清理 + 定期 cron 清理 |
| 两路径行为不一致 | bug 难定位、测试结果不可靠 | 优先统一路径 |
| 审计日志与 session store 分歧 | backend HTTP 失败导致 DB 无记录 | 增加本地 journal 到 DB 的补偿同步 |
| LLM 响应格式变化 | `output_mapper` 解析失败 | 增加 schema 校验 + 降级到纯文本 |

---

## 六、建议开发顺序

```
Phase 1 (P0):
  1. 修复 assets/members 上下文为空 → 新增 backend 端点
  2. 启用 scheduler 核心定时任务
  
Phase 2 (P0 + P1):
  3. Agent-First 路径添加 provider 重试/级联
  4. 统一两条执行路径（legacy → agent_dispatch 迁移）
  
Phase 3 (P1):
  5. 完善 web search 在 Agent-First 路径中的支持
  6. 实现 token 计量
  7. 修复 stream 中 plan_update 事件处理
  
Phase 4 (P2):
  8. Vision 能力接入
  9. 审计日志增强
  10. Temp 配置清理健壮性
  11. Skill 运行时安装完善
```
