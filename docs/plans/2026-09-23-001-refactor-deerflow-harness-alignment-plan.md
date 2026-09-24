---
date: 2026-09-23
module: agent, backend
problem_type: architecture-alignment
artifact_contract: ce-unified-plan/v1
artifact_readiness: implementation-ready
execution: code
tags: [deerflow, checkpoint, resume, run-journal, run-event-store, stream-bridge, harness-alignment]
---

# DeerFlow Harness 对齐 — Checkpoint Resume + RunEventStore + Persistent RunStore

## Summary

对照 DeerFlow 上游 harness 的三大核心能力（RunEventStore、Checkpoint-based Resume、Persistent RunStore），将 Numina 当前缺失的能力分**三个阶段**补齐。重新排序以优先交付用户价值（checkpoint resume），再补齐基础设施（事件持久化、RunStore）。架构统一遵循 DeerFlow 原生组件——直接使用 `DbRunEventStore`、复用 `RunPipeline.checkpoint_id`、自建 SQLite `RunStore`（DeerFlow 仅提供 memory + abstract）。

### 阶段映射

| 阶段 | 目标 | Units | 用户价值 |
|------|------|-------|----------|
| Phase 1: Checkpoint Resume | 失败后从断点恢复 | U1, U2, U3 | "从断点继续" 按钮 |
| Phase 2: Event Persistence | 永久事件日志 | U4 | 可查询的 run 事件 |
| Phase 3: Persistent RunStore | 跨重启 run 状态 | U5 | 孤儿恢复、重启不丢状态 |

## Problem Frame

Numina 的 agent 模块已完成了 DeerFlow harness 的核心集成（StreamBridge、SSE wire format、RunManager、Skill system），但在以下三个关键能力域存在差距：

1. **Checkpoint-based Resume** — DeerFlow 的 checkpointer 每步自动保存图状态，支持失败后从 checkpoint 恢复执行。Numina 已有共享 checkpointer 且 `RunPipeline` 有 `checkpoint_id` 参数，但 runner 从不使用，失败后只能从头重跑。
2. **RunEventStore** — DeerFlow 自带 `DbRunEventStore`（SQLAlchemy-backed），Numina 完全未使用。现有替代方案（Redis StreamBridge 24h TTL + session_journal JSONL）分散且不持久。
3. **Persistent RunStore** — DeerFlow 的 `RunManager(store=None)` 支持可选持久化 backing，Numina 使用 `store=None`（纯内存态），进程重启后所有 run 状态丢失。

> **注意**: 当前 asset-report 的失败率较低（多数 run 成功完成），checkpoint resume 主要面向长耗时 run 的 LLM provider 超时/网络中断场景。具体故障频率需在 Phase 1 交付后通过 U4 的事件日志量化。

## Requirements

| ID | 需求 | 来源 |
|----|------|------|
| R1 | Checkpoint resume：失败后可手动触发从 checkpoint 恢复 | 用户要求 |
| R2 | 在 AITask 表记录 `last_checkpoint_id`，为 resume 提供数据基础 | R1 依赖 |
| R3 | Runner 自动检测失败 checkpoint 并恢复（Phase 1 后续） | 用户要求 |
| R4 | 使用 DeerFlow `DbRunEventStore` 持久化事件日志（不自建表） | DeerFlow 对齐 |
| R5 | RunManager 使用持久化 SQLite RunStore | DeerFlow 对齐 |
| R6 | 所有新增组件优先复用 DeerFlow 原生实现 | 架构约束 |
| R7 | 每个阶段独立可交付、可单独部署 | 工程约束 |

## Key Technical Decisions

### KTD1. 直接使用 DeerFlow `DbRunEventStore`（不自建事件表）(revised per review F3)

**原方案**: 自建 `ai_run_events` 表 + `AiRunEvent` ORM 模型 + 自定义 consumer。

**修订**: DeerFlow 已提供 `DbRunEventStore`（`deerflow/runtime/events/store/db.py`），schema 完全匹配需求（`thread_id, run_id, event_type, category, content, metadata, seq`）。直接使用 `DbRunEventStore` + `RunEventRow` ORM 模型，通过 Alembic 迁移创建 `run_events` 表。

**实现**: Backend 初始化时创建 `DbRunEventStore` 实例。Event persistence consumer 将 Redis StreamBridge 事件翻译为 `RunEventStore.put_batch()` 调用。`family_id` 作为 metadata 字段传入（不修改 DeerFlow 的表结构）。

**Chosen over**: 自建 `ai_run_events` 表 — 违反 R6（复用 DeerFlow 原生实现），且会与 DeerFlow 的 `run_events` 表产生重复。

### KTD2. Checkpoint resume 通过 `RunPipeline.checkpoint_id` 实现 (session-settled: user-directed)

DeerFlow 的 checkpoint resume 涉及 delta linearization、rollback points 等复杂机制。Numina 使用 full mode checkpointer，不需要 delta 处理。

**决策**: 只在 runner 层面增加 checkpoint_id 的记录和恢复逻辑。失败时从 checkpointer 读取最新 checkpoint ID，重试时传入 `RunPipeline(checkpoint_id=...)`。

**Chosen over**: 完整复刻 DeerFlow delta checkpoint linearization — Numina 使用 full mode，不需要。

### KTD3. 直接 import DeerFlow 类，不复制代码 (per review)

Numina 已大量直接 import DeerFlow 类（`from deerflow.runtime import ...`、`from deerflow.persistence.engine import ...` 等 40+ 处）。DeerFlow 是 `pyproject.toml` 的声明依赖（`deerflow-harness` pinned at `6556d09d`）。

**可直接复用的 DeerFlow 类：**

| 类/模块 | Import 路径 | 用途 |
|---------|-------------|------|
| `DbRunEventStore` | `deerflow.runtime.events.store.db` | 事件持久化（U4） |
| `RunEventRow` | `deerflow.persistence.models.run_event` | ORM 模型（U4 Alembic） |
| `RunEventStore` | `deerflow.runtime.events.store.base` | 抽象接口 |
| `get_session_factory` | `deerflow.persistence.engine` | 获取 async session factory |
| `RunManager` | `deerflow.runtime` | Run 生命周期管理（已有） |
| `RunRecord` / `RunStatus` | `deerflow.runtime` | Run 数据模型（已有） |

**Base 兼容性处理：** Numina 和 DeerFlow 各自有独立的 `DeclarativeBase` 子类（各自拥有独立 metadata）。`RunEventRow` 注册在 DeerFlow 的 Base 上。Alembic 迁移需合并两个 metadata：

```python
# alembic/env.py — 合并 DeerFlow 的 metadata
from packages.db.session import Base as NuminaBase
from deerflow.persistence.base import Base as DeerFlowBase
NuminaBase.metadata.append_declarative_base(DeerFlowBase)
target_metadata = NuminaBase.metadata
```

**Session factory**: Agent 的 `main.py` 已调用 `deerflow.persistence.engine.init_engine()` 初始化 DeerFlow DB engine。`DbRunEventStore(session_factory=get_session_factory())` 直接复用该 engine。Backend 侧需要在 lifespan 中也初始化 DeerFlow engine（指向同一个 DB）。

### KTD4. Persistent RunStore 需自建 SQLite 实现 (revised per review F1)

**原方案**: "DeerFlow 已有 RunStore 抽象和 RunRecord 模型，直接复用避免重复"。

**修订**: 经查证，DeerFlow 仅提供 `RunStore` 抽象接口（`base.py`，14 个抽象方法）和 `MemoryRunStore`（`memory.py`，485 行）。**没有** SQLite/PostgreSQL-backed 实现。Numina 需要自建 `NuminaSqliteRunStore` 实现全部 14 个抽象方法。

**14 个抽象方法**: `put`, `get`, `list_by_thread`, `update_status`, `start_run`, `delete`, `update_model_name`, `update_run_completion`, `list_pending`, `list_inflight`, `aggregate_tokens_by_thread`, `update_lease`, `claim_for_takeover`, `list_inflight_with_expired_lease`。

**工期评估**: 参考 `MemoryRunStore`（485 行），SQLite 实现预计 400-600 行（含 SQL 事务管理、lease 原子操作）。建议 3-5 天工期。

**Chosen over**: 继续 `store=None` — 无法支持跨重启孤儿恢复。

---

## Implementation Units

### U1. AITask 增加 last_checkpoint_id + Agent 侧捕获上报

**Goal**: 在 AITask 表记录每次 run 的最后 checkpoint ID，agent 在 stream 结束后自动捕获并上报。

**Requirements**: R1, R2, R6

**Dependencies**: none

**Files**:
- `server/packages/db/models/ai_task.py` — 增加 `last_checkpoint_id` (String, nullable) 字段
- `server/apps/backend/alembic/versions/<new>_add_last_checkpoint_id_to_ai_tasks.py` — 新增迁移
- `server/apps/backend/app/services/ai_task_service.py` — 增加 `update_checkpoint_id()` 方法
- `server/apps/backend/app/routers/ai_internal.py` — 新增 `POST /internal/tasks/{task_id}/checkpoint`
- `server/apps/backend/app/routers/ai_tasks.py` — task detail 返回 `last_checkpoint_id`
- `server/apps/agent/services/runtime/run_pipeline.py` — 修改 `__aexit__` 捕获 checkpoint ID
- `server/apps/agent/core/backend_client.py` — 新增 `report_checkpoint_id()` 方法
- `server/tests/backend/test_ai_task_checkpoint.py` — 新增测试
- `server/tests/agent/unit/test_run_pipeline_checkpoint.py` — 新增测试

**Approach**:

1. **ORM 迁移**: 在 `AiTask` 模型添加 `last_checkpoint_id` (String, nullable) 字段，Alembic 迁移。

2. **Backend endpoint**: 新增 `POST /internal/tasks/{task_id}/checkpoint`，使用 `verify_agent_token` 认证（与现有 task 端点一致），接收 `{ "checkpoint_id": "..." }` body，调用 `AITaskService.update_checkpoint_id()`。

3. **Agent 侧捕获**: 在 `RunPipeline.__aexit__` 的 finally 块中（audit log 之后），使用**异步** checkpointer API 读取最新 checkpoint：
   ```python
   # Directional guidance — not implementation specification
   try:
       checkpointer = _get_shared_checkpointer()
       config = {"configurable": {"thread_id": self.thread_id}}
       checkpoint_tuple = await checkpointer.aget_tuple(config)  # 异步 API
       if checkpoint_tuple and checkpoint_tuple.checkpoint:
           checkpoint_id = checkpoint_tuple.checkpoint.get("id")
           if checkpoint_id:
               await BackendClient(family_id=self.family_id).report_checkpoint_id(
                   task_id=self.record.metadata.get("task_id"),
                   checkpoint_id=checkpoint_id,
               )
   except Exception:
       logger.debug("checkpoint_id capture failed (non-fatal)", exc_info=True)
   ```

**Patterns to follow**: 现有 `POST /internal/tasks/{task_id}/complete` 端点的认证和参数模式

**Test scenarios**:
- `last_checkpoint_id` 默认 null，更新后正确存储
- Agent stream 结束后 checkpoint_id 被正确捕获并上报
- Checkpointer 读取失败不影响 run 完成（non-fatal）
- Backend endpoint 使用 `verify_agent_token` 认证，跨家庭请求返回 403

**Verification**: `cd server && uv run pytest tests/backend/test_ai_task_checkpoint.py tests/agent/unit/test_run_pipeline_checkpoint.py` 通过

---

### U2. Checkpoint-based Resume — 手动触发（Phase 1 前端）

**Goal**: 前端可以手动触发 "从断点继续"，后端将 `last_checkpoint_id` 传给 agent，agent 从该 checkpoint fork 恢复执行。

**Requirements**: R1

**Dependencies**: U1

**Files**:
- `server/apps/backend/app/routers/ai_report.py` — 修改 `trigger_generate_events` 支持 `resume=true`
- `server/apps/agent/services/runtime/worker.py` — 修改 `_run_asset_report_agent` 提取 `checkpoint_id`
- `server/apps/agent/app/routers/gateway.py` — 确保 `checkpoint_id` 通过 `config.configurable` 传递
- `frontend/apps/main/src/api/ai.ts` — 修改 API 类型，task detail 返回 `last_checkpoint_id`
- `frontend/apps/main/src/pages/AIReportPage.vue` — 增加 "从断点继续" 按钮
- `frontend/apps/main/src/i18n/locales/zh-CN.ts` — 增加 i18n key
- `server/tests/backend/test_ai_report_checkpoint_resume.py` — 新增测试

**Approach**:

1. **Backend resume 触发**: `POST /ai/report/generate/events?resume=true` 时，读取 `task.last_checkpoint_id`，注入到 agent trigger body 的 `config.configurable.checkpoint_id` 字段。

2. **Agent worker 提取**: `_run_asset_report_agent` 需要从 `graph_input` 的 `config` 中提取 `checkpoint_id`（与 `_run_numina_agent` 现有逻辑一致，参见 `worker.py:1695-1701`），传给 `RunPipeline(checkpoint_id=...)`。

3. **前端 UX 流程**:
   - **按钮可见条件**: `stream.status === 'error' && task.last_checkpoint_id != null`
   - **点击后**: 调用 `POST /ai/report/generate/events?resume=true`，UI 进入 streaming 状态
   - **恢复中**: 显示 "从断点恢复中..." 进度消息，timeline 从已完成的步骤开始显示
   - **部分输出处理**: resumed run 继续使用同一个 thread，checkpointer 恢复消息历史，LLM 从上次中断处继续
   - **错误状态**: resume 失败（checkpoint 过期/损坏）→ 显示 "断点恢复失败，请重新生成"，提供 "重新生成" 按钮
   - **注意**: checkpoint fork 是 LangGraph 图状态恢复，不是业务步骤跳过。LLM 从 checkpointed 消息历史继续，可能重复部分工作（如重新生成已完成的 markdown），这是 LangGraph 的正常行为。

4. **Checkpoint fork 语义**: DeerFlow checkpointer fork 恢复最后保存的图状态（消息列表 + tool 结果）。LLM 从该状态继续生成。由于 asset-report 是单次 `run_skill()` 调用，LLM 会从 checkpointed 消息历史自然继续——但不保证精确跳过已完成步骤。

**Patterns to follow**: `_run_numina_agent` 的 `checkpoint_id` 提取路径（`worker.py:1695-1701`）

**Test scenarios**:
- `resume=true` 时 `last_checkpoint_id` 正确传递给 agent
- `_run_asset_report_agent` 从 `config.configurable.checkpoint_id` 提取并传给 RunPipeline
- Agent 从 checkpoint 恢复执行并继续产出事件
- 无 `last_checkpoint_id` 时 `resume=true` 返回 400
- Checkpoint 损坏/过期时前端显示错误状态

**Verification**: 手动测试：生成报告 → 中途失败 → 点击 "从断点继续" → 报告从断点恢复

---

### U3. Checkpoint-based Resume — 自动检测（Phase 1 后续）

**Goal**: Worker runner 自动检测上一次失败的 run，在重试时自动从 checkpoint 恢复。

**Requirements**: R3

**Dependencies**: U2

**Files**:
- `server/apps/agent/services/runtime/run_pipeline.py` — 修改 `__aenter__` 增加自动检测
- `server/apps/agent/services/runtime/worker.py` — 修改 runner 函数支持 `auto_resume` 标志
- `server/apps/agent/core/backend_client.py` — 新增 `get_task_status()` 查询方法
- `server/tests/agent/unit/test_worker_auto_resume.py` — 新增测试

**Approach**:

1. **数据源**: `_was_last_run_failed()` 通过 `BackendClient.get_task_status(family_id, task_id)` 查询 AITask 的 status。如果 status 为 `failed`/`interrupted` 且 `last_checkpoint_id` 不为空，返回 True。

2. **自动检测逻辑**: 在 `RunPipeline.__aenter__` 中，如果 `checkpoint_id` 为 None 且 `auto_resume=True`：
   ```python
   # Directional guidance
   if self.checkpoint_id is None and auto_resume:
       task_status = await BackendClient(family_id).get_task_status(task_id)
       if (task_status.get("status") in ("failed", "interrupted")
           and task_status.get("last_checkpoint_id")):
           self.checkpoint_id = task_status["last_checkpoint_id"]
   ```

3. **`auto_resume` 标志**: 通过 agent trigger body 的 `config.configurable.auto_resume` 传入。Backend 在重新触发 failed task 时自动设置此标志。

4. **恢复语义**: checkpoint fork 后 LLM 从 checkpointed 消息历史继续。由于 LangGraph 的非确定性，恢复后的输出可能与中断前不完全一致。

**Test scenarios**:
- 上一次 run 失败后，新 run 自动从 checkpoint 恢复
- 上一次 run 成功时，不触发自动恢复
- `auto_resume=False` 时不自动恢复
- BackendClient 查询失败时不影响正常 run 启动

**Verification**: `cd server && uv run pytest tests/agent/unit/test_worker_auto_resume.py` 通过

---

### U4. Event Persistence — 使用 DeerFlow DbRunEventStore

**Goal**: 将 Redis StreamBridge 事件持久化到 DeerFlow 的 `DbRunEventStore`（`run_events` 表），实现可查询的永久事件日志。

**Requirements**: R4, R6

**Dependencies**: none（可与 U1 并行）

**Files**:
- `server/apps/backend/app/services/event_persistence_consumer.py` — 新增消费者（翻译 Redis 事件 → DbRunEventStore 调用）
- `server/apps/backend/app/services/bridge_consumer.py` — 在 `_spawn_lifecycle_consumer` 增加事件转发
- `server/apps/backend/alembic/env.py` — 合并 DeerFlow Base metadata
- `server/apps/backend/alembic/versions/<new>_add_run_events_table.py` — 引入 RunEventRow 迁移
- `server/apps/backend/app/main.py` — lifespan 中初始化 DeerFlow engine（如未初始化）
- `server/tests/backend/test_event_persistence_consumer.py` — 新增测试

**Approach**:

1. **直接 import DeerFlow 类**（不复制代码）:
   ```python
   from deerflow.runtime.events.store.db import DbRunEventStore
   from deerflow.persistence.engine import get_session_factory
   ```
   `DbRunEventStore` 接受 `async_sessionmaker[AsyncSession]` 参数。Agent 侧 `get_session_factory()` 已在 `main.py` lifespan 中初始化；Backend 侧需在同一 lifespan 中调用 `init_engine()` 指向同一个 DB。

2. **Alembic metadata 合并**: 在 `apps/backend/alembic/env.py` 中合并 DeerFlow 的 Base metadata，使 `run_events` 表纳入 Alembic 管理：
   ```python
   from packages.db.session import Base as NuminaBase
   from deerflow.persistence.base import Base as DeerFlowBase
   NuminaBase.metadata.append_declarative_base(DeerFlowBase)
   target_metadata = NuminaBase.metadata
   ```
   然后运行 `alembic revision --autogenerate` 生成 `run_events` 表迁移。

3. **集成注意事项**:
   - **`family_id` 租户隔离**: DeerFlow `RunEventRow` 无 `family_id` 列。将 `family_id` 存入 `event_metadata` JSON 字段。查询时通过 `event_metadata["family_id"].as_string() == family_id` 过滤。
   - **`user_context` ContextVar**: `list_*` 方法调用 `get_current_user()`。Consumer 在后台运行，所有查询传 `user_id=AUTO`。写入时 `user_id` 自动为 `None`。
   - **双数据库兼容**: `DbRunEventStore` 原生支持 SQLite（`FOR UPDATE` 行锁）和 PostgreSQL（`pg_advisory_xact_lock`）。

4. **Event Persistence Consumer**: 订阅与 lifecycle consumer 相同的 Redis Stream。对每个事件，翻译为 `DbRunEventStore.put_batch()` 调用：
   - `event_type` 映射：`messages` → `llm.ai.response`，`custom` → `trace`，`end` → `run.end`，`error` → `run.error`
   - `family_id` 存入 `event_metadata` 字段
   - 批量写入（每 20 条 flush，对齐 DeerFlow 的 `flush_threshold`）

5. **数据保留**: 使用 `DbRunEventStore.delete_by_thread()` 和 `delete_by_run()` 实现清理。默认保留 30 天。

6. **集成**: 在 `_spawn_lifecycle_consumer` 中增加 `persist_events=True` 参数。启用时，lifecycle consumer 在读取事件的同时转发给 `EventPersistenceConsumer`。

**Patterns to follow**: DeerFlow `DbRunEventStore.put_batch()` 的批量写入模式

**Test scenarios**:
- 事件正确从 Redis 写入 `run_events` 表
- `family_id` 正确存入 metadata
- 重复事件不会重复插入（`put_if_absent` 幂等）
- DB 写入失败时事件不丢失（buffer 回退重试）
- 30 天保留策略正确清理旧事件

**Verification**: `cd server && uv run pytest tests/backend/test_event_persistence_consumer.py` 通过

---

### U5. Persistent RunStore for RunManager

**Goal**: 将 `RunManager(store=None)` 切换到 SQLite-backed `NuminaSqliteRunStore`，支持跨重启的 run 状态追踪。

**Requirements**: R5, R6

**Dependencies**: U1（task 表中已有 `last_checkpoint_id`，RunStore 可引用）

**Files**:
- `server/apps/agent/services/runtime/numina_run_store.py` — 新增 SQLite RunStore（14 个方法）
- `server/apps/agent/services/runtime/lifespan.py` — 修改 `init_runtime` 传入 store
- `server/apps/agent/services/runtime/gc.py` — 修改孤儿恢复逻辑
- `server/apps/agent/alembic/versions/<new>_add_run_records_table.py` — 新增迁移
- `server/tests/agent/unit/test_numina_run_store.py` — 新增测试

**Approach**:

1. **实现 `NuminaSqliteRunStore`**: 实现 DeerFlow `RunStore` 的全部 14 个抽象方法。参考 `MemoryRunStore`（`deerflow/runtime/runs/store/memory.py`，485 行）的结构，使用 DeerFlow 的 `get_session_factory()` 获取 `async_sessionmaker`（与 KTD4 共用同一个 DeerFlow DB engine）。

2. **核心方法**（按优先级分批实现）:
   - **第一批（核心 CRUD）**: `put`, `get`, `delete`, `update_status`, `start_run`, `list_inflight`, `list_pending`
   - **第二批（lease 管理）**: `update_lease`, `claim_for_takeover`, `list_inflight_with_expired_lease`
   - **第三批（完成/统计）**: `update_run_completion`, `update_model_name`, `aggregate_tokens_by_thread`

3. **表结构**: `run_records`（`run_id TEXT PK`, `thread_id TEXT`, `status TEXT`, `on_disconnect TEXT`, `metadata_json TEXT`, `lease_expires_at TIMESTAMP`, `created_at TIMESTAMP`, `updated_at TIMESTAMP`）。

4. **Lifespan 集成**: `init_runtime` 中创建 `NuminaSqliteRunStore` 实例，传入 `RunManager(store=run_store)`。

5. **孤儿恢复**: `gc.py` 的 `reconcile_orphaned_runs()` 从 persistent store 读取 inflight runs。启动时标记所有 `status=running` 但 lease 过期的 run 为 `interrupted`。

6. **Reconciliation 策略**: persistent store 成为主路径；现有 AITask-based fallback 仅在 `store=None`（内存模式）时激活。添加 guard 防止双重处理。

**工期**: 参考 MemoryRunStore（485 行），预计 400-600 行 SQLite 实现，3-5 天。

**Test scenarios**:
- 全部 14 个方法正确实现并通过单元测试
- Run 创建后持久化到 SQLite
- Agent 重启后可以从 store 恢复 inflight run 列表
- 孤儿恢复正确标记 interrupted runs
- Lease 过期 + claim_for_takeover 原子操作正确
- `store=None` 时 AITask fallback 正常工作

**Verification**: `cd server && uv run pytest tests/agent/unit/test_numina_run_store.py` 通过

---

## Verification Contract

| Gate | Command | Expected |
|------|---------|----------|
| Backend lint | `cd server && uv run ruff check apps/` | All checks passed |
| Backend tests | `cd server && uv run pytest tests/backend/ -x -q` | All pass |
| Agent tests | `cd server && uv run pytest tests/agent/ -x -q` | All pass |
| Alembic migrations | `cd server/apps/backend && uv run alembic upgrade head` | Success |
| Frontend typecheck | `cd frontend/apps/main && pnpm typecheck` | No new errors |
| Frontend tests | `cd frontend/apps/main && pnpm vitest run` | All pass |
| Checkpoint resume e2e | 手动：生成报告 → 中途失败 → 点击 "从断点继续" | 报告从断点恢复 |

## Definition of Done

- [ ] 所有 5 个 Implementation Units 交付
- [ ] 3 个 Alembic 迁移已应用（`last_checkpoint_id`、`run_events`、`run_records`）
- [ ] Backend + Agent 全部测试通过
- [ ] Frontend typecheck 无新增错误
- [ ] Checkpoint resume 端到端验证：报告生成失败 → 从断点恢复成功
- [ ] 事件持久化验证：Redis 事件成功写入 `run_events` 表并可查询
- [ ] `RunManager` persistent store 验证：agent 重启后孤儿恢复正常工作

## Risks & Dependencies

| Risk | Impact | Mitigation |
|------|--------|------------|
| Checkpoint fork 后 LLM 输出不一致 | U2/U3 恢复后报告内容可能变化 | 这是 LangGraph 非确定性的固有行为，文档中明确说明 |
| U5 RunStore 实现工期超预期 | 14 个抽象方法，含 lease CAS 操作 | 参考 MemoryRunStore 结构；可分两批实现（核心 CRUD 先，lease 后） |
| Checkpointer `aget_tuple` API 差异 | U1 checkpoint_id 捕获可能失败 | try/except non-fatal；添加单元测试验证 API |
| Redis StreamBridge 事件丢失导致 event persistence 不完整 | U4 的事件日志有缺失 | StreamBridge 24h TTL + MAXLEN 保护；consumer 失败时 buffer 回退重试 |
| `_was_last_run_failed` 查询增加 agent→backend HTTP 开销 | U3 每次 run 启动增加一次 API 调用 | 轻量查询（单行 SELECT）；失败时 non-fatal，降级为不恢复 |
| `sync_tool_patch.py` monkey-patch 兼容性 | HARNESS_VERSION 升级后 patch 可能失效 | 每次升级须运行 `pytest tests/agent/ -v`；关注 `_patched_get_available_tools`、`_apply_active_skill_tool_filter` 的方法签名变化 |
| `_generate_temp_config` 缓存 key 复杂度 | 新增配置维度需更新 9 维元组 | 在 `_adapter_cache` 声明处补充注释，记录每个维度的含义和新增时的更新要求 |
| DeerFlow `reload_app_config` 全局副作用 | 并发创建不同家庭 client 时 config 竞争 | `_init_lock` 序列化同 key 创建；client 创建后立即捕获 `_app_config`（不在 stream 时重读）；升级为 DeerFlow 版本后须验证此假设 |

---

## Architecture Evaluation: Multi-Tenant DeerFlow Integration

> 本节评估 Numina 的多租户 DeerFlow 集成架构是否合理，以及是否最大化复用了 DeerFlow。

### 当前架构

```
family_adapter_cache (LRU, max 100 families)
│
├── Family A ──→ temp config.yaml ──→ NuminaDeerFlowClient A
├── Family B ──→ temp config.yaml ──→ NuminaDeerFlowClient B
└── Family C ──→ temp config.yaml ──→ NuminaDeerFlowClient C

共享: checkpointer (thread_id 隔离) + stream_bridge (Redis, run_id 隔离)
```

每个家庭通过 `_generate_temp_config()` 生成临时 `config.yaml`，注入模型/Memory/MCP/Skill/Sandbox 等配置。`_generate_temp_config` 模块化设计（`_inject_memory`, `_inject_mcp`, `_inject_skills`, `_inject_token_budget`, `_inject_web_search`）使每个关注点独立可维护。

### 评估矩阵

| 维度 | 评估 | 说明 |
|------|------|------|
| DeerFlow 复用率 | ✅ 高 | 执行引擎、Skill 系统、MCP 客户端、中间件链、Checkpointer、SSE 协议全部直接复用 |
| 升级兼容性 | ✅ 好 | `deerflow-harness` pip 依赖跟踪上游；`sync_tool_patch` 是主要适配风险点 |
| 多租户隔离 | ✅ 完善 | Memory 路径 + MCP 配置 + Checkpointer thread_id + StreamBridge key 四维隔离 |
| 配置灵活性 | ✅ 高 | 每个家庭独立配置模型、MCP、Skill、Memory |
| 性能 | ✅ 合理 | LRU (max 100) 避免重复创建；共享 checkpointer 避免多实例开销 |

### Per-Family Client 方案论证

**为什么 per-family DeerFlowClient 是正确的方案：** DeerFlow 的 `DeerFlowClient.__init__` 调用 `reload_app_config(config_path)` 加载全局 `AppConfig`。每个家庭的模型/MCP/Skill 配置不同，必须有独立的 client 实例。DeerFlow 原生不支持运行时配置切换——没有 "per-request config override" 机制。

**替代方案对比：**

| 方案 | 优势 | 劣势 |
|------|------|------|
| Per-family client (当前) | 完整隔离；匹配 DeerFlow 设计 | LRU 管理复杂度；temp dir 清理 |
| 单 client + per-request override | 更简单 | DeerFlow 不支持；需 fork harness |
| 共享 client + config 热切换 | 节省内存 | `reload_app_config` 全局，并发不安全 |

### DeerFlow 复用清单

| 组件 | 复用方式 | 评估 |
|------|----------|------|
| `DeerFlowClient` | 子类化 `NuminaDeerFlowClient` | ✅ 最小化扩展 |
| `RunManager` / `RunRecord` / `RunStatus` | 直接 import | ✅ 零修改 |
| `StreamBridge` | 直接 import + `NuminaRedisStreamBridge` 扩展 | ✅ 合理扩展 |
| `reload_app_config` | 直接调用 | ✅ DeerFlow 原生 |
| `filter_tools_by_skill_allowed_tools` | 通过 `sync_tool_patch` 间接使用 | ✅ |
| `TodoListMiddleware` | 子类化 | ✅ |
| `LocalSkillStorage` | DeerFlow 原生扫描 | ✅ |
| `DbRunEventStore` | 直接 import（本计划新增） | ✅ |
| `compact_thread_context` | 通过 `compact_service.py` 封装 | ✅ |
| `DeerFlowClient.stream()` | 通过 adapter 层调用 | ✅ |

### 结论

**架构合理，DeerFlow 复用率高。** 核心执行路径（`DeerFlowClient.stream()` → LangGraph → bridge）完全复用 DeerFlow，自定义仅限于配置注入层（`family_adapter_cache`）和适配层（`sync_tool_patch`、`NuminaDeerFlowClient`）。升级红利通过 pip 依赖自动传递——DeerFlow 的执行引擎、Skill 系统、MCP 客户端、中间件、checkpointer 等核心组件的改进自动生效。主要维护成本集中在 `sync_tool_patch.py`（monkey-patch 兼容性）和 temp config 管理。

### 改进项（纳入本计划 Risks）

1. **`sync_tool_patch.py` 升级风险**: 每次 `HARNESS_VERSION` 升级须运行 `pytest tests/agent/ -v`，特别关注 `_patched_get_available_tools` 和 `_apply_active_skill_tool_filter` 的方法签名变化
2. **缓存 key 文档化**: 在 `_adapter_cache` 声明处补充注释，记录 9 维 key 各字段含义和新增配置维度时的更新要求
3. **`reload_app_config` 全局副作用验证**: HARNESS_VERSION 升级时须验证 DeerFlow 是否仍在 stream() 时重读全局 config（当前假设 client 创建后不再重读）

## Sources & Research

- DeerFlow `DbRunEventStore`: `server/.venv/.../deerflow/runtime/events/store/db.py` — 可直接复用
- DeerFlow `RunStore` ABC: `server/.venv/.../deerflow/runtime/runs/store/base.py` — 14 个抽象方法
- DeerFlow `MemoryRunStore`: `server/.venv/.../deerflow/runtime/runs/store/memory.py` — 485 行参考实现
- DeerFlow `RunJournal`: `server/.venv/.../deerflow/runtime/journal.py` — ~980 行回调处理器（本次不复刻）
- Numina `RunPipeline`: `server/apps/agent/services/runtime/run_pipeline.py` — `checkpoint_id` 参数已存在
- Numina checkpointer: `server/apps/agent/services/deerflow_adapter/family_adapter_cache.py` — `_get_shared_checkpointer()`
- Numina `bridge_consumer.py`: `server/apps/backend/app/services/bridge_consumer.py` — Redis subscribe + lifecycle consumer
