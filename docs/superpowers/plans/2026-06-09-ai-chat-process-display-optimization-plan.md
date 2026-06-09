# AI Chat 处理过程展示优化 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 统一 Journal 事件命名、持久化 Tool 事件、实现 UI 平滑过渡、优化回答宽度和内容过滤

**Architecture:** Backend 统一事件命名并在 streaming 时同步写入 journal；Frontend Normalizer 兼容新旧格式；AiStepBlock 用 CSS transition + mode="out-in" 实现顺序过渡

**Tech Stack:** Python/FastAPI (backend), Vue 3 + TypeScript (frontend), CSS transitions

---

## Task 1: Backend Journal 事件命名统一

**Files:**
- Modify: `server/apps/agent/services/session_journal.py`

**Spec Reference:** §一 Backend Journal 事件命名统一

- [ ] **Step 1: 读取 session_journal.py 确认当前事件命名**

Run: Read `server/apps/agent/services/session_journal.py`
Expected: 找到 `write_tool_call` 和 `write_tool_result` 方法，事件类型为 `tool.call_started` / `tool.call_completed`

- [ ] **Step 2: 修改 write_tool_call 事件类型**

将 `"tool.call_started"` 改为 `"tool.call"`，payload 结构调整为：

```python
# write_tool_call 方法
event = _make_event(
    "tool.call",  # 原为 "tool.call_started"
    session_id=session_id,
    family_id=family_id,
    actor="assistant",
    visibility="public",
    payload={
        "tool": {  # 结构与 streaming 事件一致
            "id": tool_id,
            "name": tool_name,
            "display_name": tool_name,
            "icon": "tool",
            "arguments": arguments,
        }
    },
)
```

- [ ] **Step 3: 修改 write_tool_result 事件类型**

将 `"tool.call_completed"` 改为 `"tool.result"`：

```python
# write_tool_result 方法
event = _make_event(
    "tool.result",  # 原为 "tool.call_completed"
    session_id=session_id,
    family_id=family_id,
    actor="tool",
    visibility="public",
    payload={
        "tool_id": tool_id,
        "result": {
            "success": success,
            "execution_time_ms": execution_time_ms,
            "error": error,
        }
    },
)
```

- [ ] **Step 4: 运行 backend tests 验证改动**

Run: `cd server && uv run pytest apps/agent/tests/unit/test_session_journal.py -v -k "tool"`
Expected: PASS (如有测试)

- [ ] **Step 5: Commit**

```bash
git add server/apps/agent/services/session_journal.py
git commit -m "refactor(agent): unify journal event naming to tool.call/tool.result

- Rename tool.call_started → tool.call
- Rename tool.call_completed → tool.result
- Align payload structure with streaming EventStreamBuilder

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
```

---

## Task 2: Backend orchestrator.py 添加 Journal 写入

**Files:**
- Modify: `server/apps/agent/services/orchestrator.py`

**Spec Reference:** §二 Backend 持久化 Tool 事件 (orchestrator.py)

- [ ] **Step 1: 读取 orchestrator.py 确认 streaming tool 事件位置**

Run: Read `server/apps/agent/services/orchestrator.py`, focus on `_process_deerflow_chunk` function
Expected: 找到 `yield evt.to_ndjson()` 和 `yield builder.tool_result(...).to_ndjson()` 位置

- [ ] **Step 2: 在 tool_call yield 后添加 journal.write_tool_call**

在 `if chunk.type == "tool_call":` 分支中，yield 之后添加：

```python
# 新增：持久化到 journal
try:
    session_journal.write_tool_call(
        family_id=family_id,
        session_id=effective_thread_id,
        tool_name=tool_name,
        tool_id=backend_id,
        arguments=args,
    )
except Exception as e:
    logger.warning("[orchestrator] journal write_tool_call failed: %s", e)
```

- [ ] **Step 3: 在 tool_result yield 后添加 journal.write_tool_result**

在 `if chunk.type == "tool_result":` 分支中，yield 之后添加：

```python
# 新增：持久化到 journal
try:
    session_journal.write_tool_result(
        family_id=family_id,
        session_id=effective_thread_id,
        tool_id=backend_id,
        success=True,
        execution_time_ms=0,  # TODO: streaming path lacks timing metadata
    )
except Exception as e:
    logger.warning("[orchestrator] journal write_tool_result failed: %s", e)
```

- [ ] **Step 4: 确认 session_journal 已导入**

检查文件顶部是否有 `from .session_journal import SessionJournal` 或类似导入，若无则添加：

```python
from .session_journal import session_journal  # 或根据实际模块结构调整
```

- [ ] **Step 5: 运行 backend typecheck**

Run: `cd server && uv run mypy apps/agent/services/orchestrator.py`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add server/apps/agent/services/orchestrator.py
git commit -m "feat(agent): persist tool events to journal in orchestrator streaming

- Add journal.write_tool_call after tool_call yield
- Add journal.write_tool_result after tool_result yield
- Wrap in try/except to prevent streaming interruption

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
```

---

## Task 3: Backend agent_dispatch.py 添加 Journal 写入

**Files:**
- Modify: `server/apps/agent/services/agent_dispatch.py`

**Spec Reference:** §二 Backend 持久化 Tool 事件 (agent_dispatch.py)

- [ ] **Step 1: 读取 agent_dispatch.py 确认 streaming tool 事件位置**

Run: Read `server/apps/agent/services/agent_dispatch.py`, focus on `_stream_deerflow_response` function (lines 571-602)
Expected: 找到 `yield evt.to_ndjson()` 和 `yield builder_events.tool_result(...).to_ndjson()` 位置

- [ ] **Step 2: 在 tool_call yield 后添加 journal.write_tool_call**

在 `if kind == "tool_call":` 分支中，yield 之后添加：

```python
# 新增：持久化到 journal
try:
    session_journal.write_tool_call(
        family_id=family_id,
        session_id=session_id,
        tool_name=tname,
        tool_id=backend_id,
        arguments=call["args"],
    )
except Exception as e:
    logger.warning("[agent_dispatch] journal write_tool_call failed: %s", e)
```

- [ ] **Step 3: 在 tool_result yield 后添加 journal.write_tool_result**

在 `if kind == "tool_result":` 分支中，yield 之后添加：

```python
# 新增：持久化到 journal
try:
    session_journal.write_tool_result(
        family_id=family_id,
        session_id=session_id,
        tool_id=backend_id,
        success=True,
        execution_time_ms=0,
    )
except Exception as e:
    logger.warning("[agent_dispatch] journal write_tool_result failed: %s", e)
```

- [ ] **Step 4: 确认 session_journal 已导入**

检查文件顶部导入，若无则添加：

```python
from .session_journal import session_journal
```

- [ ] **Step 5: 运行 backend typecheck**

Run: `cd server && uv run mypy apps/agent/services/agent_dispatch.py`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add server/apps/agent/services/agent_dispatch.py
git commit -m "feat(agent): persist tool events to journal in agent_dispatch streaming

- Add journal.write_tool_call after tool_call yield
- Add journal.write_tool_result after tool_result yield
- Wrap in try/except to prevent streaming interruption

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
```

---

## Task 4: Frontend Normalizer 兼容新旧格式

**Files:**
- Modify: `frontend/apps/main/src/utils/aiEventNormalizer.ts`

**Spec Reference:** §三 Frontend Normalizer 兼容处理

- [ ] **Step 1: 读取 aiEventNormalizer.ts 确认当前事件处理**

Run: Read `frontend/apps/main/src/utils/aiEventNormalizer.ts`
Expected: 找到 `case 'tool.call':` 或类似事件处理分支

- [ ] **Step 2: 添加旧格式 fallback 分支**

在 tool 事件处理部分添加兼容逻辑（完整字段映射）：

```typescript
case 'tool.call':
case 'tool.call_started':  // 兼容旧格式
  if (event.tool || event.toolName) {
    // 统一处理：提取 tool 信息，映射旧格式字段
    const toolInfo = event.tool || {
      id: event.toolId ?? event.tool_id,      // 旧格式用 toolId 或 tool_id
      name: event.toolName ?? event.tool_name,
      display_name: event.toolName ?? event.tool_name,
      icon: event.icon ?? 'tool',
      arguments: event.arguments ?? event.args ?? {},
    };
    // 创建 step 时使用 toolInfo，与现有 'tool.call' handler 一致
    const step: ProcessStep = {
      id: generateStepId(),
      type: 'tool_call',
      status: 'running',
      name: toolInfo.name,
      displayName: toolInfo.display_name,
      icon: toolInfo.icon,
      args: toolInfo.arguments,
    };
    steps.push(step);
  }
  break;

case 'tool.result':
case 'tool.call_completed':  // 兼容旧格式
  // 更新对应 step 的 status 和 result
  const targetStep = findStepByToolId(event.toolId ?? event.tool_id);
  if (targetStep) {
    targetStep.status = 'done';
    targetStep.resultSummary = event.result?.summary ?? event.summary;
  }
  break;
```

- [ ] **Step 3: 运行 frontend typecheck**

Run: `cd frontend/apps/main && pnpm typecheck`
Expected: PASS

- [ ] **Step 4: 运行 frontend tests**

Run: `cd frontend/apps/main && pnpm test:run`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add frontend/apps/main/src/utils/aiEventNormalizer.ts
git commit -m "fix(frontend): add fallback for legacy tool event types

- Support tool.call_started → tool.call mapping
- Support tool.call_completed → tool.result mapping
- Backward compatible with old JSONL format

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
```

---

## Task 5: Frontend AiStepBlock CSS Transition

**Files:**
- Modify: `frontend/apps/main/src/components/ai/AiStepBlock.vue`

**Spec Reference:** §四 Frontend UI 平滑过渡

- [ ] **Step 1: 读取 AiStepBlock.vue 确认当前结构**

Run: Read `frontend/apps/main/src/components/ai/AiStepBlock.vue`
Expected: 找到 args 和 result 显示区域，检查是否有 `<Transition>` 组件

- [ ] **Step 2: 添加 mode="out-in" 到 args Transition**

修改 args 显示区域：

```vue
<!-- 参数显示区域：先淡出再淡入 result -->
<Transition name="args-fade" mode="out-in">
  <div v-if="status === 'running' || status === 'streaming' || isExpanded" class="tool-args">
    <!-- args content -->
  </div>
</Transition>
```

- [ ] **Step 3: 确保 result Transition 不重叠**

修改 result 显示区域：

```vue
<!-- 结果显示区域 -->
<Transition name="result-fade">
  <div v-if="status === 'done' || status === 'error' || status === 'failed'" class="tool-result">
    <!-- result content -->
  </div>
</Transition>
```

- [ ] **Step 4: 添加 CSS transition 样式**

在 `<style scoped>` 中添加：

```css
/* 参数淡出 */
.args-fade-enter-active,
.args-fade-leave-active {
  transition: opacity 0.2s ease;
}
.args-fade-enter-from,
.args-fade-leave-to {
  opacity: 0;
}

/* 结果淡入 */
.result-fade-enter-active,
.result-fade-leave-active {
  transition: opacity 0.2s ease;
}
.result-fade-enter-from,
.result-fade-leave-to {
  opacity: 0;
}

/* Reduced-motion: disable animation */
@media (prefers-reduced-motion: reduce) {
  .args-fade-enter-active,
  .args-fade-leave-active,
  .result-fade-enter-active,
  .result-fade-leave-active {
    transition: none;
  }
}
```

**边界情况:** 如果 status 从 running → error/done <200ms（transition 时间内），args-fade 和 result-fade 可能并行执行。CSS 依赖 Vue `mode="out-in"` 确保顺序过渡；对于快速失败场景，result opacity 从 0 开始渐显，不会与 args 全 opacity 重叠。

- [ ] **Step 5: 运行 frontend typecheck**

Run: `cd frontend/apps/main && pnpm typecheck`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add frontend/apps/main/src/components/ai/AiStepBlock.vue
git commit -m "feat(frontend): add CSS transition for tool status change

- Add mode=\"out-in\" to args Transition for sequential fade
- Add args-fade and result-fade CSS classes
- Support prefers-reduced-motion for accessibility

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
```

---

## Task 6: Frontend 回答宽度优化

**Files:**
- Modify: `frontend/apps/main/src/pages/AIChatPage.vue`

**Spec Reference:** §五 回答宽度优化

- [ ] **Step 1: 读取 AIChatPage.vue CSS 确认当前宽度**

Run: Read `frontend/apps/main/src/pages/AIChatPage.vue`, focus on `.bubble` CSS
Expected: 找到 `max-width: 86%` 或类似设置

- [ ] **Step 2: 修改 assistant bubble 宽度**

找到 `.bubble.assistant` 或 `.bubble` 样式，修改：

```css
.bubble.assistant {
  max-width: 95%;  /* 原为 86% */
}

/* Mobile breakpoint: 95% 在 ≤428px 可能与表格溢出冲突，保持 90% 作为安全值 */
@media (max-width: 428px) {
  .bubble.assistant {
    max-width: 90%;
  }
}
```

- [ ] **Step 3: 确保 agent-run-canvas 全宽**

添加或确认：

```css
.agent-run-canvas {
  width: 100%;
  max-width: 100%;
}
```

- [ ] **Step 4: 运行 frontend typecheck**

Run: `cd frontend/apps/main && pnpm typecheck`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add frontend/apps/main/src/pages/AIChatPage.vue
git commit -m "style(frontend): widen assistant bubble to 95%

- Increase max-width from 86% to 95%
- Ensure agent-run-canvas uses full width

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
```

---

## Task 7: Frontend Prompt 内容过滤增强

**Files:**
- Modify: `frontend/apps/main/src/utils/contentFilter.ts`

**Spec Reference:** §六 Prompt 内容过滤增强

- [ ] **Step 1: 读取 contentFilter.ts 确认当前过滤模式**

Run: Read `frontend/apps/main/src/utils/contentFilter.ts`
Expected: 找到 `FORBIDDEN_PATTERNS` 数组

- [ ] **Step 2: 添加新过滤模式**

扩展 `FORBIDDEN_PATTERNS` 数组：

```typescript
const FORBIDDEN_PATTERNS = [
  // ... 现有模式 ...

  // 新增：联网搜索、思考过程等提示词
  /^联网搜索[：:].*$/gm,
  /^正在搜索[：:].*$/gm,
  /^搜索结果[：:].*$/gm,
  /^思考过程[：:].*$/gm,
  /^分析过程[：:].*$/gm,
  /^推理步骤[：:].*$/gm,

  // DeerFlow/Agent 内部标识
  /^DeerFlow.*$/gm,
  /^Agent.*执行.*$/gm,
]
```

- [ ] **Step 3: 运行 frontend typecheck**

Run: `cd frontend/apps/main && pnpm typecheck`
Expected: PASS

- [ ] **Step 4: Commit**

```bash
git add frontend/apps/main/src/utils/contentFilter.ts
git commit -m "feat(frontend): enhance prompt content filtering

- Add patterns for 联网搜索/思考过程 prompts
- Add DeerFlow/Agent internal markers

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
```

---

## Task 8: Frontend Markdown 表格 CSS 样式

**Files:**
- Modify: `frontend/apps/main/src/components/ai/AiFinalAnswer.vue`

**Spec Reference:** §七.6 Markdown 表格渲染实现要点

- [ ] **Step 1: 读取 AiFinalAnswer.vue 确认 markdown 渲染**

Run: Read `frontend/apps/main/src/components/ai/AiFinalAnswer.vue`
Expected: 找到 `.answer-markdown` 或类似 CSS class

- [ ] **Step 2: 添加表格 CSS 样式**

在 `<style scoped>` 中添加：

```css
/* Markdown 表格样式 */
.answer-markdown :deep(table) {
  width: 100%;
  border-collapse: collapse;
  margin: 8px 0;
  overflow-x: auto;
  display: block;
  overscroll-behavior-x: contain;  /* 防止水平滑动触发父级垂直滚动 */
}

.answer-markdown :deep(th),
.answer-markdown :deep(td) {
  border: 1px solid var(--separator);
  padding: 6px 10px;
  text-align: left;
}

.answer-markdown :deep(th) {
  background: var(--bg-secondary);
  font-weight: 500;
}

.answer-markdown :deep(tr:nth-child(even) td) {
  background: var(--bg-secondary);
}
```

- [ ] **Step 3: 运行 frontend typecheck**

Run: `cd frontend/apps/main && pnpm typecheck`
Expected: PASS

- [ ] **Step 4: Commit**

```bash
git add frontend/apps/main/src/components/ai/AiFinalAnswer.vue
git commit -m "style(frontend): add markdown table CSS styles

- Add border and padding for th/td
- Add header background color
- Add even-row stripe pattern
- Support horizontal scroll for wide tables

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
```

---

## Verification Checkpoint

**Spec Coverage:**
- §一 Backend Journal 事件命名统一 → Task 1 ✓
- §二 Backend 持久化 Tool 事件 → Task 2, Task 3 ✓
- §三 Frontend Normalizer 兼容处理 → Task 4 ✓
- §四 Frontend UI 平滑过渡 → Task 5 ✓
- §五 回答宽度优化 → Task 6 ✓
- §六 Prompt 内容过滤增强 → Task 7 ✓
- §七.6 Markdown 表格 CSS → Task 8 ✓

**Placeholder Scan:** 1 处已知 TODO — Task 2 Step 3 `execution_time_ms=0` 标注 "streaming path lacks timing metadata"，接受为已知限制

**Type Consistency:**
- `session_journal.write_tool_call(tool_name, tool_id, arguments)` 参数顺序一致
- `session_journal.write_tool_result(tool_id, success, execution_time_ms)` 参数顺序一致
- **已知差异:** Journal payload 不含 `tool_type` / `data` 字段（与 streaming 事件结构差异），接受为存储简化决策
- **已知限制:** `execution_time_ms=0` 硬编码，streaming path 无 timing metadata，调试时需参考 wall-clock delta

---

## Risks and Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| Journal 写入失败影响 streaming | Medium | Task 2/3 用 try/except 包裹，失败不中断 streaming |
| 旧会话不兼容新格式 | High | Task 4 Normalizer fallback 处理旧格式 |
| CSS transition 移动端卡顿 | Low | Task 5 添加 `prefers-reduced-motion` 禁用动画 |
| Journal payload 缺失 tool_type/data 字段 | Low | 接受为存储简化决策，调试时参考 streaming 原始事件 |
| execution_time_ms 硬编码为 0 | Low | 接受为已知限制，session replay 时需重新计算 timing |
| args/result transition 策略与 DOM 结构潜在冲突 | Medium | 执行时验证 isExpanded 状态下的显示逻辑 |

---

## Open Questions

None — spec 已通过两轮验证，无阻塞问题。

---

## Design Decisions (Review Session)

| # | Question | Decision | Rationale |
|---|----------|----------|-----------|
| Q1 | args/result transition 策略 | **方案 A: args 自动折叠** | done/error 时 args 默认折叠，用户可手动展开。符合 spec §四 "compressed" 目标，transition 可顺序执行 |
| Q2 | tool_type/data payload parity | **方案 B: 接受差异** | Journal payload 简化存储效率高。当前需求为展示而非 replay，调试时参考 streaming 原始事件 |
| Q3 | execution_time_ms 计算 | **方案 B: 接受硬编码 0** | 保持 Plan 简洁。当前需求不需要 timing 分析，后续可扩展 |

**执行 Note:** Task 5 执行时验证 args v-if 条件与 isExpanded 的互斥逻辑，确保 `mode="out-in"` 有效。