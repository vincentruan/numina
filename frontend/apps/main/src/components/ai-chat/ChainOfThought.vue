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
import { Badge } from 'vant'
import { useI18n } from 'vue-i18n'
import { getToolIcon, getToolDisplayNameKey } from '@/utils/ai-chat/tool-icon-map'
import {
  extractReasoningContentFromMessage,
  extractToolCalls,
} from '@/utils/ai-chat'
import ChainOfThoughtSearchResults from './ChainOfThoughtSearchResults.vue'
import CodeBlock from './CodeBlock.vue'
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
          content: reasoning,
          status: 'done',
        })
      }

      // 工具调用
      const toolCalls = extractToolCalls(message)
      for (const tc of toolCalls) {
        allSteps.push({
          type: 'toolCall',
          id: tc.id,
          name: tc.name,
          displayName: tc.displayName,
          args: tc.args,
          result: tc.resultSummary,
          status: tc.status,
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
        existingStep.status = message.error ? 'error' : 'done'
      }
    }
  }

  return allSteps
})

// 可见步骤
const visibleSteps = computed(() => {
  const max = props.maxVisible || 3
  if (expanded.value) {
    return steps.value
  }
  return steps.value.slice(0, max)
})

// 隐藏的步骤数量
const hiddenCount = computed(() => steps.value.length - visibleSteps.value.length)

// 最后一个工具调用步骤
const lastToolCallStep = computed(() => {
  const toolCalls = steps.value.filter(s => s.type === 'toolCall')
  return toolCalls[toolCalls.length - 1] || null
})

// 最后的推理步骤
const lastReasoningStep = computed(() => {
  const reasonings = steps.value.filter(s => s.type === 'reasoning')
  return reasonings[reasonings.length - 1] || null
})

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

// 工具名称获取
function getName(step: { type: string; name?: string; displayName?: string }): string {
  if (step.type === 'reasoning') return t('aiChat.thinkingLabel')
  // Use i18n key for tool display name
  if (step.displayName) return step.displayName
  return t(getToolDisplayNameKey(step.name || ''))
}

// 状态 badge 类型
function getBadgeType(status: string): 'success' | 'danger' | 'primary' {
  if (status === 'done') return 'success'
  if (status === 'error') return 'danger'
  return 'primary'
}

// 关键参数提取（用于简洁展示）
// Tool args interface for key argument extraction
interface ToolArgsWithPath {
  path?: string
  file_path?: string
}
interface ToolArgsWithCommand {
  command?: string
  code?: string
}
interface ToolArgsWithQuery {
  query?: string
}

function getKeyArg(step: { name?: string; args?: Record<string, unknown> }): string | null {
  if (!step.args) return null

  const name = step.name?.replace(/^(mcp|skill|builtin):\/\//, '')

  if (name === 'read_file' || name === 'write_file' || name === 'str_replace') {
    const pathArgs = step.args as ToolArgsWithPath
    return pathArgs.path || pathArgs.file_path || null
  }
  if (name === 'bash') {
    const bashArgs = step.args as ToolArgsWithCommand
    const cmd = bashArgs.command || ''
    return cmd.length > 30 ? cmd.slice(0, 30) + '...' : cmd
  }
  if (name === 'web_search') {
    const searchArgs = step.args as ToolArgsWithQuery
    const query = searchArgs.query || ''
    return query.length > 20 ? `"${query.slice(0, 20)}..."` : `"${query}"`
  }

  return null
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
    const parsed = JSON.parse(step.result)
    if (Array.isArray(parsed)) {
      return parsed.map(item => ({
        url: item.url || item.link || item.source_url || '',
        title: item.title || item.name || '',
        snippet: item.snippet || item.description || '',
      })).filter(item => item.url)
    }
    // Some results are nested under 'results' key
    if (parsed.results && Array.isArray(parsed.results)) {
      return parsed.results.map(item => ({
        url: item.url || item.link || '',
        title: item.title || '',
        snippet: item.snippet || '',
      })).filter(item => item.url)
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
    <!-- 推理区域（可折叠） -->
    <div v-if="lastReasoningStep" class="thinking-section">
      <button
        class="thinking-toggle"
        @click="showThinking = !showThinking"
      >
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <path d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.984 3.984 0 0014 21a3.984 3.984 0 00-2.612-1.267l-.548-.547z"/>
        </svg>
        <span class="thinking-label">{{ t('aiChat.expandReasoning') }}</span>
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

      <div v-if="showThinking" class="thinking-content">
        {{ lastReasoningStep.content }}
      </div>
    </div>

    <!-- 工具调用历史 -->
    <div class="cot-steps">
      <!-- 折叠按钮 -->
      <button
        v-if="hiddenCount > 0"
        class="expand-btn"
        @click="expanded = !expanded"
      >
        <svg
          width="12"
          height="12"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          stroke-width="2"
          :class="['chevron', { rotated: expanded }]"
        >
          <polyline points="6 9 12 15 18 9"/>
        </svg>
        <span class="expand-label">
          {{ expanded ? t('aiChat.collapse') : t('aiChat.moreSteps', { count: hiddenCount }) }}
        </span>
      </button>

      <!-- 步骤列表 -->
      <div
        v-for="step in visibleSteps"
        :key="step.id"
        class="cot-step"
        :class="[
          step.type,
          step.status,
          { last: step === lastToolCallStep, running: step.status === 'running' }
        ]"
      >
        <!-- Step header -->
        <div class="step-header">
          <!-- 图标 -->
          <SvgIcon :name="getIcon(step)" class="step-icon" />

          <!-- 名称 -->
          <span class="step-name">{{ getName(step) }}</span>

          <!-- 关键参数 -->
          <span v-if="getKeyArg(step)" class="step-arg">
            {{ getKeyArg(step) }}
          </span>

          <!-- 状态 -->
          <div class="step-status">
            <!-- Loading -->
            <svg
              v-if="step.status === 'running'"
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

            <!-- Badge -->
            <Badge v-else :type="getBadgeType(step.status)" size="small">
              {{ step.status === 'done' ? '✓' : step.status === 'error' ? '✗' : '' }}
            </Badge>
          </div>

          <!-- 耗时 -->
          <span v-if="step.elapsedMs" class="step-time">{{ step.elapsedMs }}ms</span>
        </div>

        <!-- 进度消息 -->
        <div v-if="step.progressMessage" class="step-progress">
          {{ step.progressMessage }}
        </div>

        <!-- 错误信息 -->
        <div v-if="step.status === 'error' && step.result" class="step-error">
          {{ step.result }}
        </div>

        <!-- 工具特定结果可视化 -->
        <div v-if="step.status === 'done' && step.type === 'toolCall'" class="step-result">
          <!-- web_search/image_search 结果 -->
          <ChainOfThoughtSearchResults
            v-if="getSearchResults(step)"
            :results="getSearchResults(step)!"
            :max-visible="3"
          />

          <!-- bash 命令 CodeBlock -->
          <CodeBlock
            v-else-if="getBashCommand(step)"
            language="bash"
            :code="getBashCommand(step)!"
            :show-line-numbers="false"
          />

          <!-- write_file/read_file artifact 点击 -->
          <button
            v-else-if="getArtifactPath(step)"
            class="artifact-link"
            @click="handleArtifactClick(getArtifactPath(step)!)"
          >
            <SvgIcon name="file-text" class="artifact-icon" />
            <span class="artifact-path">{{ getArtifactPath(step) }}</span>
            <SvgIcon name="external-link" class="external-icon" />
          </button>
        </div>
      </div>
    </div>
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
}

.step-icon {
  width: 16px;
  height: 16px;
  color: var(--text-secondary);
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