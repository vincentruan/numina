---
title: Scheduled Tasks - Plan
type: feat
date: "2026-11-03"
topic: scheduled-tasks-t23
artifact_contract: ce-unified-plan/v1
product_contract_source: ce-brainstorm
execution: code
---

## Goal Capsule

- **Objective:** 家庭 Owner 可通过 UI 管理定时 AI 任务，自定义报告生成的时间、频率和启停状态。
- **Product authority:** AI 设置页 "定时任务" tab。
- **Open blockers:** None.

---

## Product Contract

### Summary

用户可配置的定时任务管理系统。Owner 在 AI 设置页新增的"定时任务" tab 中创建、编辑、删除定时任务，选择要触发的 AI 技能（asset-report、literacy-report），设置 cron 表达式或预设频率。scheduler_worker 以轮询模式检查到期任务并执行，复用现有的 scheduler_worker → backend → agent 链路。

### Problem Frame

当前定时 AI 报告生成是 hardcoded 的：`auto_report_job` 每日 08:35 触发资产报告，`literacy_report_weekly_job` 每周日 02:00 触发识字周报。用户无法：

- 调整报告生成时间（例如改为晚上而非早晨）
- 调整频率（例如每周而非每日）
- 临时禁用某个定时任务而不删除配置
- 为不同技能设置不同的调度策略

这导致用户要么忍受不合适的时间，要么完全关闭自动生成功能。

### Requirements

**Data Model**

- R1. 系统维护 `scheduled_tasks` 表，存储用户配置的定时任务。每条记录包含：family_id、skill_id（asset-report / literacy-report）、cron 表达式、是否启用、下次执行时间、上次执行时间、执行状态。
- R2. `scheduled_tasks` 表通过 Alembic 迁移创建，包含必要的索引（family_id + is_enabled、next_run_at）。

**API**

- R3. 提供 CRUD 端点：`GET/POST/PUT/DELETE /api/v1/ai/scheduled-tasks`。POST 创建新任务，PUT 更新现有任务（包括启用/禁用切换），DELETE 删除任务。
- R4. 所有端点需要 Owner 权限验证。非 Owner 访问返回 403。
- R5. 创建/更新任务时，系统根据 cron 表达式计算 `next_run_at` 并持久化。cron 表达式以 Asia/Shanghai 时区解释，`next_run_at` 存储为 UTC。无效 cron 表达式返回 400。
- R6. skill_id 必须是白名单内的值（当前：asset-report、literacy-report）。非法 skill_id 返回 400。

**Scheduler Worker**

- R7. scheduler_worker 新增轮询任务（每 60 秒，`max_instances=1` 防并发），查询 `is_enabled=true AND next_run_at <= now() AND status != 'running'` 的任务并执行。使用 SELECT FOR UPDATE SKIP LOCKED 或状态乐观锁防止重复执行。
- R8. 任务执行走现有链路：通过 backend 内部端点触发对应 AI 技能的 stream_run（超时 5 分钟）。执行完成后更新 `last_run_at`、`status`，并计算下一个 `next_run_at`。
- R9. 执行失败时记录错误信息到 `last_error` 字段，`status` 标记为 failed，但不阻止下次调度。连续失败由 future work 处理。
- R10. 现有的 hardcoded `auto_report_job` 和 `literacy_report_weekly_job` 在迁移期间保留，但可通过配置禁用。迁移完成后移除。

**Frontend**

- R11. AI 设置页重构为 tabbed 布局，新增"定时任务" tab 与现有 provider 配置并列。
- R12. 定时任务列表展示所有任务，显示技能名称、cron 描述（人类可读）、状态、上次/下次执行时间。
- R13. 提供创建/编辑表单：技能选择（dropdown）、频率预设（每日/每周/自定义）+ cron 表达式输入、启用开关。
- R14. 删除操作需二次确认。

### Key Decisions

- **轮询模式 vs 动态注册** (session-settled: user-directed — chosen over 动态注册模式: 简单可靠，重启后自动恢复，无需在 APScheduler 中维护动态任务状态) — scheduler_worker 定期查询 DB 中到期任务执行，而非在任务创建时动态注册到 APScheduler。Governs R7, R8.
- **Owner-only 权限** (session-settled: user-directed — chosen over Adult 成员均可: 定时任务影响家庭 AI 资源消耗，应由 Owner 管控) — 仅家庭 Owner 可管理定时任务。Governs R4.
- **AI 设置页 tab** (session-settled: user-directed — chosen over 独立页面: 与 AI 相关配置聚合，减少导航层级) — 定时任务 UI 作为 AI 设置页的新 tab。Governs R11.
- **可调度技能范围** (session-settled: user-directed — chosen over 全量技能: 先覆盖已有定时任务的两种技能，验证模式后再扩展) — 当前仅支持 asset-report 和 literacy-report。Governs R6.

### Actors

- A1. **Family Owner** — 创建、编辑、删除、启用/禁用定时任务。
- A2. **Family Member (non-owner)** — 只读查看定时任务列表（可选，当前版本可不实现）。
- A3. **scheduler_worker** — 轮询并执行到期任务。
- A4. **backend** — 提供 CRUD API，验证权限，计算 next_run_at。
- A5. **agent** — 接收 stream_run 请求，执行 AI 技能。

### Key Flows

- F1. **Owner 创建定时任务**
  - **Covers R3, R5, R6, R11, R13.**
  - **Trigger:** Owner 在 AI 设置页点击"新建定时任务"。
  - **Actors:** A1, A4
  - **Steps:** Owner 选择技能、设置频率/时间、确认创建。Backend 验证 skill_id 白名单和 cron 格式、计算 next_run_at、持久化记录。
  - **Outcome:** 新任务出现在列表中，显示下次执行时间。

- F2. **scheduler_worker 执行到期任务**
  - **Covers R7, R8, R9.**
  - **Trigger:** 轮询周期到达，存在 is_enabled=true AND next_run_at <= now() AND status != 'running' 的任务。
  - **Actors:** A3, A4, A5
  - **Steps:** scheduler_worker 查询到期任务（乐观锁防止并发） → 调用 backend 内部端点（仅传 task_id）→ backend 从 DB 读取 skill_id 并触发 agent stream_run → agent 执行 AI 技能 → 执行完成 → scheduler_worker 更新 last_run_at、status、next_run_at。
  - **Outcome:** 任务状态更新为 success/failed，next_run_at 指向下一个执行时间点。

- F3. **Owner 禁用定时任务**
  - **Covers R3, R7.**
  - **Trigger:** Owner 切换任务的启用开关。
  - **Actors:** A1, A4
  - **Steps:** Backend 更新 is_enabled=false。scheduler_worker 下次轮询时跳过该任务。
  - **Outcome:** 任务保留在列表中但不再执行，显示为"已禁用"状态。

### Acceptance Examples

- AE1. **创建每日资产报告任务**
  - **Covers R1, R3, R5, R6, R11, R13.**
  - **Given:** Owner 进入 AI 设置页 "定时任务" tab，列表为空。
  - **When:** Owner 点击"新建"，选择"资产报告"，频率选"每日"，时间设为 09:00，确认。
  - **Then:** 列表显示新任务：技能=资产报告，频率=每日 09:00，状态=启用，下次执行=明日 09:00。

- AE2. **scheduler_worker 执行到期任务**
  - **Covers R7, R8.**
  - **Given:** 存在一条 is_enabled=true, next_run_at=2026-11-03 09:00, skill_id=asset-report 的任务。当前时间 09:01。
  - **When:** scheduler_worker 轮询触发。
  - **Then:** 任务被执行，agent 生成资产报告。任务更新：last_run_at=2026-11-03 09:01, status=success, next_run_at=2026-11-04 09:00。

- AE3. **非 Owner 尝试创建任务**
  - **Covers R4.**
  - **Given:** Adult 成员（非 Owner）进入 AI 设置页。
  - **When:** 尝试 POST /api/v1/ai/scheduled-tasks 创建任务。
  - **Then:** 返回 403 Forbidden。

### Scope Boundaries

**Deferred for later:**

- 任务执行历史查看（当前只存 last_run_at / status，不存完整执行日志）
- 连续失败告警/通知机制
- finance-coach、dashboard-narrative 等其他技能的定时支持
- 复杂 cron 表达式（当前仅支持预设频率 + 基础 cron）
- 任务模板/复制功能

**Outside this product's identity:**

- 实时任务编排（不属于定时任务范畴）
- 跨家庭任务共享（每个家庭的定时任务独立）

### Sources / Research

- 现有定时任务链路: `server/apps/scheduler_worker/jobs/__init__.py:auto_report_job` → `server/apps/backend/app/routers/ai_internal.py:auto_generate_reports` → agent stream_run
- Agent scheduler 契约（未启用）: `server/apps/agent/app/scheduler.py` — 定义了 stream_run 调度契约但零活跃任务
- Family 模型: `report_auto_generate_enabled` 字段已存在
- GitHub Issue #176 T23: "启用 DeerFlow 调度系统 + 支持定时 AI 报告生成"
- DB 模型模式: `server/packages/db/models/family.py` — Snowflake ID, UTCDateTime, Base 继承
- scheduler_worker 模式: `server/apps/scheduler_worker/jobs/__init__.py` — lazy imports, SessionLocal with try/finally
- 前端 AI 设置页: `frontend/apps/main/src/pages/AIConfigPage.vue` — 当前为列表页，需重构为 tabbed

---

## Planning Contract

**Product Contract preservation:** unchanged — all R-IDs, A-IDs, F-IDs, AE-IDs preserved. Flows updated with Covers citations. R5, R7, R8 strengthened with timezone, concurrency, and timeout qualifiers (implementation detail, not scope change).

### Key Technical Decisions

KTD1. **DB Schema Design** (Governs R1, R2) — `scheduled_tasks` 表使用 Snowflake ID 主键（与其他模型一致），`family_id` 为 BigInteger 外键关联 families 表。`cron_expression` 存储标准 5 字段 cron 格式（minute hour day month dow）。`skill_id` 为 VARCHAR(50) 存储技能标识符。`status` 枚举：idle/running/success/failed。索引：`(family_id, is_enabled)` 用于列表查询，`(is_enabled, next_run_at)` 用于轮询查询。

KTD2. **API Auth Pattern** (Governs R3, R4) — 所有端点（包括 GET）均需 Owner 权限验证，与 session-settled Owner-only 决策一致。复用现有 `require_owner` 依赖（参考 `server/apps/backend/app/auth/deps.py`）。所有查询必须同时过滤 `current_user.family_id`，防止跨家庭访问。

KTD3. **Cron Computation** (Governs R5) — 使用 `croniter` 库计算 `next_run_at`。创建/更新任务时，根据 cron 表达式和当前时间计算下一次执行时间。执行完成后，再次调用 croniter 计算下一个周期。时区：cron 表达式以 Asia/Shanghai 解释，`next_run_at` 存储为 UTC。

KTD4. **Scheduler Polling Job** (Governs R7, R8) — 新增 `scheduled_task_poll_job` 注册到 `setup_all_jobs()`，trigger 为 `interval` 60 秒，`max_instances=1` 防止并发。查询到期任务后，逐个调用 backend 内部端点触发执行。每个任务执行独立，一个失败不影响其他。执行超时 5 分钟。

KTD5. **Backend Internal Endpoint** (Governs R8) — 新增 `POST /api/v1/internal/ai/scheduled-tasks/execute` 端点，仅接收 `task_id`（不接收 `skill_id`，从 DB 读取以防白名单绕过）。验证 system token（从 `packages/security/service_auth/agent_token_verify.py` 导入 `verify_system_token`）。复用现有 `auto_generate_reports` 的 AgentClient 调用模式。

KTD6. **Frontend Tab Refactor** (Governs R11) — 将 `AIConfigPage.vue` 重构为 `<van-tabs>` 布局，第一个 tab 为现有 provider 配置，第二个 tab 为定时任务管理。使用 `v-show` 保持 tab 状态（避免 `v-if` 导致状态丢失）。定时任务 tab 使用 `van-list` 展示任务列表，`van-popup` + 表单实现创建/编辑。

### Assumptions

- `croniter` 库已安装或可通过 `uv add croniter` 添加
- 现有 `auto_report_job` 和 `literacy_report_weekly_job` 在迁移期保留，通过环境变量 `DISABLE_LEGACY_REPORT_JOBS=true` 控制是否跳过
- 前端 i18n key 按现有模式添加到 `zh-CN.ts` 和 `en-US.ts`

### Implementation Constraints

- 遵循 `server/AGENTS.md` Import Direction：apps 不互相导入，共享逻辑走 packages
- 遵循 `server/apps/scheduler_worker/AGENTS.md` 的 lazy import 和 session 管理模式
- 遵循 `frontend/AGENTS.md` 的 `<script setup lang="ts">` 和 Vant 4 模式

---

## Implementation Units

### U1. Database Model and Migration

- **Goal:** 创建 `scheduled_tasks` 表和对应的 ORM 模型
- **Requirements:** R1, R2
- **Dependencies:** None
- **Files:**
  - Create: `server/packages/db/models/scheduled_task.py`
  - Modify: `server/packages/db/models/__init__.py` (export ScheduledTask)
  - Create: `server/apps/backend/alembic/versions/xxxx_add_scheduled_tasks.py`
- **Approach:**
  1. 定义 `ScheduledTask` 模型，继承 `Base`，字段：id (BigInteger PK), family_id (BigInteger FK), skill_id (VARCHAR 50), cron_expression (VARCHAR 100), is_enabled (Boolean default true), next_run_at (UTCDateTime), last_run_at (UTCDateTime nullable), status (VARCHAR 20 default 'idle'), last_error (Text nullable), created_at, updated_at
  2. 添加索引：`ix_scheduled_tasks_family_enabled` on (family_id, is_enabled), `ix_scheduled_tasks_poll` on (is_enabled, next_run_at)
  3. 在 `__init__.py` 导出 `ScheduledTask`
  4. 生成 Alembic 迁移：`cd server/apps/backend && uv run alembic revision --autogenerate -m "add scheduled_tasks table"`
- **Patterns to follow:** `server/packages/db/models/family.py`, `server/packages/db/models/ai_task.py`
- **Test scenarios:**
  - Model can be instantiated with required fields
  - Table created with correct columns and indexes
  - Migration applies and rolls back cleanly
- **Verification:** `uv run alembic upgrade head` succeeds; `SELECT * FROM scheduled_tasks` returns empty table

---

### U2. Backend CRUD API

- **Goal:** 实现定时任务的 RESTful CRUD 端点
- **Requirements:** R3, R4, R5, R6
- **Dependencies:** U1
- **Files:**
  - Create: `server/apps/backend/app/routers/ai_scheduled_tasks.py`
  - Create: `server/apps/backend/app/schemas/scheduled_task.py`
  - Modify: `server/apps/backend/app/main.py` (register router)
- **Approach:**
  1. 定义 Pydantic schemas：`ScheduledTaskCreate`, `ScheduledTaskUpdate`, `ScheduledTaskResponse`（继承 SnowflakeBase）。`ScheduledTaskCreate` 中 `skill_id` 验证：regex `^[a-z][a-z0-9_-]*$`，max_length=50；`cron_expression` 验证：regex `^\S+ \S+ \S+ \S+ \S+$`（5 字段），max_length=100
  2. 实现 CRUD 端点：
     - `GET /api/v1/ai/scheduled-tasks` — 返回 `family_id=current_user.family_id` 的所有任务（Owner 权限）
     - `POST /api/v1/ai/scheduled-tasks` — 创建任务，验证 skill_id 格式和白名单，用 croniter 计算 next_run_at（Asia/Shanghai 时区→UTC 存储），croniter 异常返回 400
     - `PUT /api/v1/ai/scheduled-tasks/{id}` — 更新任务，**必须同时过滤 `task_id` AND `family_id=current_user.family_id`**，不存在返回 404
     - `DELETE /api/v1/ai/scheduled-tasks/{id}` — 删除任务，同样过滤 family_id
  3. Owner 权限验证：所有端点使用 `require_owner` 依赖（`server/apps/backend/app/auth/deps.py:619-630`）
  4. skill_id 白名单：`ALLOWED_SCHEDULABLE_SKILLS = {"asset-report", "literacy-report"}`
  5. 在 `main.py` 注册 router
- **Patterns to follow:** `server/apps/backend/app/routers/ai_report.py` (AI router pattern), `server/apps/backend/app/schemas/ai_report.py`
- **Test scenarios:**
  - Covers AE1: Owner creates task with valid skill_id, next_run_at computed correctly (UTC)
  - Covers AE3: Non-owner receives 403 on POST and GET
  - Invalid skill_id format returns 400 (not in whitelist returns different 400 message)
  - Invalid cron expression returns 400 (not 500)
  - GET returns only tasks for caller's family
  - Owner of family A cannot PUT/DELETE family B's task (returns 404, not 403)
  - PUT updates task and recomputes next_run_at
  - DELETE removes task
- **Verification:** `uv run pytest tests/backend/test_ai_scheduled_tasks.py -v` passes

---

### U3. Backend Internal Execute Endpoint

- **Goal:** 实现供 scheduler_worker 调用的内部执行端点
- **Requirements:** R8
- **Dependencies:** U1
- **Files:**
  - Modify: `server/apps/backend/app/routers/ai_internal.py`
- **Approach:**
  1. 新增 `POST /api/v1/internal/ai/scheduled-tasks/execute` 端点
  2. 仅接收 `task_id` 参数（**不接收 skill_id** — 从 DB 读取，防止白名单绕过）
  3. 验证 system token（从 `packages/security/service_auth/agent_token_verify.py` 导入 `verify_system_token`，不创建新副本）
  4. 查询 task 记录，读取 `skill_id`，验证 task 存在且 `is_enabled=true`
  5. 根据 skill_id 分发到对应的执行逻辑（复用 `auto_generate_reports` 的 AgentClient 调用模式）
  6. 返回执行结果（success/failed）
- **Patterns to follow:** `server/apps/backend/app/routers/ai_internal.py:auto_generate_reports`
- **Test scenarios:**
  - Valid task_id triggers agent stream_run with skill_id from DB
  - Invalid task_id returns 404
  - Disabled task returns 400
  - Missing system token returns 401
  - Caller cannot override skill_id via request body (only task_id accepted)
- **Verification:** `uv run pytest tests/backend/test_ai_internal_scheduled_tasks.py -v` passes

---

### U4. Scheduler Worker Polling Job

- **Goal:** 实现定时任务轮询和执行逻辑
- **Requirements:** R7, R8, R9, R10
- **Dependencies:** U1, U3
- **Files:**
  - Modify: `server/apps/scheduler_worker/jobs/__init__.py`
  - Modify: `server/apps/scheduler_worker/scheduler.py`
- **Approach:**
  1. 新增 `scheduled_task_poll_job()` 函数：
     - 查询 `is_enabled=true AND next_run_at <= now() AND status != 'running'` 的任务
     - **并发保护**：执行前将 status 更新为 'running'，WHERE 条件包含 `status != 'running'`，仅当 rowcount==1 时继续（乐观锁）
     - 逐个调用 backend 内部端点 `POST /internal/ai/scheduled-tasks/execute`（仅传 task_id），HTTP 超时 5 分钟
     - 执行成功：更新 `last_run_at`, `status='success'`, 计算下一个 `next_run_at`
     - 执行失败：更新 `status='failed'`, `last_error`（截断至 1000 字符，不含堆栈），不阻止下次调度
     - Worker 启动时：检查 `status='running' AND updated_at < 10分钟前` 的任务，重置为 `status='idle'`（崩溃恢复）
  2. 在 `setup_all_jobs()` 注册新任务：trigger=`interval`, seconds=60, id=`scheduled_task_poll`, **max_instances=1**
  3. 遵循 lazy import 和 SessionLocal with try/finally 模式
  4. 添加环境变量 `DISABLE_LEGACY_REPORT_JOBS` 控制是否跳过 `auto_report_job` 和 `literacy_report_weekly_job`
- **Patterns to follow:** `server/apps/scheduler_worker/jobs/__init__.py:auto_report_job`, `server/apps/scheduler_worker/scheduler.py` job registration
- **Test scenarios:**
  - Covers AE2: Poll job finds due task, executes, updates status and next_run_at
  - Poll job skips disabled tasks
  - Poll job skips tasks with next_run_at in future
  - Poll job skips tasks already in 'running' status
  - Failed execution records error (truncated to 1000 chars) but doesn't block other tasks
  - max_instances=1 prevents concurrent poll executions
  - Startup recovery resets stale 'running' tasks to 'idle'
  - Legacy jobs skipped when DISABLE_LEGACY_REPORT_JOBS=true
- **Verification:** `uv run pytest tests/scheduler_worker/test_scheduled_task_poll.py -v` passes

---

### U5. Frontend Scheduled Tasks Tab

- **Goal:** 在 AI 设置页新增定时任务管理 tab
- **Requirements:** R11, R12, R13, R14
- **Dependencies:** U2
- **Files:**
  - Modify: `frontend/apps/main/src/pages/AIConfigPage.vue`
  - Create: `frontend/apps/main/src/components/ai/ScheduledTasksTab.vue`
  - Create: `frontend/apps/main/src/api/ai-scheduled-tasks.ts`
  - Modify: `frontend/apps/main/src/i18n/locales/zh-CN.ts`
  - Modify: `frontend/apps/main/src/i18n/locales/en-US.ts`
- **Approach:**
  1. 重构 `AIConfigPage.vue`：用 `<van-tabs>` 包裹现有 provider 列表和新的定时任务 tab。**使用 `v-show` 而非 `v-if` 保持 tab 内容状态**（避免切换 tab 时丢失 draggable 排序、测试状态、API key 显示等）。现有 provider tab 的所有功能（draggable、test model、circuit reset）必须保持正常
  2. 创建 `ScheduledTasksTab.vue` 组件：
     - 初始加载显示 `van-skeleton`
     - 空列表显示 `EmptyState` 组件（含"创建第一个定时任务"按钮）
     - `van-list` 包裹在 `van-pull-refresh` 内展示任务列表（技能名称、cron 描述、状态、上次/下次执行时间）
     - API 错误显示 `showFailToast`
     - `van-button` 新建按钮（底部 page-actions 区域，block plain icon="plus"）→ 打开 `van-popup` 表单
     - 表单使用 `van-form` + `van-field` 配合 `:rules` 验证：
       - 技能选择：`van-field` readonly + `van-popup` + `van-picker`（遵循 AGENTS.md picker 模式）
       - 频率选择：`van-radio-group`（每日/每周/自定义），预设自动生成 cron（每日=`0 9 * * *`，每周=`0 9 * * 0`）
       - 自定义 cron：`van-field` + placeholder 示例，blur 时实时验证 5 字段格式
       - 提交时后端返回 400 显示 `showFailToast`
     - 每个任务卡片：编辑按钮、删除按钮（`showConfirmDialog` 二次确认，confirm type=danger）、启用开关
     - 非 Owner 用户：显示只读列表 + EmptyState 提示"仅家庭 Owner 可管理定时任务"，无创建/编辑/删除按钮
  3. 创建 API 封装：`fetchScheduledTasks`, `createScheduledTask`, `updateScheduledTask`, `deleteScheduledTask`
  4. 添加 i18n keys（包括验证消息）
- **Patterns to follow:** `frontend/apps/main/src/pages/AIConfigPage.vue` (existing patterns), `frontend/apps/main/src/api/ai-chat.ts` (API pattern)
- **Test scenarios:**
  - Covers AE1: Create task form submits, list refreshes with new task
  - Loading state shows skeleton, then list or empty state
  - Empty state shows EmptyState component with create button
  - Delete shows showConfirmDialog, cancel/confirm works correctly
  - Toggle enable/disable updates task
  - Invalid cron expression shows inline error on blur
  - Invalid cron expression rejected by backend returns showFailToast
  - Tab switch preserves provider tab state (draggable order, test state)
  - Non-owner sees read-only list with "仅家庭 Owner 可管理" message, no action buttons
  - API failure shows showFailToast
- **Verification:** `pnpm -r lint && pnpm -r typecheck` passes; manual verification on dev server: tab refactor doesn't break existing provider functionality

---

## Verification Contract

| Unit | Command | Pass Criteria |
|------|---------|---------------|
| U1 | `cd server/apps/backend && uv run alembic upgrade head` | Migration applies without error |
| U2 | `cd server && uv run pytest tests/backend/test_ai_scheduled_tasks.py -v` | All tests pass |
| U3 | `cd server && uv run pytest tests/backend/test_ai_internal_scheduled_tasks.py -v` | All tests pass |
| U4 | `cd server && uv run pytest tests/scheduler_worker/test_scheduled_task_poll.py -v` | All tests pass |
| U5 | `cd frontend && pnpm -r lint && pnpm -r typecheck && pnpm -r test:run` | All checks pass |
| Integration | `cd server && uv run ruff check apps/ && uv run mypy apps/ --explicit-package-bases` | No errors |

---

## Definition of Done

**Global:**
- All implementation units complete and verified
- Alembic migration applies cleanly on fresh and existing databases
- Backend tests pass (`pytest tests/backend/ tests/scheduler_worker/`)
- Frontend lint, typecheck, and tests pass
- Manual E2E verification: Owner can create/edit/delete scheduled tasks in UI
- Manual E2E verification: scheduler_worker executes due tasks and updates status

**Per-unit:**
- U1: Model importable, migration reversible
- U2: CRUD endpoints return correct responses, auth enforced
- U3: Internal endpoint triggers agent execution
- U4: Poll job finds and executes due tasks
- U5: Tab renders, forms submit, list updates

**Cleanup:**
- No dead code or unused imports
- No placeholder comments or TODO markers
- Documentation updated if needed (AGENTS.md job inventory)
- After 1 release, remove `auto_report_job` and `literacy_report_weekly_job`, remove `DISABLE_LEGACY_REPORT_JOBS` flag

---

## Deferred / Open Questions

**Deferred to implementation:**

- **Owner deactivation behavior (F8):** What happens to scheduled tasks when family owner changes or is deactivated? Implementer should decide: preserve tasks (new owner inherits), suspend, or delete. Default: preserve.
- **Pagination (S8):** GET list returns all tasks per family. Expected <50 per family. Document as assumption; add pagination if exceeded.
- **Non-owner read access (D6, A2):** Current version implements Owner-only for all endpoints (per session-settled decision). Non-owner read access deferred to future enhancement.

**Considered and not built:**

- **Lease/heartbeat mechanism for 'running' status (F4):** Crash recovery via startup stale-task reset (included in U4) is sufficient for v1. Heartbeat adds complexity without proportional benefit.
- **Split U5 into sub-units (S4):** U5 is larger than other units but represents a single deliverable (the scheduled tasks UI). Splitting adds coordination overhead without reducing risk.
- **Execution history view:** Explicitly excluded per Scope Boundaries (deferred for later).

