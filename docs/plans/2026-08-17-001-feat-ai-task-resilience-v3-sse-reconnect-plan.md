---
artifact_contract: ce-unified-plan/v1
artifact_readiness: implementation-ready
date: 2026-08-17
revised: 2026-08-17 (review-applied)
type: feat
depends_on: 2026-08-15-002-feat-ai-task-resilience-v2-full-coverage-plan
---

# AI Task Resilience v3: SSE 重连 + 机制 C 事件分发 - Plan

## Goal Capsule

**Objective:** 让用户在页面导航中断后返回时，能**立即恢复 SSE 流式体验**（而非纯轮询等待完成）。同时修复 SSE 生命周期相关的 pre-existing bug（complete_task 解耦、404 轮询风暴）。Report JSON 校验移至 agent 侧（保持 agent harness 层职责一致性）。

**交付策略（review 后调整）：**

| 批次 | 内容 | 估时 | 说明 |
|------|------|------|------|
| **Batch 1**（首期 ship） | Pre-Batch 0 + Phase 1-3 + Phase 5.4 + F1/F4/F7/F12 修复 | ~16h | SSE 重连 + 生产 bug 修复 + 生命周期修复 |
| **Batch 2**（后续） | Phase 4A (deferred) + Phase 4B (agent-side) + Phase 5.1-5.3 | ~13.5h | 架构优化 + 报告质量加固 |

**核心决策（已对齐）：**
1. **机制 C**：Agent 始终 publish 事件，Backend 全权决定分发策略（SSE 转发 / 跳过中间转发）
2. **Backend 中转**：前端不直连 Agent，所有 SSE 经 Backend 中转（安全 + tenant 隔离 + 持久化）
3. **Subscribe-only 端点**：新增 `GET /ai/tasks/{task_id}/stream` 用于 SSE 重连，不触发新任务
4. **Bridge buffer 始终持久化**：agent 始终 publish 所有事件到 bridge buffer（无论有无 subscriber）；Phase 4A 的优化是跳过 SSE 转发（不是跳过 buffer）

**不做的事：**
- 不让前端直连 Agent SSE（安全风险）
- 不改 Agent 的 `bridge.publish()` 调用方式（机制 C 下 Agent 无感知）
- 不改 StreamBridge 底层存储（memory/redis 双模式保留）
- 不改 AITask 表的 `skill_id` 字段名（术语遗留，单独 PR 处理）
- ~~Phase 4A subscriber_aware 优化不在首期~~（review 后 defer 到 Batch 2）
- ~~Report JSON 校验放在 backend~~（review 后移到 agent 侧，保持架构一致性）

**术语澄清：**
- **Application Scenario（应用场景）**：`narrative` / `coach` / `literacy` / `report` / `chat` — AITask 表 `skill_id` 字段所指的维度
- **Skill（技能）**：agent 侧 skill.md 定义的能力（如 asset-report、finance-coach 等 agent app）— 属于 agent harness 层
- 本 plan 中 "scenario result" 指应用场景的最终产出（如 narrative 文本、coach 建议 JSON），"skill" 仅在涉及 agent 侧 skill.md 时使用

---

## 架构变更概览

### 当前架构（v2）

```
用户离开页面 → 前端 SSE abort → 只走 useTaskPolling (2s)
                                    ↓
                              GET /tasks/detail/{id} 轮询
                                    ↓
                              等 completed → GET 缓存结果
                                    
问题：用户看不到 中断→完成 期间的流式输出
```

### 目标架构（v3）

```
用户在页面 → SSE 实时流式（thinking + deltas）    ← 不变
用户离开   → 前端 SSE abort，agent 继续写 bridge buffer
用户返回   → 前端检测 task running
           → GET /tasks/{id}/stream?last_event_id=... ← 新端点
           → Backend 从 bridge buffer replay 中断的事件
           → 用户立即看到流式输出（从断点恢复）
           
Bridge buffer 始终由 agent 填充（无论有无 subscriber）→ reconnect 总能 replay
```

### 数据流（机制 C）

```
Agent (纯 harness)                    Backend (事件中枢)                  Frontend
─────────────────                    ──────────────────                  ────────
pipeline 运行                         
  bridge.publish(event) ──────────→  收到事件                            (bridge buffer
                                      │                                   始终持久化)
                                      ├─ 有 subscriber?                 
                                      │   YES → 转发 SSE ────────────→  接收 event
                                      │   NO  → 跳过 SSE 转发           
                                      │         (bridge buffer 仍填充)  
                                      └─ end sentinel →                 
                                          complete_task()               
                                          ↑ 由独立 asyncio.Task 执行     
                                            (不依赖 SSE generator)      
```

> **F1 修复（Pre-Batch 0）：** `complete_task()` 从 SSE generator 移到独立 `asyncio.Task`，解决客户端断开后任务永远 running 的 pre-existing bug。

---

## Pre-Batch 0: SSE 生命周期修复（F1 + F4）

> **Review 新增**：解决 pre-existing bug — 客户端 SSE 断开后 `complete_task()` 永远不执行。

### 0.1 问题根因

`complete_task()` 在 `consume_task_stream` async generator 内（`bridge_consumer.py:162-167`）。当客户端断开连接，ASGI/Starlette 取消 generator → `complete_task()` 不执行 → 任务永远停在 `running`。

同样，result 持久化（`upsert_skill_result`）在 router SSE wrapper 内（`dashboard.py:395`, `ai_finance_coach.py:47`），也在 generator 取消后丢失。

### 0.2 修复方案

**将 bridge 消费和 result 持久化从 SSE response 生命周期解耦：**

```python
# In trigger endpoint (e.g., POST /dashboard/narrative):
async def trigger_narrative(...):
    task = AITaskService.trigger_narrative(...)
    
    # Spawn independent consumer task (survives SSE disconnect)
    consumer_task = asyncio.create_task(
        _consume_and_persist(task.id, task.run_id, family_id, db_session)
    )
    
    # SSE response only reads from shared queue
    return StreamingResponse(
        _sse_forwarder(consumer_task),  # reads from queue, doesn't own lifecycle
        media_type="text/event-stream",
    )

async def _consume_and_persist(task_id, run_id, family_id, db):
    """Independent consumer — survives SSE disconnect."""
    async for event in bridge_consumer(task_id, run_id, family_id):
        if event.type == "custom" and event.data.type.endswith(".result"):
            # Persist result (was previously in router SSE wrapper)
            await upsert_skill_result(task_id, event.data, db)
        if event.type == "end":
            await AITaskService.complete_task(task_id, db)
            break
```

**文件：** `bridge_consumer.py`（新增 `_consume_and_persist`）、4 个 router 文件（改用新 consumer 模式）

### 0.3 F12 修复：exception 泄露

`bridge_consumer.py:183` 的 `str(e)` 直接发到 SSE error event，可能包含内部路径/DB 连接串。

**修复：** 映射已知异常类型为 user-safe 消息，未知异常 log 完整错误 + 返回通用消息。

```python
except Exception as e:
    logger.error(f"[bridge_consumer] task={task_id} error: {e}", exc_info=True)
    safe_msg = _map_to_safe_message(e)  # RuntimeError → '任务未找到', else → '服务异常'
    yield f"event: error\ndata: {json.dumps({'error': safe_msg})}\n\n"
```

---

## Phase 1: Backend Subscribe-Only SSE 端点

### 1.1 新增端点

**端点：** `GET /api/v1/ai/tasks/{task_id}/stream`

**职责：** 订阅已有任务的 SSE 流，支持 Last-Event-ID 断点恢复。**不触发新任务。**

**行为矩阵：**

| task.status | buffer 状态 | 响应 |
|-------------|------------|------|
| `running` / `queued` / `post_processing` | 存在 | 200 `text/event-stream`，从 Last-Event-ID 或 buffer 起点 replay |
| `running` / `queued` / `post_processing` | 不存在（gap） | 200 `text/event-stream`，立即 `event: gap` + 关闭 |
| `completed` | — | 200 `text/event-stream`，发 `event: result` (cached) + `event: end` + 关闭 |
| `failed` / `cancelled` / `timeout` | — | 200 `text/event-stream`，发 `event: error` (error_message) + `event: end` + 关闭 |
| 不存在 / 不属于此 family | — | 404 |

**代码位置：** `server/apps/backend/app/routers/ai_tasks.py`

```python
@router.get("/{task_id}/stream")
async def stream_task_events(
    task_id: int,
    request: Request,
    last_event_id: str | None = Header(None),
    current_user: User = Depends(require_adult),
    db: Session = Depends(get_db),
):
    """Subscribe-only SSE endpoint for task stream reconnection.
    
    Does NOT trigger a new task. Subscribes to the existing task's
    bridge buffer and replays events from Last-Event-ID (if provided).
    """
    task = AITaskService.get_task_by_id(task_id, current_user.family_id, db)
    if not task:
        raise AppError(ErrorCode.NOT_FOUND, "任务不存在")
    
    # Terminal states: emit cached result and close
    if task.status in ("completed", "failed", "cancelled", "timeout"):
        return StreamingResponse(
            _emit_scenario_result(task),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )
    
    # Active task: subscribe to bridge buffer
    if not task.run_id:
        raise AppError(ErrorCode.NOT_FOUND, "任务尚未分配 run_id")
    
    return StreamingResponse(
        consume_task_stream(
            task_id=task.id,
            family_id=current_user.family_id,
            last_event_id=last_event_id,
            run_id=task.run_id,
        ),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            # Standard SSE headers for EventSource compatibility
            "Connection": "keep-alive",
        },
    )


async def _emit_scenario_result(task) -> AsyncIterator[str]:
    """Emit cached scenario result for terminal tasks, then close."""
    if task.status == "completed":
        # Load scenario-specific result (not "skill" — see terminology note)
        result = _load_scenario_result(task)
        yield f"event: result\ndata: {json.dumps(result, default=str)}\n\n"
    elif task.status in ("failed", "cancelled", "timeout"):
        yield f"event: error\ndata: {json.dumps({'error': task.error_message or '任务异常终止'})}\n\n"
    yield "event: end\ndata: null\n\n"
```

### 1.2 Scenario Result Loader（F10 细化）

`_load_scenario_result(task)` 根据 `task.skill_id`（应用场景标识）从对应的结果存储加载已完成的结果：

| 应用场景 (scenario) | 查询函数 | 返回格式 | SSE event data |
|---------------------|---------|---------|----------------|
| `narrative` | `latest_by_skill(db, family_id, 'narrative')` → `.report_data` | `str` (markdown 文本) | `{"narrative": "..."}` |
| `coach` | `latest_by_skill(db, family_id, 'finance_coach')` → `.report_json` | `dict` (建议 JSON) | 原样透传 JSON |
| `literacy` | `db.query(LiteracyWeeklyReport).filter(family_id=...).order_by(desc(created_at)).first()` | `dict` (周报) | `{"report": {...}}` |
| `report` | `db.query(FamilyReport).filter(family_id=...).order_by(desc(created_at)).first()` | `dict` (报告) | `{"report": {...}}` |
| `chat` | N/A | N/A | chat 不走此端点 |

> **F9 术语修正：** 上表中 "应用场景 (scenario)" 统一使用，不混用 "skill"。

```python
async def _load_scenario_result(task, db: Session) -> dict:
    """Load cached result for terminal task by scenario type."""
    scenario = task.skill_id  # 'narrative' / 'coach' / 'literacy' / 'report'
    
    if scenario in ('narrative', 'coach'):
        skill_key = 'narrative' if scenario == 'narrative' else 'finance_coach'
        cached = latest_by_skill(db, task.family_id, skill_key)
        if not cached:
            return {"error": "结果未找到"}
        if scenario == 'narrative':
            return {"narrative": cached.report_data}
        else:
            return cached.report_json  # already a dict
    elif scenario == 'literacy':
        report = db.query(LiteracyWeeklyReport).filter(
            LiteracyWeeklyReport.family_id == task.family_id
        ).order_by(desc(LiteracyWeeklyReport.created_at)).first()
        return {"report": report.to_dict()} if report else {"error": "报告未找到"}
    elif scenario == 'report':
        report = db.query(FamilyReport).filter(
            FamilyReport.family_id == task.family_id
        ).order_by(desc(FamilyReport.created_at)).first()
        return {"report": report.to_dict()} if report else {"error": "报告未找到"}
    else:
        return {"error": f"未知场景: {scenario}"}
```

### 1.3 安全约束

- `require_adult` — 只有 adult 角色能订阅
- `family_id` 校验 — task 必须属于当前用户的 family（tenant 隔离）
- **F7 修复：并发连接上限** — per-family_id 最多 3 个活跃 SSE 连接（通过 `SubscriberRegistry` 或 `asyncio.Semaphore` 实现），超过返回 `429 Too Many Connections`
- 无 rate limit（SSE 长连接，不同于 REST 轮询）

### 1.4 测试

- 单元测试：`tests/backend/test_ai_tasks_stream.py`
  - Running task → SSE stream with events
  - Completed task → cached result emitted
  - Failed task → error emitted
  - Cross-family task → 404
  - Last-Event-ID replay → correct offset
  - StreamGap → gap event emitted

---

## Phase 2: Frontend SSE 重连支持

### 2.1 API 层：`subscribeTaskStream()`

**文件：** `frontend/apps/main/src/api/ai-tasks.ts`

```typescript
/**
 * Subscribe to a task's SSE stream (subscribe-only, no trigger).
 * 
 * Used for SSE reconnection when user navigates back to a page
 * while a task is still running. Supports Last-Event-ID for
 * gap-free replay from the bridge buffer.
 */
export interface TaskStreamCallbacks {
  onEvent: (event: string, data: unknown) => void
  onGap: () => void
  onEnd: () => void
  onError: (message: string) => void
}

export interface TaskStreamHandle {
  abort: () => void
}

export function subscribeTaskStream(
  taskId: string,
  callbacks: TaskStreamCallbacks,
  options?: { lastEventId?: string },
): TaskStreamHandle {
  const controller = new AbortController()
  void runTaskStream(controller, taskId, callbacks, options)
  return { abort: () => controller.abort() }
}

async function runTaskStream(
  controller: AbortController,
  taskId: string,
  callbacks: TaskStreamCallbacks,
  options?: { lastEventId?: string },
): Promise<void> {
  const url = `/api/v1/ai/tasks/${taskId}/stream`
  const headers: Record<string, string> = { Accept: 'text/event-stream' }
  if (options?.lastEventId) {
    headers['Last-Event-ID'] = options.lastEventId
  }
  
  const res = await fetch(url, {
    method: 'GET',
    headers,
    credentials: 'include',
    signal: controller.signal,
  })
  
  if (!res.ok) {
    callbacks.onError(`stream.request_failed:${res.status}`)
    return
  }
  
  // Parse SSE stream (same pattern as streamNarrative/runNarrativeStream)
  const reader = res.body?.getReader()
  if (!reader) {
    callbacks.onError('stream.unavailable')
    return
  }
  
  // ... SSE parsing loop, calling callbacks.onEvent/onGap/onEnd
}
```

### 2.2 `useTaskResume.ts` 增强

**文件：** `frontend/apps/main/src/composables/useTaskResume.ts`

当前此 composable 未被使用。Phase 2 将其改造为统一的 resume 入口：

```typescript
/**
 * useTaskResume — 统一的任务恢复 composable。
 * 
 * 当用户返回页面时，检测是否有 running task：
 * - 有 → 尝试 SSE 重连（subscribeTaskStream）
 * - SSE 不可用（gap / completed）→ fallback 到 useTaskPolling
 * 
 * 替代各组件的 inline resumeIfRunning() 逻辑。
 */
export function useTaskResume(
  capability: string, // 'coach' | 'narrative' | 'literacy' | 'report'
  options: {
    onStreamEvent?: (event: string, data: unknown) => void
    onComplete?: (task: AITask) => void
    onError?: (task: AITask) => void
  },
) {
  const taskId = ref<string | null>(null)
  const status = ref<'idle' | 'connecting' | 'streaming' | 'polling' | 'completed' | 'failed'>('idle')
  const lastEventId = ref<string | null>(null)
  
  // SSE handle for cleanup
  let streamHandle: TaskStreamHandle | null = null
  // Fallback polling
  const { cancel: cancelPolling, status: pollingStatus } = useTaskPolling(taskId, {
    onComplete: options.onComplete,
    onError: options.onError,
  })
  
  async function resume(): Promise<boolean> {
    // F8 修复：使用实际存在的 getAITasks() API（非 getAITask）
    const tasks = await getAITasks(capability)
    const task = tasks[0]  // 取最新的一个
    if (!task?.task_id || !['running', 'queued', 'post_processing'].includes(task.status)) {
      return false
    }
    
    taskId.value = task.task_id
    status.value = 'connecting'
    
    // Try SSE reconnection first
    streamHandle = subscribeTaskStream(task.task_id, {
      onEvent: (event, data) => {
        status.value = 'streaming'
        // Track Last-Event-ID for subsequent reconnects
        // (SSE spec: id field in event frame)
        options.onStreamEvent?.(event, data)
      },
      onGap: () => {
        // Buffer overflow — fallback to polling
        status.value = 'polling'
      },
      onEnd: () => {
        // Stream ended — task likely completed
        // useTaskPolling will pick up the terminal state
      },
      onError: () => {
        // SSE failed — fallback to polling
        status.value = 'polling'
      },
    }, {
      lastEventId: lastEventId.value || undefined,
    })
    
    return true
  }
  
  function cleanup() {
    streamHandle?.abort()
    streamHandle = null
    cancelPolling()
  }
  
  return { taskId, status, resume, cleanup }
}
```

### 2.3 各 stream 函数增强

每个 stream 函数（`streamNarrative`、`getFinanceCoach` 等）需要支持一个可选的 `subscribeOnly` 模式：

```typescript
// 现有：trigger + stream
streamNarrative(callbacks) → POST /dashboard/narrative → SSE

// 新增：subscribe-only（不 trigger）
subscribeTaskStream(taskId, callbacks) → GET /tasks/{id}/stream → SSE
```

前端各 consumer 不需要改 `streamNarrative` 等函数，而是用 `subscribeTaskStream` 作为**重连专用路径**。

---

## Phase 3: Consumer Resume 逻辑统一

### 3.1 改造 4 个 consumer 组件

每个 consumer 从 inline `resumeIfRunning()` 迁移到 `useTaskResume`：

#### DashboardNarrativeCard.vue

```diff
- async function resumeIfRunning() {
-   const task = await getAITask('narrative')
-   if (task.task_id && ['running', 'queued', 'post_processing'].includes(task.status)) {
-     narrativeTaskId.value = task.task_id
-     return true
-   }
-   ...
- }

+ const { taskId: narrativeTaskId, status: resumeStatus, resume, cleanup } = useTaskResume('narrative', {
+   onStreamEvent: (event, data) => {
+     // Route events to the same handlers as triggerStream
+     if (event === 'custom' && data.type === 'reasoning_delta') {
+       thinking.value += data.content
+     } else if (event === 'messages') {
+       narrative.value = (narrative.value || '') + data.content
+     } else if (event === 'custom' && data.type === 'dashboard_narrative.result') {
+       narrative.value = data.narrative
+     }
+   },
+   onComplete: async () => {
+     narrativeTaskId.value = null
+     streaming.value = false
+     await loadCached()
+   },
+   onError: (task) => {
+     narrativeTaskId.value = null
+     streaming.value = false
+     showToast(task.error_message || t('dashboard.narrative.error.generation_failed'))
+   },
+ })

  onActivated(async () => {
-   const resumed = await resumeIfRunning()
+   const resumed = await resume()
    if (!resumed) await loadCached()
  })

  onUnmounted(() => {
+   cleanup()
    // ... existing cleanup
  })
```

#### FinanceCoachCard.vue — 同上模式
#### LiteracyReportPage.vue — 同上模式
#### AIReportPage.vue + AIHubPage.vue — 同上模式

> **Report 特殊性：** Report 使用 `useReportStream`（含 3-step timeline），前端交互不变。
> 后端 Report 管道未来会重构为 conversation loop（agent 输出 JSON → backend 校验/修复 → 不通过则重试），
> 但那是独立的 plan（见 §后续规划）。本 plan 中 Report 只改 resume 机制，不改管道。

```diff
  # AIReportPage.onMounted:
- task = await getAITask('report')
- if task running → stream.startPolling()  # 30s long-poll
+ const { resume, cleanup } = useTaskResume('report', {
+   onStreamEvent: (event, data) => {
+     // Route to useReportStream's event handlers (timeline updates)
+     stream.handleReconnectEvent(event, data)
+   },
+   onComplete: () => loadExistingReport(),
+ })
+ await resume()
```

### 3.2 useTaskPolling 的角色变化

Phase 3 后，`useTaskPolling` 从 **主恢复机制** 变为 **SSE 的 fallback**：

```
resume() 被调用
  ├─ 成功找到 running task
  │   ├─ 尝试 SSE → 成功 → 实时流式
  │   ├─ SSE gap → fallback 到 useTaskPolling
  │   └─ SSE error → fallback 到 useTaskPolling
  └─ 无 running task → idle
```

---

## Phase 4A: Backend 双模式事件分发（机制 C）— ⏸ Deferred 到 Batch 2

> **Review 后 defer**：subscriber_aware 优化收益可忽略（bridge buffer 由 agent 始终填充，"跳过" 只省 json.dumps CPU，自托管单实例无扩展压力）。Phase 1-3 SSE 重连不依赖 Phase 4A。
> 
> 如果后续需要多实例扩展或大规模并发，可再引入 SubscriberRegistry。

### 4.1 Subscriber-Aware Bridge Consumer

**核心改动：** `bridge_consumer.py` 增加 subscriber 感知逻辑。

```python
async def consume_task_stream(
    task_id: str,
    family_id: int,
    last_event_id: str | None = None,
    run_id: str | None = None,
    subscriber_aware: bool = False,  # NEW: mechanism C
) -> AsyncIterator[str]:
    """
    When subscriber_aware=True:
    - If no frontend subscriber is actively reading, skip intermediate events
    - Only persist the final result (on 'end' or result event)
    
    When subscriber_aware=False (default, backward compatible):
    - All events are forwarded as SSE (current behavior)
    """
```

### 4.2 实现方式：Backend 内部 subscriber 注册表

```python
# In bridge_consumer.py or a new subscriber_registry.py

class SubscriberRegistry:
    """Track active SSE subscribers per task_id."""
    
    def __init__(self):
        self._subscribers: dict[str, int] = {}  # task_id → active count
    
    def register(self, task_id: str):
        self._subscribers[task_id] = self._subscribers.get(task_id, 0) + 1
    
    def unregister(self, task_id: str):
        count = self._subscribers.get(task_id, 0)
        if count > 0:
            self._subscribers[task_id] = count - 1
    
    def has_subscriber(self, task_id: str) -> bool:
        return self._subscribers.get(task_id, 0) > 0

_registry = SubscriberRegistry()
```

在 trigger 端点（`POST /dashboard/narrative` 等）调用 `consume_task_stream` 时：
- 注册 subscriber（前端正在听）
- `subscriber_aware=True` → 正常转发所有事件

在 subscribe-only 端点（`GET /tasks/{id}/stream`）调用时：
- 注册 subscriber
- 从 Last-Event-ID 开始转发

在 trigger 端点但**前端立即断开**时：
- Subscriber count 降为 0
- `consume_task_stream` 检测到 `has_subscriber(task_id) == False`
- 跳过中间事件的 SSE 格式化，只监听 `end` sentinel 做 `complete_task()`
- 最终结果由 agent 侧的持久化逻辑写入（已有机制：agent 在 custom event 中写 scenario result cache）

### 4.3 Agent 侧无需改动

机制 C 的关键：**Agent 的 `bridge.publish()` 调用完全不变**。

Agent 始终 publish 所有事件到 bridge buffer。Backend 决定是否转发给前端：

```
Agent bridge.publish(event) → 始终执行
                               ↓
Backend consume_task_stream:
  has_subscriber? 
    YES → yield SSE event to frontend
    NO  → skip yield, just track end sentinel
```

### 4.4 纯后台任务的优化路径

当 trigger 端点被调用但**没有前端等待**时（例如 scheduler_worker 触发的定时报告）：

```python
# In the trigger endpoint:
async def trigger_narrative(...):
    task = AITaskService.trigger_narrative(...)
    
    # Check if there's an active subscriber (frontend waiting for SSE)
    has_subscriber = _registry.has_subscriber(task.id)
    
    if has_subscriber:
        # Interactive mode: stream events to frontend
        return StreamingResponse(
            consume_task_stream(task.id, family_id, subscriber_aware=True),
            media_type="text/event-stream",
        )
    else:
        # Background mode: fire-and-forget, no SSE
        # Task runs, agent publishes to bridge, backend skips forwarding
        # complete_task() is called when end sentinel is received
        return JSONResponse({"task_id": task.id, "status": "queued"})
```

**问题：** trigger 端点总是有前端在听（是前端调的 POST）。后台任务由 scheduler_worker 触发，走的是不同路径。

**实际场景分解：**

| 触发者 | 有前端在听？ | 走什么路径 |
|--------|------------|----------|
| 用户在前端点击"生成" | ✅ | POST → SSE stream（现有） |
| scheduler_worker 定时触发 | ❌ | internal API → 直接跑，不 return SSE |
| 用户触发后切走页面 | 先 ✅ 后 ❌ | POST → SSE → 前端 abort → backend 检测到 subscriber=0 → 跳过后续转发 |

第三种场景是机制 C 的核心优化点：用户切走后，backend 停止无意义的 SSE 格式化，但 agent 继续执行。

---

## Phase 4B: Report 管道重构 — JSON 校验 + Conversation Loop — ⏸ Deferred 到 Batch 2

> **Review 后调整**：
> - JSON 校验 + retry 从 backend 移到 **agent 侧** asset-report pipeline（F2+F5 修复）
> - 与 "agent is pure harness" 一致：agent 管 LLM 对话质量，backend 只存结果
> - 移到 Batch 2 因为需要先设计 agent 侧 conversation turn 接口

### 4B.1 目标（调整后）

将 Report JSON 校验 + conversation retry 放在 **agent 侧** asset-report pipeline 内部。Backend 只负责存储最终校验通过的结果。

**前端交互不变**：3-step timeline、thinking、tool calls 展示保持原样。

### 4B.2 数据流（调整后 — agent 侧闭环）

```
Agent (asset-report pipeline)
  │
  ├─ 流式输出（thinking, tool calls, markdown）→ bridge.publish() → SSE 实时展示
  │
  └─ 同时受 prompt 约束输出结构化 JSON（在 final custom event 中）
       │
       ▼
  Agent 内部（新增校验环节）
    ├─ 解析 JSON
    ├─ Schema 校验（pydantic model）
    ├─ 不通过 → jsonrepair 尝试修复
    │   ├─ 修复成功 → bridge.publish(result event)
    │   └─ 修复失败 → 新增 conversation turn（LLM 重新生成）
    │       └─ 最多 3 次 retry，之后 publish error event
    └─ 通过 → bridge.publish(result event)
       │
       ▼
Backend 只负责：
  - 接收 result event → 存入 family_reports
  - 接收 end sentinel → complete_task()
  - 不做 JSON 校验
```

### 4B.3 实现方式（调整后 — agent 侧）

**Agent 侧（Batch 2）：**
- asset-report pipeline 增加 JSON 校验环节（在现有 3-step 输出的最后一步后）
- pydantic schema 定义 + jsonrepair 修复（agent 依赖）
- Conversation loop：校验失败后，在 agent 内部发起新的 LLM conversation turn
- 最多 3 次 retry，之后 publish error event

**Backend 侧：**
- 无新增代码（backend 只存 result，不校验）
- ~~`report_validator.py`~~ 不再需要

**`jsonrepair` 依赖：**
- Agent 侧 `uv add jsonrepair`（而非 backend）

### 4B.4 与 SSE 重连的交互

Report 的 SSE 重连和 coach/narrative/literacy 走**完全相同**的 `useTaskResume` 路径。
区别仅在于后端多了 JSON 校验层，对前端透明。

### 4B.5 错误处理

| 场景 | 处理 |
|------|------|
| JSON 首次通过 | 正常存储 + complete |
| JSON 首次不通过，jsonrepair 修复 | 修复后存储 + complete |
| JSON 不通过，retry 1-2 次后通过 | 正常存储 + complete |
| JSON 3 次 retry 仍不通过 | fail_task + error_message="报告结构化输出校验失败" |
| Retry 过程中 agent 超时 | fail_task + error_message="报告生成超时" |

---

## Phase 5: 加固（v2 遗留事项纳入）

> 从 v2 plan 的延后/遗留事项中提取与 v3 高度相关的项目，一并加固。
> 经代码核实，v2 的 double-complete（#3）和 Narrative TTL 缓存（#4）已实现，无需重复。

### 5.1 周期性孤儿任务检测（v2 KTD-7 遗留 — 确认未实现）

**核实结果：** 基础设施就绪（`get_stale_running_tasks()` + `interrupt_task(lease_guard=True)`），但**零调用方**。无定时器、无 background loop。

**实现：**
- `server/apps/backend/app/services/orphan_detector.py`
- 每 120s 扫描 `AITask.status IN ('running','post_processing') AND lease_expires_at < now()`
- 调用已有 `interrupt_task(lease_guard=True)` 标记孤儿为 `interrupted`
- 注册为 FastAPI lifespan 后台任务（`asyncio.create_task`）

**文件：** `server/apps/backend/app/services/orphan_detector.py` + `app/main.py` lifespan 注册

### 5.2 熔断器补全（v2 U14/U15 Phase 2 follow-up — 确认未实现）

**核实结果：** 熔断器框架完整（`services/circuit_breaker/`），Coach/Report/ASR 已接入，但 Literacy 和 Narrative 路由**零引用** `circuit_breaker`。

**实现：**
- 为 `ai_literacy_report.py` 和 `dashboard.py`（narrative 部分）添加 `check_circuit_blocked()` 门控
- 复用已有适配器模式（参考 `ai_finance_coach.py` 和 `ai_report.py` 的实现）
- 配置：与 Coach/Report 对齐的失败阈值和恢复窗口

**文件：** `ai_literacy_report.py`、`dashboard.py` 路由层

### 5.3 Run Duration 记录（v2 DeerFlow alignment — 确认未实现）

**核实结果：** AITask 有 `started_at` + `completed_at`，但无人计算 diff 存储 duration。

**实现：**
- `AITask.progress` 中新增 `duration_seconds` 字段（progress 是 JSON 字段，无需 schema migration）
- 在 `complete_task()` / `fail_task()` 时计算 `completed_at - started_at` 并写入 progress
- 前端不消费此字段（后续 analytics 使用）

**文件：** `ai_task_service.py`

### 5.4 生产 bug 修复：404 轮询风暴 + 页面级轮询生命周期

> 来源：测试中发现 task detail 404 导致所有页面反复提示"资源不存在"。
> 根因：`useTaskPolling.pollOnce()` 的 catch 不区分 HTTP status code，404 被当作瞬态网络错误继续轮询。

**问题 1：离开页面仍轮询**

当前 `useTaskPolling` 在 `onUnmounted` 才 stop，但 KeepAlive 缓存的页面（Dashboard、AIHub）
`onUnmounted` 不触发 — 只有 `onDeactivated` 触发。导致用户切走后轮询继续。

**修复：**
- `useTaskPolling` 增加 `onDeactivated` 暂停 + `onActivated` 恢复
- 或者：`useTaskResume` 在 `cleanup()` 中显式调用 `stop()`（Phase 2 已设计）
- 确保 KeepAlive 场景下 `onDeactivated` → 暂停轮询，`onActivated` → 恢复轮询

**问题 2：404 应静默停止轮询**

**修复：**
```typescript
// useTaskPolling.ts pollOnce() catch 块
catch (err) {
  if (disposed) return
  const status = (err as any)?.response?.status
  if (status === 404) {
    // Task not found — stop polling silently (data anomaly or backend cleanup)
    status.value = 'failed'
    errorMessage.value = ''  // 静默，不 toast
    clearTimer()
    return
  }
  // Other errors (500, network) — keep polling, just log
  console.warn('[useTaskPolling] poll error:', err)
}
```

**问题 3：回到场景页才查询 + 接续最新进展**

已由 Phase 2-3 的 `useTaskResume` 设计覆盖：
- `onActivated` → `resume()` → `getAITask(capability)` → 有 running task → SSE 重连
- 无需额外改动

**问题 4：瞬时 404（任务尚未创建完成）→ 重试按钮**

当前 trigger 后 500ms 就查 task（`setTimeout(async () => getAITask(...), 500)`），
如果 backend 创建 AITask 慢（agent 启动延迟），可能返回空/404。

**修复：**
- trigger 后改为 **渐进式重试**：500ms → 1s → 2s → 4s（exponential backoff，最多 4 次）
- 如果所有重试都失败 → 显示重试按钮（不 toast 错误）
- 用户点重试按钮 → 先查旧 task_id 状态（如果存在且 running/completed → 复用）
- 旧 task 确实异常 → 触发新的 trigger

**代码位置：** `useTaskResume.ts` + 各 consumer 的 trigger 逻辑

**文件：** `useTaskPolling.ts`（404 静默）、`useTaskResume.ts`（生命周期 + 渐进重试）、各 consumer（retry button）

| 事项 | 状态 | 说明 |
|------|------|------|
| Report double-complete 清理 | ✅ 已解决 | `complete_task()` 已有 `if task.status in (...)` 幂等保护 |
| Narrative TTL 缓存 | ✅ 已实现 | `SKILL_TTL = timedelta(hours=4)` + `is_cache_fresh()` 检查 + config 可调 |

---

## 实施计划

### Batch 1 任务分解（首期 ship）

| # | 任务 | Phase | 文件 | 估时 |
|---|------|-------|------|------|
| T0 | **complete_task 生命周期解耦 + result 持久化 + exception 泄露修复** | Pre-0 | `bridge_consumer.py`, 4 个 router | 2h |
| T1 | Backend subscribe-only 端点 | 1 | `ai_tasks.py` | 2h |
| T2 | `_emit_scenario_result` + scenario result loader（含 F10 细化） | 1 | `ai_tasks.py` | 1.5h |
| T3 | Backend 单元测试（Phase 1） | 1 | `tests/backend/test_ai_tasks_stream.py` | 1.5h |
| T4 | Frontend `subscribeTaskStream()` API | 2 | `api/ai-tasks.ts` | 1h |
| T5 | `useTaskResume` composable 改造（含 F8 getAITask 修复） | 2 | `composables/useTaskResume.ts` | 2h |
| T6 | DashboardNarrativeCard 接入 useTaskResume | 3 | `DashboardNarrativeCard.vue` | 1h |
| T7 | FinanceCoachCard 接入 useTaskResume | 3 | `FinanceCoachCard.vue` | 1h |
| T8 | LiteracyReportPage 接入 useTaskResume | 3 | `LiteracyReportPage.vue` | 1h |
| T9 | AIReportPage + AIHubPage 接入 | 3 | `AIReportPage.vue`, `AIHubPage.vue` | 2h |
| T18 | 404 静默停止轮询 | 5.4 | `useTaskPolling.ts` | 0.5h |
| T19 | KeepAlive 生命周期暂停/恢复轮询 | 5.4 | `useTaskPolling.ts`, `useTaskResume.ts` | 1h |
| T20 | Trigger 后渐进重试 + retry 按钮 | 5.4 | `useTaskResume.ts`, 各 consumer | 1.5h |
| T7b | SSE 端点并发连接上限（F7） | 1 | `ai_tasks.py` | 0.5h |
| T21 | 集成测试 + 手动验证（Batch 1） | all | — | 2h |

**Batch 1 总计：~20.5h（约 3 个工作日）**

### Batch 2 任务分解（后续）

| # | 任务 | Phase | 文件 | 估时 |
|---|------|-------|------|------|
| T10 | SubscriberRegistry + subscriber-aware consume（F6 re-eval） | 4A | `bridge_consumer.py`, `subscriber_registry.py` | 2h |
| T11 | Trigger 端点 subscriber-aware 模式 | 4A | 4 个 router 文件 | 2h |
| T12b | Report JSON 校验（agent 侧） | 4B | `agent/services/report/` | 2h |
| T13b | Report conversation retry loop（agent 侧） | 4B | `agent/services/runtime/worker.py` | 3h |
| T14b | `jsonrepair` 依赖 + 集成（agent 侧） | 4B | `agent/pyproject.toml` | 0.5h |
| T15 | 周期性孤儿检测 | 5.1 | `orphan_detector.py`, `app/main.py` | 1.5h |
| T16 | Literacy + Narrative 熔断器 | 5.2 | `ai_literacy_report.py`, `dashboard.py` | 1.5h |
| T17 | Run duration 记录（F13: defer, 可从 started_at+completed_at 计算） | 5.3 | — | 0h (skip) |
| T22 | 集成测试 + 手动验证（Batch 2） | all | — | 1.5h |

**Batch 2 总计：~14h（约 2 个工作日）**

### 实施顺序

```
Batch 1: Pre-0 (T0) → Phase 1 (T1-T3, T7b) → Phase 2 (T4-T5) → Phase 3 (T6-T9) → Phase 5.4 (T18-T20) → T21
              ↑ 生命周期修复       ↑ 后端+安全          ↑ 前端独立         ↑ 联调              ↑ 404修复    ↑ 验证

Batch 2: Phase 4A (T10-T11) → Phase 4B agent-side (T12b-T14b) → Phase 5.1-5.2 (T15-T16) → T22
              ↑ 机制C优化             ↑ 报告质量                 ↑ 加固
```

### 验证计划

**Batch 1 验证：**

| 验证项 | 方法 | 预期 |
|--------|------|------|
| **F1 修复：complete_task 解耦** | 触发任务 → SSE 期间断开连接 → 检查 DB | 任务最终 completed（不卡在 running） |
| **F4 修复：result 持久化** | 触发 narrative → 断开 SSE → 检查 skill cache | result 已持久化 |
| **F12 修复：exception 泄露** | 触发错误场景 → 检查 SSE error event | 无内部路径/连接串泄露 |
| Subscribe-only 端点 | `curl GET /tasks/{id}/stream` | 收到 SSE 事件流 |
| **F7 修复：并发连接上限** | 同一 family 开 4 个 SSE 连接 | 第 4 个返回 429 |
| Last-Event-ID replay | 断开后用 last_event_id 重连 | 从断点恢复，无重复 |
| StreamGap 处理 | 超过 256 事件后重连 | 收到 `event: gap` |
| 前端 SSE 重连 | Dashboard 触发 coach → 切页 → 回来 | 立即看到流式输出 |
| Fallback to polling | 模拟 gap | 自动降级到 2s 轮询 |
| 404 静默 | 手动删除 AITask → 观察前端 | 轮询停止，无 toast，无错误提示 |
| KeepAlive 暂停 | 触发任务 → 切到其他 tab → 检查 network | 无轮询请求 |
| 渐进重试 | Mock backend 延迟创建 AITask → 触发 | 500ms→1s→2s→4s 重试，最终显示 retry 按钮 |
| Retry 按钮复用 | 旧 task 仍在 running → 点 retry | 复用旧 task，不创建新任务 |

**Batch 2 验证：**

| 验证项 | 方法 | 预期 |
|--------|------|------|
| 机制 C subscriber 感知 | 触发后切走 → 检查 backend 日志 | subscriber=0 后停止 SSE 转发 |
| Report JSON 校验（agent 侧） | 触发报告生成 → 检查结构化输出 | JSON 通过校验存入 family_reports |
| Report retry loop | 模拟 JSON 不合法（mock 输出坏 JSON） | 最多 3 次 retry 后 fail |
| 孤儿检测 | 手动设置 lease_expires_at 过期 → 等待 120s | 任务标记 timeout |
| 熔断器 | 连续 3 次 agent 调用失败 | 熔断器打开，快速返回错误 |
| double-complete 幂等 | 并发触发 complete_task | 只有一次实际执行 |

---

## 风险与缓解

| 风险 | 概率 | 影响 | 缓解 |
|------|------|------|------|
| **Bridge buffer 溢出（>256 事件）** — adversarial F-5 | 中 | 中 | StreamGap → 前端 fallback 到 polling + reload cached。**待 Batch 2 前验证生产事件数**（XLEN 查询） |
| Memory 模式进程重启丢 buffer | 低 | 中 | Redis 模式用于生产；memory 模式仅 dev |
| Subscribe-only 端点被滥用 | 低 | 低 | ~~自托管连接数少~~ → **F7 修复：per-family 并发上限 3** |
| useTaskResume 改造引入回归 | 中 | 中 | 保留 useTaskPolling 作为 fallback；渐进式迁移 |
| ~~Phase 4A subscriber 注册表竞态~~ | — | — | **Phase 4A deferred 到 Batch 2** |
| ~~jsonrepair 修复错误结构~~ | — | — | **移到 agent 侧（Batch 2），与 LLM conversation 闭环** |
| ~~Report retry loop 死循环~~ | — | — | **agent 侧硬上限 3 次 + error event** |
| 孤儿检测误杀（agent 慢但健康） | 低 | 中 | lease_expires_at 由 heartbeat 续期；只有真正无响应的才超时 |
| 404 误判（真瞬态 vs 真异常） | 中 | 中 | 渐进重试（500ms→4s）覆盖创建延迟；retry 按钮先查旧 task 再决定 |
| KeepAlive onDeactivated 未触发 | 低 | 低 | useTaskResume.cleanup() 兜底 stop |
| **Pre-existing: SSE 断连后 complete_task 不执行** — adversarial F1 | 高 | 高 | **Pre-Batch 0 修复：complete_task 移到独立 asyncio.Task** |
| **Pre-existing: result 持久化在 SSE 断连后丢失** — feasibility F4 | 高 | 高 | **Pre-Batch 0 修复：result 持久化移到独立消费者** |
| **Pre-existing: bridge_consumer 泄露 raw exception** — security F12 | 中 | 中 | **Pre-Batch 0 修复：映射为 user-safe 消息** |

---

## 关联文档

- [[ai-task-resilience-v2-fully-landed]] — v2 整体落地状态
- [[ai-task-resilience-polling-perf-deferred]] — S4 轮询性能分析（本次 Phase 4A 解决）
- Plan: `docs/plans/2026-08-15-002-feat-ai-task-resilience-v2-full-coverage-plan.md`
- Bridge consumer: `server/apps/backend/app/services/bridge_consumer.py`
- StreamBridge: `server/packages/db/stream_bridge/`
- Circuit breaker: `server/apps/backend/app/services/circuit_breaker.py`

---

## Review Findings (ce-doc-review, 2026-08-17)

6 personas reviewed this plan. Findings applied:

| ID | 来源 | 严重度 | 问题 | 处理 | 决策 |
|----|------|--------|------|------|------|
| F1 | adversarial+feasibility+security | P0 | complete_task() 在 SSE generator 内，断连后不执行（pre-existing bug） | **Apply** | D14 |
| F2 | adversarial+feasibility | P0 | Phase 4B conversation retry 无 backend→agent 通信路径 | **Apply** | D17 (移到 agent 侧) |
| F3 | product-lens | P1 | 两个目标 bundle + 404 bug fix 排最后 | **Apply** | D15 (分批交付) |
| F4 | feasibility | P1 | Result 持久化在 SSE 断连后丢失 | **Apply** | D14 (与 F1 合并) |
| F5 | adversarial | P1 | Phase 4B 与 "agent as pure harness" 矛盾 | **Apply** | D17 (移到 agent 侧) |
| F6 | adversarial+product-lens | P1 | Phase 4A subscriber_aware 优化收益可忽略 | **Defer** | D16 |
| F7 | security | P1 | SSE 端点无并发连接上限 | **Apply** | D18 |
| F8 | feasibility | P1 | getAITask() 不存在 | **Apply** | plan 修正 |
| F9 | adversarial | P2 | "跳过中间事件 buffer" 术语错误 | **Apply** | plan 修正 |
| F10 | feasibility | P2 | _load_scenario_result 缺具体实现 | **Apply** | plan 细化 |
| F11 | feasibility | P2 | Result 持久化职责不明确 | **Apply** | 与 F4 合并 |
| F12 | security | P2 | bridge_consumer 泄露 raw exception | **Apply** | Pre-Batch 0 修复 |
| F13 | product-lens | P2 | Run duration 无消费者 | **Defer** | D19 |

**Residual risks from review:**
- 256-event buffer 未验证生产事件数 — Batch 2 前需 XLEN 查询
- SubscriberRegistry 单进程约束 — Batch 2 实现时需文档化
- Bridge buffer 含敏感财务数据 (Redis plaintext) — 已有风险，plan 未引入新风险

---

## 决策记录

| # | 决策 | 理由 | 否决方案 |
|---|------|------|---------|
| D1 | 机制 C（agent 无感知） | Agent 最纯粹，零额外逻辑 | A: backend 在 trigger 时告知; B: agent 每轮查 subscriber count |
| D2 | Backend 中转（不直连 agent） | 安全 + tenant 隔离 + 持久化 | 前端直连 agent SSE |
| D3 | GET /tasks/{id}/stream 独立端点 | 幂等、不触发新任务、复用 bridge_consumer | 复用 POST trigger 端点 |
| D4 | useTaskPolling 作为 SSE 的 fallback | 保留现有稳定性，渐进迁移 | 直接替换 useTaskPolling |
| D5 | Phase 4A+4B+5 全部首期 | Agent 纯 harness 化是架构目标；v2 遗留加固趁此机会一并清理 | 分批交付（增加 PR 数量和 review 成本） |
| D6 | Report JSON 校验用 jsonrepair | 轻量、专注、开源成熟 | 自己写修复逻辑（维护成本高） |
| D7 | Scenario result 命名（非 skill cache） | skill = agent 侧 skill.md 技能设定 | 沿用 skill_results 命名 |
| D8 | 孤儿检测间隔 120s | 与 lease_expires_at 默认值对齐 | 60s（太频繁）/ 300s（太慢） |
| D9 | Report retry 上限 3 次 | 平衡质量和延迟 | 无限 retry（用户等太久）/ 1 次（容错太低） |
| D10 | double-complete 和 Narrative TTL 不重复实现 | 代码核实已实现（幂等保护 + 4h TTL） | 重新实现（冗余） |
| D11 | 404 静默停止（不 toast） | 404 = 数据异常，用户无法修复，toast 无意义 | 404 显示 toast（用户困惑） |
| D12 | 渐进重试 500ms→1s→2s→4s（最多 4 次） | 覆盖 agent 启动延迟，总等待 ~8s 可接受 | 固定 500ms 单次查（太短）/ 立即重试（浪费请求） |
| D13 | Retry 按钮先查旧 task 再决定 | 避免不必要的 retrigger（旧 task 可能仍在跑） | 直接 retrigger（浪费资源 + 可能重复生成） |
| **D14** | **complete_task() 移到独立 asyncio.Task（F1 修复）** | ASGI 取消 SSE generator 后 complete_task 不执行是 pre-existing bug | 保留在 generator 内（依赖客户端不断连） |
| **D15** | **分批交付：Batch 1 (SSE+bugfix) + Batch 2 (架构优化)（F3 修复）** | SSE 重连是用户可感知的 UX 提升，应优先 ship；机制 C + JSON pipeline 是架构投资 | 全部首期交付（增加一次性 review 成本但降低风险） |
| **D16** | **Phase 4A subscriber_aware 优化 defer 到 Batch 2（F6 修复）** | bridge buffer 由 agent 始终填充，"跳过" 只省 json.dumps CPU；自托管单实例无扩展压力 | 首期实现 SubscriberRegistry（4h 换来零实际节省） |
| **D17** | **Report JSON 校验移到 agent 侧（F2+F5 修复）** | 与 "agent is pure harness" 一致；避免 backend↔agent 跨模块通信（当前架构无此通道） | Backend 侧 report_validator.py（需引入不存在的反向通信路径） |
| **D18** | **SSE 端点加 per-family 并发上限 3（F7 修复）** | 防止单用户耗尽 uvicorn 连接池（DoS 向量） | 无上限（自托管场景连接数少） |
| **D19** | **Run duration 不预存（F13 修复）** | 可从 started_at + completed_at 实时计算，无当前消费者 | 预存到 AITask.progress（为未来 analytics 准备） |
