<template>
  <div
    class="ai-step-block"
    :class="[
      `ai-step-block--${status}`,
      { 'ai-step-block--active': isActive, 'ai-step-block--compressed': compressed },
    ]"
    role="listitem"
    :aria-expanded="canCollapse ? isExpanded : undefined"
    :aria-controls="canCollapse ? contentId : undefined"
  >
    <!-- Header -->
    <div
      class="step-header"
      :role="canCollapse ? 'button' : undefined"
      :tabindex="canCollapse ? 0 : undefined"
      :aria-expanded="canCollapse ? isExpanded : undefined"
      :aria-label="canCollapse && compressed && type === 'tool_call'
        ? (isExpanded ? t('aiProcess.collapseToolCall') : t('aiProcess.expandToolCall'))
        : undefined"
      @click="canCollapse && toggle()"
      @keydown.enter="canCollapse && toggle()"
      @keydown.space.prevent="canCollapse && toggle()"
    >
      <span class="step-icon" aria-hidden="true">{{ statusIcon }}</span>
      <div class="step-info">
        <span class="step-title">
          {{ headerTitle }}
          <span v-if="showSummary && summary" class="step-summary">{{ summary }}</span>
        </span>
        <span
          class="step-time"
          :class="{ 'step-time--compressed': compressed }"
          :aria-live="status === 'streaming' || status === 'running' ? 'polite' : undefined"
        >
          {{ formattedDuration }}
        </span>
      </div>
      <van-icon
        v-if="canCollapse"
        name="arrow-down"
        class="step-toggle"
        :class="{ 'step-toggle--expanded': isExpanded }"
        aria-hidden="true"
      />
    </div>

    <!-- Content (collapsible) -->
    <Transition name="step-content">
      <div v-show="!canCollapse || isExpanded" :id="contentId" class="step-body">
        <!-- Reasoning content -->
        <div v-if="type === 'reasoning'" class="reasoning-content" :class="{ 'body-streaming': status === 'streaming' }">
          {{ content }}
        </div>

        <!-- Tool call content -->
        <template v-else-if="type === 'tool_call'">
          <!-- Live status text (running only) -->
          <div
            v-if="status === 'running'"
            class="tool-status-text"
            aria-live="polite"
          >
            <Transition name="status-fade" mode="out-in">
              <span :key="statusText" class="tool-status-inner">{{ statusText }}</span>
            </Transition>
          </div>

          <div v-if="!compressed || isExpanded" class="tool-args" :class="{ 'args-running': status === 'running' }">
            <span class="args-label">{{ t('aiProcess.argsLabel') }}</span>
            <span class="args-value">{{ argsSummary }}</span>
          </div>
          <div v-if="status === 'done' || status === 'error'" class="tool-result" :class="resultClass">
            <span class="result-icon">{{ resultStatusIcon }}</span>
            <span class="result-text">{{ resultText }}</span>
          </div>
        </template>

        <!-- Subagent content -->
        <template v-else-if="type === 'subagent'">
          <div class="subagent-body">
            <div v-if="description" class="subagent-desc">{{ description }}</div>
            <div v-if="result" class="subagent-result">{{ result }}</div>
            <div v-if="error" class="subagent-error">{{ error }}</div>
          </div>
        </template>

        <!-- Artifact content -->
        <template v-else-if="type === 'artifact'">
          <a
            class="artifact-link"
            :href="url || '#'"
            :target="url ? '_blank' : undefined"
            :rel="url ? 'noopener noreferrer' : undefined"
          >
            <span class="artifact-icon" aria-hidden="true">📎</span>
            <span class="artifact-title">{{ title }}</span>
            <span v-if="path" class="artifact-path">{{ path }}</span>
          </a>
        </template>

        <!-- Progress content -->
        <template v-else-if="type === 'progress'">
          <div v-if="description" class="progress-desc">{{ description }}</div>
        </template>
      </div>
    </Transition>
  </div>
</template>

<script setup lang="ts">
import { computed, onUnmounted, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { useStepCollapse } from '@/composables/useStepCollapse'
import { useToolStatusText } from '@/composables/useToolStatusText'
import { getToolDisplayInfo, formatArgsSummary } from '@/utils/toolDisplayMapping'

const props = withDefaults(defineProps<{
  type: 'reasoning' | 'tool_call' | 'subagent' | 'artifact' | 'progress'
  id: string
  status: 'pending' | 'streaming' | 'running' | 'done' | 'error' | 'failed'
  content?: string
  name?: string
  displayName?: string
  icon?: string
  toolType?: string
  args?: Record<string, unknown>
  resultSummary?: string
  error?: string
  result?: string
  elapsedMs?: number
  autoCollapseSignal?: boolean
  defaultExpanded?: boolean
  compressed?: boolean
  progressMessage?: string
  // subagent / progress / artifact props
  title?: string
  description?: string
  taskId?: string
  url?: string
  path?: string
  kind?: 'data' | 'link' | 'image' | 'file' | 'other' | 'report'
  // U5: Chinese summary text (aiStepSummary.ts provides i18n key)
  summaryText?: string
  // U5: Show detail panel toggle (for redacted args display)
  showDetail?: boolean
}>(), {
  defaultExpanded: true,
  compressed: false,
  autoCollapseSignal: false,
  showDetail: false,
})

const { t } = useI18n()
const contentId = computed(() => `step-content-${props.id}`)

// Collapse logic: reasoning always, compressed tool_call can re-expand
const canCollapse = computed(
  () => props.type === 'reasoning' || (props.type === 'tool_call' && props.compressed),
)
const autoCollapseSignalRef = computed(() => props.autoCollapseSignal)
const statusRef = computed(() => props.status)

// Compressed tool_call starts collapsed (user must tap to expand)
const effectiveDefaultExpanded = props.compressed && props.type === 'tool_call'
  ? false
  : props.defaultExpanded

const { isExpanded, toggle } = useStepCollapse({
  defaultExpanded: effectiveDefaultExpanded,
  autoCollapseSignal: autoCollapseSignalRef,
  status: statusRef,
})

// Active state (streaming or running)
const isActive = computed(() => props.status === 'streaming' || props.status === 'running')

// Duration ticker for active steps
const tickMs = ref(0)
let tickInterval: ReturnType<typeof setInterval> | null = null
// Track when the step became active, for elapsed calculation
let activeStartMs = 0

function startTick() {
  if (tickInterval) return
  activeStartMs = Date.now()
  tickMs.value = Date.now()
  tickInterval = setInterval(() => {
    tickMs.value = Date.now()
  }, 1000)
}

function stopTick() {
  if (tickInterval) {
    clearInterval(tickInterval)
    tickInterval = null
  }
}

watch(
  () => props.status,
  (val) => {
    if (val === 'streaming' || val === 'running') {
      startTick()
    } else {
      stopTick()
    }
  },
  { immediate: true },
)

onUnmounted(() => {
  stopTick()
})

// Duration display
const computedElapsedMs = computed(() => {
  if (props.elapsedMs) return props.elapsedMs
  if (isActive.value) return tickMs.value - (props.elapsedMs || 0)
  return 0
})

// Live status text for running tool_call steps
const toolTypeRef = computed(() => props.toolType)
const liveElapsedMs = computed(() =>
  isActive.value ? tickMs.value - activeStartMs : (props.elapsedMs ?? 0),
)
const progressMessageRef = computed(() => props.progressMessage)
const { statusText } = useToolStatusText({
  toolType: toolTypeRef,
  elapsedMs: liveElapsedMs,
  progressMessage: progressMessageRef,
})

const formattedDuration = computed(() => {
  const ms = props.elapsedMs ?? (isActive.value ? Math.floor((tickMs.value - Date.now()) / 1000) * 1000 : 0)
  if (ms <= 0) return ''
  if (ms < 1000) return `${ms}ms`
  const s = Math.floor(ms / 1000)
  if (props.type === 'reasoning') return t('aiProcess.reasoningDuration', { seconds: s })
  return `${s}s`
})

// Status icon
const statusIcon = computed(() => {
  switch (props.status) {
    case 'pending': return '○'
    case 'streaming': return '💭'
    case 'running': return '⚙'
    case 'done': return '✓'
    case 'error':
    case 'failed': return '✗'
    default: return '○'
  }
})

// Header title
const headerTitle = computed(() => {
  if (props.type === 'reasoning') return t('aiProcess.stepReasoning')
  if (props.type === 'tool_call') {
    // U5: Use summaryText if provided (Chinese summary from aiStepSummary.ts)
    if (props.summaryText) {
      const info = getToolDisplayInfo(props.name || '', props.displayName, props.icon, props.toolType)
      return `${info.icon} ${t(props.summaryText)}`
    }
    const info = getToolDisplayInfo(props.name || '', props.displayName, props.icon, props.toolType)
    return `${info.icon} ${info.displayName}`
  }
  if (props.type === 'subagent') return props.title || props.taskId || ''
  if (props.type === 'artifact') return props.title || ''
  if (props.type === 'progress') return props.title || ''
  return ''
})

// Summary extraction for reasoning
const summary = computed(() => {
  if (props.type !== 'reasoning' || !props.content) return ''
  const text = props.content.trim()
  // Extract first sentence, truncate to ~40 chars for CJK, ~60 for Latin
  const firstSentence = text.split(/[.!?\n]/)[0] || text.slice(0, 60)
  const maxChars = /[一-鿿]/.test(firstSentence) ? 40 : 60
  if (firstSentence.length > maxChars) {
    return firstSentence.slice(0, maxChars) + '…'
  }
  return firstSentence !== text ? firstSentence + '…' : firstSentence
})

const showSummary = computed(() => props.type === 'reasoning' && props.status === 'done')

// Tool call specifics
const toolDisplayInfo = computed(() =>
  getToolDisplayInfo(props.name || '', props.displayName, props.icon, props.toolType),
)

const argsSummary = computed(() =>
  formatArgsSummary(props.args || {}, toolDisplayInfo.value.argsTemplate),
)

const resultStatusIcon = computed(() => props.status === 'done' ? '✓' : '✗')
const resultClass = computed(() => props.status === 'done' ? 'result-success' : 'result-error')
const resultText = computed(() => props.error || props.resultSummary || t('aiProcess.statusDone'))
</script>

<style scoped>
.ai-step-block {
  position: relative;
  display: flex;
  flex-direction: column;
  gap: 6px;
  padding: 10px 12px;
  background: var(--card-bg);
  border-radius: 8px;
  border: 1px solid var(--color-card-border);
  transition: opacity 0.2s ease;
}

/* Status states */
.ai-step-block--pending { opacity: 0.55; }
.ai-step-block--streaming,
.ai-step-block--running { opacity: 1; }
.ai-step-block--done { opacity: 0.75; }
.ai-step-block--error,
.ai-step-block--failed { opacity: 1; border-color: var(--color-error); }

/* Active gradient border via ::before */
.ai-step-block--active::before {
  content: '';
  position: absolute;
  inset: -1px;
  border-radius: 8px;
  padding: 1px;
  background: linear-gradient(
    90deg,
    var(--van-primary-color) 0%,
    var(--color-action-blue) 50%,
    var(--van-primary-color) 100%
  );
  background-size: 200% 100%;
  animation: gradient-sweep 2s linear infinite;
  -webkit-mask: linear-gradient(#fff 0 0) content-box, linear-gradient(#fff 0 0);
  mask: linear-gradient(#fff 0 0) content-box, linear-gradient(#fff 0 0);
  -webkit-mask-composite: xor;
  mask-composite: exclude;
  pointer-events: none;
}

@keyframes gradient-sweep {
  from { background-position: 0% center; }
  to { background-position: 200% center; }
}

/* Compressed mode: single-line layout */
.ai-step-block--compressed {
  flex-direction: row;
  align-items: center;
  gap: 8px;
  padding: 6px 10px;
}

.ai-step-block--compressed .step-info {
  flex: 1;
  display: flex;
  align-items: center;
  gap: 8px;
}

/* step-body visibility for compressed mode is handled entirely by v-show (canCollapse=true for tool_call) */

.ai-step-block--compressed .step-toggle {
  display: block;
}

/* Header */
.step-header {
  display: flex;
  align-items: center;
  gap: 10px;
  cursor: default;
}

.step-header[role='button'] {
  cursor: pointer;
  user-select: none;
  -webkit-user-select: none;
}

.step-header[role='button']:focus-visible {
  outline: 2px solid var(--van-primary-color);
  outline-offset: 2px;
  border-radius: 4px;
}

.ai-step-block--reasoning .step-header {
  cursor: pointer;
}

.step-icon {
  font-size: 14px;
  flex-shrink: 0;
}

.step-info {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.step-title {
  font-size: 13px;
  font-weight: 500;
  color: var(--text-primary);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.step-summary {
  margin-left: 6px;
  font-size: 12px;
  color: var(--text-secondary);
  font-weight: normal;
}

.step-time {
  font-size: 11px;
  color: var(--text-tertiary);
  font-variant-numeric: tabular-nums;
}

.step-time--compressed {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.step-toggle {
  color: var(--text-secondary);
  font-size: 16px;
  flex-shrink: 0;
  transition: transform 0.2s ease;
}

.step-toggle--expanded {
  transform: rotate(180deg);
}

/* Body */
.step-body {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

/* Reasoning content */
.reasoning-content {
  padding: 8px 10px;
  background: var(--bg-secondary);
  border-radius: 4px;
  font-size: 12px;
  color: var(--text-secondary);
  line-height: 1.6;
  white-space: pre-wrap;
  word-break: break-word;
}

.reasoning-content.body-streaming {
  background: linear-gradient(
    90deg,
    var(--card-bg) 25%,
    var(--bg-secondary) 50%,
    var(--card-bg) 75%
  );
  background-size: 200%;
  animation: body-shimmer 1.5s linear infinite;
}

@keyframes body-shimmer {
  from { background-position: 200% center; }
  to { background-position: -200% center; }
}

/* Tool args */
.tool-args {
  padding: 8px 10px;
  background: var(--bg-secondary);
  border-radius: 4px;
  font-size: 12px;
}

.tool-args.args-running {
  background: linear-gradient(
    90deg,
    var(--bg-secondary) 25%,
    rgba(var(--color-action-blue-rgb), 0.08) 50%,
    var(--bg-secondary) 75%
  );
  background-size: 200%;
  animation: body-shimmer 1.5s linear infinite;
}

.args-label {
  color: var(--text-secondary);
  margin-right: 4px;
}

.args-value {
  color: var(--text-primary);
}

/* Tool result */
.tool-result {
  padding: 8px 10px;
  background: var(--card-bg);
  border-radius: 4px;
  border: 1px solid var(--color-card-border);
  display: flex;
  align-items: flex-start;
  gap: 6px;
  font-size: 12px;
}

.result-success {
  border-color: var(--color-success);
}

.result-error {
  border-color: var(--color-error);
  background: rgba(var(--color-error-rgb), 0.06);
}

.result-icon {
  flex-shrink: 0;
}

.result-success .result-icon { color: var(--color-success); }
.result-error .result-icon { color: var(--color-error); }

.result-text {
  flex: 1;
  color: var(--text-primary);
  white-space: pre-wrap;
  word-break: break-word;
}

/* Tool status text */
.tool-status-text {
  height: 20px;
  line-height: 20px;
  overflow: hidden;
  font-size: 12px;
  color: var(--text-secondary);
}

.tool-status-inner {
  display: block;
}

/* Status text fade transition */
.status-fade-enter-active,
.status-fade-leave-active {
  transition: opacity 0.15s ease;
}

.status-fade-enter-from,
.status-fade-leave-to {
  opacity: 0;
}

.status-fade-enter-to,
.status-fade-leave-from {
  opacity: 1;
}

/* Content transition */
.step-content-enter-active,
.step-content-leave-active {
  transition: max-height 0.3s ease, opacity 0.2s ease;
  overflow: hidden;
}

.step-content-enter-from,
.step-content-leave-to {
  max-height: 0;
  opacity: 0;
}

.step-content-enter-to,
.step-content-leave-from {
  max-height: 500px;
  opacity: 1;
}

/* Subagent */
.subagent-body {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.subagent-desc {
  font-size: 12px;
  color: var(--text-secondary);
}

.subagent-result {
  font-size: 12px;
  color: var(--text-secondary);
  white-space: pre-wrap;
  word-break: break-word;
}

.subagent-error {
  font-size: 12px;
  color: var(--color-error);
  word-break: break-word;
}

/* Artifact */
.artifact-link {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 6px 10px;
  border-radius: 4px;
  background: var(--card-bg);
  border: 1px solid var(--color-card-border);
  font-size: 12px;
  color: var(--color-action-blue);
  text-decoration: none;
}

.artifact-link:hover {
  background: rgba(var(--color-action-blue-rgb), 0.08);
}

.artifact-path {
  color: var(--text-tertiary);
  font-family: var(--font-mono);
  font-size: 11px;
}

/* Progress */
.progress-desc {
  font-size: 12px;
  color: var(--text-secondary);
}

/* Reduced motion */
@media (prefers-reduced-motion: reduce) {
  .ai-step-block--active::before {
    animation: none;
    background: var(--van-primary-color);
  }

  .reasoning-content.body-streaming,
  .tool-args.args-running {
    animation: none;
    background: var(--bg-secondary);
  }

  .step-content-enter-active,
  .step-content-leave-active {
    transition: opacity 0.2s ease;
  }
}

/* Mobile responsive */
@media (max-width: 768px) {
  .ai-step-block {
    padding: 8px 10px;
    gap: 4px;
  }

  .step-header {
    gap: 8px;
  }

  .step-icon {
    font-size: 12px;
  }

  .step-title {
    font-size: 12px;
  }

  .step-time {
    font-size: 10px;
  }

  .reasoning-content,
  .tool-args,
  .tool-result {
    padding: 6px 8px;
    font-size: 11px;
  }
}
</style>