# Agent 模块全面重构需求文档

**日期：** 2026-05-16  
**状态：** 待规划  
**范围：** `server/apps/agent/`

---

## 背景

Agent 模块基于 DeerFlow 2.0 harness 构建，但当前实现存在三类系统性偏差：

1. **协议偏差** — 流式事件处理使用自定义 `[THINK]`/`[TEXT]` 前缀，而非 DeerFlow 2.0 标准的 `messages-tuple`/`values`/`end` 事件协议；`DeerFlowClient` 初始化未使用 `subagent_enabled`、`plan_mode` 等 2.0 新参数。
2. **能力缺口** — 长 agent 任务（多步规划、子 agent 协调）未激活；并发上限（4）和超时（60s）不适合长周期任务；JSONL 会话日志存储在容器本地磁盘，重启即丢失。
3. **隔离缺口** — DeerFlow memory（facts）在所有家庭间共享，存在跨家庭数据污染风险。

本次重构目标：使 agent 模块完全运行在 DeerFlow 2.0 的标准路径上，同时补全三项核心能力。

---

## 目标与成功标准

| 目标 | 验收标准 |
|------|---------|
| DeerFlow 2.0 协议对齐 | 流式事件处理直接消费 `messages-tuple`/`values`/`end`，无自定义前缀解析 |
| 家庭维度模型管理 | `DeerFlowClient` 通过 `model_name` 参数注入模型，temp config 文件路径废弃 |
| 长 agent 任务支持 | `subagent_enabled=True` 和 `plan_mode=True` 可按 skill 配置启用；超时可配置至 300s |
| JSONL 持久化 | 会话事件写入 DeerFlow Postgres persistence engine，重启后可查询 |
| 家庭级内存隔离 | 每个家庭有独立的 memory namespace，facts 不跨家庭可见 |
| Gateway API 集成 | 支持通过 Gateway API 查询模型列表、管理技能启用状态、清理线程数据 |

---

## 范围

### 包含

- `services/deerflow_adapter/adapter.py` — 流式事件协议迁移，`DeerFlowClient` 参数补全
- `services/deerflow_adapter/family_adapter_cache.py` — 模型注入方式迁移，内存隔离实现
- `services/session_journal.py` — 保持文件写入逻辑不变，补充 `jsonl_path` 返回值供 session_store 持久化
- `services/session_store.py` + backend `ai_chat_sessions` 表 — 新增 `jsonl_path` 字段，upsert 时写入
- `deerflow_config/base/config.yaml` — 超时、并发、subagent、plan_mode 配置项
- `app/routers/cache.py` + 新增 Gateway API 路由 — 技能管理、线程清理、模型列表端点
- `skills/*.md` frontmatter — 补充 `subagent_enabled`、`plan_mode` 字段
- 相关单元测试和集成测试

### 不包含

- 前端 UI 变更（Gateway API 管理界面留待后续）
- 新增 AI 能力/skill（本次只改基础设施）
- APScheduler 定时任务激活（Phase 0 保持不变）
- JSONL 文件的实际存储迁移（文件继续写磁盘，只新增路径引用持久化）

---

## 详细需求

### R1：流式事件协议迁移

**当前行为：** `adapter.py` 的 `_produce()` 函数手动解析 `event.data` 中的 `reasoning_content` 和 Anthropic thinking blocks，拼接 `[THINK]{content}` 前缀字符串推入队列。

**目标行为：** 直接消费 DeerFlow 2.0 标准事件：
- `messages-tuple` with `type=ai` → 文本内容（含 thinking blocks）
- `values` → 标题、状态等元数据
- `end` → 用量统计（tokens）

**约束：**
- NDJSON 流协议（`chat/ask/stream`）已使用标准事件类型，保持不变
- 旧的 `text/plain` 流协议（其他 capability）迁移到 NDJSON，或保留但去掉自定义前缀解析
- `[THINK]` 前缀在 NDJSON 协议中已通过 `phase.thinking` 事件类型表达，不需要前缀

### R2：DeerFlowClient 参数补全

**当前行为：** `family_adapter_cache._init_client()` 只传 `config_path` 和 `checkpointer`。

**目标行为：** 按 skill 配置传入完整参数：

```python
DeerFlowClient(
    config_path=...,
    checkpointer=...,
    model_name=family_model_id,      # 直接传参，废弃 temp config 注入
    thinking_enabled=skill.thinking,
    subagent_enabled=skill.subagent_enabled,
    plan_mode=skill.plan_mode,
)
```

**约束：**
- `model_name` 直接传参后，`_generate_temp_config()` 中的模型注入逻辑可删除，但 `api_key`/`base_url` 仍需通过 config 文件注入（DeerFlow 2.0 无直接传参路径）
- `subagent_enabled` 和 `plan_mode` 是 per-dispatch 参数，不是 per-client 参数——需确认 DeerFlow 2.0 API 是否支持在 `stream()` 调用时覆盖

### R3：家庭级内存隔离

**当前行为：** 所有家庭共享一个 DeerFlow memory 实例（`deerflow_config/base/config.yaml` 中的 `memory.path` 指向单一 JSON 文件）。

**目标行为：** 每个家庭有独立的 memory namespace：
- 方案 A（推荐）：memory 路径按家庭分段，如 `data/memory/{family_id}/memory.json`，在 `_generate_temp_config()` 中动态注入
- 方案 B：若 DeerFlow 2.0 memory 支持 Postgres namespace，通过 `memory.namespace = family_id` 配置

**约束：**
- 内存隔离不影响 checkpointer（checkpointer 已通过 `thread_id` 隔离，无需变更）
- 家庭 memory 文件随家庭缓存清理时一并清理（或保留供审计）

### R4：JSONL 会话日志路径引用持久化

**当前行为：** `session_journal.py` 将事件写入 `data/sessions/{family_id}/{session_id}.jsonl`（容器本地磁盘）。`session_store.py` 通过 backend HTTP 将会话元数据（标题、状态、摘要）写入 backend DB，但 `jsonl_path` 字段未持久化——重启后无法通过 session ID 找回对应的 JSONL 文件。

**目标行为：** JSONL 文件继续写磁盘，但将文件路径引用持久化到 backend DB：

- **JSONL 文件存储不变** — 继续写 `{SESSIONS_DATA_DIR}/{family_id}/{session_id}.jsonl`，`SessionJournalService` 逻辑不变
- **路径引用写入 backend DB** — `session_store.py` 的 `upsert_session()` 调用在创建会话时同步写入 `jsonl_path` 字段（本地路径、共享存储挂载路径、或网盘 URL 均可）
- **读取时通过路径定位文件** — `GET /sessions/{id}/events` 先从 backend DB 查询 `jsonl_path`，再读取对应文件；不再依赖运行时内存中的 `_path_cache`
- **路径格式无约束** — `jsonl_path` 是不透明字符串，支持本地路径（`/app/data/sessions/...`）、NFS/SMB 挂载路径、或对象存储 URL（`s3://...`、`oss://...`）；agent 只负责写入路径，不负责解析格式

**约束：**
- backend DB schema 需新增 `jsonl_path` 字段到 `ai_chat_sessions` 表（Alembic migration）
- `jsonl_path` 在 `session.start` 事件写入时确定，后续不变
- 写入 `jsonl_path` 失败仍静默处理（不阻断主流程），但需记录 WARNING
- 审计日志（`audit_logger.py`）保持独立，不迁移（它是 ops 日志，不是用户数据）
- DeerFlow 自身的 checkpointer/memory DB 复用 backend 已有的 SQLite 或 Postgres 实例（通过 `DEERFLOW_DB_URL` 指向同一连接串），不独立配置新数据库

### R5：长 agent 任务支持

**当前行为：** `_SEMAPHORE(4)` + `ThreadPoolExecutor(4)`，超时 60s（`ai_config` 默认值），`subagent_enabled` 和 `plan_mode` 未传入 `DeerFlowClient`。

**目标行为：**
- 超时可按 skill 配置，默认 120s，长任务 skill（`report`、`time_machine`）可配置至 300s
- `skills/*.md` frontmatter 新增 `subagent_enabled: bool`（默认 false）和 `plan_mode: bool`（默认 false）字段
- 并发上限从 4 提升至 8（`_SEMAPHORE(8)` + `ThreadPoolExecutor(8)`），非流式 `_CHECKPOINTER_LOCK` 保持不变（SQLite 限制）
- 若 `DEERFLOW_DB_URL` 配置了 Postgres，`_CHECKPOINTER_LOCK` 可移除（Postgres 支持并发写）

### R6：Gateway API 集成

新增三个内部端点，代理到 DeerFlow Gateway API：

| 端点 | 方法 | 代理目标 | 用途 |
|------|------|---------|------|
| `/internal/models` | GET | `GET /api/models` | 查询当前 DeerFlow 可用模型列表 |
| `/internal/skills/{name}` | PUT | `PUT /api/skills/{name}` | 动态启用/禁用 skill |
| `/internal/threads/{id}` | DELETE | `DELETE /api/threads/{id}` | 清理会话线程数据 |

**约束：**
- 这三个端点仅供 backend 内部调用，需 `X-Agent-Token` 认证
- Gateway API 地址从 `AgentSettings` 读取（新增 `DEERFLOW_GATEWAY_URL` 环境变量，默认 `http://localhost:8001`）

---

## 非功能需求

- **向后兼容：** `model_name` 传参失败时降级到 temp config 注入；`jsonl_path` 写入 backend DB 失败不阻断主流程
- **测试覆盖：** 每项变更需对应单元测试；R4 需集成测试覆盖 `jsonl_path` 写入和读取路径
- **无新依赖：** 不引入 DeerFlow 之外的新 Python 包

---

## 开放问题

1. **`subagent_enabled`/`plan_mode` 是 per-client 还是 per-dispatch？** 需确认 DeerFlow 2.0 vendored harness 的 `DeerFlowClient.stream()` 签名是否支持在调用时覆盖这两个参数。若只能在 client 初始化时设置，则 family_adapter_cache 需按 `(family_id, config_id, subagent_enabled, plan_mode)` 四元组缓存。
2. **DeerFlow memory Postgres namespace 支持？** 需确认 vendored harness 的 memory 配置是否支持 per-namespace 路径，或只能通过文件路径区分。
3. **`_CHECKPOINTER_LOCK` 移除条件：** Postgres checkpointer 是否真正支持并发写，需在 vendored harness 代码中验证。

---

## 依赖

- DeerFlow vendored harness 版本需支持 `model_name` 直接传参（需确认 `vendor/deerflow-harness/` 当前版本）
- `DEERFLOW_DB_URL` 复用 backend 已有的 SQLite 或 Postgres 连接串，在 Docker Compose 中与 backend 共享同一环境变量，不独立配置新数据库实例
- `DEERFLOW_GATEWAY_URL` 需在 Docker Compose 中配置（默认 `http://localhost:8001`）
- backend `ai_chat_sessions` 表需新增 `jsonl_path` 字段（Alembic migration，属于 backend 模块变更）
