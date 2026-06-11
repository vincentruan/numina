---
name: ai-agent-execution-display-optimization
description: AI Agent 执行过程展示优化 — 解决 MCP 调用展示体验、历史恢复完整性、宽度优化等问题
created: 2026-06-10
deepened: 2026-06-10
status: active
type: feat
Origin: docs/superpowers/plans/2026-06-10-ai-agent-execution-display-optimization-requirements.md
---

# AI Agent 执行过程展示优化

## Problem Frame

用户在 AI Chat 页面与 Agent 交互时存在以下体验问题：

1. **MCP 调用视觉体验问题** — 实时流式对话中，工具调用 running → done 的状态变化让用户感知为"重复展示"（先显示参数，后显示结果）
2. **历史恢复不完整** — Journal 未记录 `plan.update`、`subagent.update` 等事件，导致历史会话无法恢复完整执行过程
3. **宽度利用不足** — 短任务 Agent 回答仍使用窄气泡宽度，未充分利用页面空间

### Root Cause Analysis

| 问题 | 根因代码位置 | 影响 |
|------|-------------|------|
| 工具调用"重复"感 | `AiProcessBlock.vue:296` — `base.compressed = step.status === 'done'` | running 状态保持展开显示参数，done 状态压缩显示结果，过渡期视觉变化感知为两条消息 |
| Journal 事件缺失 | `session_journal.py` 缺少 `write_plan_update()`、`write_subagent_update()` | 历史恢复无 plan 进度条、无子代理执行信息 |
| 宽度受限 | `aiTaskDetection.ts` — `isLongTask()` 门槛过高（≥3 步骤或 deepThink） | Agent 回答被窄气泡限制 |

---

## Summary

本计划通过三个方案解决 AI Agent 执行过程展示的视觉体验、数据完整性和布局优化问题：

- **方案 A-1**：修改工具调用压缩逻辑，让 running 状态也使用压缩模式，参数默认折叠
- **方案 B**：扩展 Journal 写入方法，补充 plan.update 和 subagent.update 事件类型
- **方案 C**: 调整宽度判定逻辑，Agent 回答区域达到用户消息气泡宽度 1.5x

---

## Scope Boundaries

### In Scope

- 前端工具调用状态展示优化（压缩逻辑、CSS 过渡）
- 后端 Journal 事件扩展（新增写入方法）
- Agent 回答宽度优化（判定逻辑、CSS）
- 历史会话恢复完整性（事件持久化 + 前端重放）

### Deferred to Follow-Up Work

- Markdown 流式渲染优化（已在其他任务中处理）
- 深色模式适配（已在其他任务中处理）

### Non-Goals

- Agent 人格/提示词调整
- MCP 工具注册/配置变更
- 多租户隔离架构调整
- 认证/授权流程变更

---

## Key Technical Decisions

### KTD-1: Running 状态默认压缩

**Decision**: 工具调用 running 状态也使用 `compressed=true`，参数默认折叠，用户点击可展开。

**Rationale**:
- 当前用户感知"重复"源于 running 展开 + done 压缩的视觉变化
- DeerFlow 模式：ToolMessage 嵌入父 AIMessage group，不单独展示
- 压缩模式下单卡片只显示状态文本，状态变化更平滑

**Implementation**: 修改 `AiProcessBlock.vue:296` 压缩判定逻辑。

### KTD-2: Journal 事件结构复用

**Decision**: 新增方法复用 `_make_event()` helper，保持与现有事件一致的结构。

**Rationale**:
- 现有 `write_tool_call()`、`write_tool_result()` 已建立事件结构模式
- `aiEventNormalizer.ts` 前端已支持 `plan.update`、`subagent.update` 事件解析
- 保持结构一致性确保前端重放无需修改

**Implementation**: `session_journal.py` 新增方法，`agent_dispatch.py` 调用集成。

### KTD-3: 宽度判定策略

**Decision**: Agent 回答区域宽度应达到用户消息气泡宽度的 1.5x，通过组合方案实现：
- CSS `max-width` 调整至 98%
- `isLongTask()` 门槛降低：`steps.some(s => s.type === 'tool_call') || deepThink`

**Rationale**:
- 当前门槛（≥3 步骤或 deepThink）对简单工具调用场景不适用
- 用户期望：Agent 内容区应比普通用户消息更宽（AC-5: ≥1.5x）
- 组合方案：CSS 调整影响所有 assistant 消息，isLongTask 调整决定是否使用全宽 canvas

**Canonical Target**: AC-5 的「1.5x」为唯一规范目标。删除所有「full-width」「全宽」等模糊术语引用。

**Implementation**: 调整 `aiTaskDetection.ts` + `AIChatPage.vue` CSS（详见 U4）。

---

## Implementation Units

---

### U1. 工具调用 Running 状态压缩优化

**Goal**: 让工具调用 running 状态也使用压缩模式，参数默认折叠，消除视觉"重复"感。

**Requirements**: AC-1, AC-2

**Dependencies**: None

**Files**:
- `frontend/apps/main/src/components/ai/AiProcessBlock.vue` (modify)
- `frontend/apps/main/src/components/ai/AiStepBlock.vue` (modify — 添加 args 条件渲染)
- `frontend/apps/main/src/composables/useStepCollapse.ts` (review)
- `frontend/apps/main/tests/unit/AiStepBlock.test.ts` (extend)

**Approach**:
1. 修改 `AiProcessBlock.vue:296` 压缩判定：`base.compressed = step.status === 'done' || step.status === 'running'`
2. **关键修改**: `AiStepBlock.vue` 在 compressed + running 状态下需条件隐藏 args：
   - 当前 `AiStepBlock.vue:65-68` 无论 compressed 值都会渲染 args
   - 添加 v-if guard: `v-if="!compressed && step.status === 'running'"` 或 computed 属性 `showArgsInRunning`
   - 压缩模式 running 状态只显示工具名 + 状态指示器（spinner/text）
3. 验证 CSS transition (`tool-state-enter-active/leave-active`) 在 compressed 切换时平滑过渡
4. 用户可点击 header 展开，展开后显示 args（running）或 result（done）

**Interaction States**:
- **Hover**: 微亮背景 (`background: rgba(--van-primary-color, 0.08)`)
- **Press**: scale 0.98 效果
- **Focus**: 跟随系统默认 focus ring，不额外定义
- **State persistence**: running→done 切换时保持 compressed 状态不变（不自动折叠/展开）

**Patterns to follow**:
- 现有 `useStepCollapse` composable 处理展开/折叠逻辑
- `AiStepBlock.vue:166-168` `effectiveDefaultExpanded` 计算模式

**Test scenarios**:
- **Happy path**: tool_call step with status='running' renders compressed by default; tap header expands showing args
- **Happy path**: status transitions from 'running' to 'done'; card stays compressed, content changes from args to result
- **Edge case**: compressed tool_call with status='error' shows error summary correctly
- **Edge case**: user expands running card, then status becomes done — card stays expanded (preserve user choice)
- **Interaction**: Hover state shows subtle background highlight; press shows 0.98 scale
- **Integration**: Live stream scenario with multiple tool calls arriving and completing sequentially

**Verification**: Visual inspection in browser + unit tests pass. Run `pnpm test:run` in frontend/apps/main.

---

### U2. Journal Plan Update 事件扩展

**Goal**: 扩展 `session_journal.py` 支持 `plan.update` 事件写入，确保历史恢复可见 Plan 进度条。

**Requirements**: AC-3

**Dependencies**: **阻塞项** — 需先确认 DeerFlow adapter 中 `plan.update` 事件的发射时机和回调点（见 Dependencies 章节 Q1）。建议实现顺序：先完成 U1 和 U4，后置 U2/U3 待 DeerFlow 集成确认。

**Files**:
- `server/apps/agent/services/session_journal.py` (modify)
- `server/apps/agent/services/agent_dispatch.py` (modify — 调用点，待 DeerFlow 回调确认)
- `server/apps/agent/tests/unit/test_session_journal.py` (add)

**Approach**:
1. 在 `session_journal.py` 添加 `write_plan_update()` 方法：
   ```python
   def write_plan_update(
       self,
       *,
       family_id: str,
       session_id: str,
       todos: list[dict[str, Any]],
   ) -> None:
       event = _make_event(
           "plan.update",
           session_id=session_id,
           family_id=family_id,
           actor="assistant",
           visibility="public",
           payload={"todos": todos},
       )
       self.append_event(family_id, session_id, event)
   ```
2. **调用点集成**（待 DeerFlow 确认）：在 `agent_dispatch.py` 的 DeerFlow astream 回调中调用该方法，当 DeerFlow 发出 plan.update 时触发。需先追踪 DeerFlow orchestrator 的 plan 状态变化回调点。
3. 确认前端 `aiEventNormalizer.ts` 已正确处理 `plan.update` 事件（无需修改）

**Patterns to follow**:
- 现有 `write_tool_call()` 方法结构
- `_make_event()` helper 统一事件格式

**Test scenarios**:
- **Happy path**: `write_plan_update()` writes valid JSONL line with type='plan.update'
- **Edge case**: Empty todos list — method should still write event (frontend handles empty gracefully)
- **Error path**: Invalid family_id/session_id — raises ValueError from `_validate_id`

**Verification**: Backend unit tests pass. Run `uv run pytest apps/agent/tests/unit/test_session_journal.py -v`.

---

### U3. Journal Subagent Update 事件扩展

**Goal**: 扩展 `session_journal.py` 支持 `subagent.update` 事件写入，确保历史恢复可见子代理执行过程。

**Requirements**: AC-4

**Dependencies**: U2 (同模式扩展) + **阻塞项** — 同样需先确认 DeerFlow adapter 中 `subagent.update` 事件的发射时机

**Files**:
- `server/apps/agent/services/session_journal.py` (modify)
- `server/apps/agent/services/agent_dispatch.py` (modify — 调用点，待 DeerFlow 回调确认)
- `server/apps/agent/tests/unit/test_session_journal.py` (extend)

**Approach**:
1. 在 `session_journal.py` 添加 `write_subagent_update()` 方法：
   ```python
   def write_subagent_update(
       self,
       *,
       family_id: str,
       session_id: str,
       task_id: str,
       status: str,
       title: str | None = None,
       description: str | None = None,
       result: str | None = None,
       error: str | None = None,
   ) -> None:
       event = _make_event(
           "subagent.update",
           session_id=session_id,
           family_id=family_id,
           actor="assistant",
           visibility="public",
           payload={
               "subagent": {
                   "taskId": task_id,
                   "status": status,
                   "title": title,
                   "description": description,
                   "result": result,
                   "error": error,
               }
           },
       )
       self.append_event(family_id, session_id, event)
   ```
2. **调用点集成**（待 DeerFlow 确认）：在 DeerFlow subagent 回调中调用该方法，需先追踪 DeerFlow 的 subagent 状态变化回调点
3. 确认前端 `aiEventNormalizer.ts` 已正确处理 `subagent.update` 事件（无需修改）

**Patterns to follow**:
- U2 的 `write_plan_update()` 结构
- payload 结构与前端 `aiEventNormalizer.ts:283-316` 解析逻辑匹配

**Test scenarios**:
- **Happy path**: `write_subagent_update()` writes valid JSONL with type='subagent.update'
- **Edge case**: Partial update (only status changed) — method accepts optional fields
- **Error path**: Invalid task_id format — raises ValueError

**Verification**: Backend unit tests pass. Run `uv run pytest apps/agent/tests/unit/test_session_journal.py -v`.

---

### U4. 宽度判定逻辑优化

**Goal**: Agent 回答区域达到用户消息气泡宽度的 1.5x，提升内容可读性。

**Requirements**: AC-5

**Dependencies**: None (独立于其他单元)

**Files**:
- `frontend/apps/main/src/utils/aiTaskDetection.ts` (modify)
- `frontend/apps/main/src/pages/AIChatPage.vue` (modify CSS)
- `frontend/apps/main/src/components/ai/AgentRunCanvas.vue` (review)

**Approach** (组合方案):

**方案 A: CSS max-width 调整**
```css
.bubble.assistant {
  max-width: 98%;  /* 从当前值提升，使 Agent 回答更宽 */
}

/* Mobile breakpoint */
@media (max-width: 428px) {
  .bubble.assistant {
    max-width: 100%;  /* 移动端全宽 */
  }
}
```

**方案 B: isLongTask 门槛降低**
```typescript
// Current: >=3 steps OR deepThink OR trigger tool
// Proposed: any tool_call step OR deepThink
export function isLongTask(steps: ProcessStep[], deepThink: boolean): boolean {
  if (deepThink) return true
  return steps.some(s => s.type === 'tool_call')
}
```

**组合策略**: CSS 调整确保所有 assistant 消息更宽（baseline 1.5x），isLongTask 调整决定是否使用 AgentRunCanvas 全宽容器（工具调用场景）。

**Responsive Behavior**:
- Desktop/Tablet: `max-width: 98%`，配合 isLongTask 决定是否使用 canvas
- Mobile (≤428px): `max-width: 100%`，保持现有响应式逻辑不变，safe-area padding 自动处理

**Patterns to follow**:
- 现有 `AgentRunCanvas.vue` 全宽容器模式
- CSS 变量 `--van-primary-color` 等 Vant 4 token

**Test scenarios**:
- **Happy path**: Single tool_call response uses wider layout (≥1.5x user message width)
- **Edge case**: Pure reasoning response (no tool calls) — uses bubble width but still wider baseline (98% max-width)
- **Edge case**: deepThink=true with no tools — uses full-width canvas per existing logic
- **Mobile (≤428px)**: max-width: 100%, respects safe-area padding, no overflow
- **Measurement**: Agent bubble width ≥ 1.5x user message bubble width (AC-5 target)

**Verification**: Visual inspection in browser, test with various response types. Run `pnpm typecheck && pnpm test:run`.

---

### U5. 集成验证与回归测试

**Goal**: 验证三个方案的集成效果，确保现有能力不受影响。

**Requirements**: AC-6

**Dependencies**: U1, U4 (先完成前端优化), U2, U3 (后置待 DeerFlow 确认)

**Files**:
- `frontend/apps/main/tests/unit/aiEventNormalizer.test.ts` (review)
- `frontend/apps/main/tests/e2e/` (review — if exists)
- `server/apps/agent/tests/integration/` (review)

**Approach**:
1. 运行前端全量测试：`pnpm -r test:run && pnpm -r typecheck && pnpm -r lint`
2. 运行后端全量测试：`uv run pytest apps/agent/tests/ -v && uv run ruff check && uv run mypy`
3. 手动验收场景：
   - 新建会话，观察工具调用 running→done 过渡平滑度
   - 点击工具调用卡片展开/折叠交互
   - 历史会话恢复，确认 Plan 进度条和子代理信息可见
   - Agent 回答宽度测量 vs 用户消息宽度
4. 验证现有能力不受影响：模型选择、会话管理、多租户隔离

**Test scenarios**:
- **Integration**: Full stream flow with tool calls, plan updates, and final answer
- **Integration**: History recovery replay produces complete process steps
- **Regression**: Model selection dropdown still functional
- **Regression**: DeepThink mode still triggers full-width display
- **Regression**: Error handling paths still show error cards correctly

**Verification**: All automated tests pass, manual scenarios verified.

---

## Risk Analysis & Mitigation

| Risk | Severity | Mitigation |
|------|----------|------------|
| Running 压缩导致用户无法查看正在执行的参数详情 | Medium | 用户可点击 header 展开；添加 tooltip 或 hint 提示可展开 |
| Journal 写入增加存储空间 | Low | 评估增量大小；plan/subagent 事件相对稀疏 |
| 宽度调整影响移动端布局 | Medium | 重点测试移动端 H5；验证 safe-area padding |
| 历史恢复事件重放顺序不一致 | Low | `aiEventNormalizer.ts` 已处理事件合并；测试验证 |

---

## Dependencies

- **DeerFlow 事件格式 (阻塞项)**: U2/U3 实现前需先确认 DeerFlow adapter 中 `plan.update`、`subagent.update` 事件的发射时机和回调点。建议实现顺序：U1 → U4 → U2/U3。
- **前端事件处理**: `aiEventNormalizer.ts` 已支持相关事件类型，无需额外修改
- **测试环境**: 需能触发工具调用、plan 更新、subagent 执行的完整 Agent 流程

---

## Verification Strategy

### Automated Tests

| Component | Test Command |
|-----------|-------------|
| Frontend unit | `cd frontend/apps/main && pnpm test:run` |
| Frontend typecheck | `cd frontend/apps/main && pnpm typecheck` |
| Backend unit | `cd server && uv run pytest apps/agent/tests/unit/ -v` |
| Backend lint | `cd server && uv run ruff check apps/agent/` |

### Manual Verification

1. **AC-1**: 实时流式对话，工具调用 running→done 过渡平滑，无视觉"重复"感
2. **AC-2**: 工具调用参数默认折叠，点击 header 可展开
3. **AC-3**: 历史会话恢复后，Plan 进度条可见
4. **AC-4**: 历史会话恢复后，子代理执行过程可见
5. **AC-5**: Agent 回答区域宽度 ≥ 用户消息气泡宽度 1.5x
6. **AC-6**: 现有能力不受影响（模型选择、高可用、会话管理等）

---

## Deferred Questions

- **Q1 (阻塞项)**: DeerFlow 发出 `plan.update` / `subagent.update` 事件的确切时机和回调点？需在实现 U2/U3 前确认 DeerFlow adapter 的回调注册机制。
- Q2: 已在 U4 中解决 — ≤428px 断点时 `max-width: 100%`，保持现有响应式逻辑。

**Resolution Status**: Q1 待 DeerFlow 集成确认后再细化 U2/U3 调用点；Q2 已在 U4 响应式策略中明确。

### Code Review Deferred Items (2026-06-11) — RESOLVED

以下 findings 在代码审查中被 deferred，已于 2026-06-11 处理完毕：

| ID | 文件 | 问题 | 解决状态 |
|----|------|------|---------|
| CR-2 | `AIChatPage.vue:1515` | `renderThrottleTimers.delete(msgId)` 引用未定义变量 | ✅ **已修复** — 删除遗留死代码 |
| CR-4 | `AiStepBlock.vue:234` | statusText 硬编码中文字符串 | ✅ **已修复** — 改用 i18n 插值 `statusRunningAction`, `defaultAction` 等 keys |
| CR-6 | `stream_events.py:230` | `todos: list[dict]` 类型提示不完整 | ✅ **评估决策** — 保持现状，`list[dict]` 是 Python 3.9+ 简化语法，功能等效 |
| CR-8 | `agent_dispatch.py:649` | `import hashlib` 在循环内部 | ✅ **已修复** — 移至文件顶部标准库 imports 区域 |

### P1-P2 遗留问题 — RESOLVED

以下 P1-P2 findings 已于 2026-06-11 处理：

| ID | 优先级 | 类别 | 问题 | 解决状态 |
|----|--------|------|------|---------|
| CR-9 | P1 | 测试覆盖 | `write_plan_update()` 缺少单元测试 | ✅ **已添加** — `test_session_journal.py` 新增 `TestSessionJournalPlanUpdate` |
| CR-10 | P1 | 测试覆盖 | `write_subagent_update()` 缺少单元测试 | ✅ **已添加** — `test_session_journal.py` 新增 `TestSessionJournalSubagentUpdate` |
| CR-11 | P1 | 测试覆盖 | `removeQuestionEcho()` 边界情况未测试 | ✅ **已添加** — `contentFilter.test.ts` 新增 edge cases describe block |
| CR-12 | P1 | 测试覆盖 | `subagent_update()` 缺少单元测试 | ✅ **已添加** — 创建 `test_stream_events_subagent.py` |
| CR-13 | P2 | 架构 | Canvas 阈值可能过度触发 | ✅ **评估决策** — 保持现状，符合 U4 规范，待 UX 反馈调优 |
| CR-14 | P2 | 数据 | Plan ID 稳定性问题 | ✅ **评估决策** — 低优先级限制，前端不依赖 ID 匹配 DeerFlow |
| CR-15 | P2 | 性能 | `seen_tool_call_ids` 内存清理 | ✅ **评估决策** — 原审查误判，局部变量在 generator 结束时自动 GC |

### 测试验证

- **后端 pytest**: 23 passed (session_journal + stream_events_subagent)
- **前端 vitest**: 534 passed (AiStepBlock + contentFilter)
- **TypeScript typecheck**: ✅ 通过
- **Ruff lint**: ✅ 通过

---

## Related Documents

- Origin: `docs/superpowers/plans/2026-06-10-ai-agent-execution-display-optimization-requirements.md`
- DeerFlow spec: `~/geek_space/github/deer-flow-reference/docs/superpowers/specs/2026-06-10-deerflow-agent-architecture-design.md`
- Architecture pattern: `docs/solutions/architecture-patterns/mcp-chat-adapter-architecture-2026-05-21.md`
- Stream contract: `docs/solutions/integration-issues/deerflow-adapter-stream-type-mismatch-and-security-issues-2026-05-16.md`