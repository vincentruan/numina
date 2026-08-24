---
artifact_contract: ce-unified-plan/v1
artifact_readiness: implementation-ready
product_contract_source: ce-plan-bootstrap
execution: code
---

# 修复 AI 资产报告生成：事件流 + 任务生命周期 + 错误处理

## Summary

修复 AI 资产报告生成的三个根因：(1) 报告 JSON 验证失败后 pipeline 标记 error 但 lifecycle consumer 仍调用 `complete_task`；(2) 错误事件未通过 bridge 传递到前端；(3) Redis 未启用导致跨进程事件传递依赖缺失。在保持 DeerFlow pipeline 架构和 backend-owned buffer 原则下修复。

## Goal Capsule

**Objective:** 确保 AI 资产报告生成在所有路径下正确处理——成功时持久化报告并通过 SSE 通知前端，失败时 AITask 标记为 failed 且前端显示错误信息。用户无论怎样操作页面（刷新、离开、退出），回来都能看到正确的最终状态。

---

## 根因调查结论

### 根因 1：lifecycle consumer 不区分成功/失败

**现象**：`ai_reports` 表为空，但 `AITask.status=completed`

**证据链**：
1. Agent pipeline 执行 LLM 生成报告 JSON
2. JSON 验证失败 → 重试 3 次仍失败
3. `worker.py:730` — `p.set_error("报告结构化输出校验失败")` 被调用
4. `RunPipeline.__aexit__` — `end_payload = {"status": "error"}` 发布到 bridge
5. `bridge.publish_end()` 发布 end marker
6. Backend lifecycle consumer 收到 END_SENTINEL → **无条件调用 `complete_task()`**
7. AITask 被标记为 completed，但无报告数据

**缺陷位置**：`bridge_consumer.py:190-191` — `elif event_type == "end": AITaskService.complete_task(task_id, db)` 不检查 end payload 中的 status。

### 根因 2：error 事件未通过 bridge 传递

**现象**：前端 SSE 流只显示心跳，从未收到 error 事件

**证据链**：
1. `worker.py:721-733` — 验证失败后调用 `p.set_error()` 但**未向 bridge 发布 error 事件**
2. `RunPipeline.__aexit__` 发布 `end` 事件（payload 含 `status: "error"`）
3. Redis bridge 将 end entry 转为 `END_SENTINEL`（无 payload 数据）
4. `consume_task_stream` 收到 END_SENTINEL → yield `event: end\ndata: null`
5. 前端收到 `end` → 尝试加载报告 → 无报告 → 显示加载状态

**缺陷位置**：
- `worker.py:721-733` — 缺少 `bridge.publish(run_id, "error", {...})`
- `redis.py:140-141` — END_SENTINEL 丢弃了 end payload 数据

### 根因 3：Redis 未启用（已修复）

**现象**：agent 和 backend 各自独立的 in-memory bridge 无法共享事件

**已修复**：commit `1508ee1e` — 启用 Redis service + `STREAM_BRIDGE_TYPE=redis`

---

## 验收条件

### AC1：报告生成成功路径

1. 触发报告生成 → 前端显示进度（step 1/2/3）
2. Agent 完成 → 报告 JSON 写入 `ai_reports` 表
3. AITask 状态 → `completed`
4. 前端收到 SSE `end` 事件 → 加载并显示完整报告
5. 用户离开页面再返回 → 直接显示已完成报告

### AC2：报告生成失败路径（JSON 验证失败）

1. 触发报告生成 → 前端显示进度
2. LLM 输出无效 JSON → 重试 3 次 → 仍失败
3. Agent bridge 发布 `error` 事件（含错误信息）
4. AITask 状态 → `failed`（非 completed）
5. 前端收到 SSE `error` 事件 → 显示"报告生成失败"提示
6. 前端显示重试按钮
7. 用户离开页面再返回 → 显示失败状态 + 重试按钮

### AC3：报告生成失败路径（persist 失败）

1. 报告 JSON 验证通过
2. `persist_report_result` 调用失败
3. Agent bridge 发布 `error` 事件
4. AITask 状态 → `failed`
5. 前端显示错误提示 + 重试按钮

### AC4：页面离开/返回（任务进行中）

1. 触发报告生成
2. 切换到其他页面
3. Agent 继续执行，事件写入 Redis
4. 返回报告页面
5. 前端通过 `useTaskResume` 重连 SSE
6. 从断点继续流式输出

### AC5：页面离开/返回（任务已完成）

1. 报告生成完成
2. 用户离开页面
3. 返回报告页面
4. 前端查询 AITask → `completed`
5. 直接加载报告数据展示

### AC6：页面离开/返回（任务失败）

1. 报告生成失败（JSON 验证或 persist 失败）
2. 用户离开页面
3. 返回报告页面
4. 前端查询 AITask → `failed`
5. 显示错误信息 + 重试按钮

---

## 修复方案

### 架构约束

- **DeerFlow pipeline 模式**：`RunPipeline.__aenter__/__aexit__` 管理生命周期，`bridge.publish()` 发布事件
- **Backend-owned buffer**：Redis bridge 是事件传递的中间层，backend 持有缓存
- **不改变 pipeline 结构**：修复在现有框架内进行，不引入新的执行路径

### 数据流（修复后）

```
Agent Pipeline                    Redis Stream               Backend Consumers
───────────────                   ────────────               ─────────────────
bridge.publish("custom", step1) → XADD event →              SSE consumer → 前端 (step 1)
bridge.publish("custom", step2) → XADD event →              SSE consumer → 前端 (step 2)
bridge.publish("error", {...])  → XADD event →              SSE consumer → 前端 (error msg)
                                   ↑ 新增                      
bridge.publish_end()            → XADD end   →              lifecycle consumer → 检查 DB
                                                               ├── report 存在 → complete_task
                                                               └── report 不存在 → fail_task
                                                             SSE consumer → 检查 AITask status
                                                               ├── completed → yield end
                                                               └── failed → yield error + end
```

---

## Implementation Units

### U1. Agent pipeline 发布 error 事件到 bridge

**Goal:** 报告验证失败或 persist 失败时，显式发布 error 事件到 bridge，确保前端能收到错误信息。

**Files:**
- `server/apps/agent/services/runtime/worker.py` — 修改 `_run_asset_report_pipeline`

**Approach:**

在 `worker.py:721-733`（JSON 验证失败路径）添加 bridge error 事件发布：

```
if validation_errors:
    # 现有代码: p.set_error(...)
    # 新增: 发布 error 事件到 bridge
    await bridge.publish(p.run_id, "error", {
        "error": "报告结构化输出校验失败，请重试",
        "error_type": "ReportValidationError",
    })
```

在 `worker.py:769-785`（persist 失败路径）同样添加：

```
except Exception as persist_exc:
    # 现有代码: p.set_error(...)
    # 新增: 发布 error 事件到 bridge
    await bridge.publish(p.run_id, "error", {
        "error": "报告保存失败，请重试",
        "error_type": type(persist_exc).__name__,
    })
```

**Patterns to follow:**
- `worker.py:1007` — 已有的 `bridge.publish(run_id, "custom", ...)` 模式
- DeerFlow SSE 协议的 `error` frame 格式

**Test scenarios:**
- JSON 验证失败 → bridge 收到 error 事件（type=ReportValidationError）
- persist 失败 → bridge 收到 error 事件（type=异常类名）
- 正常路径 → 无 error 事件

**Verification:** Agent 单元测试中 mock bridge，验证 error 事件发布。

---

### U2. Lifecycle consumer 验证任务结果

**Goal:** lifecycle consumer 收到 end 事件时，不再无条件调用 `complete_task`。对于 report 任务，验证 `ai_reports` 表中有数据后才 complete，否则 fail。

**Files:**
- `server/apps/backend/app/services/bridge_consumer.py` — 修改 `_spawn_lifecycle_consumer` 内的 `_consume`

**Approach:**

在 `bridge_consumer.py:190-191`（end 事件处理）替换无条件 complete：

```
elif event_type == "end":
    # 验证任务结果是否存在
    if _verify_task_result(task_id, family_id, db):
        AITaskService.complete_task(task_id, db)
    else:
        AITaskService.fail_task(task_id, "任务完成但未生成预期结果", db)
```

新增 `_verify_task_result` 辅助函数：

```
def _verify_task_result(task_id, family_id, db) -> bool:
    """验证任务是否产生了预期结果。"""
    task = AITaskService.get_task_by_id(task_id, family_id, db)
    if not task:
        return False
    # report 任务: 检查 ai_reports 表
    if task.skill_id == "report":
        from apps.backend.app.models.ai_report import AIReport
        return db.query(AIReport).filter(
            AIReport.family_id == int(family_id)
        ).first() is not None
    # 其他任务: 默认认为成功（agent 通过 set_error 控制状态）
    return True
```

**Patterns to follow:**
- `ai_report.py:158-222` — `_watch_report_task_completion` 的 DB 查询模式
- `bridge_consumer.py:191` — 现有的 `complete_task` 调用模式

**Test scenarios:**
- Report 任务 + report 存在 → `complete_task` 被调用
- Report 任务 + report 不存在 → `fail_task` 被调用（message="任务完成但未生成预期结果"）
- 非 report 任务（narrative, coach）→ `complete_task` 被调用（默认行为不变）
- 任务不存在 → `fail_task` 被调用

**Verification:** Backend 单元测试中 mock DB 查询，验证 complete/fail 分支。

---

### U3. SSE consumer 转发 task 最终状态

**Goal:** SSE consumer 收到 end 事件时，检查 AITask 最终状态。如果 failed，发送 error 事件到前端后再发送 end。

**Files:**
- `server/apps/backend/app/services/bridge_consumer.py` — 修改 `consume_task_stream`

**Approach:**

在 `bridge_consumer.py:247-248`（end 事件处理）添加状态检查：

```
elif event_type == "end":
    # 检查 AITask 最终状态
    db = SessionLocal()
    try:
        task = AITaskService.get_task_by_id(task_id, family_id, db)
        if task and task.status == "failed":
            error_msg = task.error_message or "任务执行失败"
            yield f"event: error\ndata: {json.dumps({'error': error_msg})}\n\n"
    finally:
        db.close()
    yield f"event: end\ndata: {json.dumps(None)}\n\n"
    return
```

**Patterns to follow:**
- `bridge_consumer.py:256-258` — 现有的 error 事件 yield 格式
- `ai_report.py:371-376` — error 事件的 SSE 格式

**Test scenarios:**
- AITask completed → yield `event: end`（无 error）
- AITask failed + error_message 存在 → yield `event: error` 然后 `event: end`
- AITask failed + error_message 为空 → yield `event: error`（默认"任务执行失败"）然后 `event: end`
- AITask 不存在 → yield `event: end`

**Verification:** 单元测试 mock AITaskService，验证 error/end 事件序列。

---

### U4. 前端处理 error + end 事件序列

**Goal:** 前端收到 error 事件后记录错误信息，收到 end 事件后显示错误状态（而非加载状态）。

**Files:**
- `frontend/apps/main/src/composables/useReportStream.ts` — 检查 error 事件处理

**Approach:**

检查 `useReportStream.ts` 中 `event === 'error'` 的处理：
- 确认 `status` 被设为 `'error'`
- 确认 `errorMessage` 被设为后端提供的错误信息
- 确认后续的 `end` 事件不会覆盖 error 状态

如果 `end` 事件处理会重置 error 状态，需修改为：当 `status === 'error'` 时，`end` 事件不改变状态。

**Patterns to follow:**
- `useReportStream.ts:442-444` — 现有的 error 事件处理
- `useReportStream.ts:434-436` — end 事件处理

**Test scenarios:**
- 收到 `error` → status=error, errorMessage 设置
- 收到 `error` 然后 `end` → status 保持 error（不被 end 覆盖）
- 收到 `end`（无前置 error）→ 正常加载报告

**Verification:** 前端组件测试，模拟 error + end 事件序列。

---

## Scope Boundaries

### Deferred for later

- 重构架构：Backend-owned EventBuffer + Agent HTTP 推送（见前一版 plan）— 需要更大的重构，当前修复在现有 Redis bridge 架构下进行
- `RunPipeline.__aexit__` 中 END_SENTINEL 携带 payload 数据 — 需要修改 StreamBridge 抽象层
- `_watch_report_task_completion` 轮询逻辑清理 — 当前被 U2 的结果验证替代
- Redis stream cleanup delay 调优（当前 60s 可能过短）

### Out of scope

- DeerFlow harness 修改
- LLM 输出质量改进（prompt engineering）
- 前端 KeepAlive / 页面生命周期管理（已在 commit 134247d2 修复）

---

## Risks & Dependencies

| Risk | Impact | Mitigation |
|------|--------|------------|
| `_verify_task_result` 查询时序 | Report persist 是异步的，可能在 end 事件到达前未完成 | Agent pipeline 在 `publish_end` 前等待 persist 完成（同步 await） |
| 非 report 任务的 result 验证 | 其他任务类型可能有类似问题 | U2 默认返回 True（不改变现有行为），后续按需添加验证 |
| Redis 连接中断 | Lifecycle consumer 无法收到 end 事件 | 已有 Redis 重连机制（bridge_consumer.py:271-284），orphan_detector 120s 兜底 |

---

## Verification Contract

### 本地验证（dev server + demouser）

1. **成功路径**：
   - 启动 dev server
   - 以 demouser 登录
   - 触发 AI 资产报告生成
   - 验证：进度显示 → 报告渲染 → AITask=completed → ai_reports 有数据

2. **失败路径（模拟 JSON 验证失败）**：
   - 通过修改 prompt 或 mock LLM 输出无效 JSON
   - 验证：error 事件显示 → AITask=failed → 前端显示重试按钮

3. **页面离开/返回**：
   - 触发报告生成 → 切换到 dashboard → 等待 → 返回报告页
   - 验证：看到最新进展或已完成结果

4. **页面刷新**：
   - 触发报告生成 → F5 刷新 → 验证自动重连或显示已完成结果

### 生产验证

1. Redis service 运行正常
2. Agent bridge 使用 Redis（日志确认）
3. 报告生成 → ai_reports 有数据
4. 失败场景 → AITask=failed + 前端显示错误
