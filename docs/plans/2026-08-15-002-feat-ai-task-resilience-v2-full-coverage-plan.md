---
artifact_contract: ce-unified-plan/v1
artifact_readiness: implementation-ready
product_contract_source: ce-brainstorm
execution: code
date: 2026-08-15
revised: 2026-08-15
type: feat
---

# AI Task Resilience v2: 统一任务跟踪 + 双层流式恢复 - Plan

## Goal Capsule

**Objective:** 以 **AITask 表** 为核心，构建统一的任务跟踪与双层恢复机制。所有 AI 任务（包括 Chat）统一走 AITask 跟踪，用户切走页面后 DeerFlow 继续后台执行，回来时通过双层模型恢复：在页面时 bridge consumer SSE 实时流式 + 切走/刷新后 AITask 轮询。Agent 在执行过程中通过 HTTP callback 将关键进度写入 AITask.progress。

**Product authority:** Backend 拥有 AITask 生命周期管理和进度查询 API。Agent 专注于 DeerFlow agent 能力执行，通过 HTTP callback 更新进度。前端在页面时通过 bridge consumer SSE 实时接收，切走后通过轮询 `/api/v1/ai/tasks/{id}` 恢复。

**Open blockers:**
- Import/Wish-Advice 是同步处理，非流式 — 不在本次转换范围
- Chat 增加 AITask 后台跟踪，用户在页面时仍保留 SSE 流式体验

### Context

v1 实现（U1-U8）构建了基础设施：StreamBridge、AITask 追踪、bridge consumer、优雅关停、孤儿恢复。**但只有 `asset-report` 完成了 AITask 跟踪。** 其余 AI 功能仍是 fire-and-forget。

v2 架构经过三轮评审修正：
1. ~~第一轮：移动 Gateway 组件~~ → DeerFlow 是单进程，无组件可移动
2. ~~第二轮：EventBus 抽象层~~ → 过度设计，轮询模型更简单且足够
3. **第三轮（当前）：双层模型（SSE 在页面 + 轮询恢复）+ 统一后台执行** → AITask 作为唯一状态源，在页面时 bridge consumer SSE 实时流式 + 切走后轮询恢复

**为什么选轮询而非 EventBus：**

| 维度 | EventBus (push) | 轮询 (pull) |
|------|----------------|-------------|
| 延迟 | 毫秒级 | 1-2s（后台任务可接受） |
| 断线恢复 | 需 Last-Event-ID + gap 检测 | 天然支持（下次 poll 即可） |
| 复杂度 | Protocol + 订阅管理 + 背压 | 极简：DB 写 + DB 读 |
| 集群支持 | 需 Redis pub/sub | DB 本身就是共享存储 |
| 前端改造 | SSE 重连 + gap 处理 | 标准轮询 |

**核心洞察**：除了 Chat 的 token-by-token 流式体验，其他后台任务（Report/Coach/Literacy/Narrative）的用户不需要逐 token 实时流。他们只需要知道"任务在跑、跑到哪了、最终结果是什么"。

本计划解决：

1. **统一任务跟踪**：所有 AI 任务（含 Chat）创建 AITask 记录
2. **进度轮询**：Agent 通过 HTTP callback 写入关键进度，前端轮询获取
3. **后台续命**：用户切走页面后任务继续执行，回来时恢复状态
4. **Chat 增强**：Chat 增加 AITask 后台跟踪（用户在页面时仍保留 SSE 流式）
5. **用户主动取消**：所有 AI 任务支持用户主动取消（当前仅 Chat 有取消按钮，其余功能缺失）

---

## Product Contract

### Requirements

#### R1: AITask 进度模型 + HTTP Callback

Backend 扩展 AITask 作为唯一任务状态源。Agent 在执行过程中通过 HTTP callback 更新进度。

**AITask.progress JSON 结构（按功能类型）：**

```python
# 后台任务（Finance Coach / Literacy / Narrative / Report）
AITask.progress = {
    "status": "generating",        # generating | processing | complete
    "step": "analyzing_assets",    # 当前步骤名称
    "steps_completed": 1,          # 已完成步骤数
    "steps_total": 3,              # 总步骤数
    "result_summary": "...",       # 完成后的结果摘要（可选）
}

# Chat 任务
AITask.progress = {
    "status": "generating",
    "message_count": 5,            # 当前对话消息数
    "last_assistant_message_id": "msg_xxx",
}
```

**Agent HTTP Callback 端点：**

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `POST /internal/tasks/{task_id}/progress` | Agent → Backend | 更新 AITask.progress JSON |
| `POST /internal/tasks/{task_id}/complete` | Agent → Backend | 标记任务完成 + 最终结果 |
| `POST /internal/tasks/{task_id}/fail` | Agent → Backend | 标记任务失败 + 错误信息 |
| `POST /internal/tasks/{task_id}/heartbeat` | Agent → Backend | 续期 lease_expires_at |
| `POST /internal/tasks/{task_id}/cancel` | Agent → Backend | Agent 确认取消完成（Backend 通过已有 `/api/threads/{id}/runs/{run_id}/cancel` 通知 Agent 停止） |

**写入频率**：约 3-5 次/任务（关键节点，不是逐 token）。heartbeat 频率 = `lease_ttl / 3`（对齐 DeerFlow `_heartbeat_loop` 模式），当前 lease_ttl=120s → heartbeat 每 40s 一次。

**职责分配：**

| 职责 | Backend | Agent |
|------|---------|-------|
| AITask 创建/查询 | ✅ | ❌ |
| 进度更新 API | ✅ 接收 callback | ✅ 发送 callback |
| lease heartbeat | ✅ 接收 | ✅ 每 40s 发送（lease_ttl/3） |
| 任务结果存储 | ✅ DB | ❌ |
| AI 任务执行 | ❌ | ✅ DeerFlow |
| 实时 SSE 流式（Chat 在页面时） | ❌ | ✅ StreamBridge |
| checkpointer | ❌ | ✅ LangGraph（开发: SQLite / 生产: PostgreSQL via `DEERFLOWDB_URL`） |

#### R2: 统一任务跟踪（5 个 AI 功能）

所有 AI 任务统一创建 AITask 记录，前端通过轮询获取状态：

1. Backend 创建 AITask 记录（skill_id 区分功能）
2. Backend 触发 Agent（非流式或流式）
3. Agent 执行过程中通过 HTTP callback 更新进度
4. 前端定时轮询 `/api/v1/ai/tasks/{task_id}` 获取状态
5. 用户切走页面后任务继续执行，回来时通过轮询恢复

**转换目标（5 个 AI 功能）：**

| Feature | Current Pattern | Target |
|---------|----------------|--------|
| Finance Coach | `agent_client.stream()` HTTP proxy | AITask(coach) + bridge consumer SSE (on-page) + Agent HTTP callback + 前端轮询 (recovery) |
| Literacy Report | `agent_client.stream()` HTTP proxy | AITask(literacy) + bridge consumer SSE (on-page) + Agent HTTP callback + 前端轮询 (recovery) |
| Dashboard Narrative | `agent_client.stream()` HTTP proxy | AITask(narrative) + bridge consumer SSE (on-page) + Agent HTTP callback + 前端轮询 (recovery) |
| Asset Report | AITask(report) + bridge consumer (v1) | 保持不变（v1 已实现） |
| **AI Chat** | 前端直连 Agent SSE（无 AITask） | **新增 AITask(chat) 后台跟踪** + 用户在页面时保留 SSE |

**Chat 的特殊处理：**
- 用户在 Chat 页面时：保留现有 SSE 直连 Agent（token-by-token 流式体验不变）
- 用户切走页面时：DeerFlow 继续后台执行（AITask 跟踪），回来时通过 checkpointer + AITask 恢复
- 用户刷新页面时：从 DeerFlow checkpointer 恢复对话历史，如果任务还在跑则重连 SSE

**不转换（有意为之）：**

| Feature | Current Pattern | 原因 |
|---------|----------------|------|
| Wish Advice | 同步 HTTP 调用 | 非流式，`generate_advice()` 直接返回 JSON，亚秒级 |
| Bill Import | 同步文件处理 | 非流式，parse → DB write |
| `ai_suggest` | 轻量 LLM 调用 | 亚秒级，无需任务追踪 |
| `ai_input_polish` | 轻量 LLM 调用 | 亚秒级，无需任务追踪 |
| `ai_config` | provider 验证 | 亚秒级，无需任务追踪 |
| `ai_skills` | 管理操作 | 非 AI 任务 |

#### R3: Unified Task Lifecycle

所有 AI 任务创建 AITask 记录。`skill_id` 区分功能：

| skill_id | Feature | Trigger Route | 跟踪方式 |
|----------|---------|---------------|----------|
| `report` | Asset Report | `/ai/report/generate/events` | AITask + bridge consumer (v1 已实现) |
| `coach` | Finance Coach | `/ai/finance-coach/generate` | AITask + HTTP callback + 前端轮询 (本次) |
| `literacy` | Literacy Report | `/ai/literacy-report/generate/events` | AITask + HTTP callback + 前端轮询 (本次) |
| `narrative` | Dashboard Narrative | `/dashboard/narrative` | AITask + HTTP callback + 前端轮询 (本次) |
| `chat` | AI Chat | `/api/threads/{id}/runs/stream` | AITask 后台跟踪 + SSE 流式 (本次) |

任务状态统一：`running → post_processing → completed | failed | interrupted | timeout | cancelled`

**已有 `cancelled` 状态**（v1 的 `cancel_task()` 实现），完整状态机：
`queued → running → post_processing → completed | failed | interrupted | timeout | cancelled`

#### R4: 前端恢复策略（轮询 + SSE 混合）

**两层分离**：

| 层 | 用途 | 机制 | 写频率 |
|---|------|------|-------|
| **实时流式层** | Chat 用户在页面时的 token-by-token 体验 | SSE (bridge consumer for Report/Coach/Literacy/Narrative; direct proxy for Chat) | 每个 token |
| **任务跟踪层** | 所有任务的状态 + 进度 + 断线恢复 | AITask.progress (DB) + 轮询 | 关键节点（3-5 次/任务） |

**各功能恢复行为：**

| Feature | 用户在页面时 | 用户切走/刷新后 |
|---------|------------|----------------|
| Report | SSE 流式 (v1, bridge consumer) | 轮询 AITask → 显示进度/结果 |
| Coach | SSE 流式 (bridge consumer, U13) | 轮询 AITask → 显示结果 |
| Literacy | SSE 流式 (bridge consumer, U14) | 轮询 AITask → 显示结果 |
| Narrative | SSE 流式 (bridge consumer, U15) | 轮询 AITask → 显示结果 |
| **Chat** | **SSE 流式**（现有模式不变） | **从 checkpointer 恢复对话历史** + 如果任务还在跑则重连 SSE |

**前端轮询策略：**

```typescript
// useTaskPolling(taskId, interval = 2000)
// - 每 2s 轮询 GET /api/v1/ai/tasks/{taskId}
// - status=running → 更新进度条/步骤显示
// - status=completed → 停止轮询，显示结果
// - status=failed/interrupted → 停止轮询，显示错误 + 重试按钮
// - 页面不可见时（document.hidden）暂停轮询，重新可见时恢复
```

**Chat 恢复流程：**
1. 用户在 Chat 页面 → SSE 直连 Agent（token-by-token，现有模式不变）
2. 用户切走 → AITask(chat) 跟踪继续，DeerFlow checkpointer 持久化对话状态
3. 用户返回 → **先检查 AITask.status**（terminal state preflight，对齐 DeerFlow `shouldSkipReconnect()`）：
   - completed → 从 checkpointer 加载完整对话，不重连 SSE
   - failed/interrupted → 显示错误 + 重试按钮
   - running → 从 checkpointer 加载已有对话 + 重连 SSE 继续接收
4. 用户刷新页面 → 同上（hard navigation）

#### R5: Graceful Shutdown — Backend 主导的两层协调

**Phase 1 — 拒绝新任务（立即，两层）：**
- Backend `ShutdownGuardMiddleware`：返回 503 + `Retry-After: 30`
- Agent 拒绝新 run 创建（通过 shutdown_state 或 HTTP 503）

**Phase 2 — Drain 进行中的任务（有界等待）：**
- Backend：
  - 现有 SSE 连接保持打开
  - 等待 `shutdown_timeout`（60s，可通过 `RUN_DRAIN_TIMEOUT_SECONDS` 环境变量配置）
  - 超时后标记剩余 AITask 为 `interrupted`
- Agent：
  - 停止接受新 run
  - 进行中的 agent 任务继续执行
  - Backend 通过已有端点 `/api/threads/{id}/runs/{run_id}/cancel` 通知 Agent 取消特定任务
  - Agent 收到取消信号后优雅停止 DeerFlow 执行，并调用 `cancel_task()` 回调确认

**Phase 3 — 清理退出：**
- Backend：关闭 DB 连接池，退出
- Agent：关闭 checkpointer，退出

**中断任务标识：**
- `error_message = "服务重启，任务中断，请重试"`
- 前端检测 `status=interrupted` → 显示重试按钮
- 用户点击重试 → 创建新 AITask，重新触发 Agent

#### R6: Orphan Recovery — Backend 启动时 + 周期性执行

**启动时恢复：**
1. Backend 启动时查询 `AITask WHERE status IN ('running','post_processing') AND lease_expires_at < now`
2. 对每个过期任务：条件性声明（原子 UPDATE + lease guard）
3. 新任务保护：如果同一 `(family_id, skill_id)` 已有更新的 completed 任务，跳过
4. 标记 interrupted with error message
5. 前端展示 interrupted 任务 + 重试引导

**周期性检测（Phase 2）：**
- 间隔：每 120s 执行一次（与 `lease_expires_at` 默认 120s 对齐）
- 复用启动时的恢复逻辑

#### R7: Tenant Isolation

所有任务数据按 `family_id` 隔离：
- AITask 查询始终包含 `WHERE family_id = :family_id`
- Agent HTTP callback 必须携带 `X-Family-Id` header
- API 端点通过现有 family-scoped JWT/cookie 认证

v1 已实现，无需修改。

#### R8: 用户主动取消

所有 AI 任务支持用户主动取消。当前状态：
- **Chat**: 已有取消（前端 stop 按钮 → `client.runs.cancel()` → Agent `RunManager.cancel()`）
- **Report/Coach/Literacy/Narrative**: **无取消入口**（前端无按钮，后端 `cancel_task()` 仅更新 DB 不停 Agent 执行，`VALID_SKILL_IDS` 不含新功能）

v2 补全：
1. 新增 `POST /api/v1/ai/tasks/{task_id}/cancel` 端点（task_id 级别，替代旧的 skill_id 级别）
2. Backend 收到取消请求后：立即标记 `AITask.status = cancelled` + 调用 Agent `/api/threads/{id}/runs/{run_id}/cancel` 停止执行
3. 前端各 AI 功能页面在任务 `running` 状态时显示取消按钮
4. 清理现有死代码（`api/ai.ts:cancelAITask()` 从未调用）

### Flows

#### Flow 1: 后台任务正常执行（轮询模式）

```
Frontend                    Backend                      Agent
   |                           |                           |
   |-- POST /generate -------->|                           |
   |                           |-- create AITask (DB)      |
   |<-- { task_id, status } ---|                           |
   |                           |-- agent_client.post() --->| (触发，非流式)
   |                           |                           |-- run_agent()
   |                           |                           |   执行中...
   |                           |<-- POST /tasks/{id}/progress --| (步骤1完成)
   |                           |-- AITask.progress 更新    |
   |                           |                           |   继续执行...
   |                           |<-- POST /tasks/{id}/progress --| (步骤2完成)
   |                           |                           |
   |-- GET /tasks/{id} (2s) -->|                           |
   |<-- { status, progress } --|                           |
   |   (显示进度)               |                           |
   |                           |                           |
   |                           |<-- POST /tasks/{id}/complete ---| (完成)
   |                           |-- AITask → completed      |
   |                           |                           |
   |-- GET /tasks/{id} (2s) -->|                           |
   |<-- { status: completed, result } --|                  |
   |   (显示结果，停止轮询)     |                           |
```

#### Flow 2: Chat 执行（SSE 流式 + AITask 后台跟踪）

```
Frontend                    Backend                      Agent
   |                           |                           |
   | (用户在 Chat 页面)         |                           |
   |-- POST /runs/stream ----->|                           |
   |                           |-- create AITask(chat)     |
   |                           |-- agent_client.stream() ->| (SSE 流式)
   |<-- SSE: token1 -----------|<-- stream frame ----------|
   |<-- SSE: token2 -----------|<-- stream frame ----------|
   |   (token-by-token 显示)   |                           |
   |                           |                           |
   | (用户切走页面)             |                           |
   |   SSE 断开                |   DeerFlow 继续执行       |
   |                           |   checkpointer 持久化     |
   |                           |<-- POST /tasks/{id}/progress --| (heartbeat)
   |                           |                           |
   | (用户返回)                 |                           |
   |-- GET /tasks/{id} ------->|                           |
   |<-- { status: running } ---|                           |
   |-- 从 checkpointer 加载对话历史                          |
   |-- POST /runs/stream ----->| (重连 SSE)                |
   |<-- SSE: 继续流式 ---------|                           |
```

**关键**：Chat 在用户在页面时保持 SSE token-by-token 流式体验。AITask 跟踪只用于后台续命和断线恢复。

#### Flow 3: 优雅关停

```
SIGTERM → Backend + Agent
   |
   Backend:
   |-- shutting_down = True
   |-- reject new POST → 503
   |-- drain timeout 60s:
   |      wait for in-flight tasks to complete
   |      check AITask lease_expires_at for dead workers
   |-- timeout → mark remaining AITask "interrupted"
   |-- close DB pool
   |-- exit

   Agent:
   |-- shutting_down = True
   |-- reject new run triggers → 503
   |-- in-flight agent tasks continue
   |-- on cancel request (via existing `/api/threads/{id}/runs/{run_id}/cancel`):
   |      stop agent execution
   |      call cancel_task() callback to Backend
   |      close checkpointer
   |-- exit
```

#### Flow 4: 孤儿恢复（Backend 启动时）

```
Backend startup:
   |
   |-- reconcile_orphaned_tasks():
   |      query AITask WHERE status IN ('running','post_processing')
   |        AND lease_expires_at < now
   |      for each stale task:
   |        conditional UPDATE (lease guard prevents split-brain)
   |        mark interrupted with error message
   |-- start accepting requests
```

#### Flow 5: 用户主动取消

```
Frontend                    Backend                      Agent
   |                           |                           |
   |-- POST /tasks/{id}/cancel->|                           |
   |                           |-- AITaskService.cancel_task()
   |                           |   (immediate DB: status=cancelled)
   |                           |                           |
   |                           |-- POST /threads/{id}/runs/{run_id}/cancel -->|
   |                           |                           |-- RunManager.cancel()
   |                           |                           |-- stop DeerFlow execution
   |                           |                           |
   |                           |<-- POST /internal/tasks/{id}/cancel ----------|
   |                           |   (Agent confirm, idempotent no-op since already cancelled)
   |                           |                           |
   |<-- { ok: true, status: "cancelled" }                  |
   |                           |                           |
```

**关键设计：**
- Backend **立即**标记 cancelled（不等 Agent 确认），用户得到即时反馈
- Agent 取消确认回调是幂等的（已 cancelled → no-op）
- 如果 Agent 已自行完成（cancel 和 complete 竞争），`cancel_task()` 只从 running/post_processing 转 cancelled，completed 的任务不会被回退

### Acceptance Examples

#### AE1: Finance Coach — leave and return

1. User opens Dashboard, FinanceCoachCard triggers advice generation
2. Backend creates AITask (skill_id=coach, status=running)
3. Backend triggers Agent (non-streaming), starts polling
4. Agent executes, POST progress updates to Backend
5. Frontend polls every 2s, shows progress
6. User navigates away (polling stops)
7. Agent continues generating (progress saved in DB)
8. User returns to Dashboard after 30s
9. Frontend polls AITask → sees latest progress or completed result
10. If still running: continues polling until complete

#### AE2: AI Chat — page refresh during response（新增后台跟踪）

1. User in AI chat, sends message
2. Backend creates AITask (skill_id=chat, status=running)
3. Frontend 直连 Agent SSE（token-by-token 流式体验不变）
4. Agent starts generating response via DeerFlow
5. DeerFlow checkpointer 持久化对话状态
6. User refreshes page (hard navigation)
7. Chat page re-mounts → 从 DeerFlow checkpointer 恢复 thread 状态
8. 用户看到之前的对话历史（从 checkpointer 加载）
9. 如果 AITask 仍 running → 重连 SSE 继续接收
10. 如果 AITask 已 completed → 显示完整回复

**与 v1 的区别**：v1 中 Chat 无 AITask 跟踪，刷新后只能从 checkpointer 恢复历史。v2 增加了 AITask 跟踪，可以判断任务是否仍在运行并决定是否重连 SSE。

#### AE3: Graceful shutdown during literacy report

1. Literacy report generation in progress (skill_id=literacy, status=running)
2. Deploy triggers SIGTERM to Backend and Agent
3. Backend stops accepting new tasks (503), drain starts
4. Agent stops accepting new runs, continues in-flight task
5. If report completes within 60s → Backend marks "completed"
6. If not → Backend marks "interrupted" with error "服务重启，任务中断，请重试"
7. User returns → sees interrupted task with retry button

#### AE4: Agent crash recovery（单例模式）

1. Agent process crashes mid-task (OOM, unhandled exception)
2. AITask remains "running" but lease_expires_at expires (no heartbeat)
3. Backend 检测到 Agent 进程消失（HTTP health check 失败或 lease 过期）
4. Backend 标记 AITask "interrupted" with error "智能体暂时不可用，请重试"
5. Frontend shows interrupted state + retry button
6. User retries → new AITask created, Agent restarted

#### AE5: User cancels running Finance Coach task

1. User triggers Finance Coach on Dashboard → AITask created (skill_id=coach, status=running)
2. Agent starts executing, frontend polls progress every 2s
3. User decides to cancel → clicks cancel button
4. Frontend calls `POST /api/v1/ai/tasks/{task_id}/cancel`
5. Backend immediately marks `AITask.status = cancelled`
6. Backend calls Agent `/api/threads/{id}/runs/{run_id}/cancel` → Agent stops execution
7. Agent calls `cancel_task()` callback → idempotent no-op (already cancelled)
8. Frontend polling sees `status=cancelled` → stops polling, shows cancelled state

### Key Decisions

| # | Decision | Rationale |
|---|----------|-----------|
| KTD-1 | **轮询模型**（前端 2s 轮询 AITask，非 EventBus push） | 后台任务不需要逐 token 实时流。轮询天然支持断线恢复，无需 Last-Event-ID/gap 检测。DB 本身就是共享存储，集群模式零额外依赖。 |
| KTD-2 | **AITask 作为唯一状态源** | 统一查询路径。skill_id 区分功能。已有复合索引 `(family_id, skill_id, status)`。progress JSON 承载进度信息。 |
| KTD-3 | **Agent HTTP callback 更新进度**（3-5 次/任务，关键节点） | DB 写入不是逐 token，而是逐关键步骤。heartbeat 每 40s（lease_ttl/3）一次。极低写入量。 |
| KTD-4 | **Chat 增加 AITask 后台跟踪**（用户在页面时仍 SSE 流式） | 统一所有 AI 任务的跟踪模型。Chat 用户在页面时保留 SSE token-by-token 体验，切走/刷新后通过 AITask + checkpointer 恢复。 |
| KTD-5 | **两层分离**：实时流式层（SSE）+ 任务跟踪层（AITask 轮询） | SSE 负责 token-by-token 流式体验（Chat 在页面时 + Coach/Literacy/Narrative 在页面时 via bridge consumer）。AITask 负责状态/进度/恢复。互不干扰。（OQ-1 resolved 后更新） |
| KTD-6 | **60s graceful shutdown drain** | 大多数 AI 任务应在 60s 内完成或到达安全检查点。可通过环境变量配置。 |
| KTD-7 | **lease heartbeat + gc.py 孤儿恢复** | Agent 每 40s（lease_ttl/3）heartbeat 续期 lease_expires_at。Backend 启动时 + 周期性扫描 stale tasks。已有实现。 |
| KTD-8 | **Wish-Advice/Import 不转换** | 非流式功能。Wish-Advice 是同步 HTTP 调用；Import 是文件处理 + DB 写入。亚秒级，不需要任务追踪。 |
| KTD-17 | **用户取消端点使用 task_id（非 skill_id）** | 现有 `POST /api/v1/ai/tasks/{skill_id}/cancel`（`ai_tasks.py:156`）按 skill_id 查找任务，但 v2 引入 AITask 主键后，task_id 更精确（避免同 skill_id 多个任务的歧义）。新端点 `POST /api/v1/ai/tasks/{task_id}/cancel` 替代旧端点，tenant isolation 通过 `family_id` 过滤保证。取消立即生效（DB 先标记），Agent 停止异步执行。 |

### Outstanding Questions

> 所有原始 Outstanding Questions 已在 Planning 阶段解决。Resolved 记录见文末 `## Deferred / Open Questions` 节。

| # | Question | Status | Resolution |
|---|----------|--------|------------|
| OQ-2* | Dashboard-narrative 和 wish-advice 是否需要 TTL 缓存？ | Deferred | Planning 阶段决定（唯一遗留项） |

### How This Work Fits Together

**Architectural shift (from v1):**
- v1: 只有 asset-report 走 AITask 跟踪，其余 fire-and-forget。bridge_consumer 硬编码 Redis。
- v2: 所有 AI 任务统一 AITask 跟踪。Agent HTTP callback 更新进度。前端轮询获取状态。无 EventBus。

**Builds on v1 (reused):**
- AITask schema (run_id, worker_id, lease_expires_at, progress) — already migrated
- AITaskService extensions (get_task_by_run_id, get_stale_running_tasks, etc.) — already implemented
- Tenant isolation — already implemented
- `packages/db/stream_bridge` — still used for Chat SSE when user is on page
- Graceful shutdown + orphan recovery — already implemented in v1

**Agent 侧变更：**
- 新增 HTTP callback 端点：Agent 执行中 POST progress/heartbeat 到 Backend
- 复用已有 `/api/threads/{id}/runs/{run_id}/cancel` 端点：Backend 通知 Agent 取消任务（无需新增）
- 新增 `cancel_task()` 回调：Agent 确认取消完成（Agent → Backend，U11）
- 保留 StreamBridge（用于 Chat SSE 流式）
- Chat 新增 AITask 跟踪（skill_id=chat）

**DeerFlow 参考模式（对齐）：**
- RunManager `create_or_reject()` 原子准入 → 我们使用 AITask 唯一约束实现相同效果
- `lease_expires_at` + heartbeat loop → 已有 v1 实现，直接复用
- `reconcile_orphaned_inflight_runs()` → 已有 v1 实现，直接复用
- `asyncio.shield(run_manager.shutdown())` drain → 已有 v1 实现，直接复用
- `reconnectOnMount: true` + checkpointer → Chat 前端恢复模式

**Enables future:**
- User-built custom agents (same AITask pattern, skill_id = "agent-{id}")
- Task history and analytics (all AI features tracked in one table)
- Phase 2: 周期性孤儿检测（如需要）
- Phase 2: Redis EventBus（如未来需要跨进程事件传递）

---

## Scope Boundaries

### In Scope
- **统一任务跟踪**：所有 AI 任务（含 Chat）创建 AITask 记录
- **进度轮询**：Agent HTTP callback 更新 AITask.progress，前端 2s 轮询
- **功能转换**：3 个流式功能从直接代理转换为 AITask + 双层模型（在页面时 bridge consumer SSE + 切走后轮询恢复）
- **Chat 后台跟踪**：Chat 增加 AITask 跟踪，用户在页面时保留 SSE 流式
- **优雅关停**：复用 v1 实现
- **孤儿恢复**：复用 v1 实现

### Out of Scope
- EventBus 抽象层（不需要，轮询模型更简单）
- 新 AI 功能开发
- Wish-Advice/Import 转换（非流式，不需要）
- LangGraph checkpointer 迁移（保持在 Agent）
- Agent 的 DeerFlow agent 执行逻辑（不变）
- 前端 token-by-token 流式改为轮询（Chat 保持 SSE）

---

## Planning Contract

### Key Technical Decisions (Implementation)

| # | Decision | Rationale |
|---|----------|-----------|
| KTD-9 | **`progress` JSON 列已存在，无需新 migration** | `x9876y4zqr0_add_task_tracking_fields.py` 已添加 `progress` (JSON, nullable) + `lease_expires_at` 列。实现直接使用现有 schema。 |
| KTD-10 | **AITaskResponse 须扩展 `progress` 字段** | 当前 `AITaskResponse`（`server/apps/backend/app/routers/ai_tasks.py:41-56`）缺少 `progress`、`lease_expires_at`、`queue_position`、`session_id` 字段。前端轮询需要 `progress` 才能展示步骤进度。 |
| KTD-11 | **Backend 内部回调端点须全部新建** | 当前不存在 `POST /internal/tasks/{id}/progress|complete|fail|heartbeat|cancel`。Agent 目前没有向 Backend 报告进度的 HTTP 路径。5 个端点均需创建（4 个 Agent → Backend 回调 + 1 个取消确认回调）。 |
| KTD-12 | **Agent BackendClient 须新增 5 个回调方法** | `server/apps/agent/core/backend_client.py` 有 ~25 个方法，但没有 `report_progress()`、`complete_task()`、`fail_task()`、`heartbeat()`、`cancel_task()`。其中 4 个是 Agent → Backend 回调（progress/complete/fail/heartbeat），`cancel_task()` 是 Agent 确认取消完成的回调。Agent 目前通过 SQLAlchemy 直接写 DB（如 `persist_report_result()`），但进度报告应走 HTTP 回调以保持职责分离。 |
| KTD-13 | **task_id 通过 trigger request 传递** | Agent runner 当前不知道自己的 AITask ID。Backend 在触发 Agent 时将 `task_id` 传入 request：bridge consumer 功能通过 `agent_client.post()` body 传递；Chat 通过 `agent_client.stream()` 的 request body 传递（扩展 `ChatRunRequest`）。Agent 在回调中使用该 ID。 |
| KTD-14 | **Bridge consumer 是唯一完成权威**（OQ-4 resolved） | 对于使用 bridge consumer 的功能（Coach/Literacy/Narrative），bridge consumer 在流结束时标记 completed/failed。Agent runner 只负责 heartbeat + progress，不调用 complete_task/fail_task。Chat 无 bridge consumer，Agent 调用 complete/fail（与现有 Import-parse 模式一致，后者不在 v2 范围）。 |
| KTD-15 | **Agent runner 在 `run_skill()` 前后插入回调** | Bridge consumer 功能（Coach/Literacy/Narrative，U12）：runner 只发 heartbeat + progress，不调用 complete/fail（bridge consumer 负责）。Chat（U18）：runner 发 complete/fail（无 bridge consumer）。Heartbeat 在后台 task 中每 40s 续期。不需要在 DeerFlow stream 中间插入进度（逐 token 进度不属于此计划）。 |
| KTD-16 | **Dashboard Narrative 从 GET 改为 POST + 双层模型** | 当前 `GET /dashboard/narrative` 是唯一的 GET SSE 端点。转换为 `POST /dashboard/narrative/generate`，用户在页面时通过 bridge consumer SSE 实时接收（与 Coach/Literacy 一致，OQ-1 resolved），切走/刷新后通过轮询 AITask 恢复。破坏性 API 变更，但所有调用方都在项目内。 |

### Implementation Constraints (Research-Discovered)

**Backend 现状：**
- `AITaskService` 已有完整方法：`create_task()`、`complete_task()`、`fail_task()`、`update_lease()`、`mark_interrupted()` — 直接复用
- `bridge_consumer.py` 已有 `consume_task_stream()` — 转换功能时复用此模式
- `ai_report.py` 是参考实现（`trigger_generate_events` line 224）— 转换功能时对齐此模式
- `ai_internal.py` 是内部端点路由 — 新增回调端点放此文件

**Agent 现状：**
- 4 个 runner 在 `server/apps/agent/services/runtime/worker.py` — `_run_finance_coach_agent`(802)、`_run_literacy_weekly_report_agent`(1277)、`_run_dashboard_narrative_agent`(971)、`_run_numina_agent`(1040)
- 所有 runner 使用 `RunPipeline` context manager + `p.run_skill()` 模式
- `gc.py` 中 `drain_inflight_runs()` + `reconcile_orphaned_runs()` 已有 — 直接复用
- Agent 触发请求 models 在 `server/apps/agent/app/routers/gateway.py` — 需扩展 `task_id` 字段

**Frontend 现状：**
- `useReportStream.ts` 是唯一完整的参考实现（SSE + AITask polling + run_id + Last-Event-ID + reconnect）
- Finance Coach：SSE 逻辑内联在 `getFinanceCoach()` API 函数中，无 composable
- Literacy：`useLiteracyStream.ts` composable，无 run_id 捕获，无重连
- Dashboard Narrative：callback-based `streamNarrative()` API 函数，无 composable
- Chat：`useThreadChat.ts` 使用 LangGraph SDK `client.runs.stream()`，捕获 run_id 但仅用于 cancel

### Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Agent callback 失败（网络瞬断）导致进度丢失 | Low | Low | 3-5 次写入，单次失败不影响整体。bridge consumer 安全网保底完成/失败。 |
| Dashboard Narrative GET→POST 破坏外部调用 | Low | Low | 项目内闭环，无外部消费者。前端同步更新。 |
| Chat AITask 跟踪与现有 SSE 流式冲突 | Medium | Medium | 两层分离：SSE 负责实时流，AITask 只记录状态。互不干扰。Chat runner 中 AITask 创建在 `start_run()` 之前，SSE 流不变。 |
| Heartbeat 40s 间隔在慢网络下不够 | Low | Low | lease_ttl=120s 有 3x 容错。单次 heartbeat 丢失不影响。 |
| Chat SSE fallback 和 agent callback 竞争完成 | Low | Low | Chat 无 bridge consumer，Backend SSE proxy 作为 fallback。`complete_task()` 幂等：只从 running/post_processing 转 completed。先到的赢，后到的是 no-op。 |
| 用户取消与任务完成竞争 | Low | Low | Backend 立即标记 cancelled，Agent 回调幂等。若 Agent 已在 cancel 前完成（`completed` 状态），`cancel_task()` 的 WHERE 条件不匹配 → no-op。用户看到 completed 而非 cancelled，这是正确行为（任务已成功后取消无效）。 |

---

## Verification Contract

### V1: 单元级验证

| Gate | Command | Scope | Pass Criteria |
|------|---------|-------|---------------|
| Backend lint | `cd server && uv run ruff check apps/backend apps/agent packages/db` | All modified Python files | 0 errors |
| Backend typecheck | `cd server && uv run mypy .` | Full server workspace | 0 errors |
| Backend unit tests | `cd server && uv run pytest tests/backend/ -x -v` | Backend services, routers, models | All pass |
| Agent unit tests | `cd server && uv run pytest tests/agent/ -x -v` | Agent worker, runtime | All pass |
| Frontend typecheck | `cd frontend && pnpm typecheck` | Full frontend workspace | 0 errors |
| Frontend unit tests | `cd frontend/apps/main && npx vitest run` | All frontend tests | All pass |

### V2: 集成级验证

| Gate | Method | Scope | Pass Criteria |
|------|--------|-------|---------------|
| Alembic fresh-DB | `rm -f /tmp/test.db && DATABASE_URL=sqlite+aiosqlite:////tmp/test.db uv run alembic upgrade head` | Migration idempotency | 0 errors, all tables created |
| Docker smoke | `docker-compose up -d && sleep 30 && curl http://localhost:8080/api/v1/health` | Full stack startup | Health check 200 |
| Agent→Backend progress callback | 触发 Finance Coach → 检查 Backend 日志 | HTTP callback | Agent POST /internal/tasks/{id}/progress 成功，AITask.progress 更新 |
| Agent heartbeat | 触发长任务 → 观察 heartbeat | lease 续期 | AITask.lease_expires_at 每 40s 更新（lease_ttl/3） |
| 用户取消端到端 | 触发任务 → `POST /api/v1/ai/tasks/{task_id}/cancel` → 检查 DB + Agent 日志 | 用户取消 | AITask → cancelled, Agent 收到 cancel 信号停止执行, cancel_task() 回调幂等 no-op |

### V3: 功能级验证（4 个 AI 功能 + Chat）

对每个 AI 功能执行以下验证矩阵：

| Test | Method | Expected Result |
|------|--------|-----------------|
| **正常执行** | 触发功能，等待完成 | AITask created → running → completed, 进度轮询正常 |
| **离开再回来** | 触发功能 → 切换页面 → 返回 | 轮询 AITask → 显示最新进度或结果 |
| **任务失败** | 模拟 Agent 错误（如 provider 不可用） | AITask → failed, 前端显示错误信息 |
| **任务超时** | 触发功能 → 等待 lease 过期（120s）无 heartbeat | AITask → interrupted（孤儿恢复机制），前端显示中断提示 |
| **取消任务** | 触发功能 → 前端点击取消 → `POST /tasks/{task_id}/cancel` | AITask → cancelled（立即），Agent 收到 cancel 信号停止，前端轮询确认 cancelled |
| **取消竞争** | 触发功能 → 等接近完成 → 同时取消 | 若已完成则 cancel 返回 completed（不回退），若仍在跑则 cancelled |
| **Chat SSE 流式** | 在 Chat 页面发送消息 | token-by-token SSE 流式正常（不变） |
| **Chat 切走恢复** | Chat 生成中切走 → 返回 | 从 checkpointer 恢复对话历史，如果仍在跑则重连 SSE |

### V4: AITask 跟踪专项验证

| Test | Method | Expected Result |
|------|--------|-----------------|
| **Finance Coach AITask** | Review `ai_finance_coach.py` | 创建 AITask(skill_id=coach)，Agent HTTP callback 更新进度 |
| **Dashboard Narrative AITask** | Review `dashboard.py`（`get_narrative`, line 203） | 创建 AITask(skill_id=narrative)，Agent HTTP callback 更新进度 |
| **Literacy Report AITask** | Review `ai_literacy_report.py` | 创建 AITask(skill_id=literacy)，Agent HTTP callback 更新进度 |
| **Chat AITask** | Review `ai_chat.py` + `useThreadChat.ts` | 创建 AITask(skill_id=chat)，SSE 流式不变，切走后可恢复 |
| **前端轮询** | Review `useTaskPolling.ts` | 2s 间隔轮询，status=completed 时停止，页面不可见时暂停 |
| **进度 JSON 结构** | 触发各功能 → GET /tasks/{id} | AITask.progress 包含 step/steps_completed/status |

### V5: 优雅关停验证

| Test | Method | Expected Result |
|------|--------|-----------------|
| **拒绝新任务** | 发送 SIGTERM → 立即 POST 新任务 | 503 + Retry-After header |
| **进行中的任务继续** | SIGTERM 时有正在执行的任务 | 任务继续执行（最多 60s） |
| **60s 超时中断** | SIGTERM 时有长耗时任务（>60s） | 超时后 AITask → interrupted |
| **中断任务标识** | 任务被优雅关停中断 | error_message = "服务重启，任务中断，请重试" |
| **前端重试引导** | 访问被中断的任务 | 显示重试按钮 + 错误信息 |

### V6: 孤儿恢复验证

| Test | Method | Expected Result |
|------|--------|-----------------|
| **启动时恢复** | 手动标记 AITask running + lease expired → 重启 Backend | 任务被标记 interrupted |
| **新任务保护** | 同一 (family_id, skill_id) 已有 completed 任务 + stale running 任务 | stale 任务不被标记 interrupted（跳过） |
| **条件性声明** | 两个进程同时尝试 claim 同一个 orphan | 只有一个成功（原子 UPDATE） |
| **Agent crash** | 停止 Agent 进程 → Backend 检测到 | AITask 标记 interrupted |

### V7: 回归验证（确保 v1 功能不退化）

| Test | Method | Expected Result |
|------|--------|-----------------|
| **Asset Report E2E** | 完整流程：生成报告 → 查看结果 | 与 v1 行为一致（仍使用 bridge consumer） |
| **Finance Coach E2E** | Dashboard 触发 → 查看建议 | 现在通过 AITask + 轮询（之前是直接代理） |
| **AI Chat E2E** | 发送消息 → 收到回复 | Chat 功能正常（SSE 流式 + AITask 后台跟踪） |
| **Wish Advice E2E** | 触发建议 → 查看结果 | 仍使用同步调用，不受影响 |
| **Bill Import E2E** | 上传文件 → 导入数据 | 仍使用同步处理，不受影响 |
| **租户隔离** | 两个 family 分别触发任务 | 无法看到对方的任务或事件 |
| **并发安全** | 同一 family 同时触发两个相同功能 | 第二个被拒绝或排队 |

### Verification Execution Order

建议按以下顺序执行验证：

1. **V1**（单元级）— 确保基础代码质量
2. **V2**（集成级）— 确保部署环境正常
3. **V4**（AITask 跟踪）— 确保所有功能正确创建 AITask
4. **V3**（功能级）— 逐个功能验证
5. **V5**（优雅关停）— 运维关键路径
6. **V6**（孤儿恢复）— 容错验证
7. **V7**（回归）— 确保无退化

每个阶段的验证全部通过后，才进入下一阶段。

---

## Implementation Units

> 依赖关系：U9/U10/U20 无依赖（并行） → U11 → U12 → U13/U14/U15/U16/U18（并行） → U17/U19/U21

### U9. Backend Internal Callback Endpoints

**Goal:** 创建 5 个 Agent→Backend HTTP 回调端点，用于进度更新、完成、失败、心跳续期和取消。

**Files:**
- Modify: `server/apps/backend/app/routers/ai_internal.py` — 新增 5 个端点
- Modify: `server/apps/backend/app/schemas/ai_task.py` — 新增 `TaskProgressRequest`、`TaskCompleteRequest`、`TaskFailRequest`、`TaskHeartbeatRequest` request schemas

**Approach:**

在 `ai_internal.py` 新增 5 个端点（X-Agent-Token 认证，与现有 internal 端点一致）：

1. `POST /internal/tasks/{task_id}/progress` — 更新 `AITask.progress` JSON 字段（size limit: `len(json.dumps(progress)) < 10000`，OQ-5 resolved）
2. `POST /internal/tasks/{task_id}/complete` — 标记 completed + 可选 result_summary 存入 progress
3. `POST /internal/tasks/{task_id}/fail` — 标记 failed + error_message
4. `POST /internal/tasks/{task_id}/heartbeat` — 调用 `AITaskService.update_lease()` 续期 lease_expires_at
5. `POST /internal/tasks/{task_id}/cancel` — Agent 确认取消完成。Backend 通过已有 Agent 端点 `/api/threads/{id}/runs/{run_id}/cancel` 通知 Agent 停止，Agent 停止后调用此端点更新 AITask 状态

所有端点需要 tenant isolation：使用 `verify_agent_token`（`ai_deps.py`）返回的 JWT 验证 `family_id`（来自 `X-Family-Id` header），与 `AITask.family_id` 校验匹配。不使用 request body 中的 family_id 作为授权依据（与现有 ai_internal.py 全部 20+ 端点一致）。

复用现有 `AITaskService` 方法：`complete_task()`、`fail_task()`、`update_lease()`。progress 端点需要新方法或直接 DB 更新 `AITask.progress` 字段。

> **关键修正**：现有 `complete_task()` 和 `fail_task()` 缺少 `family_id` 过滤（`ai_task_service.py:198-212`），需扩展签名加入 `family_id` 参数（对齐 `update_lease()` 和 `get_task_by_id()` 的模式）。回调端点使用原子 UPDATE（task_id + family_id 同时在 WHERE 子句），参考 `mark_interrupted(lease_guard=True)` 模式。

**Dependencies:** 无

**Patterns to follow:**
- `server/apps/backend/app/routers/ai_internal.py` — 现有 internal 端点模式（X-Agent-Token auth via `verify_service_token`）
- `server/apps/backend/app/services/ai_task_service.py` — 现有 AITaskService 方法

**Test scenarios:**
1. POST progress → `AITask.progress` 字段更新为请求 body 中的 JSON
2. POST complete → `AITask.status` 变为 `completed`，`completed_at` 设置
3. POST complete 幂等性 → 已 completed 的任务再次 complete 不报错
4. POST fail → `AITask.status` 变为 `failed`，`error_message` 截断到 500 字符
5. POST heartbeat → `AITask.lease_expires_at` 更新为 now + 120s
6. Tenant isolation → task_id 存在但 family_id 不匹配 → 404
7. POST cancel → `AITask.status` 变为 `cancelled`（Agent 确认取消完成回调）
8. 不存在的 task_id → 404

**Verification:** `cd server && uv run pytest tests/backend/ -x -v -k "task_callback"` — all pass

---

### U10. AITaskResponse Schema Extension

**Goal:** 扩展 `AITaskResponse` schema 以包含 `progress` 字段，使前端轮询能获取任务进度。同时扩展查询端点支持 `session_id` 过滤。

**Files:**
- Modify: `server/apps/backend/app/routers/ai_tasks.py` — 扩展 `AITaskResponse`（line 41-56）+ 扩展 `get_tasks()` 支持 `session_id` 查询参数

**Approach:**

在 `AITaskResponse` 中新增字段：
- `progress: dict | None = None` — 任务进度 JSON（step, steps_completed, status 等）
- `lease_expires_at: datetime | None = None` — lease 过期时间
- `queue_position: int | None = None` — 排队位置
- `session_id: int | None = None` — 关联的 AIChatSession ID

同时在 `get_tasks()` 查询端点新增 `session_id` 查询参数（`GET /ai/tasks?skill_id=chat&session_id={id}`），用于 Chat 前端按 session 查找关联 AITask（U19 依赖）。

这些字段已在 AITask model 中存在（`server/packages/db/models/ai_task.py`），只需在 response schema 中暴露。`AITaskResponse` 继承 `SnowflakeBase`，ID 字段自动序列化为 string。

> **关键修正**：`ai_tasks.py:27-35` 的 `VALID_SKILL_IDS` 集合当前只有 `{report, alerts, disposal, allocation, spending_leak, liability, time_machine}`。必须扩展加入 `coach`、`literacy`、`narrative`、`chat`，否则前端按 skill_id 查询时返回 `{status: idle}`，所有新功能进度轮询失效。

**Dependencies:** 无

**Patterns to follow:**
- `server/apps/backend/app/routers/ai_tasks.py` — 现有 schema 定义
- `server/packages/db/models/ai_task.py` — model 字段参考

**Test scenarios:**
1. GET /tasks/{id} → response 包含 `progress` 字段（None 当无进度时）
2. AITask.progress 有值时 → response 返回完整 JSON 结构
3. `lease_expires_at` 在 response 中正确序列化为 ISO 格式

**Verification:** `cd server && uv run pytest tests/backend/ -x -v -k "ai_task"` — all pass

---

### U20. Backend User Cancel Endpoint

**Goal:** 创建用户侧的任务取消端点 `POST /api/v1/ai/tasks/{task_id}/cancel`，使用户能主动取消正在运行的 AI 任务。

**Files:**
- Modify: `server/apps/backend/app/routers/ai_tasks.py` — 新增 `cancel_task_by_id` 端点
- Modify: `server/apps/backend/app/services/ai_task_service.py` — 新增 `cancel_task_by_id()` 方法

**Approach:**

在 `ai_tasks.py` 新增端点（JWT auth + tenant isolation，与现有 `ai_tasks.py` 端点一致）：

`POST /api/v1/ai/tasks/{task_id}/cancel`

1. 验证 family_id（从 JWT 提取），查询 AITask WHERE `id=task_id AND family_id=family_id`
2. 如果任务不存在或不属于该家庭 → 404
3. 如果任务不在 `running/post_processing/queued` 状态 → 返回当前状态（幂等，不报错）
4. 如果任务有 `run_id`（Agent 正在执行）→ 调用 Agent `POST /api/threads/{thread_id}/runs/{run_id}/cancel`（fire-and-forget，不等响应）
5. 立即标记 `AITask.status = cancelled` + `completed_at = now`
6. 返回 `{ ok: true, status: "cancelled", task_id: task_id }`

**与旧端点的关系：** 现有 `POST /api/v1/ai/tasks/{skill_id}/cancel`（`ai_tasks.py:156`）保留兼容，但 v2 前端使用新的 task_id 端点。旧端点的 `VALID_SKILL_IDS` 不含 coach/literacy/narrative/chat，无法取消新功能。

**Agent 调用细节：**
- Backend 需要知道 Agent 的 thread_id 才能调用 `/api/threads/{id}/runs/{run_id}/cancel`
- `AITask.session_id` 即 thread_id（Chat 创建时传入，Coach/Literacy/Narrative 在 trigger 时也传入）
- 如果 `session_id` 为 None（如某些 Report 场景），使用 thread_id = family_id 的默认 thread（对齐 Agent 端的 thread 创建逻辑）
- Agent 调用失败（如 Agent 已自行完成）→ 不影响 DB 标记（已 cancelled）

**Dependencies:** 无（与 U9/U10 并行）

**Patterns to follow:**
- `server/apps/backend/app/routers/ai_tasks.py:156-169` — 现有 cancel 端点（参考 auth 模式）
- `server/apps/backend/app/services/ai_task_service.py:233-249` — 现有 `cancel_task()`（扩展为 task_id 级别）

**Test scenarios:**
1. POST cancel → `AITask.status` 变为 `cancelled`，`completed_at` 设置
2. 已 completed 的任务 cancel → 返回 `completed`（幂等，不回退）
3. 已 cancelled 的任务再次 cancel → 返回 `cancelled`（幂等）
4. Tenant isolation → task_id 存在但 family_id 不匹配 → 404
5. 有 run_id 的任务 cancel → Agent 收到 cancel 信号（mock 验证 HTTP 调用）
6. 无 run_id 的任务 cancel → 仅 DB 标记，不调 Agent
7. 不存在的 task_id → 404
8. queued 状态的任务 cancel → 直接标记 cancelled（无需通知 Agent）

**Verification:** `cd server && uv run pytest tests/backend/ -x -v -k "task_cancel"` — all pass

---

### U11. Agent BackendClient Callback Methods

**Goal:** 在 Agent 的 `BackendClient` 中新增 5 个 HTTP 回调方法，对应 U9 创建的 Backend 端点。其中 4 个是 Agent → Backend 状态回调（progress/complete/fail/heartbeat），`cancel_task()` 是 Agent 确认取消完成的回调。

**Files:**
- Modify: `server/apps/agent/core/backend_client.py` — 新增 `report_progress()`、`complete_task()`、`fail_task()`、`heartbeat()`、`cancel_task()` 方法

**Approach:**

新增 5 个方法，使用现有 `self._client`（httpx.AsyncClient）发送 POST 请求：

```python
async def report_progress(self, task_id: int, family_id: int, progress: dict) -> None
async def complete_task(self, task_id: int, family_id: int, result_summary: str | None = None) -> None
async def fail_task(self, task_id: int, family_id: int, error_message: str) -> None
async def heartbeat(self, task_id: int, family_id: int) -> None
async def cancel_task(self, task_id: int, family_id: int) -> None  # Agent 确认取消完成
```

所有方法调用 `resp.raise_for_status()`，失败时抛异常（与现有 `post_*` 方法模式一致）。自动携带 `X-Family-Id` header（BackendClient 已有此逻辑）。

**Dependencies:** U9（Backend 端点必须先存在）

**Patterns to follow:**
- `server/apps/agent/core/backend_client.py` — 现有 `persist_report_result()` 等方法的 raise_for_status 模式
- 错误处理：调用方可选择性 try/except + logger.warning，不中断 agent 执行

**Test scenarios:**
1. `report_progress()` → POST /internal/tasks/{id}/progress 被调用，body 包含 progress JSON
2. `complete_task()` → POST /internal/tasks/{id}/complete 被调用
3. `fail_task()` → POST /internal/tasks/{id}/fail 被调用，body 包含 error_message
4. `heartbeat()` → POST /internal/tasks/{id}/heartbeat 被调用
5. `cancel_task()` → POST /internal/tasks/{id}/cancel 被调用（Agent 确认取消完成）
6. 网络错误 → 方法抛异常（raise_for_status），调用方 try/except 处理
7. `X-Family-Id` header 自动附加

**Verification:** `cd server && uv run pytest tests/agent/ -x -v -k "backend_client"` — all pass

---

### U12. Agent Runner Progress Callback Hooks

**Goal:** 在 3 个 agent runner（Finance Coach、Literacy Report、Dashboard Narrative）中插入进度回调和心跳循环，使任务执行过程中 AITask.progress 被更新。Chat runner 由 U18 单独处理。

**Files:**
- Modify: `server/apps/agent/services/runtime/worker.py` — 在 `_run_finance_coach_agent`(802)、`_run_literacy_weekly_report_agent`(1277)、`_run_dashboard_narrative_agent`(971) 中插入回调
- Modify: `server/apps/agent/app/routers/gateway.py` — 扩展 `FinanceCoachRunRequest`(305)、`LiteracyWeeklyReportRunRequest`(595)、`DashboardNarrativeRunRequest`(526) 新增 `task_id: int | None = None` 字段

**Approach:**

1. **扩展 request models**：在 gateway.py 的 3 个 request model 中新增 `task_id: int | None = None`（可选，向后兼容）

2. **Runner 回调模式**（每个 runner 中）：
   - 接收 `task_id` 参数
   - 在 `p.run_skill()` 之前：调用 `backend_client.heartbeat(task_id, family_id)` 标记开始
   - **不调用 complete_task / fail_task**（OQ-4 resolved）：bridge consumer 是唯一完成权威，runner 只负责 heartbeat + progress
   - 启动后台 `asyncio.Task` 每 40s 调用 `backend_client.heartbeat(task_id, family_id)`，runner 结束时 cancel

3. **进度报告**：在 skill 执行的关键节点（如 report 的 step2_json 解析后）调用 `backend_client.report_progress(task_id, family_id, progress_dict)`。当前 runner 已有 custom event 发送点，在同一位置增加 callback。

4. **Chat runner (`_run_numina_agent`)**：暂不修改（U18 单独处理），`task_id` 字段在 ChatRunRequest 中新增但暂不使用。

**Dependencies:** U11（BackendClient 方法必须先存在）

**Patterns to follow:**
- `server/apps/agent/services/runtime/worker.py` — 现有 runner 模式（RunPipeline context manager）
- `server/apps/agent/core/backend_client.py` — raise_for_status 回调模式
- DeerFlow `_heartbeat_loop` 模式（每 lease_ttl/3 续期）

**Test scenarios:**
1. Finance Coach runner → task_id 传入 → heartbeat 在 run_skill 前调用
2. Finance Coach runner 成功 → **不调用 complete_task**（bridge consumer 负责）
3. Finance Coach runner 异常 → **不调用 fail_task**（bridge consumer 负责）
4. Heartbeat 后台 task 每 40s 触发一次 → runner 结束后 cancel
5. task_id 为 None 时 → 所有 callback 跳过（向后兼容）
6. 所有 3 个 runner（coach/literacy/narrative）行为一致

**Verification:** `cd server && uv run pytest tests/agent/ -x -v -k "runner_progress or worker_callback"` — all pass

---

### U13. Finance Coach Router Conversion

**Goal:** 将 Finance Coach 从 `agent_client.stream()` 直接代理转换为 AITask 跟踪 + `agent_client.post()` + bridge consumer 模式。

**Files:**
- Modify: `server/apps/backend/app/routers/ai_finance_coach.py` — 重写 `trigger_finance_coach`（line 124）

**Approach:**

对齐 `ai_report.py:trigger_generate_events`（line 224）参考实现：

1. 保留现有 circuit breaker + 8h cache 逻辑
2. 在 cache miss 后：`AITaskService.get_running_task(family_id, "coach", db)` 检查是否有运行中任务
3. 创建 AITask：`AITaskService.create_task(family_id, "coach", session_id=None, db, run_id=None)`
4. 替换 `agent_client.stream()` 为 `agent_client.post()` — 非流式触发
5. 使用 `consume_task_stream()` 消费 bridge → SSE 返回前端（保留前端 SSE 体验的同时后端获得任务跟踪）
6. 在 `consume_task_stream()` 返回后：bridge consumer 已自动完成/失败任务

注意：此转换使 Finance Coach 与 Asset Report 使用完全相同的模式。前端 SSE 接口不变（仍返回 SSE frames），但后端多了 AITask 跟踪层。

**Dependencies:** U12（Agent 端已支持 task_id + 回调）

**Patterns to follow:**
- `server/apps/backend/app/routers/ai_report.py:trigger_generate_events` — 参考实现（line 224-350）
- `server/apps/backend/app/services/bridge_consumer.py:consume_task_stream` — bridge consumer 模式

**Test scenarios:**
1. 正常流程 → AITask created → running → completed，SSE 正常返回
2. 并发请求 → 第二个请求检测到 running task → 返回已有 task 信息
3. Circuit breaker 触发 → 503 正常
4. Cache hit → 直接返回缓存，不创建 AITask
5. Agent 失败 → AITask → failed，SSE 返回 error frame
6. 前端 SSE 接口不变 → 现有前端代码无需修改（过渡期）

**Verification:** `cd server && uv run pytest tests/backend/ -x -v -k "finance_coach"` — all pass

---

### U14. Literacy Report Router Conversion

**Goal:** 将 Literacy Report 从 `agent_client.stream()` 直接代理转换为 AITask 跟踪 + `agent_client.post()` + bridge consumer 模式。

**Files:**
- Modify: `server/apps/backend/app/routers/ai_literacy_report.py` — 重写 `trigger_generate_events`（line 201）

**Approach:**

对齐 `ai_report.py:trigger_generate_events` 参考实现，与 U13 相同模式：

1. 保留现有 child_id 验证 + cache 逻辑
2. 新增 circuit breaker（当前缺失，对齐 Coach/Report）→ **Phase 2 follow-up**：v2 不阻塞，后续统一添加
3. 在 cache miss 后：检查 running task → 创建 AITask(skill_id="literacy")
4. 替换 `agent_client.stream()` 为 `agent_client.post()`
5. 使用 `consume_task_stream()` 消费 bridge → SSE 返回前端

**Dependencies:** U12（Agent 端已支持 task_id + 回调）

**Patterns to follow:**
- `server/apps/backend/app/routers/ai_report.py:trigger_generate_events` — 参考实现
- `server/apps/backend/app/routers/ai_finance_coach.py` — U13 实现（相同模式）

**Test scenarios:**
1. 正常流程 → AITask created → running → completed
2. child_id 验证失败 → 403/404
3. 并发请求 → 检测到 running task
4. Agent 失败 → AITask → failed
5. Cache hit → 不创建 AITask

**Verification:** `cd server && uv run pytest tests/backend/ -x -v -k "literacy_report"` — all pass

---

### U15. Dashboard Narrative Router Conversion

**Goal:** 将 Dashboard Narrative 从 GET SSE 代理转换为 POST + bridge consumer SSE（在页面时）+ AITask 轮询（切走后）双层模型（OQ-1 resolved）。

**Files:**
- Modify: `server/apps/backend/app/routers/dashboard.py` — 重写 `get_narrative`（line 203），从 GET 改为 POST
- Modify: 前端调用方同步更新（在 U17 中处理）

**Approach:**

与 Coach/Literacy（U13/U14）相同的双层模型（OQ-1 resolved）：

1. `POST /dashboard/narrative/generate` → 创建 AITask(skill_id="narrative") → `agent_client.post()` → 通过 `consume_task_stream()` (bridge consumer) SSE 流式返回前端
2. 保留 cache + threshold gate 逻辑
3. 新增 circuit breaker（当前缺失）→ **Phase 2 follow-up**：v2 不阻塞，后续统一添加
4. 删除旧 GET 端点（U17 前端同步切换到 POST + bridge consumer SSE / 轮询）
5. **切走/刷新后**：使用 `useTaskPolling(taskId)` 轮询 AITask 恢复状态

> **部署注意**：U15（后端）和 U17（前端）必须原子部署。如有过渡期需求，可临时保留旧 GET 端点返回 503 + Location header 指向新 POST。

**Dependencies:** U12（Agent 端已支持 task_id + 回调）

**Patterns to follow:**
- `server/apps/backend/app/routers/ai_report.py:trigger_generate_events` — 参考实现
- `server/apps/backend/app/routers/dashboard.py` — 现有 cache + threshold gate 模式

**Test scenarios:**
1. POST generate → AITask created → SSE 流开始（用户在页面时实时接收）
2. 缓存 hit → 不创建 AITask，直接返回缓存结果
3. Threshold gate → 数据不足时返回空（不创建任务）
4. 并发请求 → 检测到 running task

**Verification:** `cd server && uv run pytest tests/backend/ -x -v -k "narrative"` — all pass

---

### U16. Frontend useTaskPolling Composable

**Goal:** 提取通用的任务轮询 composable，供所有非 Chat AI 功能使用。

**Files:**
- Create: `frontend/apps/main/src/composables/useTaskPolling.ts`
- Test: `frontend/apps/main/src/composables/__tests__/useTaskPolling.spec.ts`

**Approach:**

从 `useReportStream.ts` 的内联 `pollTaskUntilComplete()` 提取为通用 composable：

```typescript
// useTaskPolling(taskId: Ref<string | null>, options?: { interval?: number })
// - 每 interval（默认 2000ms）轮询 GET /api/v1/ai/tasks/{taskId}
// - taskId 变为非 null 时开始轮询
// - status=completed → 停止轮询，emit onComplete(result)
// - status=failed/interrupted/timeout → 停止轮询，emit onError(error)
// - status=running → 更新 progress 数据
// - document.hidden 时暂停轮询，重新可见时恢复
// - 组件 unmount 时自动停止
```

使用现有 `api/ai-tasks.ts:getTaskById()` API。

**Dependencies:** U10（AITaskResponse 须包含 progress 字段）

**Patterns to follow:**
- `frontend/apps/main/src/composables/useReportStream.ts` — 参考实现（内联 pollTaskUntilComplete）
- `frontend/apps/main/src/composables/useTaskResume.ts` — 任务恢复模式
- `frontend/apps/main/src/api/ai-tasks.ts` — 现有 getTaskById API

**Test scenarios:**
1. taskId 设为非 null → 开始轮询（2s 间隔）
2. status=completed → 停止轮询，onComplete 回调触发
3. status=failed → 停止轮询，onError 回调触发
4. document.hidden → 暂停轮询
5. document 重新可见 → 恢复轮询
6. 组件 unmount → 轮询停止，无内存泄漏
7. taskId 为 null → 不启动轮询

**Verification:** `cd frontend/apps/main && npx vitest run -t "useTaskPolling"` — all pass

---

### U17. Frontend Feature Integration

**Goal:** 将 Finance Coach、Literacy Report、Dashboard Narrative 前端切换到双层模型（在页面时 bridge consumer SSE + 切走后 AITask 轮询恢复）。

**Files:**
- Modify: `frontend/apps/main/src/api/ai.ts` — 更新 `getFinanceCoach()` 从 SSE 改为 POST + 轮询
- Modify: `frontend/apps/main/src/composables/useLiteracyStream.ts` — 切换到 AITask + 轮询
- Modify: `frontend/apps/main/src/api/ai.ts` 或相关组件 — Dashboard Narrative 调用从 GET 改为 POST + 轮询
- Modify: 使用 U16 的 `useTaskPolling` composable

**Approach:**

**双层模型（OQ-1 resolved）**：

- **用户在页面时**：保留现有 SSE 流式体验（bridge consumer），用户看到实时 token-by-token 输出
- **用户切走/刷新后**：通过 `useTaskPolling(taskId)` 轮询 AITask 恢复状态

三个功能统一模式：
1. POST 触发 → 返回 `{ task_id }`
2. **在页面时**：通过 bridge consumer SSE 实时接收进度/结果（与 Report 现有模式一致）
3. **切走/刷新后**：使用 `useTaskPolling(taskId)` 轮询状态
4. status=completed → 从 AITask.progress.result_summary 或缓存 API 获取结果
5. status=failed/interrupted → 显示错误 + 重试按钮
6. status=running → 显示进度（step、steps_completed/steps_total）

**Dependencies:** U13、U14、U15、U16（后端转换 + 轮询 composable 须就绪）

**Patterns to follow:**
- `frontend/apps/main/src/composables/useReportStream.ts` — 参考实现（SSE 层）
- `frontend/apps/main/src/composables/useTaskPolling.ts` — U16 创建的通用 composable（轮询层）

**Test scenarios:**
1. Finance Coach → POST trigger → SSE 流式显示进度 → completed → 显示结果
2. Literacy Report → 同上
3. Dashboard Narrative → POST trigger → SSE 流式 → completed → 显示结果
4. 离开页面 → 切到轮询 → 返回 → 恢复 SSE（或轮询 completed）
5. 任务失败 → 显示错误信息 + 重试按钮
6. 刷新页面 → 轮询恢复 → 显示最新状态
7. 重试 → 创建新 AITask，重新开始

**Verification:**
- `cd frontend && pnpm typecheck` — 0 errors
- `cd frontend/apps/main && npx vitest run` — all pass

---

### U21. Frontend Cancel Button Integration

**Goal:** 为所有 AI 功能页面添加取消按钮，使用户能在任务运行时主动取消。同时清理现有死代码。

**Files:**
- Modify: `frontend/apps/main/src/api/ai.ts` — 新增 `cancelTaskById(taskId)` 方法，替换死代码 `cancelAITask()`
- Modify: `frontend/apps/main/src/composables/useTaskPolling.ts`（U16）— 新增 `cancel()` 方法
- Modify: `frontend/apps/main/src/pages/AIReportPage.vue` — 添加取消按钮
- Modify: `frontend/apps/main/src/pages/AIHubPage.vue` — 添加取消按钮（Coach/Literacy）
- Modify: `frontend/apps/main/src/pages/DashboardPage.vue` 或 Narrative 组件 — 添加取消按钮

**Approach:**

1. **API 层**：新增 `cancelTaskById(taskId: string): Promise<{ ok: boolean; status: string }>` 调用 `POST /api/v1/ai/tasks/{task_id}/cancel`
2. **useTaskPolling 扩展**：新增 `cancel()` 方法 → 调用 `cancelTaskById` → 停止轮询 → 更新本地状态为 cancelled
3. **各页面 UI**：当 `taskStatus === 'running'` 时显示取消按钮（van-button，红色/警告样式），点击后调用 `cancel()` + 确认对话框
4. **Chat 不变**：Chat 继续使用现有的 stop 按钮（`cancelStream()` → `client.runs.cancel()`），不走新端点
5. **清理死代码**：删除 `api/ai.ts:cancelAITask()`（从未调用）

**Dependencies:** U16（useTaskPolling）、U17（feature integration）、U20（后端 cancel 端点）

**Patterns to follow:**
- `frontend/apps/main/src/components/ai-chat/InputBox.vue:1022-1032` — 现有 Chat stop 按钮（参考 UI 模式）
- `frontend/apps/main/src/composables/useReportStream.ts` — 现有 SSE 层（参考 abort 模式）

**Test scenarios:**
1. Finance Coach running → 点击取消 → API 调用成功 → 轮询停止 → 显示 cancelled 状态
2. Literacy running → 同上
3. Dashboard Narrative running → 同上
4. Asset Report running → 同上
5. 任务已完成 → 取消按钮不显示
6. 取消确认对话框 → 用户取消确认 → 不发送 API 请求
7. API 返回错误 → 显示 toast 错误信息，按钮恢复可用

**Verification:**
- `cd frontend && pnpm typecheck` — 0 errors
- `cd frontend/apps/main && npx vitest run -t "cancel"` — all pass

---

### U18. Chat Backend AITask Tracking

**Goal:** 为 Chat 新增 AITask 后台跟踪，使用户切走页面后任务继续执行并可通过轮询恢复。

**Files:**
- Modify: `server/apps/backend/app/routers/ai_chat.py` — 在 chat 触发时创建 AITask(skill_id="chat")
- Modify: `server/apps/agent/services/runtime/worker.py` — `_run_numina_agent`(1040) 新增 task_id 参数 + 回调

**Approach:**

1. **Backend 侧**（`ai_chat.py`）：
   - 在 SSE proxy 开始前：`AITaskService.create_task(family_id, "chat", session_id, db)`
   - 将 `task_id` 传入 agent trigger request
   - SSE 流正常代理（不改变用户体验）
   - Backend SSE proxy 作为 fallback 完成权威：若 Agent complete 回调因网络丢失，SSE 流结束后 Backend 可补标 completed/failed
   - Agent 完成时调用 complete/fail 回调（与 L991 一致，幂等）

2. **Agent 侧**（`_run_numina_agent`）：
   - 接收 `task_id` 参数（可选，向后兼容）
   - **与 Bridge consumer 功能不同**：Chat 没有 bridge consumer，因此 Agent 必须调用 complete/fail 回调标记终态（与 Import-parse 一致）
   - 幂等设计：用户离页后 Agent 继续运行，完成时状态仍正确更新
   - 不改变 SSE 流式输出（Chat 用户在页面时仍看到 token-by-token 流式）

3. **Chat 特殊点**：
   - Chat 的 SSE 走 `agent_client.stream()` 而非 `agent_client.post()` + bridge consumer
   - AITask 跟踪是**附加层**，不改变 SSE 流式路径
   - 前端通过 AITask 判断任务状态（completed → 不重连 SSE，running → 重连）

**Dependencies:** U10（`chat` 加入 VALID_SKILL_IDS）、U12（Agent 回调机制就绪）

**Patterns to follow:**
- `server/apps/backend/app/routers/ai_finance_coach.py` — U13 的 AITask 创建模式
- `server/apps/agent/services/runtime/worker.py:_run_numina_agent` — 现有 Chat runner

**Test scenarios:**
1. Chat 消息发送 → AITask(skill_id=chat, status=running) 创建
2. Chat 正常完成 → AITask → completed
3. Chat 异常 → AITask → failed
4. SSE 流式不受影响 → token-by-token 正常
5. Agent 侧 task_id 参数为 None（旧版 Backend 未传 task_id） → Agent 不发送回调（向后兼容）
6. 用户离页 → Agent 继续执行 → complete 回调 → AITask completed → 用户回来时 U19 正确判断

**Verification:** `cd server && uv run pytest tests/backend/ -x -v -k "chat_task"` — all pass

---

### U19. Chat Frontend Recovery Flow

**Goal:** 实现 Chat 前端基于 AITask 状态的恢复逻辑。

**Files:**
- Modify: `frontend/apps/main/src/composables/ai-chat/useThreadChat.ts` — 新增 AITask 状态预检
- Modify: `frontend/apps/main/src/api/ai-tasks.ts` — 可能需要新增按 session_id 查询 task 的方法

**Approach:**

在 Chat 页面 mount/reconnect 时新增 AITask 状态预检：

1. 查询当前 session 的 AITask（通过 `GET /api/v1/ai/tasks?skill_id=chat&session_id={id}`）
2. 根据 AITask.status 决策：
   - `completed` → 调用 `POST /api/threads/{session_id}/history` 加载完整对话，不重连 SSE
   - `failed/interrupted` → 显示错误 + 重试按钮
   - `running` → 调用 `POST /api/threads/{session_id}/history` 加载已有对话 + 重连 SSE 继续接收
   - 无 AITask → 正常流程（新对话或从 checkpointer 加载）

3. **数据获取端点（OQ-2 resolved）**：
   - AITask.session_id 即 thread_id（Chat 创建 AITask 时传入）
   - 使用现有 LangGraph proxy 端点：`POST /api/threads/{thread_id}/history` 获取对话历史
   - 无需新增 API，前端已有调用这些端点的逻辑

4. **Terminal state preflight**（对齐 DeerFlow `shouldSkipReconnect()`）：在尝试 SSE reconnect 前检查 AITask 是否已进入终态，避免无谓的重连尝试。

**Dependencies:** U18（Chat AITask 跟踪须就绪）

**Patterns to follow:**
- `frontend/apps/main/src/composables/ai-chat/useThreadChat.ts` — 现有 SSE 连接逻辑
- `frontend/apps/main/src/composables/useReportStream.ts` — terminal state preflight 模式
- DeerFlow `reconnectOnMount: true` + checkpointer 恢复模式

**Test scenarios:**
1. Chat 生成中刷新页面 → AITask running → 从 checkpointer 加载历史 + 重连 SSE
2. Chat 已完成 → AITask completed → 加载完整对话，不重连 SSE
3. Chat 失败 → AITask failed → 显示错误 + 重试按钮
4. Chat 正常（无中断）→ 无 AITask 或 AITask completed → 正常加载
5. 用户在 Chat 页面时 → SSE 流式不受影响（token-by-token 正常）

**Verification:**
- `cd frontend && pnpm typecheck` — 0 errors
- `cd frontend/apps/main && npx vitest run -t "useThreadChat"` — all pass

---

## Definition of Done

### Functional Completeness

- [ ] 3 个流式功能（Finance Coach、Literacy Report、Dashboard Narrative）全部从直接 SSE 代理转换为 AITask 跟踪 + 轮询模式
- [ ] Chat 新增 AITask 后台跟踪，用户在页面时 SSE 流式体验不变
- [ ] Agent 通过 HTTP callback 在关键节点更新 AITask.progress（3-5 次/任务）
- [ ] Agent heartbeat 每 40s 续期 lease_expires_at
- [ ] 前端 useTaskPolling composable 可复用于所有非 Chat AI 功能
- [ ] Chat 前端基于 AITask 状态决策是否重连 SSE
- [ ] 所有 AI 任务（Report/Coach/Literacy/Narrative）支持用户主动取消（cancel 按钮 + 后端端点）
- [ ] 无新 database migration（使用现有 progress 列）

### Quality Gates

- [ ] `cd server && uv run ruff check apps/backend apps/agent packages/db` — 0 errors
- [ ] `cd server && uv run mypy .` — 0 errors
- [ ] `cd server && uv run pytest tests/backend/ -x -v` — all pass
- [ ] `cd server && uv run pytest tests/agent/ -x -v` — all pass
- [ ] `cd frontend && pnpm typecheck` — 0 errors
- [ ] `cd frontend/apps/main && npx vitest run` — all pass
- [ ] Asset Report E2E 无退化（v1 功能不受影响）
- [ ] Wish Advice / Bill Import 无退化（不转换的功能不受影响）

### Handoff Criteria

- [ ] 所有 13 个 Implementation Units（U9-U21）已完成
- [ ] Verification Contract V1-V7 全部通过
- [ ] Git commits 按 U-ID 组织，每个 U-ID 一个逻辑提交

---

## Appendix: Review Findings & Revision History

### Revision 1 (2026-08-15): Premise Corrections (ce-doc-review)

**S0 — DeerFlow 架构误读（Critical）。** 原计划基于 "DeerFlow 有 Gateway/Worker 服务拆分" 的前提，但 DeerFlow 实际是单进程 FastAPI 应用。

**S1 — 流式功能范围高估。** 原计划列出 6 个功能需转换，实际只有 3 个使用 SSE 流式。

**S2 — Wish-Advice 模式错误。** 同步调用 `generate_advice()`，非流式。

**S3 — Import endpoint 不存在。** 实际是 `/parse` + `/confirm` + `/confirm-via-agent`。

**S4 — StreamBridge 位置错误。** 已在 `packages/db/stream_bridge/` 共享包。

### Revision 2 (2026-08-15): EventBus → 轮询模型

**架构方向变更。** 用户提出 EventBus 过度设计，轮询模型更简单且足够：
- 后台任务不需要逐 token 实时流
- DB 本身就是共享存储，集群模式零额外依赖
- 断线恢复天然支持，无需 Last-Event-ID/gap 检测

### Revision 3 (2026-08-15): Chat 统一后台执行

**范围扩展。** 用户要求 Chat 也支持页面切走后后台继续执行：
- Chat 增加 AITask 后台跟踪
- 用户在页面时仍保留 SSE 流式体验
- 切走/刷新后通过 checkpointer + AITask 恢复

### Revision 4 (2026-08-15): DeerFlow 模式修正分析

**两项 N/A 判断修正。** 前两轮评审中对 DeerFlow 的 `ownership_lost` 和 delta checkpoint 分析不充分，本轮基于代码实证修正：

**S5 — Ultra mode multi-agent 已被实现。** 前轮认为 ultra mode 子代理协作未实现。实证：前端 4 模式（flash/thinking/pro/ultra），ultra 启用 `subagent_enabled=True` + `is_plan_mode=True`。后端 `ai_chat.py` 透传 `subagent_enabled` 到 Agent metadata，`worker.py:_run_numina_agent` 读取后传入 `RunPipeline`。Subagent 通过 DeerFlow 内置 `task` tool 执行（同一进程、同一 run、隔离 event loop），不涉及跨进程协调。DeerFlow alignment 表补充该行为 ✅ 已有。

**S6 — `ownership_lost` fencing 当前 N/A，但原因修正。** `ownership_lost` 是进程级 fencing 信号（`RunRecord.ownership_lost: bool`），5 个触发路径全部是跨进程场景（跨 Worker 进程共享 RunStore 的 lease 竞争/接管/store 冲突）。与 Ultra mode subagent 无关（subagent 是同 run 内 background task，不触发 lease 竞争）。Numina 当前部署为**单 Agent 进程**，无跨进程 run 转移，因此 N/A。未来若部署 Agent 集群需引入类似机制。

**S7 — Delta checkpoint（CachedHistorySaver）当前暂缓，但评估理由修正。** 前轮以"使用 SQLite"为由判定 delta checkpoint 不需要。实证：**生产部署使用 PostgreSQL**（`DEERFLOWDB_URL` env，所有 Docker compose 默认），连接池 `AsyncConnectionPool(min=1, max=3, prepare_threshold=None)` 兼容 Supabase PgBouncer。在 PostgreSQL 下网络往返成本（5-50ms/写入）使全量 checkpoint 在长 thread（100+ messages）时累积延迟显著。当前暂不需要因为典型 thread 较短（10-30 messages），但未来长 thread/ultra 密集 checkpoint 场景需重新评估。启用方式：DeerFlow 已内置，配置 `checkpoint_channel_mode: delta` 即可，非从零实现。

### 关键决策变更总览

| 轮次 | 原决策 | 修正后 |
|------|-------|--------|
| R1 | 移动 Gateway 组件 | 新增 EventBus 抽象层 |
| R2 | EventBus 抽象层（内存/Redis 双实现） | **轮询模型**（AITask 进度 + 前端 2s 轮询） |
| R3 | 3 个流式功能转换 | **5 个 AI 功能**统一跟踪（含 Chat） |
| R4 | SSE Last-Event-ID 重连 | **轮询 + SSE 混合**（Chat 保留 SSE，其余轮询） |
| R5 | EventBus pub/sub 硬编码 | **DB 是唯一状态源**，集群零额外依赖 |
| R8 | 仅系统内部取消（shutdown/orphan） | **用户主动取消**（task_id 端点 + 前端按钮 + Agent 停止） |

### DeerFlow 参考对齐

| DeerFlow 模式 | Numina 实现 | 状态 |
|--------------|------------|------|
| RunManager `create_or_reject()` 原子准入 | AITask partial unique index `(family_id, skill_id) WHERE status = 'running'`（仅覆盖 running；queued 未覆盖，tech-debt） | ✅ 已有 |
| `lease_expires_at` + heartbeat loop | AITask.lease_expires_at + Agent 40s heartbeat（lease_ttl/3） | ✅ 已有 |
| `reconcile_orphaned_inflight_runs()` | AITaskService.get_stale_running_tasks() + mark_interrupted() | ✅ 已有 |
| `asyncio.shield(run_manager.shutdown())` drain | ShutdownGuardMiddleware + drain timeout | ✅ 已有 |
| `reconnectOnMount: true` + checkpointer | Chat 从 checkpointer 恢复 + AITask 判断是否重连 | ✅ 本次实现 |
| `StreamBridge` memory/redis | 保留用于 Chat SSE 流式 | ✅ 已有 |
| `StreamGap` 事件 gap 检测 | 不需要（轮询模型无 gap 概念） | N/A |
| `ownership_lost` 进程级 fencing | 不需要（见下方详细分析） | N/A |
| `CachedHistorySaver` delta checkpoint | 暂不需要（见下方详细分析），未来长 thread 场景可启用 | Deferred |
| `_persist_run_duration()` 运行时长 | 可选：在 AITask.progress 中记录 | Phase 2 |
| Ultra mode `subagent_enabled` | 已实现。前端 4 模式（flash/thinking/pro/ultra），ultra 启用 subagent。Subagent 在同一 run 内执行（background task），不涉及跨进程 | ✅ 已有 |
| `multitask_strategy` (reject/interrupt/rollback) | DeerFlow 同 thread 并发 run 准入策略。Numina 通过 AITask 唯一约束 + R1 allowlist 实现等效控制 | ✅ 已有 |

#### N/A 项详细分析（Revision 4 补充）

**`ownership_lost` 进程级 fencing — 当前不需要**

DeerFlow 的 `ownership_lost`（`RunRecord.ownership_lost: bool`）是一个**进程级 fencing 信号**，用于多 Gateway 进程共享同一 RunStore（PostgreSQL）的部署场景：

```
Worker A (process 1) ──┐
Worker B (process 2) ──┼── shared RunStore (PostgreSQL)
Worker C (process 3) ──┘

每个 Worker 有独立 worker_id = hostname:uuid
heartbeat loop 每 lease_ttl/3 续约 lease_expires_at
当续约失败或 peer claim → ownership_lost = True → 阻止本地 run 继续写 status/checkpoint
```

**触发条件**（5 个路径，全部是跨进程场景）：
1. Heartbeat 续约前检测到 lease 已过期（event loop 饱和/调度延迟）
2. Heartbeat 续约成功但响应到达时 lease 已过期（网络延迟）
3. Store 拒绝续约（peer 已通过 `claim_for_takeover` 接管）
4. Heartbeat 续约异常且 lease 已过期
5. Status/completion 持久化发现 store row 已是 `error`（peer 已 terminalize）

**与 Ultra mode multi-agent 的关系**：Ultra mode 确实启用了 subagent（`subagent_enabled=True`），但 subagent 是**同一 run 内部的 background task**（同一进程、同一 `thread_id`、隔离 event loop），通过 DeerFlow 的 `SubagentExecutor` 和 `task` tool 协调。Subagent 不涉及 lease 竞争或跨进程所有权转移，因此不触发 `ownership_lost`。

**Numina 当前不需要的原因**：
- 当前部署为**单 Agent 进程**，不存在跨进程 run 转移
- 每个 AITask 由唯一 Agent 进程处理，Agent crash 时通过 lease 过期 + `mark_interrupted()` 处理（不转移给另一个 Agent）
- OQ-6 的 lease heartbeat + gc.py 孤儿恢复已覆盖 Agent crash 场景

**未来若部署 Agent 集群**（多 Agent 实例共享 RunStore），需要引入类似 fencing 机制。届时可参考 DeerFlow 的 `RunOwnershipConfig`（`heartbeat_enabled`、`lease_seconds`、`grace_seconds`）。

---

**`CachedHistorySaver` delta checkpoint — 暂不需要，未来可启用**

DeerFlow 的 `CachedHistorySaver`（`checkpointer/cached_saver.py`）是一个**增量 checkpoint 优化层**，包裹在 raw checkpointer 之上：

```
Standard mode (full):  每次写入 = 完整状态快照
  turn 1: [msg1, msg2, msg3]           → write 3 messages
  turn 2: [msg1, msg2, msg3, msg4, msg5] → write 5 messages (重写了 1-3)

Delta mode:  每次写入 = 只写增量
  turn 1: [msg1, msg2, msg3]           → write 3 messages
  turn 2: [msg4, msg5]                  → write 2 messages (只写新增)
  turn 3: [msg6, msg7]                  → write 2 messages (只写新增)
```

**Numina 当前 checkpointer 配置**：
- 开发环境：`AsyncSqliteSaver`（SQLite 本地文件，`DEERFLOW_DB_PATH`）
- **生产环境：`AsyncPostgresSaver`（PostgreSQL，`DEERFLOWDB_URL`）**
- 连接池：`AsyncConnectionPool(min=1, max=3, prepare_threshold=None)`（Supabase PgBouncer 兼容）
- 当前使用 `full` mode（raw saver），未启用 `CachedHistorySaver`

**为什么 PostgreSQL 下 delta mode 值得关注**：

| 操作 | SQLite (本地) | PostgreSQL (远程) |
|------|--------------|-------------------|
| 写入一个 checkpoint | < 1ms | 5-50ms（网络往返） |
| 100 message thread 全量写 | ~5ms | 20-100ms |
| 每 turn 全量写（频繁 LLM 调用） | 可忽略 | **累积延迟显著** |

**当前暂不需要的理由**：
- Numina 典型 Chat thread 较短（10-30 messages），全量写入成本可控
- 非 Chat 功能（Report/Coach/Literacy/Narrative）是单轮任务，thread 极短

**未来需要重新评估的场景**：
- 长 thread（100+ messages）：连续辅导、长期对话
- Ultra mode 密集 checkpoint：lead agent + 多 subagent 完成各触发 checkpoint
- 启用方式：DeerFlow 已内置支持，只需配置 `checkpoint_channel_mode: delta`（`async_provider.py:243`），非从零实现

### 相关文档

- [`gateway-worker-responsibility-separation-2026-08-15.md`](../solutions/architecture-patterns/gateway-worker-responsibility-separation-2026-08-15.md) — 原架构决策文档（已废弃，premise 已修正）
- [`ai-task-resilience-v2-brainstorm.md`](../brainstorms/ai-task-resilience-v2-brainstorm.md) — 上游 Product Contract
- DeerFlow reference: `/Users/vincentruan/geek_space/github/deer-flow-reference`

---

### Revision 8 (2026-08-16): 用户主动取消缺口补全

**S8 — 用户无法主动取消非 Chat AI 任务。** 原计划缺少用户侧 cancel 入口。分析：
- 现有 `cancelAITask()` (`api/ai.ts:441`) 是死代码（从未调用）
- 现有 `POST /api/v1/ai/tasks/{skill_id}/cancel` 仅更新 DB，不调用 Agent 停止执行
- `VALID_SKILL_IDS` 不含 coach/literacy/narrative/chat
- Chat 有取消（stop 按钮 → `client.runs.cancel()`），其余功能无取消按钮

补全：
- **R8** — 新增用户主动取消需求
- **Flow 5** — 用户取消流程图（Frontend → Backend → Agent → callback）
- **AE5** — Finance Coach 取消验收示例
- **KTD-17** — 取消端点使用 task_id（非 skill_id）设计决策
- **U20** — Backend 用户取消端点（`POST /api/v1/ai/tasks/{task_id}/cancel`）
- **U21** — Frontend 取消按钮集成（Report/Coach/Literacy/Narrative 页面 + 清理死代码）
- **V2/V3** — 更新验证测试包含用户取消场景 + 取消竞争场景
- **Risk Assessment** — 新增用户取消与任务完成竞争风险

---

## Deferred / Open Questions

### From 2026-08-15 ce-doc-review (Round 2, post-enrichment)

**OQ-1 — SSE→polling UX 降级（P1）— ✅ 已解决（选 A：双层模型）。** 决定：用户在页面时保留 SSE 流式（bridge consumer），切走/刷新后通过轮询 AITask 恢复。R4 表格和 U17 已更新。理由：与 Chat 现有架构一致，用户体验最佳，U13/U14 已使用 bridge consumer 无需改动。

**OQ-2 — Chat checkpointer 数据获取 API 未定义（P1）— ✅ 已解决。** 决定：使用现有 LangGraph proxy 端点（`POST /api/threads/{thread_id}/history`），AITask.session_id 即 thread_id。U19 已补充端点说明，无需新增 API。

**OQ-3 — 前端结果获取路径未定义（P1）— ✅ 已解决。** 决定：(1) Agent callback 在 complete 时将结果写入 `AITask.progress.result_summary`（各功能：Coach→suggestions, Narrative→narrative, Literacy→report_markdown）；(2) running 状态通过 SSE 重连从 bridge consumer 继续流式（bridge consumer 已支持，U13/U14/U15 自动继承）；(3) completed 状态从 `progress.result_summary` 读取。无需新增缓存 API。

**OQ-4 — Bridge consumer vs Agent callback 完成竞争（P1）— ✅ 已解决。** 决定：对于使用 bridge consumer 的功能（Coach/Literacy/Narrative），bridge consumer 是唯一完成权威（它知道何时所有 frames 已传递），agent runner 只负责 heartbeat + progress，不调用 complete_task/fail_task。U12 已更新。Chat 无 bridge consumer，Agent 调用 complete/fail（与现有 Import-parse 模式一致，后者不在 v2 范围）。Report 的双 complete 可后续清理。

**OQ-5 — Progress JSON schema 验证（P2）— ✅ 已解决（轻量级方案）。** 决定：保持 `progress: dict | None` 灵活性，在 `report_progress` 端点加 size limit（`len(json.dumps(progress)) < 10000`），文档记录各功能预期结构。U9 已更新。

**OQ-6 — U12 progress 中间插入点（P2）— ✅ 已解决。** 决定：(1) Coach/Literacy/Narrative 接受 2 次更新（start + end），更新 R1/KTD-3；(2) Report 从 bridge consumer 监听 custom events 提取 3-step 进度（`report.step1_*`, `report.step2_json`, `report.step3_*`）；(3) Chat 的 progress = None 或 messages_count（checkpointer 是 SSOT，消息历史包含所有 thinking/tool calls/responses，用户返回时从 checkpointer 恢复完整上下文）。
