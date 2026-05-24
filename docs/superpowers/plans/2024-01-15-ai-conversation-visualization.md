# AI Conversation Visualization Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement DeerFlow-inspired AI conversation visualization with unified process blocks and final answer components for `/ai/chat` and agent feature pages.

**Architecture:** Create reusable UI components (AiProcessBlock, AiProcessStep, AiToolCallStep, AiFinalAnswer) backed by utility adapters (aiEventNormalizer, toolDisplayMapping, contentTruncator). Integrate into existing pages without replacing core streaming logic.

**Tech Stack:** Vue 3 + TypeScript + Vant 4 + marked + DOMPurify. Reuse existing patterns from TaskConsole.vue and useAITask.ts.

---

## File Structure

| File | Purpose | Action |
|------|---------|--------|
| `src/utils/aiEventNormalizer.ts` | Normalize AgentEvent to unified UI events | Create |
| `src/utils/toolDisplayMapping.ts` | Map tool names to friendly Chinese labels | Create |
| `src/utils/contentTruncator.ts` | Truncate long tool args/results with expand | Create |
| `src/components/ai/AiProcessBlock.vue` | Container: header + step list | Create |
| `src/components/ai/AiProcessStep.vue` | Single step: reasoning or placeholder | Create |
| `src/components/ai/AiToolCallStep.vue` | Tool call step with args/result summary | Create |
| `src/components/ai/AiFinalAnswer.vue` | Final answer with streaming markdown | Create |
| `src/i18n/locales/zh-CN.ts` | New UI strings for process block | Modify |
| `src/i18n/locales/en-US.ts` | English translations for new strings | Modify |
| `src/pages/AIChatPage.vue` | Replace inline thinking block with AiProcessBlock | Modify |
| `src/types/agent-stream.ts` | Add NormalizedAiEvent type | Modify |

---

### Task 1: Create `aiEventNormalizer.ts` Utility

**Files:**
- Create: `frontend/apps/main/src/utils/aiEventNormalizer.ts`
- Modify: `frontend/apps/main/src/types/agent-stream.ts`

- [ ] **Step 1: Add NormalizedAiEvent type to agent-stream.ts**

Append to `frontend/apps/main/src/types/agent-stream.ts`:

```typescript
// Normalized event types for UI consumption
export type NormalizedAiEvent =
  | { type: 'phase_change'; phase: 'connecting' | 'thinking' | 'answering' | 'done' }
  | { type: 'reasoning_delta'; content: string }
  | { type: 'reasoning_done'; elapsedMs: number }
  | { type: 'tool_call'; toolCallId: string; name: string; displayName: string; icon: string; args: Record<string, unknown> }
  | { type: 'tool_running'; toolCallId: string }
  | { type: 'tool_result'; toolCallId: string; success: boolean; summary?: string; error?: string; elapsedMs?: number }
  | { type: 'answer_delta'; content: string }
  | { type: 'answer_done' }
  | { type: 'error'; message: string; code?: string }
  | { type: 'session_end' }

export interface NormalizationState {
  phase: 'connecting' | 'thinking' | 'answering' | 'done'
  reasoningContent: string
  reasoningStartTime: number | null
  answerContent: string
  toolCalls: Map<string, { name: string; displayName: string; icon: string; args: Record<string, unknown>; status: 'pending' | 'running' | 'done' | 'error'; resultSummary?: string; error?: string; elapsedMs?: number }>
}
```

- [ ] **Step 2: Create `frontend/apps/main/src/utils/aiEventNormalizer.ts`**

```typescript
import type { AgentEvent, NormalizedAiEvent, NormalizationState } from '@/types/agent-stream'

export function createNormalizationState(): NormalizationState {
  return {
    phase: 'connecting',
    reasoningContent: '',
    reasoningStartTime: null,
    answerContent: '',
    toolCalls: new Map(),
  }
}

export function normalizeAgentEvent(event: AgentEvent, state: NormalizationState): NormalizedAiEvent[] {
  const events: NormalizedAiEvent[] = []

  switch (event.type) {
    case 'phase.connecting':
      state.phase = 'connecting'
      events.push({ type: 'phase_change', phase: 'connecting' })
      break

    case 'phase.thinking':
      state.phase = 'thinking'
      if (!state.reasoningStartTime) state.reasoningStartTime = Date.now()
      events.push({ type: 'phase_change', phase: 'thinking' })
      break

    case 'phase.answering':
      state.phase = 'answering'
      if (state.reasoningStartTime && state.reasoningContent) {
        const elapsedMs = Date.now() - state.reasoningStartTime
        events.push({ type: 'reasoning_done', elapsedMs })
      }
      events.push({ type: 'phase_change', phase: 'answering' })
      break

    case 'token.stream':
      if (event.is_thinking && event.token) {
        state.reasoningContent += event.token
        events.push({ type: 'reasoning_delta', content: event.token })
      } else if (state.phase === 'answering' && event.token) {
        state.answerContent += event.token
        events.push({ type: 'answer_delta', content: event.token })
      }
      break

    case 'tool.call':
      if (event.tool) {
        state.toolCalls.set(event.tool.id, {
          name: event.tool.name,
          displayName: event.tool.display_name || event.tool.name,
          icon: event.tool.icon || '⚙️',
          args: event.tool.arguments || {},
          status: 'running',
        })
        events.push({
          type: 'tool_call',
          toolCallId: event.tool.id,
          name: event.tool.name,
          displayName: event.tool.display_name || event.tool.name,
          icon: event.tool.icon || '⚙️',
          args: event.tool.arguments || {},
        })
        events.push({ type: 'tool_running', toolCallId: event.tool.id })
      }
      break

    case 'tool.result':
      if (event.tool_id && state.toolCalls.has(event.tool_id)) {
        const tool = state.toolCalls.get(event.tool_id)!
        tool.status = event.result?.success ? 'done' : 'error'
        tool.resultSummary = event.result?.summary
        tool.error = event.result?.error
        tool.elapsedMs = event.result?.execution_time_ms
        events.push({
          type: 'tool_result',
          toolCallId: event.tool_id,
          success: event.result?.success ?? false,
          summary: event.result?.summary,
          error: event.result?.error,
          elapsedMs: event.result?.execution_time_ms,
        })
      }
      break

    case 'capability.end':
      state.phase = 'done'
      events.push({ type: 'phase_change', phase: 'done' })
      if (state.phase === 'answering') {
        events.push({ type: 'answer_done' })
      }
      events.push({ type: 'session_end' })
      break

    case 'capability.error':
      events.push({
        type: 'error',
        message: event.error?.message || event.message || 'Unknown error',
        code: event.error?.code || event.code,
      })
      break
  }

  return events
}
```

- [ ] **Step 3: Run typecheck**

Run: `cd frontend/apps/main && npm run typecheck`
Expected: PASS with no new errors

- [ ] **Step 4: Commit**

```bash
git add frontend/apps/main/src/types/agent-stream.ts frontend/apps/main/src/utils/aiEventNormalizer.ts
git commit -m "feat(ai): add aiEventNormalizer utility for unified event handling

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

### Task 2: Create `toolDisplayMapping.ts` Utility

**Files:**
- Create: `frontend/apps/main/src/utils/toolDisplayMapping.ts`

- [ ] **Step 1: Create tool display mapping utility**

```typescript
export interface ToolDisplayInfo {
  displayName: string
  icon: string
  argsTemplate: string
  resultTemplate: string
}

// Default fallback for unknown tools
const DEFAULT_DISPLAY: ToolDisplayInfo = {
  displayName: '调用工具',
  icon: '⚙️',
  argsTemplate: '参数：{args}',
  resultTemplate: '执行完成',
}

// Known tool mappings with Chinese friendly labels
const TOOL_DISPLAY_MAP: Record<string, ToolDisplayInfo> = {
  web_search: {
    displayName: '搜索文档',
    icon: '🔍',
    argsTemplate: '查询：{query}',
    resultTemplate: '找到 {count} 个结果',
  },
  read_file: {
    displayName: '读取文件',
    icon: '📄',
    argsTemplate: '文件：{path}',
    resultTemplate: '读取 {lines} 行',
  },
  write_file: {
    displayName: '写入文件',
    icon: '✏️',
    argsTemplate: '文件：{path}',
    resultTemplate: '写入 {lines} 行',
  },
  bash: {
    displayName: '执行命令',
    icon: '⚙️',
    argsTemplate: '命令：{command}',
    resultTemplate: '执行成功',
  },
  get_asset_list: {
    displayName: '获取资产列表',
    icon: '📊',
    argsTemplate: '筛选：{filter}',
    resultTemplate: '返回 {count} 条资产',
  },
  analyze_portfolio: {
    displayName: '分析资产组合',
    icon: '📈',
    argsTemplate: '资产范围：{scope}',
    resultTemplate: '生成分析报告',
  },
  get_liability_list: {
    displayName: '获取负债列表',
    icon: '📉',
    argsTemplate: '筛选：{filter}',
    resultTemplate: '返回 {count} 条负债',
  },
  calculate_net_worth: {
    displayName: '计算净资产',
    icon: '💰',
    argsTemplate: '时间范围：{period}',
    resultTemplate: '净资产 {value}',
  },
}

/**
 * Get display info for a tool, falling back to defaults for unknown tools.
 * Backend-provided display_name/icon take precedence when available.
 */
export function getToolDisplayInfo(
  toolName: string,
  backendDisplayName?: string,
  backendIcon?: string,
): ToolDisplayInfo {
  const mapping = TOOL_DISPLAY_MAP[toolName] || DEFAULT_DISPLAY

  return {
    displayName: backendDisplayName || mapping.displayName,
    icon: backendIcon || mapping.icon,
    argsTemplate: mapping.argsTemplate,
    resultTemplate: mapping.resultTemplate,
  }
}

/**
 * Format args summary using template or fallback to JSON truncation.
 */
export function formatArgsSummary(
  args: Record<string, unknown>,
  template: string,
  maxChars: number = 60,
): string {
  // Try template-based formatting
  const formatted = template.replace(/\{(\w+)\}/g, (_, key) => {
    const value = args[key]
    if (value === undefined) return ''
    if (typeof value === 'string') return value.length > maxChars ? value.slice(0, maxChars) + '...' : value
    return String(value)
  })

  // If template produced meaningful content, use it
  if (formatted !== template && formatted.length > 0) {
    return formatted
  }

  // Fallback: truncate JSON representation
  const json = JSON.stringify(args)
  return json.length > maxChars ? json.slice(0, maxChars) + '...' : json
}

/**
 * Format result summary using template or provided summary.
 */
export function formatResultSummary(
  result: unknown,
  template: string,
  providedSummary?: string,
  success: boolean = true,
  maxChars: number = 80,
): string {
  // Use backend-provided summary if available
  if (providedSummary) {
    return providedSummary.length > maxChars ? providedSummary.slice(0, maxChars) + '...' : providedSummary
  }

  // Template-based formatting for known result patterns
  if (result && typeof result === 'object') {
    const obj = result as Record<string, unknown>
    const formatted = template.replace(/\{(\w+)\}/g, (_, key) => {
      const value = obj[key]
      if (value === undefined) return ''
      return String(value)
    })
    if (formatted !== template) return formatted
  }

  // Success/error fallback
  return success ? '执行完成' : '执行失败'
}
```

- [ ] **Step 2: Run typecheck**

Run: `cd frontend/apps/main && npm run typecheck`
Expected: PASS

- [ ] **Step 3: Commit**

```bash
git add frontend/apps/main/src/utils/toolDisplayMapping.ts
git commit -m "feat(ai): add toolDisplayMapping for friendly Chinese labels

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

### Task 3: Create `contentTruncator.ts` Utility

**Files:**
- Create: `frontend/apps/main/src/utils/contentTruncator.ts`

- [ ] **Step 1: Create content truncation utility**

```typescript
export interface TruncationResult {
  truncated: string
  isTruncated: boolean
  fullContent: string
}

/**
 * Truncate text content with configurable max chars.
 * Returns both truncated and full content for expand/collapse UI.
 */
export function truncateContent(content: string, maxChars: number = 200): TruncationResult {
  if (!content) {
    return { truncated: '', isTruncated: false, fullContent: '' }
  }

  if (content.length <= maxChars) {
    return { truncated: content, isTruncated: false, fullContent: content }
  }

  return {
    truncated: content.slice(0, maxChars) + '...',
    isTruncated: true,
    fullContent: content,
  }
}

/**
 * Truncate JSON representation with configurable max chars.
 */
export function truncateJson(obj: unknown, maxChars: number = 300): TruncationResult {
  if (!obj) {
    return { truncated: '', isTruncated: false, fullContent: '' }
  }

  const fullJson = typeof obj === 'string' ? obj : JSON.stringify(obj, null, 2)

  if (fullJson.length <= maxChars) {
    return { truncated: fullJson, isTruncated: false, fullContent: fullJson }
  }

  // For objects, try to show structure hint
  if (typeof obj === 'object' && obj !== null) {
    const objType = Array.isArray(obj) ? `Array(${obj.length})` : `Object(${Object.keys(obj).length} keys)`
    return {
      truncated: `${objType} { ... }`,
      isTruncated: true,
      fullContent: fullJson,
    }
  }

  return {
    truncated: fullJson.slice(0, maxChars) + '...',
    isTruncated: true,
    fullContent: fullJson,
  }
}

/**
 * Calculate size label for truncated content (e.g., "2.3KB").
 */
export function formatContentSize(content: string): string {
  const bytes = new Blob([content]).size
  if (bytes < 1024) return `${bytes}B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)}KB`
  return `${(bytes / (1024 * 1024)).toFixed(1)}MB`
}
```

- [ ] **Step 2: Run typecheck**

Run: `cd frontend/apps/main && npm run typecheck`
Expected: PASS

- [ ] **Step 3: Commit**

```bash
git add frontend/apps/main/src/utils/contentTruncator.ts
git commit -m "feat(ai): add contentTruncator for long args/result handling

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

### Task 4: Create `AiProcessBlock.vue` Component

**Files:**
- Create: `frontend/apps/main/src/components/ai/AiProcessBlock.vue`

- [ ] **Step 1: Create AiProcessBlock component**

```vue
<template>
  <div class="ai-process-block" :class="{ 'is-collapsed': !isExpanded }">
    <!-- Header -->
    <div class="process-header" @click="toggleExpand">
      <div class="process-icon" :class="statusClass">
        <span class="icon-symbol">{{ statusIcon }}</span>
      </div>
      <div class="process-info">
        <span class="process-title">{{ t('aiProcess.title') }}</span>
        <span class="process-status">{{ statusLabel }}</span>
      </div>
      <span class="process-elapsed">{{ formattedElapsed }}</span>
      <van-icon :name="isExpanded ? 'arrow-down' : 'arrow-up'" class="process-toggle" />
    </div>

    <!-- Body (collapsible) -->
    <div v-show="isExpanded" class="process-body">
      <!-- Reasoning step -->
      <AiProcessStep
        v-if="reasoningContent"
        type="reasoning"
        :content="reasoningContent"
        :status="reasoningStatus"
        :elapsed-ms="reasoningElapsedMs"
      />

      <!-- Tool call steps -->
      <AiToolCallStep
        v-for="step in toolSteps"
        :key="step.id"
        :tool-call-id="step.id"
        :tool-name="step.name"
        :display-name="step.displayName"
        :icon="step.icon"
        :args="step.args"
        :status="step.status"
        :result-summary="step.resultSummary"
        :error="step.error"
        :elapsed-ms="step.elapsedMs"
      />

      <!-- Empty running state -->
      <div v-if="status === 'running' && !reasoningContent && toolSteps.length === 0" class="process-empty">
        <van-loading size="14" type="spinner" />
        <span>{{ t('aiProcess.connecting') }}</span>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import AiProcessStep from './AiProcessStep.vue'
import AiToolCallStep from './AiToolCallStep.vue'

interface ToolStep {
  id: string
  name: string
  displayName: string
  icon: string
  args: Record<string, unknown>
  status: 'pending' | 'running' | 'done' | 'error'
  resultSummary?: string
  error?: string
  elapsedMs?: number
}

const props = defineProps<{
  status: 'running' | 'done' | 'error'
  elapsedMs: number
  reasoningContent?: string
  reasoningStatus?: 'streaming' | 'done'
  reasoningElapsedMs?: number
  toolSteps: ToolStep[]
  defaultExpanded?: boolean
}>()

const emit = defineEmits<{
  (e: 'toggle-expand', expanded: boolean): void
}>()

const { t } = useI18n()
const isExpanded = ref(props.defaultExpanded ?? props.status === 'running')

function toggleExpand() {
  isExpanded.value = !isExpanded.value
  emit('toggle-expand', isExpanded.value)
}

// Auto-collapse when status changes to done
watch(
  () => props.status,
  (val, prev) => {
    if (val === 'done' && prev === 'running') {
      isExpanded.value = false
    }
    if (val === 'running' && prev !== 'running') {
      isExpanded.value = true
    }
  },
)

const statusIcon = computed(() => {
  switch (props.status) {
    case 'running': return '✦'
    case 'done': return '✓'
    case 'error': return '✗'
    default: return '✦'
  }
})

const statusClass = computed(() => {
  switch (props.status) {
    case 'running': return 'status-running'
    case 'done': return 'status-done'
    case 'error': return 'status-error'
    default: return ''
  }
})

const statusLabel = computed(() => {
  switch (props.status) {
    case 'running': return t('aiProcess.statusRunning')
    case 'done': return t('aiProcess.statusDone')
    case 'error': return t('aiProcess.statusError')
    default: return ''
  }
})

const formattedElapsed = computed(() => {
  const ms = props.elapsedMs
  if (ms < 1000) return `${ms}ms`
  const s = Math.floor(ms / 1000)
  if (s < 60) return `${s}s`
  return `${Math.floor(s / 60)}m${s % 60}s`
})
</script>

<style scoped>
.ai-process-block {
  margin: 12px 0;
  border-radius: 10px;
  background: linear-gradient(135deg, #f5f3ff 0%, #ede9fe 100%);
  border: 1px solid #c4b5fd;
  overflow: hidden;
}

.is-collapsed {
  background: linear-gradient(135deg, #f0fdf4 0%, #dcfce7 100%);
  border-color: #86efac;
}

.process-header {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 12px 14px;
  cursor: pointer;
  user-select: none;
}

.process-icon {
  width: 28px;
  height: 28px;
  border-radius: 6px;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.status-running {
  background: linear-gradient(135deg, #8b5cf6, #a78bfa);
  animation: pulse 1.5s ease-in-out infinite;
}

.status-done {
  background: linear-gradient(135deg, #22c55e, #16a34a);
}

.status-error {
  background: linear-gradient(135deg, #dc2626, #b91c1c);
}

.icon-symbol {
  font-size: 14px;
  color: white;
}

@keyframes pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.6; }
}

.process-info {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.process-title {
  font-size: 13px;
  font-weight: 500;
  color: #4f46e5;
}

.is-collapsed .process-title {
  color: #166534;
}

.process-status {
  font-size: 12px;
  color: #a5b4fc;
}

.is-collapsed .process-status {
  color: #22c55e;
}

.process-elapsed {
  font-size: 12px;
  color: #94a3b8;
  font-variant-numeric: tabular-nums;
}

.process-toggle {
  color: #8b5cf6;
  font-size: 16px;
}

.is-collapsed .process-toggle {
  color: #22c55e;
}

.process-body {
  padding: 10px 14px;
  border-top: 1px solid #ddd6fe;
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.is-collapsed .process-body {
  border-top-color: #86efac;
}

.process-empty {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 13px;
  color: var(--text-secondary);
}
</style>
```

- [ ] **Step 2: Run typecheck**

Run: `cd frontend/apps/main && npm run typecheck`
Expected: PASS (AiProcessStep and AiToolCallStep not yet created - will error)

- [ ] **Step 3: Proceed to Task 5 to create dependent components before re-running typecheck**

---

### Task 5: Create `AiProcessStep.vue` and `AiToolCallStep.vue` Components

**Files:**
- Create: `frontend/apps/main/src/components/ai/AiProcessStep.vue`
- Create: `frontend/apps/main/src/components/ai/AiToolCallStep.vue`

- [ ] **Step 1: Create AiProcessStep component**

```vue
<template>
  <div class="ai-process-step">
    <div class="step-marker" :class="markerClass">
      <span class="marker-icon">{{ markerIcon }}</span>
    </div>
    <div class="step-content">
      <div class="step-header">
        <span class="step-title">{{ t('aiProcess.stepReasoning') }}</span>
        <span v-if="elapsedMs" class="step-time">{{ formatElapsedMs(elapsedMs) }}</span>
      </div>
      <div class="step-body">
        <div v-if="showFullContent" class="reasoning-full">{{ content }}</div>
        <div v-else class="reasoning-truncated">{{ truncatedContent }}</div>
        <button
          v-if="isTruncated"
          class="expand-btn"
          @click="showFullContent = !showFullContent"
        >
          {{ showFullContent ? t('aiProcess.collapse') : t('aiProcess.expand') }}
        </button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { truncateContent } from '@/utils/contentTruncator'

const props = defineProps<{
  type: 'reasoning'
  content: string
  status: 'streaming' | 'done'
  elapsedMs?: number
}>()

const { t } = useI18n()
const showFullContent = ref(false)

const markerIcon = computed(() => {
  switch (props.status) {
    case 'streaming': return '💭'
    case 'done': return '✓'
    default: return '○'
  }
})

const markerClass = computed(() => {
  switch (props.status) {
    case 'streaming': return 'marker-streaming'
    case 'done': return 'marker-done'
    default: return ''
  }
})

const { truncated, isTruncated } = truncateContent(props.content, 150)
const truncatedContent = truncated

function formatElapsedMs(ms: number): string {
  if (ms < 1000) return `${ms}ms`
  return `${Math.floor(ms / 1000)}s`
}
</script>

<style scoped>
.ai-process-step {
  display: flex;
  align-items: flex-start;
  gap: 12px;
}

.step-marker {
  width: 20px;
  height: 20px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.marker-streaming {
  background: #fbbf24;
  animation: pulse 1s infinite;
}

.marker-done {
  background: #22c55e;
}

@keyframes pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.6; }
}

.marker-icon {
  font-size: 11px;
  color: white;
}

.step-content {
  flex: 1;
  min-width: 0;
}

.step-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 6px;
}

.step-title {
  font-size: 13px;
  font-weight: 500;
  color: #374151;
}

.step-time {
  font-size: 11px;
  color: #94a3b8;
}

.step-body {
  padding: 8px 10px;
  background: white;
  border-radius: 6px;
  border: 1px solid #e2e8f0;
  font-size: 12px;
  color: #6b7280;
  line-height: 1.6;
  white-space: pre-wrap;
  word-break: break-word;
}

.reasoning-truncated {
  color: #6b7280;
}

.reasoning-full {
  color: #374151;
}

.expand-btn {
  margin-top: 6px;
  padding: 4px 8px;
  font-size: 11px;
  color: #60a5fa;
  background: none;
  border: none;
  cursor: pointer;
}

.expand-btn:hover {
  text-decoration: underline;
}
</style>
```

- [ ] **Step 2: Create AiToolCallStep component**

```vue
<template>
  <div class="ai-tool-call-step">
    <div class="step-marker" :class="markerClass">
      <span class="marker-icon">{{ statusIcon }}</span>
    </div>
    <div class="step-content">
      <div class="step-header">
        <div class="step-title-row">
          <span class="tool-icon">{{ displayIcon }}</span>
          <span class="step-title">{{ displayName }}</span>
          <span class="tool-badge">{{ toolName }}</span>
        </div>
        <span v-if="elapsedMs" class="step-time">{{ formatElapsedMs(elapsedMs) }}</span>
      </div>

      <!-- Args summary -->
      <div class="step-args" :class="{ 'args-running': status === 'running' }">
        <span class="args-label">{{ t('aiProcess.argsLabel') }}</span>
        <span class="args-value">{{ argsSummary }}</span>
      </div>

      <!-- Result summary -->
      <div v-if="status === 'done' || status === 'error'" class="step-result" :class="resultClass">
        <span class="result-icon">{{ resultStatusIcon }}</span>
        <span class="result-text">{{ resultText }}</span>
        <button
          v-if="showExpandBtn"
          class="expand-btn"
          @click="showFullResult = !showFullResult"
        >
          {{ showFullResult ? t('aiProcess.collapse') : t('aiProcess.expand') }}
        </button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { getToolDisplayInfo, formatArgsSummary, formatResultSummary } from '@/utils/toolDisplayMapping'
import { truncateJson } from '@/utils/contentTruncator'

const props = defineProps<{
  toolCallId: string
  toolName: string
  displayName?: string
  icon?: string
  args: Record<string, unknown>
  status: 'pending' | 'running' | 'done' | 'error'
  resultSummary?: string
  error?: string
  elapsedMs?: number
}>()

const { t } = useI18n()
const showFullResult = ref(false)

const displayInfo = getToolDisplayInfo(props.toolName, props.displayName, props.icon)
const displayName = displayInfo.displayName
const displayIcon = displayInfo.icon

const statusIcon = computed(() => {
  switch (props.status) {
    case 'pending': return '○'
    case 'running': return '⚙'
    case 'done': return '✓'
    case 'error': return '✗'
    default: return '○'
  }
})

const markerClass = computed(() => {
  switch (props.status) {
    case 'pending': return 'marker-pending'
    case 'running': return 'marker-running'
    case 'done': return 'marker-done'
    case 'error': return 'marker-error'
    default: return ''
  }
})

const argsSummary = formatArgsSummary(props.args, displayInfo.argsTemplate)

const resultStatusIcon = computed(() => props.status === 'done' ? '✓' : '✗')

const resultClass = computed(() => props.status === 'done' ? 'result-success' : 'result-error')

const resultText = computed(() => {
  if (props.error) return props.error
  if (showFullResult.value) return truncateJson(props.resultSummary).fullContent
  return formatResultSummary(undefined, displayInfo.resultTemplate, props.resultSummary, props.status === 'done')
})

const showExpandBtn = computed(() => {
  if (!props.resultSummary) return false
  return typeof props.resultSummary === 'string' && props.resultSummary.length > 80
})

function formatElapsedMs(ms: number): string {
  if (ms < 1000) return `${ms}ms`
  return `${Math.floor(ms / 1000)}s`
}
</script>

<style scoped>
.ai-tool-call-step {
  display: flex;
  align-items: flex-start;
  gap: 12px;
}

.step-marker {
  width: 20px;
  height: 20px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.marker-pending { background: #94a3b8; }
.marker-running { background: #3b82f6; animation: pulse 1s infinite; }
.marker-done { background: #22c55e; }
.marker-error { background: #dc2626; }

@keyframes pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.6; }
}

.marker-icon {
  font-size: 10px;
  color: white;
}

.step-content {
  flex: 1;
  min-width: 0;
}

.step-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 6px;
}

.step-title-row {
  display: flex;
  align-items: center;
  gap: 6px;
}

.tool-icon {
  font-size: 13px;
}

.step-title {
  font-size: 13px;
  font-weight: 500;
  color: #374151;
}

.tool-badge {
  font-size: 11px;
  color: #1d4ed8;
  background: #dbeafe;
  padding: 2px 6px;
  border-radius: 4px;
}

.step-time {
  font-size: 11px;
  color: #94a3b8;
}

.step-args {
  padding: 8px 10px;
  background: #eff6ff;
  border-radius: 6px;
  border: 1px solid #bfdbfe;
  margin-bottom: 6px;
  font-size: 12px;
}

.args-running {
  animation: shimmer 1.5s infinite;
  background: linear-gradient(90deg, #eff6ff 25%, #dbeafe 50%, #eff6ff 75%);
  background-size: 200%;
}

@keyframes shimmer {
  0% { background-position: 200% center; }
  100% { background-position: -200% center; }
}

.args-label {
  color: #1e40af;
  margin-right: 4px;
}

.args-value {
  color: #3b82f6;
}

.step-result {
  padding: 8px 10px;
  background: white;
  border-radius: 6px;
  border: 1px solid #e2e8f0;
  display: flex;
  align-items: flex-start;
  gap: 6px;
  font-size: 12px;
}

.result-success {
  border-color: #86efac;
}

.result-error {
  border-color: #fca5a5;
  background: #fef2f2;
}

.result-icon {
  flex-shrink: 0;
}

.result-success .result-icon { color: #22c55e; }
.result-error .result-icon { color: #dc2626; }

.result-text {
  flex: 1;
  color: #374151;
  white-space: pre-wrap;
  word-break: break-word;
}

.expand-btn {
  flex-shrink: 0;
  padding: 4px 8px;
  font-size: 11px;
  color: #60a5fa;
  background: none;
  border: none;
  cursor: pointer;
}

.expand-btn:hover {
  text-decoration: underline;
}
</style>
```

- [ ] **Step 3: Run typecheck**

Run: `cd frontend/apps/main && npm run typecheck`
Expected: PASS

- [ ] **Step 4: Commit**

```bash
git add frontend/apps/main/src/components/ai/AiProcessBlock.vue frontend/apps/main/src/components/ai/AiProcessStep.vue frontend/apps/main/src/components/ai/AiToolCallStep.vue
git commit -m "feat(ai): add AiProcessBlock, AiProcessStep, AiToolCallStep components

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

### Task 6: Create `AiFinalAnswer.vue` Component

**Files:**
- Create: `frontend/apps/main/src/components/ai/AiFinalAnswer.vue`

- [ ] **Step 1: Create AiFinalAnswer component**

```vue
<template>
  <div class="ai-final-answer" :class="{ 'is-report': isReport, 'is-streaming': streaming }">
    <!-- Report header (optional) -->
    <div v-if="isReport && reportTitle" class="answer-report-header">
      <span class="report-icon">📊</span>
      <span class="report-title">{{ reportTitle }}</span>
      <span v-if="reportMeta" class="report-meta">{{ reportMeta.generatedAt }}</span>
    </div>

    <!-- Answer content -->
    <div ref="contentRef" class="answer-content">
      <!-- eslint-disable-next-line vue/no-v-html -- sanitized via DOMPurify -->
      <div class="answer-markdown" v-html="renderedContent" />
      <span v-if="streaming" class="answer-cursor" aria-hidden="true">▋</span>
    </div>

    <!-- Actions -->
    <div v-if="!streaming && showActions" class="answer-actions">
      <button class="action-btn" @click="copyContent">
        <van-icon name="description" />
        <span>{{ t('aiProcess.copy') }}</span>
      </button>
      <button v-if="showRegenerate" class="action-btn" @click="$emit('regenerate')">
        <van-icon name="refresh" />
        <span>{{ t('aiProcess.regenerate') }}</span>
      </button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { showToast } from 'vant'
import { marked } from 'marked'
import DOMPurify from 'dompurify'

const props = defineProps<{
  content: string
  streaming?: boolean
  isReport?: boolean
  reportTitle?: string
  reportMeta?: { generatedAt: string; itemCount?: number }
  showActions?: boolean
  showRegenerate?: boolean
}>()

const emit = defineEmits<{
  (e: 'regenerate'): void
}>()

const { t } = useI18n()
const contentRef = ref<HTMLElement | null>(null)
let scrollRAF: number | null = null

const renderedContent = computed(() => {
  if (!props.content) return ''
  try {
    const html = marked.parse(props.content, { async: false }) as string
    return DOMPurify.sanitize(html)
  } catch {
    return DOMPurify.sanitize(props.content)
  }
})

// Auto-scroll during streaming
watch(
  () => props.content,
  () => {
    if (!props.streaming) return
    if (scrollRAF) return
    scrollRAF = requestAnimationFrame(() => {
      scrollRAF = null
      contentRef.value?.scrollIntoView({ behavior: 'smooth', block: 'end' })
    })
  },
)

async function copyContent() {
  try {
    await navigator.clipboard.writeText(props.content)
    showToast(t('aiProcess.copySuccess'))
  } catch {
    showToast(t('aiProcess.copyFailed'))
  }
}
</script>

<style scoped>
.ai-final-answer {
  background: white;
  border-radius: 12px;
  padding: 14px;
  box-shadow: 0 1px 2px rgba(0, 0, 0, 0.06);
}

.is-report {
  padding: 16px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.08);
}

.answer-report-header {
  display: flex;
  align-items: center;
  gap: 10px;
  padding-bottom: 12px;
  border-bottom: 1px solid #f1f5f9;
  margin-bottom: 12px;
}

.report-icon {
  font-size: 20px;
  background: linear-gradient(135deg, #10b981, #059669);
  color: white;
  width: 32px;
  height: 32px;
  border-radius: 8px;
  display: flex;
  align-items: center;
  justify-content: center;
}

.report-title {
  font-size: 16px;
  font-weight: 600;
  color: #1f2937;
}

.report-meta {
  margin-left: auto;
  font-size: 12px;
  color: #94a3b8;
}

.answer-content {
  font-size: 14px;
  color: var(--text-primary);
  line-height: 1.7;
}

.answer-markdown :deep(p) { margin: 0 0 8px; }
.answer-markdown :deep(p:last-child) { margin-bottom: 0; }
.answer-markdown :deep(ul), .answer-markdown :deep(ol) { padding-left: 18px; margin: 4px 0 8px; }
.answer-markdown :deep(li) { margin-bottom: 4px; }
.answer-markdown :deep(strong) { color: var(--text-primary); }
.answer-markdown :deep(code) { background: var(--bg-secondary); padding: 1px 4px; border-radius: 3px; font-size: 12px; }
.answer-markdown :deep(pre) { background: var(--bg-secondary); padding: 10px; border-radius: 6px; overflow-x: auto; }
.answer-markdown :deep(pre code) { background: none; padding: 0; }

.answer-cursor {
  display: inline-block;
  animation: blink 1s step-end infinite;
  color: var(--color-primary);
  margin-left: 1px;
}

@keyframes blink {
  0%, 100% { opacity: 1; }
  50% { opacity: 0; }
}

.answer-actions {
  display: flex;
  gap: 8px;
  margin-top: 12px;
  padding-top: 12px;
  border-top: 1px solid #f1f5f9;
}

.action-btn {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 8px 12px;
  font-size: 13px;
  color: #64748b;
  background: #f1f5f9;
  border: none;
  border-radius: 6px;
  cursor: pointer;
}

.action-btn:hover {
  background: #e2e8f0;
}
</style>
```

- [ ] **Step 2: Run typecheck**

Run: `cd frontend/apps/main && npm run typecheck`
Expected: PASS

- [ ] **Step 3: Commit**

```bash
git add frontend/apps/main/src/components/ai/AiFinalAnswer.vue
git commit -m "feat(ai): add AiFinalAnswer component for markdown rendering

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

### Task 7: Add i18n Keys for New UI Strings

**Files:**
- Modify: `frontend/apps/main/src/i18n/locales/zh-CN.ts`
- Modify: `frontend/apps/main/src/i18n/locales/en-US.ts`

- [ ] **Step 1: Add aiProcess keys to zh-CN.ts**

Add after the `aiChat` section in `frontend/apps/main/src/i18n/locales/zh-CN.ts`:

```typescript
  aiProcess: {
    title: '执行过程',
    statusRunning: '正在执行',
    statusDone: '已完成',
    statusError: '执行出错',
    connecting: '正在连接...',
    stepReasoning: '思考',
    argsLabel: '参数：',
    collapse: '收起',
    expand: '展开',
    copy: '复制',
    copySuccess: '✅ 已复制',
    copyFailed: '❌ 复制失败',
    regenerate: '重新生成',
  },
```

- [ ] **Step 2: Add aiProcess keys to en-US.ts**

Add the corresponding English translations in `frontend/apps/main/src/i18n/locales/en-US.ts`:

```typescript
  aiProcess: {
    title: 'Execution Process',
    statusRunning: 'Running',
    statusDone: 'Completed',
    statusError: 'Error',
    connecting: 'Connecting...',
    stepReasoning: 'Thinking',
    argsLabel: 'Args: ',
    collapse: 'Collapse',
    expand: 'Expand',
    copy: 'Copy',
    copySuccess: '✅ Copied',
    copyFailed: '❌ Copy failed',
    regenerate: 'Regenerate',
  },
```

- [ ] **Step 3: Run typecheck**

Run: `cd frontend/apps/main && npm run typecheck`
Expected: PASS

- [ ] **Step 4: Commit**

```bash
git add frontend/apps/main/src/i18n/locales/zh-CN.ts frontend/apps/main/src/i18n/locales/en-US.ts
git commit -m "feat(ai/i18n): add aiProcess keys for new components

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

### Task 8: Integrate into AIChatPage.vue (MVP - Minimal Integration)

**Files:**
- Modify: `frontend/apps/main/src/pages/AIChatPage.vue`

- [ ] **Step 1: Import new components**

Add imports at the top of the script section:

```typescript
import AiProcessBlock from '@/components/ai/AiProcessBlock.vue'
import AiFinalAnswer from '@/components/ai/AiFinalAnswer.vue'
import { createNormalizationState, normalizeAgentEvent } from '@/utils/aiEventNormalizer'
import type { NormalizationState } from '@/types/agent-stream'
```

- [ ] **Step 2: Add normalization state to Message interface**

Extend the `Message` interface to include process block data:

```typescript
interface Message {
  id: string
  role: 'user' | 'assistant'
  phase?: 'connecting' | 'thinking' | 'answering' | 'done' | 'error' | 'interrupted'
  content: string
  // Existing thinking fields (keep for backward compat)
  thinkContent?: string
  thinkOpen?: boolean
  thinkDone?: boolean
  thinkSeconds?: number
  thinkManuallyToggled?: boolean
  // New process block fields
  processStatus?: 'running' | 'done' | 'error'
  processElapsedMs?: number
  processSteps?: ToolStep[]
  // ToolTimelineItem kept for reference
  toolTimeline?: ToolTimelineItem[]
}
```

- [ ] **Step 3: Replace inline thinking block with AiProcessBlock in template**

Locate the existing thinking/tool timeline display in the assistant message template and replace with:

```vue
<!-- Process block (replaces inline thinking block) -->
<AiProcessBlock
  v-if="msg.phase && msg.phase !== 'done' && msg.phase !== 'error'"
  :status="msg.processStatus || (msg.phase === 'answering' ? 'running' : 'running')"
  :elapsed-ms="msg.processElapsedMs || 0"
  :reasoning-content="msg.thinkContent"
  :reasoning-status="msg.phase === 'thinking' ? 'streaming' : 'done'"
  :reasoning-elapsed-ms="msg.thinkSeconds ? msg.thinkSeconds * 1000 : undefined"
  :tool-steps="msg.processSteps || []"
  :default-expanded="msg.phase !== 'done'"
/>

<!-- Final answer -->
<AiFinalAnswer
  v-if="msg.content || msg.phase === 'answering'"
  :content="msg.content"
  :streaming="msg.phase === 'answering'"
  :show-actions="msg.phase === 'done'"
  :show-regenerate="msg.phase === 'done' && isLastAssistantMessage(msg.id)"
  @regenerate="handleRegenerate(msg)"
/>
```

- [ ] **Step 4: Run typecheck**

Run: `cd frontend/apps/main && npm run typecheck`
Expected: May have minor errors, fix iteratively

- [ ] **Step 5: Commit**

```bash
git add frontend/apps/main/src/pages/AIChatPage.vue
git commit -m "feat(ai/chat): integrate AiProcessBlock and AiFinalAnswer

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

### Task 9: Integration Verification

**Files:**
- Verify: All components work together

- [ ] **Step 1: Run full typecheck**

Run: `cd frontend/apps/main && npm run typecheck`
Expected: PASS with zero errors

- [ ] **Step 2: Run lint check**

Run: `cd frontend/apps/main && npm run lint`
Expected: No new errors

- [ ] **Step 3: Build check**

Run: `cd frontend/apps/main && npm run build`
Expected: Build succeeds

- [ ] **Step 4: Manual verification (describe expected behavior)**

After integration, verify:
1. `/ai/chat` user bubble appears immediately on send
2. AiProcessBlock shows during thinking/tool calls
3. AiFinalAnswer streams during answering phase
4. Process block auto-collapses on completion
5. Regenerate button works on final answer

---

### Task 10: Integration into Agent Feature Pages (Deferred to Phase 3)

This task is deferred per the design spec Phase 3 plan. The MVP scope only requires `/ai/chat` integration.

**Files to modify later:**
- `frontend/apps/main/src/pages/AIReportPage.vue`
- `frontend/apps/main/src/pages/AIAlertsPage.vue`
- `frontend/apps/main/src/pages/AIDisposalPage.vue`
- `frontend/apps/main/src/pages/AILiabilityAdvisorPage.vue`
- `frontend/apps/main/src/pages/AIAllocationPage.vue`

- [ ] **Deferred: Create shared composable for agent pages**

Will create `useAIProcessState.ts` composable to manage process state for agent feature pages, sharing logic with chat.

- [ ] **Deferred: Update each agent page to use AiProcessBlock + AiFinalAnswer**

Replace TaskConsole with AiProcessBlock for better visualization.

---

## Verification Checklist

- [ ] All utility files created and typecheck passes
- [ ] All component files created and typecheck passes
- [ ] i18n keys added and typecheck passes
- [ ] AIChatPage integration passes typecheck
- [ ] Build succeeds without errors
- [ ] Process block shows during AI execution
- [ ] Process block auto-collapses on completion
- [ ] Final answer streams correctly
- [ ] Regenerate button functional
- [ ] No breaking changes to existing functionality

---

## Notes

- MVP scope: `/ai/chat` integration only. Agent feature pages deferred to Phase 3.
- TaskConsole.vue retained for backward compat and simple use cases.
- Backend already provides `tool.display_name` and `tool.icon` via AgentEvent.
- No agent runtime or new frameworks introduced - purely UI adaptation.