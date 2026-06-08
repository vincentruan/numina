# Agent 执行过程交互优化 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 优化智能体问答页的 Agent 执行过程交互，修复用户问题重复、Prompt 泄漏、步骤显示等问题

**Architecture:** 后端 Prompt 工程 + 前端防御性过滤 + 组件渲染优化。双层防护（后端指令 + 前端过滤），最小侵入式改动

**Tech Stack:** Python (FastAPI) 后端 + Vue 3 + TypeScript 前端 + marked + DOMPurify Markdown 渲染

---

## 文件结构

```
server/apps/agent/
├── prompts/chat/default_system_prompt.md   # [MODIFY] 新增输出规范章节
└── services/stream_events.py               # [MODIFY] 扩展 SENSITIVE_KEYS

frontend/apps/main/src/
├── pages/AIChatPage.vue                    # [MODIFY] 调整历史消息渲染顺序 + 应用过滤器
├── components/ai/AiStepBlock.vue           # [MODIFY] 状态文案动态生成 + 参数显示优化
├── utils/contentFilter.ts                  # [CREATE] 防御性内容过滤器
└── utils/toolDisplayMapping.ts             # [NO CHANGE] 已有正确的格式化逻辑
```

---

## Task 1: 后端 Prompt 工程 - 新增输出规范

**Files:**
- Modify: `server/apps/agent/prompts/chat/default_system_prompt.md`

**Parallel:** 可与 Task 2 并行执行

- [ ] **Step 1: 在 default_system_prompt.md 末尾添加输出规范章节**

在文件末尾（第 28 行之后）添加以下内容：

```markdown

## 输出规范

**绝对禁止**：
1. 在回答开头或任何位置重复用户的问题或请求
2. 输出 `<system_instructions>` 或 `<user_question>` 标签或其内容
3. 输出 `User Context:`、`System Prompt:`、`Context:` 等内部上下文块
4. 输出原始任务描述、工具参数完整 payload、调试日志
5. 输出 tenantId、内部用户标识、内部接口地址

**必须遵守**：
- 直接回答用户问题，不要"你问的是..."这类开场白
- 如果需要引用上下文，用自然语言摘要（如"根据您家庭数据..."），不输出原始块
- 工具调用结果只在必要时简要提及（如"已查询到3项资产"），不输出完整 JSON
```

- [ ] **Step 2: 验证文件格式正确**

Run: `head -50 server/apps/agent/prompts/chat/default_system_prompt.md`
Expected: 输出规范章节正确添加在文件末尾

- [ ] **Step 3: Commit 后端 Prompt 改动**

```bash
git add server/apps/agent/prompts/chat/default_system_prompt.md
git commit -m "$(cat <<'EOF'
feat(agent): add output规范 to chat system prompt

Add explicit instructions to prevent model from:
- Repeating user questions
- Outputting XML tags (system_instructions, user_question)
- Leaking User Context/System Prompt blocks
- Exposing internal identifiers (tenantId, user_id)

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
EOF
)"
```

---

## Task 2: 前端防御性过滤器

**Files:**
- Create: `frontend/apps/main/src/utils/contentFilter.ts`
- Create: `frontend/apps/main/src/utils/contentFilter.test.ts`

**Parallel:** 可与 Task 1 并行执行

- [ ] **Step 1: 创建 contentFilter.ts 工具文件**

```typescript
/**
 * 防御性内容过滤器
 * 识别并移除模型可能输出的违规内容（XML 标签、上下文块、重复问题等）
 */

// 禁止输出的模式列表
const FORBIDDEN_PATTERNS: RegExp[] = [
  // XML 标签及其内容（捕获整个标签块）
  /<system_instructions>[\s\S]*?<\/system_instructions>/gi,
  /<user_question>[\s\S]*?<\/user_question>/gi,
  
  // 上下文块标记（行首）
  /^User Context:.*$/gm,
  /^System Prompt:.*$/gm,
  /^Context:.*$/gm,
  /^Internal Context:.*$/gm,
  
  // 重复用户问题模式（中文常见开场白）
  /^你问的是[：:].*$/gm,
  /^问题是[：:].*$/gm,
  /^您的问题是[：:].*$/gm,
  /^关于您问的[：:].*$/gm,
  
  // 内部标识符泄漏
  /^tenantId:.*$/gm,
  /^family_id:.*$/gm,
  /^user_id:.*$/gm,
  /^internal_user_id:.*$/gm,
]

/**
 * 过滤 AI 回答内容
 * @param raw 原始回答文本
 * @returns 过滤后的干净文本
 */
export function filterAIContent(raw: string): string {
  let filtered = raw
  
  for (const pattern of FORBIDDEN_PATTERNS) {
    filtered = filtered.replace(pattern, '')
  }
  
  // 清理多余空行（过滤后可能留下连续空行）
  filtered = filtered.replace(/\n{3,}/g, '\n\n')
  
  // 清理开头和结尾的空白
  return filtered.trim()
}
```

- [ ] **Step 2: 创建单元测试文件**

```typescript
import { describe, it, expect } from 'vitest'
import { filterAIContent } from './contentFilter'

describe('filterAIContent', () => {
  it('removes system_instructions XML tags', () => {
    const input = '这是回答开头<system_instructions>内部指令内容</system_instructions>这是正常内容'
    const output = filterAIContent(input)
    expect(output).not.toContain('<system_instructions>')
    expect(output).not.toContain('内部指令内容')
    expect(output).toContain('这是回答开头')
    expect(output).toContain('这是正常内容')
  })

  it('removes user_question XML tags', () => {
    const input = '<user_question>用户原始问题</user_question>这是AI回答'
    const output = filterAIContent(input)
    expect(output).not.toContain('<user_question>')
    expect(output).not.toContain('用户原始问题')
    expect(output).toBe('这是AI回答')
  })

  it('removes User Context blocks', () => {
    const input = 'User Context: {"family_id": "123"}\n正常回答内容'
    const output = filterAIContent(input)
    expect(output).not.toContain('User Context:')
    expect(output).not.toContain('family_id')
    expect(output).toContain('正常回答内容')
  })

  it('removes "你问的是" repeating patterns', () => {
    const input = '你问的是：我们家净资产是多少？\n根据查询结果...'
    const output = filterAIContent(input)
    expect(output).not.toContain('你问的是')
    expect(output).toContain('根据查询结果')
  })

  it('removes tenantId leakage', () => {
    const input = 'tenantId: 123456\n这是回答内容'
    const output = filterAIContent(input)
    expect(output).not.toContain('tenantId')
    expect(output).toBe('这是回答内容')
  })

  it('preserves normal content', () => {
    const input = '根据您家庭数据，当前净资产为 100 万元。'
    const output = filterAIContent(input)
    expect(output).toBe(input)
  })

  it('cleans up excessive blank lines', () => {
    const input = '内容A\n\n\n\n\n内容B'
    const output = filterAIContent(input)
    expect(output).toBe('内容A\n\n内容B')
  })

  it('handles empty input', () => {
    expect(filterAIContent('')).toBe('')
  })

  it('handles input with only forbidden content', () => {
    const input = '<system_instructions>指令</system_instructions>'
    const output = filterAIContent(input)
    expect(output).toBe('')
  })
})
```

- [ ] **Step 3: 运行测试验证过滤器工作正常**

Run: `cd frontend/apps/main && pnpm test:run src/utils/contentFilter.test.ts`
Expected: 所有测试通过

- [ ] **Step 4: Commit 前端过滤器**

```bash
git add frontend/apps/main/src/utils/contentFilter.ts frontend/apps/main/src/utils/contentFilter.test.ts
git commit -m "$(cat <<'EOF'
feat(frontend): add contentFilter for AI response sanitization

Defensive filter removes forbidden patterns:
- XML tags (system_instructions, user_question)
- Context blocks (User Context, System Prompt)
- Question repetition patterns ("你问的是")
- Internal identifiers (tenantId, family_id)

Dual protection layer with backend prompt engineering.

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
EOF
)"
```

---

## Task 3: 应用内容过滤器到 AIChatPage

**Files:**
- Modify: `frontend/apps/main/src/pages/AIChatPage.vue`

**Parallel:** 必须在 Task 2 完成后执行（依赖 contentFilter.ts）

- [ ] **Step 1: 导入 contentFilter 函数**

在第 539 行附近（其他 utils 导入之后）添加导入：

```typescript
import { filterAIContent } from '@/utils/contentFilter'
```

- [ ] **Step 2: 在 token.stream 处理中应用过滤器**

找到 `handleEvent` 函数中的 `token.stream` 处理部分（约第 1470-1487 行），修改如下：

```typescript
if (event.type === 'token.stream') {
  if (!thinkingDone && deepThink.value) {
    thinkingDone = true
    if (thinkTimer) { clearInterval(thinkTimer); thinkTimer = null }
    messages.value[msgIdx].thinkDone = true
    messages.value[msgIdx].thinkSeconds = Math.round((Date.now() - thinkStart) / 1000)
    if (!messages.value[msgIdx].thinkManuallyToggled) {
      messages.value[msgIdx].thinkOpen = false
    }
  }
  textRaw += event.token ?? ''
  // 应用内容过滤器，移除违规内容
  const filteredContent = filterAIContent(textRaw)
  messages.value[msgIdx].content = filteredContent
  renderMarkdownThrottled(filteredContent, messages.value[msgIdx])
  scrollToBottom()
  return
}
```

- [ ] **Step 3: 验证改动不破坏现有流式渲染**

检查 `renderMarkdownThrottled` 函数是否仍然正常工作。Run: `pnpm typecheck`
Expected: 类型检查通过，无错误

- [ ] **Step 4: Commit AIChatPage 改动**

```bash
git add frontend/apps/main/src/pages/AIChatPage.vue
git commit -m "$(cat <<'EOF'
feat(ai-chat): apply contentFilter to streaming tokens

Apply defensive content filter to AI response tokens before
markdown rendering. Removes forbidden patterns leaked by model.

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
EOF
)"
```

---

## Task 4: 历史消息渲染顺序调整

**Files:**
- Modify: `frontend/apps/main/src/pages/AIChatPage.vue`

**Parallel:** 可与 Task 5 并行执行

- [ ] **Step 1: 移除历史消息底部的 AiProcessFootnote**

找到第 333-342 行的 `AiProcessFootnote` 组件，修改条件使其只在实时消息中显示（移除 `phase === 'done'` 条件）：

```vue
<!-- U6: Process footnote 只用于实时消息执行过程 -->
<!-- 历史消息的执行过程移到 bubble-text 之前，不再需要底部脚注 -->
<AiProcessFootnote
  v-if="msg.role === 'assistant' && msg.phase !== 'done' && msg.phase !== 'error' && msg.processSteps && msg.processSteps.length > 0"
  :step-count="msg.processSteps.length"
  :expanded="msg.processExpanded ?? false"
  :status="msg.processStatus || 'done'"
  :elapsed-ms="msg.processElapsedMs || 0"
  :steps="msg.processSteps"
  :phase="msg.phase"
  @toggle="(expanded) => { msg.processExpanded = expanded }"
/>
```

- [ ] **Step 2: 在历史消息 bubble-text 之前添加执行过程卡片**

找到 `bubble-text` 渲染位置（约第 292-297 行），在其之前添加历史消息的执行过程渲染。

将现有逻辑扩展，让 `phase === 'done'` 的历史消息也在 bubble-text 之前显示执行过程：

```vue
<!-- 历史消息：执行过程在回答之前，默认折叠 -->
<AgentRunCanvas
  v-if="msg.role === 'assistant' && msg.phase === 'done' && shouldShowProcessBlock(msg) && shouldUseCanvas(msg)"
  :status="getProcessStatus(msg)"
  :elapsed-ms="msg.processElapsedMs || 0"
  :done-step-count="getDoneStepCount(msg)"
  :total-step-count="getTotalStepCount(msg)"
>
  <AiProcessBlock
    :status="getProcessStatus(msg)"
    :elapsed-ms="msg.processElapsedMs || 0"
    :steps="msg.processSteps || buildLegacySteps(msg)"
    :default-expanded="false"
    :phase="msg.phase"
    :reasoning-start-time="msg.reasoningStartTime ?? null"
    :plan-steps="msg.planSteps"
    :plan-source="msg.planSource"
  />
</AgentRunCanvas>
<AiProcessBlock
  v-else-if="msg.role === 'assistant' && msg.phase === 'done' && shouldShowProcessBlock(msg)"
  :status="getProcessStatus(msg)"
  :elapsed-ms="msg.processElapsedMs || 0"
  :steps="msg.processSteps || buildLegacySteps(msg)"
  :default-expanded="false"
  :phase="msg.phase"
  :reasoning-start-time="msg.reasoningStartTime ?? null"
  :plan-steps="msg.planSteps"
  :plan-source="msg.planSource"
/>

<!-- 最终回答 -->
<div
  v-if="msg.role === 'assistant' && msg.phase !== 'error'"
  class="bubble-text"
  :class="{ 'bubble-text--appearing': msg.content && msg.phase === 'answering' && !msg.renderedContent }"
  v-html="msg.renderedContent ?? ''"
/>
```

- [ ] **Step 3: 运行类型检查验证改动**

Run: `cd frontend/apps/main && pnpm typecheck`
Expected: 类型检查通过

- [ ] **Step 4: Commit 历史消息渲染改动**

```bash
git add frontend/apps/main/src/pages/AIChatPage.vue
git commit -m "$(cat <<'EOF'
feat(ai-chat): move historical process block before answer

Historical messages now show execution process before the final
answer (matching live message order). AiProcessFootnote removed
from bottom of historical messages. Default collapsed for cleaner UX.

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
EOF
)"
```

---

## Task 5: 步骤状态文案动态生成

**Files:**
- Modify: `frontend/apps/main/src/components/ai/AiStepBlock.vue`

**Parallel:** 可与 Task 4 并行执行

- [ ] **Step 1: 添加 statusText 计算属性**

在 `<script setup>` 部分，找到 `useToolStatusText` 的使用位置（约第 228-233 行），修改为使用 `displayName` 动态生成状态文案：

```typescript
// 状态文案动态生成（使用 MCP 描述）
const statusText = computed(() => {
  // 使用 displayName（如"获取家庭概览"）而非 name（如"numina-family-data_get_family_overview"）
  const baseName = props.displayName || props.name || '处理'
  
  // 动态添加状态后缀
  if (props.status === 'running') return `正在${baseName}`
  if (props.status === 'done') return `已${baseName}`
  if (props.status === 'error') return `${baseName}失败`
  if (props.status === 'streaming') return `${baseName}中...`
  return baseName
})
```

- [ ] **Step 2: 移除 useToolStatusText composable 导入**

移除不再需要的导入：

```typescript
// 移除这行：
// import { useToolStatusText } from '@/composables/useToolStatusText'
```

- [ ] **Step 3: 运行类型检查验证改动**

Run: `cd frontend/apps/main && pnpm typecheck`
Expected: 类型检查通过

- [ ] **Step 4: Commit 状态文案改动**

```bash
git add frontend/apps/main/src/components/ai/AiStepBlock.vue
git commit -m "$(cat <<'EOF'
feat(ai-step): use displayName for dynamic status text

Generate status text from MCP displayName instead of static mapping:
- running: "正在获取家庭概览"
- done: "已获取家庭概览"
- error: "获取家庭概览失败"

Backend _TOOL_REGISTRY is source of truth, frontend auto-adapts.

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
EOF
)"
```

---

## Task 6: 参数显示优化

**Files:**
- Modify: `frontend/apps/main/src/components/ai/AiStepBlock.vue`

**Parallel:** 必须在 Task 5 完成后执行

- [ ] **Step 1: 修改参数显示条件**

找到 `tool-args` div 的渲染逻辑（约第 69-72 行），修改条件让 done/error 状态默认隐藏参数：

```vue
<!-- 参数显示逻辑：running 或展开时显示 -->
<div 
  v-if="type === 'tool_call' && (status === 'running' || isExpanded)"
  class="tool-args"
  :class="{ 'args-running': status === 'running' }"
>
  <span v-if="!compressed" class="args-label">{{ t('aiProcess.argsLabel') }}</span>
  <span class="args-value">{{ argsSummary }}</span>
</div>
```

- [ ] **Step 2: 优化 argsSummary 格式（确保不出现"参数：参数："）**

检查 `formatArgsSummary` 函数调用，确保不产生重复前缀。在 `AiStepBlock.vue` 中找到 `argsSummary` 计算属性（约第 295-297 行）：

```typescript
// 确保 argsSummary 不重复 "参数：" 前缀
const argsSummary = computed(() => {
  const summary = formatArgsSummary(props.args || {}, toolDisplayInfo.value.argsTemplate)
  // 移除可能重复的 "参数：" 前缀
  if (summary.startsWith('参数：参数：')) {
    return summary.replace('参数：参数：', '参数：')
  }
  return summary
})
```

- [ ] **Step 3: 运行类型检查验证改动**

Run: `cd frontend/apps/main && pnpm typecheck`
Expected: 类型检查通过

- [ ] **Step 4: Commit 参数显示改动**

```bash
git add frontend/apps/main/src/components/ai/AiStepBlock.vue
git commit -m "$(cat <<'EOF'
feat(ai-step): hide args by default, show on expand only

- Running: show args summary (shimmer animation)
- Done/Error: hide args, show status only
- Expand: show full args (redacted)
- Fix duplicate "参数：参数：" prefix in argsSummary

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
EOF
)"
```

---

## Task 7: 后端脱敏字段扩展

**Files:**
- Modify: `server/apps/agent/services/stream_events.py`

**Parallel:** 可与任何 Task 并行执行

- [ ] **Step 1: 扩展 SENSITIVE_KEYS 脱敏字段**

找到 `SENSITIVE_KEYS` 定义（第 15-31 行），添加 Prompt 相关字段：

```python
SENSITIVE_KEYS: frozenset[str] = frozenset([
    "api_key",
    "apikey",
    "key",  # catch standalone "key" but not "keyboard" (exact match)
    "password",
    "pwd",
    "pass",  # catch standalone "pass" but not "compass" (exact match)
    "token",
    "access_token",
    "auth_token",
    "secret",
    "secret_key",
    "credential",
    "credentials",
    "private_key",
    "private",
    # 新增：Prompt 相关字段
    "system_prompt",
    "user_context",
    "internal_context",
    "task_description",
    "developer_prompt",
    "original_prompt",
])
```

- [ ] **Step 2: 验证改动不影响现有功能**

Run: `cd server && uv run pytest apps/agent/tests/unit/test_stream_events.py -v`（如果存在测试）
或运行: `cd server && uv run ruff check apps/agent/services/stream_events.py`
Expected: lint 检查通过

- [ ] **Step 3: Commit 脱敏字段扩展**

```bash
git add server/apps/agent/services/stream_events.py
git commit -m "$(cat <<'EOF'
feat(agent): extend SENSITIVE_KEYS with prompt-related fields

Add redaction for:
- system_prompt, user_context, internal_context
- task_description, developer_prompt, original_prompt

Prevents prompt leakage in tool arguments and results.

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
EOF
)"
```

---

## Task 8: 验证与测试

**Files:**
- Run manual tests as documented below

**Parallel:** 必须在所有 Task 完成后执行

- [ ] **Step 1: 运行前端类型检查**

Run: `cd frontend/apps/main && pnpm typecheck`
Expected: 无类型错误

- [ ] **Step 2: 运行前端测试**

Run: `cd frontend/apps/main && pnpm test:run`
Expected: 所有测试通过

- [ ] **Step 3: 运行后端 lint**

Run: `cd server && uv run ruff check apps/agent/`
Expected: 无 lint 错误

- [ ] **Step 4: 手动验证 - 普通短问答**

启动开发服务器，输入简单问题如"你好"，验证回答仍可用普通气泡展示。

- [ ] **Step 5: 手动验证 - "我们家净资产是多少？"**

输入问题，验证：
- 最终回答不重复用户问题
- 不出现 `<system_instructions>` 或 `User Context:` 
- 执行过程在回答之前
- 步骤状态文案友好（"正在获取家庭概览"、"已获取家庭概览"）

- [ ] **Step 6: 手动验证 - MCP 调用显示**

验证工具调用：
- 只显示一个步骤（不重复）
- running → done 状态在同一位置更新
- 默认不显示参数，点击展开后显示脱敏参数

- [ ] **Step 7: 手动验证 - Markdown 流式渲染**

让 Agent 输出一个 Markdown 表格，验证：
- 边输出边正确渲染
- 完成后格式完整
- 移动端窄屏下表格可横向滚动

- [ ] **Step 8: 手动验证 - 历史消息恢复**

刷新页面后重新进入同一会话，验证：
- 执行过程步骤正确恢复
- 最终回答正确显示

- [ ] **Step 9: Commit 最终验证状态**

```bash
git status
git log --oneline -10
```

---

## 自检清单

| 检查项 | 状态 |
|--------|------|
| Spec 覆盖完整 | [ ] 所有设计文档要求都有对应 Task |
| 无 Placeholder | [ ] 无 TBD/TODO/类似描述 |
| 类型一致性 | [ ] filterAIContent 类型签名一致、displayName 使用一致 |
| 文件路径准确 | [ ] 所有文件路径基于实际探索结果 |
| 测试覆盖 | [ ] contentFilter 有完整单元测试 |

---

## 执行顺序建议

```
Task 1 (Prompt) ─┬─► Task 3 (应用过滤器)
                 │
Task 2 (Filter) ─┘
                 
Task 4 (渲染顺序) ─┬─► Task 6 (参数优化)
                  │
Task 5 (状态文案) ─┘

Task 7 (脱敏) ───────► 可并行

Task 8 (验证) ───────► 必须最后
```

---

## 附录：验收标准汇总

1. ✅ 用户问题不重复进入 AI 回答
2. ✅ 不出现 `<system_instructions>`、`<user_question>` 标签
3. ✅ 不出现 `User Context:`、`System Prompt:` 上下文块
4. ✅ MCP 调用只显示一个步骤，状态在同一位置更新
5. ✅ 执行过程在回答之前（实时和历史消息）
6. ✅ 状态文案使用 displayName 动态生成
7. ✅ 参数默认隐藏，点击展开后显示脱敏内容
8. ✅ Markdown 流式渲染稳定
9. ✅ 刷新后执行过程正确恢复