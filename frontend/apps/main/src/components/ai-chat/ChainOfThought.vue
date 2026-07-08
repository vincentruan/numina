<script setup lang="ts">
/**
 * DeerFlow ChainOfThought 组件
 *
 * 参考: frontend/src/components/ai-elements/chain-of-thought.tsx
 *
 * 功能:
 * - 可折叠工具调用历史
 * - 工具特定图标 (web_search, read_file, write_file, bash, etc.)
 * - 结果 badge (success/error/running)
 * - 工具特定结果可视化 (web_search 链接, bash CodeBlock, artifact 点击)
 * - "X more steps" 展开按钮
 * - 最后一个 tool call 高亮显示
 */
import { ref, computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { Badge } from 'vant'
import { getToolIcon, explainToolCallKey } from '@/utils/ai-chat/tool-icon-map'
import {
  extractReasoningContentFromMessage,
  extractToolCalls,
} from '@/utils/ai-chat'
import ChainOfThoughtSearchResults from './ChainOfThoughtSearchResults.vue'
import CodeBlock from './CodeBlock.vue'
import FlipDisplay from './FlipDisplay.vue'
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

// 转换消息为 CoT steps
const steps = computed(() => {
  const allSteps: Array<{
    type: 'reasoning' | 'toolCall'
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
      for (const tc of toolCalls) {
        // Skip 'task' tool - handled by SubtaskCard
        if (tc.name === 'task') continue
        // 跳过空名 tool_call（后端有时发出 name="" 的占位条目，id 形如 tc-xxx）
        if (!tc.name) continue
        // Convert ToolCallSummary status to CoT step status
        const stepStatus: 'pending' | 'running' | 'done' | 'error' =
          tc.status === 'success' ? 'done'
          : tc.status === 'error' ? 'error'
          : tc.status === 'running' ? 'running'
          : 'pending'
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

// DeerFlow pattern: steps above the last tool call (hidden by default)
const aboveLastToolCallSteps = computed(() => {
  if (!lastToolCallStep.value) return []
  const idx = steps.value.indexOf(lastToolCallStep.value)
  return steps.value.slice(0, idx)
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

// 隐藏的历史步骤数量 (DeerFlow pattern: aboveLastToolCallSteps)
const hiddenCount = computed(() =>
  expanded.value ? 0 : aboveLastToolCallSteps.value.length
)

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

// 状态 badge 类型
function getBadgeType(status: string): 'success' | 'danger' | 'primary' {
  if (status === 'done') return 'success'
  if (status === 'error') return 'danger'
  return 'primary'
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
  const name = step.name?.replace(/^(mcp|skill|builtin):\/\//, '')
  if (name !== 'web_search' && name !== 'image_search') return null

  if (!step.result) return null

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
  const name = step.name?.replace(/^(mcp|skill|builtin):\/\//, '')
  if (name !== 'bash' && name !== 'python') return null

  const args = step.args as ToolArgsWithCommand
  return args?.command || args?.code || null
}

/**
 * Get file path for artifact click
 */
function getArtifactPath(step: { name?: string; args?: Record<string, unknown> }): string | null {
  const name = step.name?.replace(/^(mcp|skill|builtin):\/\//, '')
  if (name !== 'write_file' && name !== 'read_file' && name !== 'str_replace') return null

  const args = step.args as ToolArgsWithPath
  return args?.path || args?.file_path || null
}

/**
 * Handle artifact click - emit event to parent
 */
function handleArtifactClick(filepath: string) {
  emit('artifactSelect', filepath)
}
</script>

<template>
  <div class="chain-of-thought" :class="{ loading: showLoading }">
    <!-- DeerFlow pattern: "X more steps" button for aboveLastToolCallSteps -->
    <button
      v-if="hiddenCount > 0"
      class="expand-btn"
      @click="expanded = !expanded"
    >
      <svg
        width="14"
        height="14"
        viewBox="0 0 24 24"
        fill="none"
        stroke="currentColor"
        stroke-width="2"
        :class="['chevron', { rotated: expanded }]"
      >
        <polyline points="6 9 12 15 18 9"/>
      </svg>
      <span class="expand-label opacity-60">
        {{ expanded ? t('aiChat.collapse') : t('aiChat.moreSteps', { count: hiddenCount }) }}
      </span>
    </button>

    <!-- Tool calls content (DeerFlow pattern) -->
    <div v-if="lastToolCallStep" class="cot-content">
      <!-- Hidden history steps (shown when expanded) -->
      <template v-if="expanded">
        <div
          v-for="step in aboveLastToolCallSteps"
          :key="step.id"
          class="cot-step"
          :class="[step.type, step.status]"
        >
          <!-- Reasoning step -->
          <template v-if="step.type === 'reasoning'">
            <div class="step-header">
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" class="step-icon reasoning-icon">
                <path d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.984 3.984 0 0014 21a3.984 3.984 0 00-2.612-1.267l-.548-.547z"/>
              </svg>
              <span class="step-name">{{ t('aiChat.thinkingLabel') }}</span>
            </div>
            <div v-if="step.content" class="thinking-content-inline">{{ step.content }}</div>
          </template>

          <!-- Tool call step (history) -->
          <template v-else>
            <div class="step-header">
              <IIcon :icon="getIcon(step)" class="step-icon" />
              <span class="step-name">{{ getName(step) }}</span>
              <div class="step-status">
                <Badge :type="getBadgeType(step.status)" size="small">
                  {{ step.status === 'done' ? '✓' : step.status === 'error' ? '✗' : '' }}
                </Badge>
              </div>
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
          <div class="step-header">
            <IIcon :icon="getIcon(lastToolCallStep)" class="step-icon" />
            <span class="step-name">{{ getName(lastToolCallStep) }}</span>
            <div class="step-status">
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
              <Badge v-else :type="getBadgeType(lastToolCallStep.status)" size="small">
                {{ lastToolCallStep.status === 'done' ? '✓' : lastToolCallStep.status === 'error' ? '✗' : '' }}
              </Badge>
            </div>
          </div>

          <!-- Progress message for running step -->
          <div v-if="lastToolCallStep.progressMessage" class="step-progress">
            {{ lastToolCallStep.progressMessage }}
          </div>

          <!-- Tool-specific result visualization -->
          <div v-if="lastToolCallStep.status === 'done'" class="step-result">
            <ChainOfThoughtSearchResults
              v-if="getSearchResults(lastToolCallStep)"
              :results="getSearchResults(lastToolCallStep)!"
              :max-visible="3"
            />
            <CodeBlock
              v-else-if="getBashCommand(lastToolCallStep)"
              language="bash"
              :code="getBashCommand(lastToolCallStep)!"
              :show-line-numbers="false"
            />
            <button
              v-else-if="getArtifactPath(lastToolCallStep)"
              class="artifact-link"
              @click="handleArtifactClick(getArtifactPath(lastToolCallStep)!)"
            >
              <IIcon icon="file-text" class="artifact-icon" />
              <span class="artifact-path">{{ getArtifactPath(lastToolCallStep) }}</span>
              <IIcon icon="external-link" class="external-icon" />
            </button>
          </div>

          <!-- Error message -->
          <div v-if="lastToolCallStep.status === 'error' && lastToolCallStep.result" class="step-error">
            {{ lastToolCallStep.result }}
          </div>
        </div>
      </FlipDisplay>
    </div>

    <!-- DeerFlow pattern: Thinking collapsible (after tool calls) -->
    <template v-if="lastReasoningStep">
      <button
        class="thinking-toggle"
        @click="showThinking = !showThinking"
      >
        <div class="thinking-toggle-inner">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" class="lightbulb-icon">
            <path d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.984 3.984 0 0014 21a3.984 3.984 0 00-2.612-1.267l-.548-.547z"/>
          </svg>
          <span class="thinking-label">{{ t('aiChat.thinkingLabel') }}</span>
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
  gap: 8px;
  padding: 12px;
  background: var(--card-bg);
  border: 1px solid var(--border-color);
  border-radius: 12px;
}

.chain-of-thought.loading {
  border-color: var(--van-primary-color);
}

/* 思考区域 */
.thinking-section {
  border-bottom: 1px solid var(--border-color);
  padding-bottom: 8px;
}

.thinking-toggle {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 4px 8px;
  background: transparent;
  border: none;
  cursor: pointer;
  width: 100%;
  text-align: left;
}

.thinking-label {
  font-size: 14px;
  color: var(--van-primary-color);
  font-weight: 500;
}

.chevron {
  transition: transform 0.2s;
}

.chevron.rotated {
  transform: rotate(180deg);
}

.thinking-content {
  padding: 8px 12px;
  font-size: 13px;
  color: var(--text-secondary);
  background: rgba(129, 140, 248, 0.08);
  border-radius: 6px;
  line-height: 1.5;
  margin-top: 4px;
}

/* 工具调用步骤 */
.cot-steps {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.expand-btn {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 4px 8px;
  background: transparent;
  border: none;
  cursor: pointer;
  font-size: 12px;
  color: var(--van-primary-color);
}

.expand-label {
  font-size: 12px;
}

.cot-step {
  display: flex;
  flex-direction: column;
  gap: 2px;
  padding: 6px 8px;
  background: var(--bg-primary);
  border-radius: 6px;
  position: relative;
}

/* DeerFlow 竖直连接线：从当前步骤图标延伸到下一个步骤
   参考 chain-of-thought.tsx .step-connector */
.cot-content .cot-step:not(.last-tool-call)::after {
  content: '';
  position: absolute;
  left: 16px; /* 对齐 step-icon 中心 (8px padding + 8px icon half) */
  top: 28px;  /* 图标下方开始 */
  bottom: -4px; /* 延伸到下一个步骤 */
  width: 1px;
  background: var(--border-color, var(--separator));
  z-index: 0;
}

.cot-step.last {
  border-left: 2px solid var(--van-primary-color);
}

.cot-step.error {
  border-left-color: #ef4444;
  background: rgba(239, 68, 68, 0.05);
}

.cot-step.done {
  border-left-color: #22c55e;
}

.cot-step.running {
  border-left-color: var(--van-primary-color);
}

.step-header {
  display: flex;
  align-items: center;
  gap: 8px;
  position: relative;
  z-index: 1;
}

.step-icon {
  width: 16px;
  height: 16px;
  color: var(--text-secondary);
  background: var(--bg-primary);
  border-radius: 50%;
  flex-shrink: 0;
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

.step-progress {
  font-size: 12px;
  color: var(--van-primary-color);
  padding: 4px 8px;
  margin-left: 24px;
}

.step-error {
  font-size: 12px;
  color: #ef4444;
  padding: 4px 8px;
  background: rgba(239, 68, 68, 0.1);
  border-radius: 4px;
  margin-left: 24px;
}

/* 工具特定结果样式 */
.step-result {
  margin-left: 24px;
}

.artifact-link {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 12px;
  background: var(--bg-primary);
  border: 1px solid var(--border-color);
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

  .thinking-content {
    font-size: 12px;
  }
}
</style>