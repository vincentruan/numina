# Area 12 — AI task resilience (前端不稳定处理)

Shared conventions in [`_common.md`](../../_common.md).

覆盖 [`docs/plans/2026-08-15-002-feat-ai-task-resilience-v2-full-coverage-plan.md`](../../../../../../docs/plans/2026-08-15-002-feat-ai-task-resilience-v2-full-coverage-plan.md)
的**前端不稳定处理**维度：用户切走页面 / 刷新页面 / 任务失败 / 服务重启
（中断）/ 用户主动取消 等不稳定场景下，前端能否正确恢复（轮询 AITask / 重连
SSE / 显示重试按钮）而非卡死、空白或丢失结果。

本 Area 与 Area 3（AI 能力）、Area 6（AI chat parity）互补：Area 3/6 验证
"正常路径 + 设计出入"，本 Area 验证"异常路径 + 状态恢复"。

> **AI prerequisite:** AI 必须已启用 + provider 已配置（同 Area 3）。未启用时
> 本 Area 除 C12.9（中断态，仅需后端孤儿恢复）外全部 `SKIP-AI`。

> **Auth:** 复用 G0 成人 session（`demouser`），同 Area 3 的 cookie+localStorage
> 注入方式。AI 任务会写 `aiStore.backgroundTasks` 与 AITask 表，属**每实体写**，
> 不改全局设置（`default_currency` 等），故归入 G1（adult-stable）。

---

## 实现状态（grounded — 2026-08-16，updated after U13–U21 page wiring landed）

全部 12 个用例**当前可跑**。后端 + Agent + 前端页面接线均已落地。

| 计划单元 | 行为 | 前端落地证据 | 用例 | 状态 |
|----------|------|--------------|------|------|
| v1 report (U4) | Report SSE + 离开/返回轮询 + Last-Event-ID 重连 | `AIReportPage.vue` onMounted 恢复 + `useReportStream.startPolling()` | C12.1–C12.3 | ✅ 可跑 |
| U13 coach | Finance Coach AITask + 轮询恢复 | `FinanceCoachCard.vue` 已接 `useTaskPolling` + `resumeIfRunning()` | C12.4 | ✅ 可跑 |
| U14 literacy | Literacy AITask + 轮询恢复 | `LiteracyReportPage.vue` 已接 `useTaskPolling` + `resumeIfRunning()` | C12.5 | ✅ 可跑 |
| U15 narrative | Narrative POST + 轮询 + UI | 后端 `dashboard.py:211` POST；前端 `DashboardNarrativeCard.vue` 新建 | C12.6 | ✅ 可跑 |
| U16 useTaskPolling | 通用轮询 composable | 已建 + 已接线到所有 AI 功能页面 | — | ✅ 已接线 |
| U20 cancel 端点 | `POST /ai/tasks/detail/{id}/cancel` | 后端 `ai_tasks.py:209` 已落地 | C12.7 | ✅ 可跑 |
| U21 取消按钮 | 前端各功能取消按钮 | 各页面已接 `cancelTaskById` + 取消按钮 | C12.7 | ✅ 可跑 |
| U18/U19 chat | Chat AITask 跟踪 + 恢复预检 | `AIChatBox.vue` 已接 `getChatTaskForSession` 预检 + 状态 banner | C12.8 | ✅ 可跑 |
| R5/R6 中断重试 | interrupted → 重试按钮 | Chat banner 有 retry；非 chat 各页面有重试/重新生成按钮 | C12.9 | ✅ 可跑 |

**状态图例:** ✅ 可跑（当前代码已落地）。

---

## 用例

### C12.1 Asset Report — 离开再回来（leave-and-return 恢复） ✅

**计划来源:** R4 / Flow 1 / AE1（对应 report）。**落地状态:** ✅ 可跑。

验证用户触发报告生成后切走页面、任务后台继续执行、返回时恢复进度的能力。

```
# 触发生成
bsk navigate ${BASE}ai/report --session <id> --wait-until networkidle
bsk snapshot --session <id>
bsk click @eN --session <id>           # "开始分析" / regenerate
bsk wait-ms 3s                          # 确认已进入 streaming（step1 process）
bsk snapshot --session <id>

# 切走页面（agent 继续后台执行）
bsk navigate ${BASE}ai --session <id> --wait-until networkidle
bsk wait-ms 8s

# 返回报告页（onMounted 恢复：getAITask('report') → startPolling）
bsk navigate ${BASE}ai/report --session <id> --wait-until networkidle
bsk snapshot --session <id>
bsk screenshot --session <id> --out dogfood-output/c12.1-report-leave-return.png
```

Assertions:
- [ ] 切走前：3 步时间轴已进入 streaming（step1 `process`），非 `waiting`
- [ ] 切走期间：agent 继续执行（`AIReportPage` onUnmounted 调用 `stream.abort(true)` 保留后台 pipeline）
- [ ] 返回后：页面**不显示**"暂无报告"空态；若任务仍 running → 显示生成中进度（`aiHub.reportGenerating`），若已完成 → 直接加载已落库报告
- [ ] 无 `[console]` 错误（无未捕获的 abort/状态竞态）
- [ ] 后台任务状态被清理（`aiStore.clearBackgroundTask('report')`），AIHub 无残留"运行中"标记

### C12.2 Asset Report — 刷新页面恢复（hard reload） ✅

**计划来源:** R4 / AE2（对应 report）。**落地状态:** ✅ 可跑。

验证生成中刷新页面（hard navigation）后，onMounted 恢复逻辑从 AITask 状态
恢复而非丢失任务。

```
bsk navigate ${BASE}ai/report --session <id> --wait-until networkidle
bsk snapshot --session <id>
bsk click @eN --session <id>           # 开始分析
bsk wait-ms 3s
# 硬刷新：重新 navigate 到同一 URL（模拟 F5）
bsk navigate ${BASE}ai/report --session <id> --wait-until networkidle
bsk snapshot --session <id>
```

Assertions:
- [ ] 刷新后若 AITask 状态为 `running/queued/post_processing` → 页面进入轮询（`startPolling`），显示生成中，完成后加载报告
- [ ] 刷新后若 AITask 已 `completed` → 直接加载已落库报告（缓存 badge 或新报告）
- [ ] 刷新后若 AITask 已 `failed` 但报告已落库 → 3s 后重查并显示报告（`AIReportPage:589-604` 的 retryTimer 逻辑）
- [ ] 无 `[console]` 错误

### C12.3 Asset Report — 失败 → 错误占位 + 重试按钮 ✅

**计划来源:** V3 "任务失败" 行。**落地状态:** ✅ 可跑（需 AI 失败注入，同 C3.4）。

验证任务失败后前端显示错误占位与重试按钮，且重试可重新触发。

```
# 前置：使 AI 生成失败（临时停用 provider 或用无模型配置的 provider），
# 然后触发生成
bsk navigate ${BASE}ai/report --session <id> --wait-until networkidle
bsk snapshot --session <id>
bsk click @eN --session <id>           # 开始分析 → 失败
bsk wait-ms 12s
bsk snapshot --session <id>
```

Assertions:
- [ ] 失败后显示 failed-placeholder：错误信息 + 重试按钮（`aiTask.retry`）
- [ ] 若 step1 markdown 已落盘但 step2/3 失败 → 额外显示"查看 Markdown"弹性回退（同 C3.9）
- [ ] 点击重试 → 重新触发生成（新 AITask / 重新 `stream.connect(force)`）
- [ ] 无 `[console]` 错误（无未处理的 stream error 泄漏到全局）

> 与 C3.4/C3.9 重叠：C3.4 验证 3 步时间轴正常/失败，C3.9 验证 markdown 回退。
> 本用例聚焦**失败→重试的恢复闭环**，可合并执行，报告互引。

### C12.4 Finance Coach — 离开再回来（轮询恢复） ✅

**计划来源:** R2/U13/AE1（coach）。**落地状态:** ✅ 可跑（`FinanceCoachCard.vue` 已接 `useTaskPolling` + `resumeIfRunning()`）。

接线后验证：Dashboard 触发 coach 建议 → 切走 → 返回 → 轮询 AITask 显示进度/结果。

```
# Dashboard coach 触发 + 离开恢复流程：
bsk navigate ${BASE} --session <id> --wait-until networkidle   # Dashboard
bsk snapshot --session <id>
bsk click @eN --session <id>           # FinanceCoachCard 触发生成
bsk wait-ms 2s
bsk navigate ${BASE}ai --session <id> --wait-until networkidle  # 切走
bsk wait-ms 6s
bsk navigate ${BASE} --session <id> --wait-until networkidle    # 返回
bsk snapshot --session <id>
```

Assertions:
- [ ] 触发时创建 AITask(skill_id=coach)；用户在页面时经 bridge consumer SSE 流式
- [ ] 切走后任务后台继续；返回时前端轮询 `GET /ai/tasks/detail/{task_id}` 恢复
- [ ] `status=completed` → 显示建议结果；`status=running` → 显示进度（step/steps_completed）
- [ ] `status=failed/interrupted` → 显示错误 + 重试按钮
- [ ] 取消按钮（running 时）→ `POST /ai/tasks/detail/{id}/cancel` → 立即标记 cancelled
- [ ] 无 `[console]` 错误

### C12.5 Literacy Report — 离开再回来（轮询恢复） ✅

**计划来源:** R2/U14。**落地状态:** ✅ 可跑（`LiteracyReportPage.vue` 已接 `useTaskPolling` + `resumeIfRunning()`）。

```
# Literacy 触发 + 离开恢复流程（baby literacy-report 路由）
bsk navigate ${BASE}baby/literacy-report --session <id> --wait-until networkidle
bsk snapshot --session <id>
# ... 触发周报生成 → 切走 → 返回 ...
```

Assertions:
- [ ] AITask(skill_id=literacy) 创建；在页面时 bridge consumer SSE 流式
- [ ] 返回时轮询恢复：completed → 周报（`WeeklyReportCard` narrative）；running → 进度
- [ ] 失败/中断 → 错误 + 重试
- [ ] 取消按钮（running 时）→ 立即标记 cancelled
- [ ] 无 `[console]` 错误

### C12.6 Dashboard Narrative — POST + 离开恢复 ✅

**计划来源:** KTD-16/U15。**落地状态:** ✅ 可跑（后端 `dashboard.py:211` POST；前端 `DashboardNarrativeCard.vue` 已新建并接线到 DashboardPage）。

```
# Dashboard narrative 触发 + 离开恢复流程：
bsk navigate ${BASE} --session <id> --wait-until networkidle   # Dashboard
bsk snapshot --session <id>
# ... 找到 "本月洞察" 卡片 → 触发 → 切走 → 返回 ...
```

Assertions:
- [ ] POST `/api/v1/dashboard/narrative`（替代旧 GET）创建 AITask(skill_id=narrative)
- [ ] 在页面时 bridge consumer SSE 实时流式；切走/刷新后轮询恢复
- [ ] 缓存命中 → 不创建 AITask，直接显示 narrative
- [ ] threshold gate → 数据不足时不创建任务，显示空态 + 生成按钮
- [ ] 取消按钮（running 时）→ 立即标记 cancelled
- [ ] 无 `[console]` 错误

### C12.7 用户主动取消（Report / Coach / Literacy / Narrative / Chat） ✅

**计划来源:** R8/U20/U21/AE5/Flow 5。**落地状态:** ✅ 可跑（后端 `ai_tasks.py:209` + 各前端页面已接 `cancelTaskById` + 取消按钮；Chat banner 也有取消）。

**后端验证（当前可跑，curl 而非 bsk）:**

```bash
# 触发一个 report 任务 → 拿 task_id → 取消
# task_id 可从 GET /ai/tasks?skill_id=report 拿 running 任务
curl -s -X POST "$API/ai/tasks/detail/${TASK_ID}/cancel" -H "$AUTH"
# 期望 { ok: true, status: "cancelled", task_id: "..." }
# 幂等：再次 cancel 已 completed 的任务 → 返回 { status: "completed" }（不回退）
```

**UI 验证（已接线）:**

```
bsk navigate ${BASE}ai/report --session <id> --wait-until networkidle
bsk snapshot --session <id>
bsk click @eN --session <id>           # 开始分析 → running
bsk snapshot --session <id>
bsk click @eC --session <id>           # 取消按钮（running 时显示）
bsk snapshot --session <id>
```

Assertions:
- [ ] 任务 `running` 时各功能页面显示取消按钮（Report/Coach/Literacy/Narrative）
- [ ] 点击取消 → `POST /ai/tasks/detail/{id}/cancel` → 立即标记 `cancelled`（不等 Agent 确认）
- [ ] 轮询看到 `status=cancelled` → 停止轮询，显示已取消状态
- [ ] 任务已完成时取消按钮不显示
- [ ] 取消确认对话框取消 → 不发送请求
- [ ] Chat 取消：banner 中取消按钮 → 立即标记 cancelled + 停止轮询
- [ ] 无 `[console]` 错误

### C12.8 Chat — 刷新/切走恢复（checkpointer + AITask 预检） ✅

**计划来源:** R4 "Chat 恢复流程" / AE2 / U18/U19。**落地状态:** ✅ 可跑（`AIChatBox.vue` 已接 `getChatTaskForSession` 预检 + 状态 banner + 轮询）。

```
# 接线后预期流程：
bsk navigate ${BASE}ai/chat --session <id> --wait-until networkidle
bsk snapshot --session <id>
bsk fill @eN --value 帮我分析资产 --session <id>
bsk click @eM --session <id>           # 发送 → SSE 流式
bsk wait-ms 2s
# 生成中刷新页面
bsk navigate ${BASE}ai/chat --session <id> --wait-until networkidle
bsk snapshot --session <id>
```

Assertions:
- [ ] 用户在页面时：token-by-token SSE 流式体验不变
- [ ] 刷新后：AITask 状态预检（`getChatTaskForSession`）→ completed → 从 checkpointer 加载完整对话，banner 消失
- [ ] running → 显示 "任务仍在后台运行中" banner + 轮询；完成后自动 loadHistory
- [ ] failed/interrupted → 显示错误 banner + 重试按钮（重发最后一条用户消息）
- [ ] 取消按钮（running banner）→ 立即标记 cancelled
- [ ] 无 AITask → 正常流程（新对话 / checkpointer 加载）
- [ ] 无 `[console]` 错误

### C12.9 中断任务 → 重试按钮（graceful shutdown / orphan recovery） ✅

**计划来源:** R5/R6/AE3/AE4。**落地状态:** ✅ 可跑（后端孤儿恢复 `gc.py` 已落地；Chat banner 有 retry；非 chat 各页面有重试/重新生成按钮）。

**前置（模拟中断，非 bsk 触发）:** 中断态由后端孤儿恢复标记，浏览器 UI 测试
无法触发 SIGTERM/lease 过期。模拟方式二选一：

1. **优雅关停：** 任务生成中重启 backend/agent → 60s drain 超时后剩余 AITask
   被标 `interrupted`，`error_message="服务重启，任务中断，请重试"`。
2. **孤儿恢复：** 手动将某 running AITask 的 `lease_expires_at` 设为过去 →
   触发 `reconcile_orphaned_tasks()` → 标 `interrupted`。

```
# 前置完成后，在 UI 上验证中断态渲染
bsk navigate ${BASE}ai/report --session <id> --wait-until networkidle
bsk snapshot --session <id>
```

Assertions:
- [ ] 被中断任务的前端显示"执行中断"（`aiCanvas.statusInterrupted` 或 `chatTaskInterrupted` banner）+ 错误信息
- [ ] 显示重试按钮 → 点击创建新 AITask 重新触发（chat 重发最后一条消息；report/coach/literacy/narrative 重新生成）
- [ ] 中断任务不残留"运行中"标记（`aiStore` 后台任务清理）
- [ ] 无 `[console]` 错误（interrupted 是合法终态，非异常）

---

## 模拟不稳定状态的 API 辅助

浏览器 UI 测试无法触发服务重启 / lease 过期 / agent crash。需要诱导失败态时，
用 curl 操作 AITask 状态（仅用于预置前置条件，本 skill 不跑 API 验收）：

```bash
# 查看当前 family 的 AITask（含 progress）
curl -s -H "$AUTH" "$API/ai/tasks?skill_id=report" | jq '.data'

# 查看单任务详情（含 progress.step/steps_completed）
curl -s -H "$AUTH" "$API/ai/tasks/detail/${TASK_ID}" | jq '.data'

# 用户取消（后端已落地 U20）
curl -s -X POST -H "$AUTH" "$API/ai/tasks/detail/${TASK_ID}/cancel"

# 诱导 AI 失败：临时停用 provider（/settings/ai）或用无模型 provider
# 诱导中断：见 C12.9 前置（关停或孤儿恢复）
```

---

## Quick Reference

| Case | 恢复场景 | 涉及组件/文件 | 计划来源 | 状态 |
|------|----------|--------------|----------|------|
| C12.1 | Report 离开再回来 | `AIReportPage.vue` + `useReportStream.startPolling` | R4/AE1 | ✅ |
| C12.2 | Report 刷新恢复 | `AIReportPage.vue` onMounted 恢复 | R4/AE2 | ✅ |
| C12.3 | Report 失败→重试 | `AIReportPage.vue` failed-placeholder | V3 | ✅ |
| C12.4 | Coach 离开再回来 | `FinanceCoachCard.vue`（待接 AITask） | U13/AE1 | ⏳ U13 |
| C12.5 | Literacy 离开再回来 | `useLiteracyStream.ts`（待接轮询） | U14 | ⏳ U14 |
| C12.6 | Narrative GET→POST + 恢复 | `dashboard.py:214`（待改 POST） | KTD-16/U15 | ⏳ U15 |
| C12.7 | 用户主动取消 | `ai_tasks.py:209` + `cancelTaskById` | R8/U20/U21 | ✅ |
| C12.8 | Chat 刷新/切走恢复 | `useThreadChat.ts`（待接预检） | U18/U19/AE2 | ⏳ U18/U19 |
| C12.9 | 中断→重试 | `AgentRunHeader.vue` `statusInterrupted` | R5/R6/AE3/AE4 | ⏳ partial |
