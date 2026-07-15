<script setup lang="ts">
/**
 * DeerFlow ChainOfThought 组件
 *
 * 参考: frontend/src/components/ai-elements/chain-of-thought.tsx
 * 参考: frontend/src/components/workspace/messages/message-group.tsx
 *
 * 功能:
 * - 可折叠工具调用历史
 * - 工具特定图标 (web_search, read_file, write_file, bash, etc.)
 * - 工具特定结果可视化 (web_search 链接, bash CodeBlock, artifact 点击)
 * - "X more steps" 展开按钮
 * - 最后一个 tool call 高亮显示
 * - 思考过程折叠
 */
import { ref, computed, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { getToolIcon, explainToolCallKey, extractShortToolName } from '@/utils/ai-chat/tool-icon-map'
import {
  extractReasoningContentFromMessage,
  extractContentFromMessage,
  extractToolCalls,
} from '@/utils/ai-chat'
import MarkdownContent from './MarkdownContent.vue'
import ChainOfThoughtSearchResults from './ChainOfThoughtSearchResults.vue'
import CodeBlock from './CodeBlock.vue'
import FlipDisplay from './FlipDisplay.vue'
import LiveTimer from './LiveTimer.vue'
import IIcon from '@/components/IIcon.vue'
import type { ChatMessage } from '@/types/ai-chat/message-group'

const { t } = useI18n()

// Emit for artifact selection
const emit = defineEmits<{
  artifactSelect: [filepath: string]
}>()

const props = defineProps<{
  messages: ChatMessage[]
  isLoading?: boolean
  maxVisible?: number // 默认 3，超过折叠
  threadId?: string // 用于 artifact URL
}>()

const expanded = ref(false)
const showThinking = ref(false)

// Timing state for LiveTimer and auto-collapse
const reasoningStartTime = ref<number | null>(null)
const reasoningEndTime = ref<number | null>(null)
const manualControl = ref(false)
const autoCollapsed = ref(false)

function toggleThinking() {
  showThinking.value = !showThinking.value
  manualControl.value = true
}

// 转换消息为 CoT steps
const steps = computed(() => {
  const allSteps: Array<{
    type: 'reasoning' | 'toolCall' | 'leadingContent'
    id: string
    messageId?: string
    content?: string
    name?: string
    displayName?: string
    args?: Record<string, unknown>
    result?: string
    status: 'pending' | 'running' | 'done' | 'error'
    elapsedMs?: number
    progressMessage?: string
  }> = []

  for (const message of props.messages) {
    // 推理内容
    if (message.type === 'ai') {
      const reasoning = extractReasoningContentFromMessage(message)
      if (reasoning) {
        allSteps.push({
          type: 'reasoning',
          id: `reasoning-${message.id}`,
          messageId: message.id,
          content: reasoning,
          status: 'done',
        })
      }

      // 工具调用 (排除 task，task 由 SubtaskCard 处理)
      const toolCalls = extractToolCalls(message)

      // 过渡文本（leadingContent）：AI 消息同时携带 tool_calls 与正文 content 时，
      // content 是工具调用前的过渡说明（如"让我为您查询家庭资产负债的最新情况"）。
      // messageGroups.ts 已确保此类消息不创建独立 assistant 气泡，此处将其作为
      // ChainOfThought 块的首个步骤渲染，保持当前轮次的视觉连贯性。
      if (toolCalls.length > 0) {
        const bodyContent = extractContentFromMessage(message)
        if (bodyContent) {
          allSteps.push({
            type: 'leadingContent',
            id: `leading-${message.id}`,
            messageId: message.id,
            content: bodyContent,
            status: 'done',
          })
        }
      }

      for (const tc of toolCalls) {
        // 跳过空名 tool_call（后端有时发出 name="" 的占位条目，id 形如 tc-xxx）
        if (!tc.name) continue
        // Convert ToolCallSummary status to CoT step status.
        // DeerFlow has no per-tool "running" flag - it renders tool calls inline
        // from the messages array (a call exists => it was invoked; a Tool result
        // exists => it's done). During streaming, tool_calls arrive with
        // status='pending' (no result yet) - treat as 'running' so the spinner
        // shows. After the stream ends (isLoading=false), a pending call that
        // never received a result is treated as 'done' to avoid a stuck spinner
        // (matching DeerFlow, which never shows an indefinite loading state).
        const stepStatus: 'pending' | 'running' | 'done' | 'error' =
          tc.status === 'success' ? 'done'
          : tc.status === 'error' ? 'error'
          : tc.status === 'running' ? 'running'
          : props.isLoading ? 'running'
          : 'done'
        // Convert unknown result to string
        const resultStr = tc.result !== undefined
          ? (typeof tc.result === 'string' ? tc.result : JSON.stringify(tc.result))
          : undefined
        allSteps.push({
          type: 'toolCall',
          id: tc.id,
          messageId: message.id,
          name: tc.name,
          displayName: tc.displayName,
          args: tc.args,
          result: resultStr,
          status: stepStatus,
          elapsedMs: tc.elapsedMs,
          progressMessage: tc.progressMessage,
        })
      }
    }

    // Tool message (结果)
    if (message.type === 'tool') {
      const toolCallId = message.tool_call_id
      const existingStep = allSteps.find(s => s.type === 'toolCall' && s.id === toolCallId)
      if (existingStep) {
        existingStep.result = message.content?.toString() || ''
        existingStep.status = 'done'
      }
    }
  }

  return allSteps
})

// DeerFlow pattern: last tool call step (always visible)
const lastToolCallStep = computed(() => {
  const toolCalls = steps.value.filter(s => s.type === 'toolCall')
  return toolCalls[toolCalls.length - 1] || null
})

// leadingContent 步骤（过渡文本）：始终可见，不受折叠影响。
// 这些是 AI 消息携带 tool_calls 时的正文说明（如"让我为您查询…"），
// 必须显示在 ChainOfThought 块顶部，不应被"还有 N 步"折叠隐藏。
const leadingContentSteps = computed(() =>
  steps.value.filter(s => s.type === 'leadingContent')
)

// DeerFlow pattern: steps above the last tool call (hidden by default)
// 排除 leadingContent（始终可见）和 reasoning（按 DeerFlow 模式折叠）
const aboveLastToolCallSteps = computed(() => {
  if (!lastToolCallStep.value) return []
  const idx = steps.value.indexOf(lastToolCallStep.value)
  return steps.value
    .slice(0, idx)
    .filter(s => s.type !== 'leadingContent')
})

// DeerFlow pattern: reasoning step after the last tool call
// (reasoning that happens after tool execution, not before)
const lastReasoningStep = computed(() => {
  if (lastToolCallStep.value) {
    const idx = steps.value.indexOf(lastToolCallStep.value)
    // Find reasoning after the last tool call
    return steps.value.slice(idx + 1).find(s => s.type === 'reasoning') || null
  }
  // No tool calls: return the last reasoning
  const reasonings = steps.value.filter(s => s.type === 'reasoning')
  return reasonings[reasonings.length - 1] || null
})

// Watch for reasoning content to track start time
watch(() => lastReasoningStep.value?.content, (newVal) => {
  if (newVal && !reasoningStartTime.value) {
    reasoningStartTime.value = Date.now()
  }
})

// Watch for content after reasoning to track end time and auto-collapse
watch(() => lastToolCallStep.value, (newVal) => {
  // When tool calls appear after reasoning starts, mark reasoning as ended
  if (newVal && reasoningStartTime.value && !reasoningEndTime.value) {
    reasoningEndTime.value = Date.now()
    // Auto-expand briefly to show reasoning exists, then collapse
    setTimeout(() => {
      if (!manualControl.value) {
        showThinking.value = true
        // Auto-collapse after 2 seconds
        setTimeout(() => {
          if (!manualControl.value) {
            showThinking.value = false
            autoCollapsed.value = true
          }
        }, 2000)
      }
    }, 1000)
  }
})

// 隐藏的历史步骤数量 (DeerFlow pattern: aboveLastToolCallSteps)
// 注意：expanded 时 hiddenCount 为 0，但按钮仍需显示（文案改为"收起"）。
// 按钮的 v-if 使用 showExpandBtn（= aboveLastToolCallSteps.length > 0）而非 hiddenCount。
const hiddenCount = computed(() =>
  expanded.value ? 0 : aboveLastToolCallSteps.value.length
)

// 是否显示展开/收起按钮：当有可折叠的历史步骤时显示
const showExpandBtn = computed(() => aboveLastToolCallSteps.value.length > 0)

// 当前正在运行的步骤
const runningStep = computed(() =>
  steps.value.find(s => s.status === 'running' || s.status === 'pending')
)

// 是否显示 loading 状态
const showLoading = computed(() =>
  props.isLoading && runningStep.value?.status === 'running'
)

// 工具图标获取
function getIcon(step: { type: string; name?: string }): string {
  if (step.type === 'reasoning') return 'lightbulb'
  return getToolIcon(step.name || 'default')
}

// 工具名称获取 - 参考 DeerFlow message-group.tsx ToolCall 的行动描述模式
// 不再显示工具技术名，而是显示抽象后的行动步骤说明
// （如 web_search + query -> "在网络上搜索 XXX"，read_file + path -> "读取文件: path"）
function getName(step: { type: string; name?: string; displayName?: string; args?: Record<string, unknown> }): string {
  if (step.type === 'reasoning') return t('aiChat.thinkingLabel')
  // 使用 explainToolCallKey 生成行动描述（i18n key + params）
  const { key, params } = explainToolCallKey(step.name || '', step.args)
  return params ? t(key, params) : t(key)
}

// Tool args interfaces for result parsing
interface ToolArgsWithPath {
  path?: string
  file_path?: string
}
interface ToolArgsWithCommand {
  command?: string
  code?: string
}

// ============== Tool-specific result parsing ==============

interface SearchResultItem {
  url: string
  title?: string
  snippet?: string
}

/**
 * Parse web_search result into clickable links
 */
function getSearchResults(step: { name?: string; result?: string }): SearchResultItem[] | null {
  const name = extractShortToolName(step.name || '')
  if (name !== 'web_search' && name !== 'image_search' && name !== 'web_fetch') return null

  if (!step.result) return null

  // web_fetch: show page title as a single badge
  if (name === 'web_fetch') {
    // Try to extract title from markdown (# Title) or use URL
    const titleMatch = step.result.match(/^#\s+(.+)$/m)
    const title = titleMatch ? titleMatch[1] : step.result.slice(0, 50)
    const url = step.args?.url as string || ''
    return [{ url, title: title || url }]
  }

  try {
    // Result might be JSON array or JSON string
    const parsed = JSON.parse(step.result) as unknown
    if (Array.isArray(parsed)) {
      return parsed.map((item: unknown) => {
        const obj = item as Record<string, unknown>
        return {
          url: (obj.url || obj.link || obj.source_url || '') as string,
          title: (obj.title || obj.name || '') as string,
          snippet: (obj.snippet || obj.description || '') as string,
        }
      }).filter(item => item.url)
    }
    // Some results are nested under 'results' key
    const parsedObj = parsed as Record<string, unknown>
    if (parsedObj.results && Array.isArray(parsedObj.results)) {
      return (parsedObj.results as unknown[]).map((item: unknown) => {
        const obj = item as Record<string, unknown>
        return {
          url: (obj.url || obj.link || '') as string,
          title: (obj.title || '') as string,
          snippet: (obj.snippet || '') as string,
        }
      }).filter(item => item.url)
    }
  } catch {
    // Not JSON, try parsing as text with URLs
    const urlMatch = step.result.match(/https?:\/\/[^\s]+/g)
    if (urlMatch) {
      return urlMatch.map(url => ({ url, title: url }))
    }
  }
  return null
}

/**
 * Get bash command for CodeBlock display
 */
function getBashCommand(step: { name?: string; args?: Record<string, unknown> }): string | null {
  const name = extractShortToolName(step.name || '')
  if (name !== 'bash' && name !== 'python') return null

  const args = step.args as ToolArgsWithCommand
  return args?.command || args?.code || null
}

/**
 * Get file path for artifact click.
 * Checks args first (path/file_path), then falls back to parsing the result JSON
 * (backend sometimes sends args={} with the path only in the result payload).
 */
function getArtifactPath(step: { name?: string; args?: Record<string, unknown>; result?: string }): string | null {
  const name = extractShortToolName(step.name || '')
  if (name !== 'write_file' && name !== 'read_file' && name !== 'str_replace') return null

  const args = step.args as ToolArgsWithPath
  const argPath = args?.path || args?.file_path
  if (argPath) return argPath

  // Fallback: extract path from result JSON (e.g. {"success": true, "path": "report.md"})
  if (step.result) {
    try {
      const parsed = JSON.parse(step.result) as Record<string, unknown>
      const resultPath = (parsed.path || parsed.file_path) as string | undefined
      if (resultPath) return resultPath
    } catch {
      // Result is not JSON - ignore
    }
  }
  return null
}

/**
 * Handle artifact click - emit event to parent
 */
function handleArtifactClick(filepath: string) {
  emit('artifactSelect', filepath)
}

/**
 * Check if a step is a search/fetch type tool (uses ChainOfThoughtSearchResults).
 * Used to distinguish "empty results" from "not a search tool".
 */
function isSearchTypeTool(step: { name?: string }): boolean {
  const name = extractShortToolName(step.name || '')
  return name === 'web_search' || name === 'image_search' || name === 'web_fetch'
}

/**
 * Check if a step has an error result but no explicit 'error' status.
 * Catches cases where status is 'done' but the result payload contains an error.
 */
function hasToolError(step: { status: string; result?: string }): boolean {
  if (step.status === 'error') return true
  if (!step.result) return false
  try {
    const parsed = JSON.parse(step.result) as Record<string, unknown>
    if (parsed.error) return true
  } catch {
    // Not JSON - check for common error prefixes
    return step.result.startsWith('Error:') || step.result.startsWith('Error ')
  }
  return false
}

/**
 * Extract a short error summary from a tool result.
 * Returns a truncated, user-friendly error message.
 */
function getToolErrorSummary(step: { status: string; result?: string }): string {
  if (!step.result) return t('aiChat.toolError')
  // Try JSON extraction
  try {
    const parsed = JSON.parse(step.result) as Record<string, unknown>
    if (parsed.error) {
      const errMsg = typeof parsed.error === 'string' ? parsed.error : JSON.stringify(parsed.error)
      return errMsg.length > 120 ? errMsg.slice(0, 120) + '...' : errMsg
    }
  } catch {
    // Not JSON - use raw result
  }
  const raw = step.result
  return raw.length > 120 ? raw.slice(0, 120) + '...' : raw
}

/**
 * Check if a search-type tool completed but produced zero results.
 */
function hasEmptySearchResults(step: { name?: string; status: string; result?: string }): boolean {
  if (!isSearchTypeTool(step)) return false
  if (step.status !== 'done') return false
  if (hasToolError(step)) return false
  const results = getSearchResults(step)
  // null = not parseable / no result yet; empty array = parsed but zero items
  return results !== null && results.length === 0
}

/**
 * Check if step is web_fetch (for distinct rendering).
 */
function isWebFetch(step: { name?: string }): boolean {
  return extractShortToolName(step.name || '') === 'web_fetch'
}

/**
 * Check if step is a subagent task delegation.
 */
function isSubagentTask(step: { name?: string }): boolean {
  return extractShortToolName(step.name || '') === 'task'
}

/**
 * Get a display-friendly domain from a URL for web_fetch badge.
 */
function getFetchDomain(url: string): string {
  try {
    return new URL(url).hostname.replace(/^www\./, '')
  } catch {
    return url
  }
}
</script>

<template>
  <div class="chain-of-thought" :class="{ loading: showLoading }">
    <!-- 过渡文本（leadingContent）：始终可见，不受折叠影响 -->
    <div
      v-for="step in leadingContentSteps"
      :key="step.id"
      class="leading-content"
    >
      <MarkdownContent :content="step.content || ''" />
    </div>

    <!-- DeerFlow pattern: "X more steps" button for aboveLastToolCallSteps -->
    <button
      v-if="showExpandBtn"
      class="expand-btn"
      @click="expanded = !expanded"
    >
      <!-- DeerFlow: ChevronUp icon with rotate animation (chevron-first pattern) -->
      <svg
        width="16"
        height="16"
        viewBox="0 0 24 24"
        fill="none"
        stroke="currentColor"
        stroke-width="2"
        :class="['expand-chevron', { rotated: expanded }]"
      >
        <polyline points="18 15 12 9 6 15"/>
      </svg>
      <span class="expand-label opacity-60">
        {{ expanded ? t('aiChat.lessSteps') : t('aiChat.moreSteps', { count: hiddenCount }) }}
      </span>
    </button>

    <!-- Tool calls content (DeerFlow pattern) -->
    <div v-if="lastToolCallStep" class="cot-content">      <!-- Hidden history steps (shown when expanded) -->
      <template v-if="expanded">
        <div
          v-for="step in aboveLastToolCallSteps"
          :key="step.id"
          class="cot-step"
          :class="[step.type, step.status]"
        >
          <!-- DeerFlow pattern: step content with connector line inside icon wrapper -->
          <!-- Reasoning step -->
          <template v-if="step.type === 'reasoning'">
            <div class="step-icon-wrapper">
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" class="step-icon reasoning-icon">
                <path d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.984 3.984 0 0014 21a3.984 3.984 0 00-2.612-1.267l-.548-.547z"/>
              </svg>
              <div class="step-connector" />
            </div>
            <div class="step-body">
              <div class="step-name">{{ t('aiChat.thinkingLabel') }}</div>
              <div v-if="step.content" class="thinking-content-inline">{{ step.content }}</div>
            </div>
          </template>

          <!-- Tool call step (history) - DeerFlow pattern: no status badge, just name + result -->
          <template v-else>
            <div class="step-icon-wrapper">
              <IIcon :icon="getIcon(step)" class="step-icon" :class="{ 'subagent-icon': isSubagentTask(step) }" />
              <div class="step-connector" />
            </div>
            <div class="step-body-vertical">
              <div class="step-name" :class="{ 'subagent-name': isSubagentTask(step) }">{{ getName(step) }}</div>
              <!-- Subagent task: show progress indicator -->
              <div v-if="isSubagentTask(step) && step.status === 'running'" class="subagent-progress">
                <span class="subagent-progress-text">{{ t('aiChat.subtaskExecuting') }}</span>
              </div>
              <!-- Error state: tool returned an error -->
              <div v-if="hasToolError(step)" class="tool-error">
                <IIcon icon="x-circle" class="tool-error-icon" />
                <span class="tool-error-text">{{ getToolErrorSummary(step) }}</span>
              </div>
              <!-- Empty state: search tool returned zero results -->
              <div v-else-if="hasEmptySearchResults(step)" class="tool-empty">
                <IIcon icon="info" class="tool-empty-icon" />
                <span class="tool-empty-text">{{ t('aiChat.noResults') }}</span>
              </div>
              <!-- web_fetch: distinct badge with domain -->
              <div v-else-if="isWebFetch(step) && getSearchResults(step)" class="web-fetch-result">
                <IIcon icon="globe" class="web-fetch-icon" />
                <a
                  :href="(getSearchResults(step)![0]?.url) || '#'"
                  target="_blank"
                  rel="noopener noreferrer"
                  class="web-fetch-link"
                >
                  <span class="web-fetch-domain">{{ getFetchDomain(getSearchResults(step)![0]?.url || '') }}</span>
                  <span class="web-fetch-title">{{ getSearchResults(step)![0]?.title || getSearchResults(step)![0]?.url }}</span>
                </a>
              </div>
              <!-- Tool-specific result visualization for history steps -->
              <ChainOfThoughtSearchResults
                v-else-if="getSearchResults(step) && !isWebFetch(step)"
                :results="getSearchResults(step)!"
              />
              <CodeBlock
                v-else-if="getBashCommand(step)"
                language="bash"
                :code="getBashCommand(step)!"
                :show-line-numbers="false"
                bare
              />
              <button
                v-else-if="getArtifactPath(step)"
                class="artifact-link"
                @click="handleArtifactClick(getArtifactPath(step)!)"
              >
                <IIcon icon="file-text" class="artifact-icon" />
                <span class="artifact-path">{{ getArtifactPath(step) }}</span>
                <IIcon icon="external-link" class="external-icon" />
              </button>
            </div>
          </template>
        </div>
      </template>

      <!-- Last tool call: always visible with FlipDisplay animation -->
      <FlipDisplay :unique-key="lastToolCallStep.id">
        <div
          class="cot-step last-tool-call"
          :class="[lastToolCallStep.status, { running: lastToolCallStep.status === 'running' }]"
        >
          <!-- DeerFlow pattern: icon wrapper without connector (last step has no line) -->
          <div class="step-icon-wrapper">
            <IIcon :icon="getIcon(lastToolCallStep)" class="step-icon" :class="{ 'subagent-icon': isSubagentTask(lastToolCallStep) }" />
          </div>
          <div class="step-body-vertical">
            <div class="step-name-row">
              <span class="step-name" :class="{ 'subagent-name': isSubagentTask(lastToolCallStep) }">{{ getName(lastToolCallStep) }}</span>
              <!-- DeerFlow pattern: only show spinner for running, no ✓/✗ badge for done -->
              <svg
                v-if="lastToolCallStep.status === 'running'"
                class="status-loader animate-spin"
                width="14"
                height="14"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                stroke-width="2"
              >
                <path d="M21 12a9 9 0 11-6.219-8.56"/>
              </svg>
            </div>

            <!-- Error state: tool returned an error -->
            <div v-if="hasToolError(lastToolCallStep)" class="tool-error">
              <IIcon icon="x-circle" class="tool-error-icon" />
              <span class="tool-error-text">{{ getToolErrorSummary(lastToolCallStep) }}</span>
            </div>
            <!-- Empty state: search tool returned zero results -->
            <div v-else-if="hasEmptySearchResults(lastToolCallStep)" class="tool-empty">
              <IIcon icon="info" class="tool-empty-icon" />
              <span class="tool-empty-text">{{ t('aiChat.noResults') }}</span>
            </div>
            <!-- web_fetch: distinct badge with domain -->
            <div v-else-if="isWebFetch(lastToolCallStep) && getSearchResults(lastToolCallStep)" class="web-fetch-result">
              <IIcon icon="globe" class="web-fetch-icon" />
              <a
                :href="(getSearchResults(lastToolCallStep)![0]?.url) || '#'"
                target="_blank"
                rel="noopener noreferrer"
                class="web-fetch-link"
              >
                <span class="web-fetch-domain">{{ getFetchDomain(getSearchResults(lastToolCallStep)![0]?.url || '') }}</span>
                <span class="web-fetch-title">{{ getSearchResults(lastToolCallStep)![0]?.title || getSearchResults(lastToolCallStep)![0]?.url }}</span>
              </a>
            </div>
            <!-- Tool-specific result visualization -->
            <ChainOfThoughtSearchResults
              v-else-if="lastToolCallStep.status === 'done' && getSearchResults(lastToolCallStep) && !isWebFetch(lastToolCallStep)"
              :results="getSearchResults(lastToolCallStep)!"
            />
            <CodeBlock
              v-else-if="lastToolCallStep.status === 'done' && getBashCommand(lastToolCallStep)"
              language="bash"
              :code="getBashCommand(lastToolCallStep)!"
              :show-line-numbers="false"
              bare
            />
            <button
              v-else-if="lastToolCallStep.status === 'done' && getArtifactPath(lastToolCallStep)"
              class="artifact-link"
              @click="handleArtifactClick(getArtifactPath(lastToolCallStep)!)"
            >
              <IIcon icon="file-text" class="artifact-icon" />
              <span class="artifact-path">{{ getArtifactPath(lastToolCallStep) }}</span>
              <IIcon icon="external-link" class="external-icon" />
            </button>
          </div>
        </div>
      </FlipDisplay>
    </div>

    <!-- DeerFlow pattern: Thinking collapsible (after tool calls) -->
    <template v-if="lastReasoningStep">
      <button
        class="thinking-toggle"
        @click="toggleThinking"
      >
        <div class="thinking-toggle-inner">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" class="lightbulb-icon">
            <path d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.984 3.984 0 0014 21a3.984 3.984 0 00-2.612-1.267l-.548-.547z"/>
          </svg>
          <span class="thinking-label">{{ t('aiChat.thinkingLabel') }}</span>
          <LiveTimer
            v-if="reasoningStartTime"
            :start-time="reasoningStartTime"
            :end-time="reasoningEndTime ?? undefined"
          />
        </div>
        <svg
          width="12"
          height="12"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          stroke-width="2"
          :class="['chevron', { rotated: !showThinking }]"
        >
          <polyline points="6 9 12 15 18 9"/>
        </svg>
      </button>

      <div v-if="showThinking" class="thinking-content-expanded">
        {{ lastReasoningStep.content }}
      </div>
    </template>
  </div>
</template>

<style scoped>
.chain-of-thought {
  display: flex;
  flex-direction: column;
  gap: 8px; /* DeerFlow: gap-2 */
  padding: 12px;
  background: var(--card-bg);
  border: 1px solid var(--van-border-color, rgba(255, 255, 255, 0.08));
  border-radius: 8px; /* DeerFlow: rounded-lg */
}

.chain-of-thought.loading {
  border-color: var(--van-primary-color);
}

/* 过渡文本（leadingContent）：工具调用前的说明文字，
   始终可见，用次要样式与最终回答区分 */
.leading-content {
  font-size: 14px;
  line-height: 1.6;
  color: var(--text-secondary);
  padding: 4px 0;
}

/* Thinking collapsible toggle - DeerFlow ReasoningTrigger pattern */
.thinking-toggle {
  display: flex;
  align-items: center;
  justify-content: space-between; /* DeerFlow: label on left, chevron on right */
  gap: 8px;
  padding: 8px 12px;
  background: transparent;
  border: none;
  cursor: pointer;
  width: 100%;
  text-align: left;
}

.thinking-toggle-inner {
  display: flex;
  align-items: center;
  gap: 8px;
}

.lightbulb-icon {
  width: 16px;
  height: 16px;
  color: var(--van-primary-color);
}

.thinking-label {
  font-size: 14px;
  color: var(--van-primary-color);
  font-weight: 500;
}

.thinking-toggle .chevron {
  width: 12px;
  height: 12px;
  color: var(--text-secondary);
  transition: transform 0.2s ease;
}

.thinking-toggle .chevron.rotated {
  transform: rotate(180deg);
}

.thinking-content-expanded {
  padding: 8px 12px;
  font-size: 13px;
  color: var(--text-secondary);
  background: rgba(129, 140, 248, 0.08);
  border-radius: 6px;
  line-height: 1.5;
  margin-top: 4px;
}

.chevron {
  transition: transform 0.2s;
}

/* DeerFlow ChainOfThoughtContent: 步骤列表容器，竖直排列 */
.cot-content {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

/* DeerFlow pattern: expand button matches message-group.tsx Button styling.
   `w-full items-start justify-start text-left` + `variant="ghost"`
   DeerFlow uses ChevronUp icon (size-4) with rotate animation.
   The chevron comes BEFORE the text label (chevron-first pattern). */
.expand-btn {
  display: flex;
  align-items: flex-start; /* DeerFlow: items-start (aligns chevron with text start) */
  justify-content: flex-start; /* DeerFlow: justify-start */
  gap: 8px; /* gap-2 = 8px between chevron and label */
  width: 100%; /* DeerFlow: w-full */
  padding: 4px 0; /* minimal padding, ghost variant */
  background: transparent;
  border: none;
  cursor: pointer;
  font-size: 14px; /* DeerFlow: text-sm = 14px */
  color: var(--van-primary-color);
  text-align: left; /* DeerFlow: text-left */
}

.expand-chevron {
  width: 16px; /* DeerFlow: size-4 */
  height: 16px;
  color: var(--text-secondary);
  opacity: 0.6; /* DeerFlow: opacity-60 on icon wrapper */
  transition: transform 0.2s ease;
  flex-shrink: 0;
  margin-top: 0; /* aligns with text baseline */
}

.expand-chevron.rotated {
  transform: rotate(180deg); /* DeerFlow: rotate-180 when expanded (ChevronUp becomes ChevronDown) */
}

.expand-label {
  font-size: 14px;
  color: var(--text-secondary);
}

.cot-step {
  display: flex;
  gap: 8px; /* DeerFlow: gap-2 = 8px */
  font-size: 14px; /* DeerFlow: text-sm = 14px */
  padding: 4px 8px;
  position: relative;
}

/* DeerFlow pattern: last step has no connector line (no step after it) */
.cot-step.last-tool-call .step-connector {
  display: none;
}

/* Thinking content shown inline within step body */
.thinking-content-inline {
  font-size: 13px;
  color: var(--text-secondary);
  line-height: 1.5;
  padding: 4px 0;
}

/* DeerFlow 竖直轴线连接：参考 chain-of-thought.tsx ChainOfThoughtStep:
   `<div className="bg-border absolute top-7 bottom-0 left-1/2 -mx-px w-px" />`
   - top-7 = 28px (below 16px icon + gap)
   - left-1/2 + -mx-px = centered on icon
   - w-px = 1px width
*/
.step-connector {
  position: absolute;
  top: 28px; /* DeerFlow: top-7 = 28px (16px icon + 8px gap + 4px margin) */
  bottom: 0;
  left: 50%;
  transform: translateX(-50%);
  width: 1px;
  background: var(--separator);
  z-index: 0;
}

/* DeerFlow pattern: step body takes remaining space.
   参考 chain-of-thought.tsx: `<div className="flex-1 space-y-2 overflow-hidden">`
   space-y-2 = vertical spacing between children (label, description, results).
   Use vertical layout (flex-direction: column) so results render below the name. */
.step-body-vertical {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 8px; /* DeerFlow space-y-2 */
  overflow: hidden;
  min-width: 0;
}

/* Name row: name left, spinner right (for last-tool-call running state) */
.step-name-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
}

.step-body {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: space-between; /* name left, status badge right */
  gap: 8px;
  overflow: hidden;
  min-width: 0;
}

.step-header {
  display: flex;
  align-items: center;
  gap: 8px;
  position: relative;
  z-index: 1;
}

/* DeerFlow pattern: step icon wrapper contains icon + connector line.
   The wrapper stretches vertically (flex align-items: stretch default)
   so the connector extends from icon down to next step. */
.step-icon-wrapper {
  position: relative; /* Containing block for connector */
  margin-top: 2px; /* DeerFlow: mt-0.5 */
  flex-shrink: 0;
  display: flex;
  align-items: flex-start; /* Icon at top of wrapper */
  justify-content: center; /* Center horizontally for connector */
}

.step-icon {
  width: 16px; /* DeerFlow: size-4 */
  height: 16px;
  color: var(--text-secondary);
  font-size: 16px; /* IIcon uses 1em sizing - set font-size to match */
  flex-shrink: 0;
  /* DeerFlow: no background circle, just the icon SVG */
}

.step-name {
  font-size: 14px;
  font-weight: 500;
  color: var(--text-primary);
}

.step-arg {
  font-size: 12px;
  color: var(--text-secondary);
  max-width: 150px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.step-status {
  display: flex;
  align-items: center;
}

.status-loader {
  color: var(--van-primary-color);
}

.step-time {
  font-size: 11px;
  color: var(--text-secondary);
}

/* Tool error state: red error summary with icon */
.tool-error {
  display: flex;
  align-items: flex-start;
  gap: 6px;
  padding: 6px 10px;
  background: rgba(239, 68, 68, 0.08);
  border: 1px solid rgba(239, 68, 68, 0.2);
  border-radius: 6px;
  font-size: 12px;
  line-height: 1.4;
}

.tool-error-icon {
  width: 14px;
  height: 14px;
  color: #ef4444;
  flex-shrink: 0;
  margin-top: 1px;
}

.tool-error-text {
  color: #ef4444;
  word-break: break-word;
}

/* Tool empty state: info-style when search returns zero results */
.tool-empty {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 4px 10px;
  font-size: 12px;
  color: var(--text-secondary);
  opacity: 0.7;
}

.tool-empty-icon {
  width: 14px;
  height: 14px;
  flex-shrink: 0;
}

.tool-empty-text {
  font-style: italic;
}

/* web_fetch distinct result: domain badge + title link */
.web-fetch-result {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 6px 10px;
  background: var(--bg-secondary, rgba(127, 127, 127, 0.08));
  border: 1px solid var(--van-border-color, rgba(255, 255, 255, 0.08));
  border-radius: 8px;
}

.web-fetch-icon {
  width: 14px;
  height: 14px;
  color: var(--van-primary-color);
  flex-shrink: 0;
}

.web-fetch-link {
  display: flex;
  align-items: center;
  gap: 6px;
  text-decoration: none;
  min-width: 0;
  flex: 1;
}

.web-fetch-domain {
  font-size: 11px;
  font-weight: 500;
  color: var(--van-primary-color);
  background: rgba(129, 140, 248, 0.12);
  padding: 1px 6px;
  border-radius: 4px;
  flex-shrink: 0;
  max-width: 140px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.web-fetch-title {
  font-size: 12px;
  color: var(--text-primary);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  min-width: 0;
}

.web-fetch-link:hover .web-fetch-title {
  color: var(--van-primary-color);
}

/* 工具特定结果样式 - 不再用 margin-left: 24px，改为 step-body-vertical 内的 gap */

.artifact-link {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 12px;
  background: var(--bg-primary);
  border: 1px solid var(--van-border-color, rgba(255, 255, 255, 0.08));
  border-radius: 8px;
  cursor: pointer;
  transition: all 0.2s;
  width: 100%;
  text-align: left;
}

.artifact-link:hover {
  background: var(--card-bg);
  border-color: var(--van-primary-color);
}

.artifact-icon {
  width: 16px;
  height: 16px;
  color: var(--text-secondary);
}

.artifact-path {
  flex: 1;
  font-size: 13px;
  color: var(--text-primary);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.external-icon {
  width: 14px;
  height: 14px;
  color: var(--van-primary-color);
}

.animate-spin {
  animation: spin 1s linear infinite;
}

/* Subagent task delegation: distinct visual style */
.subagent-icon {
  color: var(--van-primary-color);
}

.subagent-name {
  color: var(--van-primary-color);
  font-weight: 500;
}

.subagent-progress {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 4px 0;
}

.subagent-progress-text {
  font-size: 12px;
  color: var(--text-secondary);
  font-style: italic;
}

@keyframes spin {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}

/* 375px */
@media (max-width: 375px) {
  .chain-of-thought {
    padding: 8px;
  }

  .step-name {
    font-size: 12px;
  }

  .step-arg {
    font-size: 11px;
    max-width: 100px;
  }

  .thinking-content-inline {
    font-size: 12px;
  }
}
</style>
