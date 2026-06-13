<template>
  <div v-if="status !== 'idle'" class="task-console">
    <!-- Header bar (摘要层) -->
    <div class="console-header" @click="toggleOpen">
      <ProcessingIcon
        v-if="status === 'running' || status === 'post_processing'"
        :active="true"
        class="console-processing-icon"
        aria-hidden="true"
      />
      <span v-else class="console-status-icon" aria-hidden="true">
        {{ statusIcon }}
      </span>

      <div class="console-header-content">
        <div class="console-title-row">
          <span v-if="hasSteps && isRunning" class="console-step-badge">
            {{ t('aiTask.stepProgress', { current: displayStepIndex + 1, total: planSteps?.length ?? 0 }) }}
          </span>
          <span class="console-title">{{ title }}</span>
        </div>
        <!-- Progress bar -->
        <div v-if="isRunning && hasSteps" class="console-progress-bar">
          <div class="progress-track">
            <div class="progress-fill" :style="{ width: `${progressPercent}%` }" />
          </div>
        </div>
      </div>

      <span v-if="status === 'queued' && queuePosition" class="console-queue-badge">
        {{ t('aiTask.queuePosition', { n: queuePosition }) }}
      </span>
      <span v-else class="console-elapsed">{{ formattedElapsed }}</span>
      <van-icon :name="isOpen ? 'arrow-up' : 'arrow-down'" class="console-toggle" />
    </div>

    <!-- Body (详情层，可折叠) -->
    <div v-show="isOpen" class="console-body">
      <!-- Failed warning bar -->
      <div v-if="status === 'failed'" class="console-error-bar" role="alert">
        <span class="error-bar-text">{{ failureMessage }}</span>
      </div>

      <!-- Queued state -->
      <div v-if="status === 'queued'" class="console-queued">
        <van-loading size="16" type="spinner" class="queue-spinner" />
        <span>{{ t('aiTask.queueWaiting') }}</span>
      </div>

      <!-- Step list (when plan steps available) -->
      <div v-else-if="hasSteps" class="console-steps">
        <div
          v-for="(step, idx) in planSteps"
          :key="step.id"
          class="step-item"
          :class="`step-item--${step.status}`"
        >
          <span class="step-icon" aria-hidden="true">
            <span v-if="step.status === 'done'" class="step-icon-done">✓</span>
            <van-loading v-else-if="step.status === 'active'" size="12" type="spinner" class="step-icon-active" />
            <span v-else class="step-icon-pending">{{ idx + 1 }}</span>
          </span>
          <span class="step-label">{{ step.label }}</span>
        </div>
      </div>

      <!-- Tool steps (fallback when no plan steps, or as sub-detail) -->
      <div v-if="!hasSteps && visibleToolSteps.length" class="console-tools">
        <div
          v-for="step in visibleToolSteps"
          :key="step.id"
          class="tool-step"
          :class="`tool-step--${step.status}`"
        >
          <span class="tool-icon">{{ step.icon }}</span>
          <span class="tool-name">{{ step.displayName }}</span>
          <span v-if="step.status === 'running'" class="tool-status tool-status--running">
            <van-loading size="10" type="spinner" />
          </span>
          <span v-else-if="step.status === 'done'" class="tool-status tool-status--done">✓</span>
          <span v-else-if="step.status === 'error'" class="tool-status tool-status--error">✗</span>
        </div>
      </div>

      <!-- Tool detail (expandable, shown under steps when detail requested) -->
      <details v-if="hasSteps && visibleToolSteps.length" class="console-tool-detail">
        <summary class="tool-detail-summary">
          {{ t('aiTask.toolDetail') }}
          <span class="tool-detail-count">{{ toolSteps?.length ?? 0 }}</span>
        </summary>
        <div class="tool-detail-list">
          <div
            v-for="step in visibleToolSteps"
            :key="step.id"
            class="tool-step"
            :class="`tool-step--${step.status}`"
          >
            <span class="tool-icon">{{ step.icon }}</span>
            <span class="tool-name">{{ step.displayName }}</span>
            <span v-if="step.status === 'running'" class="tool-status tool-status--running">
              <van-loading size="10" type="spinner" />
            </span>
            <span v-else-if="step.status === 'done'" class="tool-status tool-status--done">✓</span>
            <span v-else-if="step.status === 'error'" class="tool-status tool-status--error">✗</span>
          </div>
        </div>
      </details>

      <!-- Thinking block (collapsible) -->
      <div v-if="thinkContent" class="console-think-block">
        <button
          class="think-toggle"
          :aria-expanded="thinkOpen"
          @click.stop="thinkOpen = !thinkOpen"
        >
          <span class="think-icon" aria-hidden="true">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
              <path d="M9.663 17h4.673M12 3a6 6 0 0 1 6 6c0 2.22-1.2 4.16-3 5.2V16a1 1 0 0 1-1 1H10a1 1 0 0 1-1-1v-1.8A6 6 0 0 1 12 3z"/>
              <path d="M9 21h6"/>
            </svg>
          </span>
          <span v-if="thinkDone" class="think-status">
            {{ t('aiChat.thinkDone') }}
            <span v-if="thinkSeconds" class="think-duration">{{ thinkSeconds }}s</span>
          </span>
          <span v-else class="think-status think-status--active">{{ t('aiTask.phase.thinking') }}</span>
          <svg class="think-chevron" :class="{ 'think-chevron--open': thinkOpen }" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
            <polyline points="6 9 12 15 18 9"/>
          </svg>
        </button>
        <div v-if="thinkOpen" class="think-content">{{ thinkContent }}</div>
      </div>

      <!-- Answer content (streaming) -->
      <div v-if="answerContent" ref="answerRef" class="console-answer">
        <!-- eslint-disable-next-line vue/no-v-html -- sanitized via DOMPurify before binding -->
        <div class="answer-text" v-html="renderedAnswer" />
        <span v-if="status === 'running' && phase === 'answering'" class="answer-cursor" aria-hidden="true">▋</span>
      </div>

      <!-- Empty running state (no steps, no content) -->
      <div v-else-if="isRunning && !thinkContent && !hasSteps && !visibleToolSteps.length" class="console-empty-running">
        <ProcessingIcon :active="true" aria-hidden="true" />
        <span>{{ status === 'post_processing' ? t('aiTask.phase.postProcessing') : t('aiTask.phase.connecting') }}</span>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onUnmounted, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { marked } from 'marked'
import DOMPurify from 'dompurify'
import ProcessingIcon from '@/components/common/ProcessingIcon.vue'
import type { AITaskPhase } from '@/composables/useAITask'
import type { ToolStep } from '@/composables/useAITask'
import type { PlanStep } from '@/types/agent-stream'

const props = defineProps<{
  status: 'idle' | 'running' | 'post_processing' | 'queued' | 'completed' | 'failed' | 'timeout' | 'cancelled'
  phase?: AITaskPhase
  thinkContent?: string
  thinkDone?: boolean
  thinkSeconds?: number
  answerContent?: string
  elapsedSeconds: number
  queuePosition?: number | null
  errorCode?: string | null
  toolSteps?: ToolStep[]
  currentToolLabel?: string | null
  planSteps?: PlanStep[]
  currentStepIndex?: number
  modelValue?: boolean // isOpen
}>()

const emit = defineEmits<{
  'update:modelValue': [value: boolean]
}>()

const { t } = useI18n()
const answerRef = ref<HTMLElement | null>(null)
const thinkOpen = ref(false)
let scrollRAF: number | null = null

const ASSISTANT_PURIFY_CONFIG = {
  USE_PROFILES: { html: true },
  ALLOW_DATA_ATTR: false,
} as const

const _internalOpen = ref(props.modelValue ?? (props.status === 'running' || props.status === 'queued'))
const isOpen = computed({
  get: () => (props.modelValue !== undefined ? props.modelValue : _internalOpen.value),
  set: (val: boolean) => {
    _internalOpen.value = val
    emit('update:modelValue', val)
  },
})

function toggleOpen() {
  isOpen.value = !isOpen.value
}

const isRunning = computed(() => props.status === 'running' || props.status === 'post_processing')
const hasSteps = computed(() => (props.planSteps?.length ?? 0) > 0)

const displayStepIndex = computed(() => props.currentStepIndex ?? 0)

const progressPercent = computed(() => {
  const total = props.planSteps?.length ?? 0
  if (total === 0) return 0
  const doneCount = props.planSteps?.filter((s) => s.status === 'done').length ?? 0
  const activeCount = props.planSteps?.filter((s) => s.status === 'active').length ?? 0
  return Math.min(Math.round(((doneCount + activeCount * 0.5) / total) * 100), 100)
})

watch(
  () => props.status,
  (val, prev) => {
    if (val === 'completed' && prev !== 'completed') isOpen.value = false
    if ((val === 'running' || val === 'queued' || val === 'failed') && (prev === 'idle' || prev === 'queued')) isOpen.value = true
  },
)

watch(
  () => props.phase,
  (val) => {
    if (val === 'answering') thinkOpen.value = false
    if (val === 'thinking') thinkOpen.value = true
  },
)

watch(
  () => props.answerContent,
  () => {
    if (props.status !== 'running') return
    if (scrollRAF) return
    scrollRAF = requestAnimationFrame(() => {
      scrollRAF = null
      answerRef.value?.scrollIntoView({ behavior: 'smooth', block: 'end' })
    })
  },
)

onUnmounted(() => {
  if (scrollRAF) {
    cancelAnimationFrame(scrollRAF)
    scrollRAF = null
  }
})

const statusIcon = computed(() => {
  const icons: Partial<Record<typeof props.status, string>> = {
    queued: '🕐',
    completed: '✅',
    failed: '❌',
    timeout: '⏱️',
    cancelled: '⏹️',
  }
  return icons[props.status] ?? '⏳'
})

const title = computed(() => {
  if (isRunning.value) {
    if (props.status === 'post_processing') return t('aiTask.phase.postProcessing')
    // When plan steps exist, show the active step label
    if (hasSteps.value && props.planSteps) {
      const active = props.planSteps.find((s) => s.status === 'active')
      if (active) return active.label
    }
    // Show specific tool label when available
    if (props.currentToolLabel) return props.currentToolLabel
    if (props.phase) return t(`aiTask.phase.${props.phase}`)
    return t('aiTask.phase.connecting')
  }
  return t(`aiTask.status.${props.status}`)
})

const visibleToolSteps = computed(() => {
  if (!props.toolSteps?.length) return []
  return props.toolSteps.slice(-5)
})

const formattedElapsed = computed(() => {
  const s = props.elapsedSeconds
  if (s < 60) return `${s}s`
  return `${Math.floor(s / 60)}m${s % 60}s`
})

const renderedAnswer = computed(() => {
  if (!props.answerContent) return ''
  try {
    const html = marked.parse(props.answerContent, { async: false }) as string
    return DOMPurify.sanitize(html, ASSISTANT_PURIFY_CONFIG)
  } catch {
    return DOMPurify.sanitize(props.answerContent, ASSISTANT_PURIFY_CONFIG)
  }
})

const failureMessage = computed(() => {
  switch (props.errorCode) {
    case 'rate_limited':
      return t('aiTask.error.rateLimited')
    case 'circuit_open':
      return t('aiTask.error.circuitOpen')
    case 'extraction_failed':
    case 'structured_extraction_failed':
      return t('aiTask.error.extractionFailed')
    case 'agent_stream_error':
    case 'stream_error':
      return t('aiTask.error.streamError')
    case 'post_processing_timeout':
      return t('aiTask.error.postProcessingTimeout')
    case 'deerflow_timeout':
    case 'DeerFlowTimeoutError':
      return t('aiTask.error.deerflowTimeout')
    case 'deerflow_error':
    case 'DeerFlowError':
      return t('aiTask.error.deerflowError')
    case 'agent_create_error':
    case 'AGENT_CREATE_ERROR':
      return t('aiTask.error.agentCreateError')
    case 'config_build_error':
    case 'CONFIG_BUILD_ERROR':
      return t('aiTask.error.configBuildError')
    case 'agent_config_error':
    case 'AgentConfigError':
    case 'AGENT_CONFIG_ERROR':
      return t('aiTask.error.agentConfigError')
    case 'ai_config_error':
    case 'AiConfigError':
    case 'AI_CONFIG_ERROR':
      return t('aiTask.error.aiConfigError')
    case 'no_provider':
    case 'NoProvider':
    case 'NO_PROVIDER':
      return t('aiTask.error.noProvider')
    case 'runtime_error':
    case 'RuntimeUnavailable':
    case 'RUNTIME_ERROR':
      return t('aiTask.error.runtimeError')
    case 'model_not_support_reasoning':
      return t('aiTask.error.modelNotSupportReasoning')
    case 'web_search_config_error':
      return t('aiTask.error.webSearchConfigError')
    default:
      return t('aiTask.error.generic')
  }
})
</script>

<style scoped>
.task-console {
  margin: 12px 0;
  border-radius: 12px;
  background: var(--bg-card);
  border: 1px solid var(--border-color);
  overflow: hidden;
}

.console-header {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 14px;
  cursor: pointer;
  user-select: none;
}

.console-status-icon {
  font-size: 16px;
  flex-shrink: 0;
}

.console-processing-icon {
  --icon-size: 20px;
}

.console-header-content {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.console-title-row {
  display: flex;
  align-items: center;
  gap: 6px;
}

.console-step-badge {
  flex-shrink: 0;
  font-size: 11px;
  font-weight: 600;
  color: var(--van-primary-color);
  background: color-mix(in srgb, var(--van-primary-color) 10%, transparent);
  padding: 1px 6px;
  border-radius: 8px;
  white-space: nowrap;
}

.console-title {
  font-size: 13px;
  font-weight: 500;
  color: var(--text-primary);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.console-progress-bar {
  width: 100%;
}

.progress-track {
  height: 3px;
  background: var(--bg-secondary);
  border-radius: 2px;
  overflow: hidden;
}

.progress-fill {
  height: 100%;
  background: var(--van-primary-color);
  border-radius: 2px;
  transition: width 0.4s ease;
}

.console-elapsed {
  flex-shrink: 0;
  font-size: 12px;
  color: var(--text-tertiary);
  font-variant-numeric: tabular-nums;
}

.console-queue-badge {
  flex-shrink: 0;
  font-size: 11px;
  color: var(--color-warning, #ff9500);
  background: rgba(255, 149, 0, 0.12);
  padding: 2px 7px;
  border-radius: 10px;
}

.console-toggle {
  color: var(--text-tertiary);
  font-size: 14px;
  flex-shrink: 0;
}

.console-body {
  padding: 0 14px 14px;
  display: flex;
  flex-direction: column;
  gap: 10px;
}

/* Queued */
.console-queued {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 13px;
  color: var(--text-secondary);
  padding: 4px 0;
}

/* Step list */
.console-steps {
  display: flex;
  flex-direction: column;
  gap: 2px;
  padding: 4px 0;
}

.step-item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 6px 8px;
  border-radius: 8px;
  font-size: 13px;
  transition: background 0.2s, opacity 0.2s;
}

.step-item--active {
  background: color-mix(in srgb, var(--van-primary-color) 8%, transparent);
}

.step-item--done {
  opacity: 0.6;
}

.step-item--pending {
  opacity: 0.5;
}

.step-icon {
  width: 20px;
  height: 20px;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.step-icon-done {
  width: 18px;
  height: 18px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 50%;
  background: #22c55e;
  color: #fff;
  font-size: 10px;
  font-weight: 700;
}

.step-icon-active {
  color: var(--color-primary);
}

.step-icon-pending {
  width: 18px;
  height: 18px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 50%;
  border: 1.5px solid var(--text-tertiary);
  color: var(--text-tertiary);
  font-size: 10px;
  font-weight: 600;
}

.step-label {
  flex: 1;
  color: var(--text-primary);
}

.step-item--done .step-label {
  color: var(--text-secondary);
}

.step-item--pending .step-label {
  color: var(--text-tertiary);
}

/* Tool steps (fallback) */
.console-tools {
  display: flex;
  flex-direction: column;
  gap: 4px;
  padding: 4px 0;
}

.tool-step {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
  color: var(--text-secondary);
  padding: 3px 0;
  transition: opacity 0.2s;
}

.tool-step--done {
  opacity: 0.5;
}

.tool-step--error {
  opacity: 0.6;
  color: #dc2626;
}

.tool-icon {
  font-size: 12px;
  flex-shrink: 0;
  width: 14px;
  text-align: center;
}

.tool-name {
  flex: 1;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.tool-status {
  flex-shrink: 0;
  font-size: 11px;
}

.tool-status--running {
  display: flex;
  align-items: center;
}

.tool-status--done {
  color: #22c55e;
}

.tool-status--error {
  color: #dc2626;
}

/* Tool detail expandable */
.console-tool-detail {
  border-radius: 8px;
  background: var(--bg-secondary);
  overflow: hidden;
}

.tool-detail-summary {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 6px 10px;
  font-size: 12px;
  color: var(--text-tertiary);
  cursor: pointer;
  user-select: none;
}

.tool-detail-count {
  background: var(--bg-primary);
  border-radius: 8px;
  padding: 0 5px;
  font-size: 10px;
  min-width: 16px;
  text-align: center;
}

.tool-detail-list {
  padding: 0 10px 8px;
  display: flex;
  flex-direction: column;
  gap: 3px;
}

/* Thinking block */
.console-think-block {
  border-radius: 8px;
  background: var(--bg-secondary);
  overflow: hidden;
}

.think-toggle {
  display: flex;
  align-items: center;
  gap: 6px;
  width: 100%;
  padding: 8px 10px;
  background: none;
  border: none;
  cursor: pointer;
  text-align: left;
  color: var(--text-secondary);
  font-size: 12px;
}

.think-icon {
  color: #a78bfa;
  flex-shrink: 0;
  display: flex;
}

.think-status {
  flex: 1;
  display: flex;
  align-items: center;
  gap: 6px;
}

.think-status--active {
  color: #a78bfa;
}

.think-duration {
  color: var(--text-tertiary);
  font-size: 11px;
}

.think-chevron {
  color: var(--text-tertiary);
  transition: transform 0.2s;
  flex-shrink: 0;
}

.think-chevron--open {
  transform: rotate(180deg);
}

.think-content {
  padding: 0 10px 10px;
  font-size: 12px;
  color: var(--text-secondary);
  line-height: 1.6;
  white-space: pre-wrap;
  word-break: break-word;
}

/* Answer */
.console-answer {
  font-size: 14px;
  color: var(--text-primary);
  line-height: 1.7;
}

.answer-text :deep(p) { margin: 0 0 8px; }
.answer-text :deep(p:last-child) { margin-bottom: 0; }
.answer-text :deep(ul), .answer-text :deep(ol) { padding-left: 18px; margin: 4px 0 8px; }
.answer-text :deep(li) { margin-bottom: 4px; }
.answer-text :deep(strong) { color: var(--text-primary); }
.answer-text :deep(code) { background: var(--bg-secondary); padding: 1px 4px; border-radius: 3px; font-size: 12px; }

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

/* Empty running */
.console-empty-running {
  display: flex;
  align-items: center;
  gap: 10px;
  font-size: 13px;
  color: var(--text-secondary);
  padding: 8px 0;
}

.console-empty-running :deep(.processing-icon) {
  --icon-size: 20px;
}

/* Failure warning bar */
.console-error-bar {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 12px;
  background: rgba(220, 38, 38, 0.08);
  border-left: 3px solid #dc2626;
  border-radius: 6px;
  font-size: 13px;
  color: var(--text-primary);
}

.error-bar-text {
  flex: 1;
  line-height: 1.5;
}
</style>
