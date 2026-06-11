# AI Chat 交互流程修复实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 修复 AI 聊天交互流程的两个核心问题：(1) MCP 工具状态重叠（运行中和已完成同时显示）；(2) 提示词原文内容泄漏。

**Architecture:** 后端去重 + 前端状态同步修复。核心修改在 `agent_dispatch.py` 的消息去重逻辑和 `AIChatPage.vue` 的 capability.end 处理。

**Tech Stack:** Python (FastAPI, LangGraph), TypeScript (Vue 3), SSE/NDJSON streaming

---

## 问题根因分析（基于浏览器测试调查）

| 问题 | 根因 | 证据 |
|------|------|------|
| MCP 工具状态重叠 | 后端发送重复的 tool.call 事件（同一工具调用两次），只有一个 tool.result → 第二个 ProcessStep 永远 stuck 在 "running" | SSE reqid=42: events 0006+0007 都是 `numina-family-data_get_family_overview`，只有 event 0008 有 result |
| 提示词原文泄漏 | 后端发送重复的 answer content（事件 0009+0010 内容完全相同），且 DeerFlow memory block 未完全过滤 | SSE reqid=42: events 0009+0010 相同；event 0004 `<system-reminder>` 泄漏 |
| Phase 不同步 | `AIChatPage.vue:1506-1510` capability.end handler 直接 return，未调用 `syncStepsToMessage()` 同步 normState.phase 到 message | 代码审查：handler return 后 normState.phase='done' 但 message.phase 未更新 |
| bubble-text 不渲染 | 条件 `msg.phase !== 'error'` 但 phase 未设置 → undefined !== 'error' 成立，但 canvas stuck 在 "执行中" 状态导致视觉混乱 | DOM 检查：实时流显示 "执行中"，reload 后显示 "已完成" |

---

## 文件结构

```
server/apps/agent/
└── services/
    └── agent_dispatch.py          # 核心：SSE 事件发送去重

frontend/apps/main/src/
├── pages/
│   └── AIChatPage.vue             # 核心：capability.end phase 同步
├── utils/
│   ├── aiEventNormalizer.ts       # ProcessStep 状态管理
│   └── contentFilter.ts           # 内容过滤（已有）
└── types/
    └── agent-stream.ts            # 类型定义
```

---

## Task 1: 后端事件去重（agent_dispatch.py）

**Files:**
- Modify: `server/apps/agent/services/agent_dispatch.py`

**Root cause:** `astream()` 返回的 agent graph events 中，某些节点被多次执行或消息被重复 yield。需要在 dispatch 层添加去重逻辑。

- [ ] **Step 1: 分析 agent_dispatch.py 的消息流**

首先理解当前的消息发送逻辑：

```bash
grep -n "yield" server/apps/agent/services/agent_dispatch.py | head -30
```

找到所有 yield 点，分析重复来源。

- [ ] **Step 2: 实现 tool.call 去重**

添加 `seen_tool_calls: Set[str]` 集合，在 yield tool.call 事件前检查：

```python
# 在 stream_capability 函数开头初始化
seen_tool_calls: set[str] = set()

# 在 yield tool.call 前
if event_type == "tool.call" and event.get("tool", {}).get("id"):
    tool_id = event["tool"]["id"]
    if tool_id in seen_tool_calls:
        logger.debug(f"[dedup] Skipping duplicate tool.call for {tool_id}")
        continue
    seen_tool_calls.add(tool_id)
```

- [ ] **Step 3: 实现 answer content 去重**

添加 `last_answer_hash: str` 变量，在连续发送相同内容时跳过：

```python
# 在 stream_capability 函数开头初始化
last_answer_hash: str = ""

# 在 yield token.stream 前（非 thinking）
if event_type == "token.stream" and not event.get("is_thinking"):
    content_hash = hashlib.md5(event.get("token", "").encode()).hexdigest()[:8]
    if content_hash == last_answer_hash:
        logger.debug(f"[dedup] Skipping duplicate answer token")
        continue
    last_answer_hash = content_hash
```

- [ ] **Step 4: 过滤 DeerFlow memory block**

在 yield 任何内容前，检查是否包含 `<system-reminder>` 或 DeerFlow 内部标识：

```python
# 定义过滤模式
DEERFLOW_FILTER_PATTERNS = [
    r"<system-reminder\b[^>]*>[\s\S]*?</system-reminder>",
    r"<memory\b[^>]*>[\s\S]*?</memory>",
    r"^User Context:.*$",
    r"^Personal:.*$",
    r"^Current Focus:.*$",
]

def _filter_deerflow_content(content: str) -> str:
    """Filter DeerFlow internal content before sending to frontend."""
    for pattern in DEERFLOW_FILTER_PATTERNS:
        content = re.sub(pattern, "", content, flags=re.MULTILINE | re.IGNORECASE)
    return content.strip()
```

- [ ] **Step 5: 验证修改**

```bash
# 重启 agent 服务
docker-compose up -d --build agent

# 测试去重是否生效
# 使用 Chrome DevTools MCP 验证 SSE 响应无重复
```

---

## Task 2: 前端 capability.end Phase 同步修复

**Files:**
- Modify: `frontend/apps/main/src/pages/AIChatPage.vue:1506-1510`

**Root cause:** capability.end handler 直接 return，未调用 syncStepsToMessage() 同步 normState.phase 到 message。

- [ ] **Step 1: 分析当前 capability.end handler**

当前代码（有问题）：

```typescript
// Lines 1506-1510
if (event.type === 'capability.end') {
  if (event.result?.suggestions?.length) {
    messages.value[msgIdx].suggestions = event.result.suggestions
  }
  return  // ← Bug: returns WITHOUT syncing phase!
}
```

- [ ] **Step 2: 修复 handler - 在 return 前同步 phase**

修改为：

```typescript
if (event.type === 'capability.end') {
  // ✅ 先同步 normState 的 phase 到 message
  syncStepsToMessage(normState, messages.value[msgIdx])
  
  if (event.result?.suggestions?.length) {
    messages.value[msgIdx].suggestions = event.result.suggestions
  }
  
  // 标记消息完成
  messages.value[msgIdx].isComplete = true
  
  // 终止流式渲染
  renderThrottleTimers.delete(msgId)
  return
}
```

- [ ] **Step 3: 确保 syncStepsToMessage 同步 phase**

检查 `syncStepsToMessage` 函数定义（Lines 1431-1432），确保它同步 phase：

```typescript
function syncStepsToMessage(state: NormalizationState, msg: AiMessage) {
  // 已有：同步 steps 数组
  msg.processSteps = state.steps.map(s => ({ ...s }))
  
  // 已有：同步 processStatus
  msg.processStatus = state.phase === 'done' ? 'done' : 'running'
  
  // ✅ 新增：同步 phase 字段
  msg.phase = state.phase
  
  // 同步其他字段...
  msg.artifacts = state.artifacts
  msg.planSteps = state.planSteps
}
```

- [ ] **Step 4: 验证修改**

```bash
cd frontend/apps/main && pnpm typecheck
```

Expected: No type errors.

---

## Task 3: 前端 tool.result 状态更新修复

**Files:**
- Modify: `frontend/apps/main/src/utils/aiEventNormalizer.ts:147-174`

**Root cause:** 当后端发送重复的 tool.call 时，创建两个 ProcessStep，但只有一个 tool.result 只更新第一个，第二个永远 stuck。

- [ ] **Step 1: 分析 tool.result 处理逻辑**

当前逻辑（Lines 147-174）只更新第一个匹配的 tool_call：

```typescript
const target = state.steps.find(
  (s): s is Extract<ProcessStep, { type: 'tool_call' }> =>
    s.type === 'tool_call' && s.id === toolId,
)
```

如果有两个相同 tool_id 的 ProcessStep，`find` 只返回第一个。

- [ ] **Step 2: 修改为更新所有匹配的 tool_call**

改为：

```typescript
// 更新所有相同 tool_id 的 tool_call 步骤
state.steps
  .filter((s): s is Extract<ProcessStep, { type: 'tool_call' }> =>
    s.type === 'tool_call' && s.id === toolId,
  )
  .forEach(target => {
    target.status = (event.result?.success ?? event.success ?? false) ? 'done' : 'error'
    target.resultSummary = event.result?.summary ?? event.summary
    target.data = event.result?.data ?? event.data
    const errorObj = event.result?.error ?? event.error
    target.error = typeof errorObj === 'string' ? errorObj : errorObj?.message
    target.elapsedMs = event.result?.execution_time_ms ?? event.executionTimeMs
  })

// 发送一个 tool_result 事件（前端只关心结果）
events.push({
  type: 'tool_result',
  toolCallId: toolId,
  success: event.result?.success ?? false,
  summary: event.result?.summary,
  error: typeof errorObj === 'string' ? errorObj : errorObj?.message,
  elapsedMs: event.result?.execution_time_ms,
})
```

- [ ] **Step 3: 验证修改**

```bash
cd frontend/apps/main && pnpm typecheck
```

Expected: No type errors.

---

## Task 4: 前端内容去重（token handler）

**Files:**
- Modify: `frontend/apps/main/src/pages/AIChatPage.vue:1488-1497`

**Root cause:** 后端发送重复的 answer content 时，前端 `textRaw += event.token` 会累积重复内容。

- [ ] **Step 1: 分析当前 token 处理逻辑**

当前代码（Lines 1488-1497）：

```typescript
textRaw += event.token ?? ''
const filteredContent = filterAIContent(textRaw, q)
messages.value[msgIdx].content = filteredContent
renderMarkdownThrottled(filteredContent, messages.value[msgIdx])
```

问题：每次收到 token 都追加到 textRaw，如果后端发送重复内容，textRaw 会包含重复。

- [ ] **Step 2: 添加内容去重逻辑**

修改为：

```typescript
// 非思考内容的去重
if (!event.is_thinking && event.token) {
  // 检查是否是重复内容（当前 textRaw 已包含此 token）
  const potentialNewRaw = textRaw + event.token
  const lastNChars = textRaw.slice(-100)
  
  // 如果新 token 与最近内容重叠，跳过
  if (lastNChars.includes(event.token) && event.token.length > 20) {
    console.debug('[dedup] Skipping duplicate answer token')
  } else {
    textRaw = potentialNewRaw
  }
} else if (event.is_thinking && event.token) {
  // 思考内容直接追加（不需要去重）
  // ... existing thinking logic
}

const filteredContent = filterAIContent(textRaw, q)
messages.value[msgIdx].content = filteredContent
renderMarkdownThrottled(filteredContent, messages.value[msgIdx])
```

- [ ] **Step 3: 更稳健的去重方案 - 使用 content hash**

更好的方案是跟踪已接收内容的 hash：

```typescript
// 在 SSE handler 作用域外初始化（每个消息流）
const receivedContentHashes = new Set<string>()

// 在 token handler 中
if (!event.is_thinking && event.token) {
  const tokenHash = hashString(event.token)
  if (receivedContentHashes.has(tokenHash) && event.token.length > 50) {
    console.debug('[dedup] Skipping duplicate token block')
  } else {
    receivedContentHashes.add(tokenHash)
    textRaw += event.token
  }
}

function hashString(str: string): string {
  // 简单 hash：用于去重
  let hash = 0
  for (let i = 0; i < str.length; i++) {
    hash = ((hash << 5) - hash) + str.charCodeAt(i)
    hash = hash & hash
  }
  return hash.toString(36)
}
```

- [ ] **Step 4: 验证修改**

```bash
cd frontend/apps/main && pnpm typecheck
```

Expected: No type errors.

---

## Task 5: 验证测试（浏览器自动化测试）

**Files:**
- Test: Browser testing with Chrome DevTools MCP

- [ ] **Step 1: 启动开发环境**

```bash
docker-compose up -d --build
```

- [ ] **Step 2: 使用 Chrome DevTools MCP 测试**

使用 `/agent-skills:browser-testing-with-devtools` skill:

1. Navigate to `http://localhost/ai`
2. Login as demouser
3. Click "数鸣智能体" preset question
4. Wait for response
5. Verify:
   - Tool calls show single status (not duplicated "running" + "done")
   - Answer content not duplicated
   - No DeerFlow memory block visible
   - Canvas shows "已完成" at completion
   - bubble-text renders correctly

- [ ] **Step 3: 检查 SSE 响应**

在 DevTools Network 面板中检查 SSE 响应：

- No duplicate tool.call events
- No duplicate token.stream events (same content)
- No `<system-reminder>` in any event

- [ ] **Step 4: 检查 Console**

```bash
# 前端 console 无错误
list_console_messages → assert zero errors
```

---

## Task 6: 提交修改

- [ ] **Step 1: 运行完整测试**

```bash
cd server && uv run pytest apps/agent/tests/ -v
cd frontend/apps/main && pnpm typecheck && pnpm test:run
```

- [ ] **Step 2: Git commit**

```bash
git add server/apps/agent/services/agent_dispatch.py
git add frontend/apps/main/src/pages/AIChatPage.vue
git add frontend/apps/main/src/utils/aiEventNormalizer.ts

git commit -m "fix(ai-chat): resolve interaction flow issues - tool status overlap and content duplication

Backend fixes:
- Add tool.call deduplication in agent_dispatch.py (seen_tool_calls set)
- Add answer content deduplication (content hash comparison)
- Filter DeerFlow memory blocks before sending to frontend

Frontend fixes:
- Fix capability.end handler to sync phase before return
- Update all matching tool_call steps on tool.result (not just first)
- Add token content deduplication in SSE handler

Root causes identified via Chrome DevTools MCP browser testing:
- Duplicate tool.call events caused stuck 'running' status
- Duplicate answer tokens caused visible content duplication
- capability.end returning without syncing phase caused '执行中' stuck state

Resolves: MCP tool status overlap, prompt content leakage, phase synchronization"
```

---

## Verification Checklist

| # | Check | Expected |
|---|-------|----------|
| 1 | Tool call status | Single status (not duplicated) |
| 2 | Answer content | No visible duplication |
| 3 | DeerFlow memory | Not visible in output |
| 4 | Canvas final state | "已完成" (not stuck "执行中") |
| 5 | bubble-text | Renders during and after stream |
| 6 | SSE response | No duplicate events |
| 7 | Console | Zero errors |

---

## Risk Mitigation

| Risk | Mitigation |
|------|------------|
| Dedup breaks valid retry | Only dedup within single stream session, hash comparison threshold > 50 chars |
| Phase sync breaks other flows | Test all AI capabilities after change |
| Filter removes needed content | Only filter known DeerFlow patterns, preserve user content |