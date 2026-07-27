<template>
  <!-- DeerFlow pattern: flat step with icon + connector + content -->
  <!-- 参考：deer-flow-reference/frontend/src/components/ai-elements/chain-of-thought.tsx -->
  <div
    class="ai-step-block"
    :class="[
      `ai-step-block--${status}`,
      { 'ai-step-block--active': isActive, 'ai-step-block--compressed': compressed, 'ai-step-block--last': isLast },
    ]"
    role="listitem"
    :aria-expanded="canCollapse ? isExpanded : undefined"
    :aria-controls="canCollapse ? contentId : undefined"
  >
    <!-- Icon wrapper with connector line (deerflow pattern) -->
    <div class="step-icon-wrapper">
      <span class="step-icon" aria-hidden="true">{{ displayIcon }}</span>
      <!-- Vertical connector line to next step -->
      <div class="step-connector" aria-hidden="true" />
    </div>

    <!-- Content area -->
    <div class="step-content">
      <!-- Label row (deerflow: icon + label) -->
      <div
        class="step-label"
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
        <span class="step-title">{{ headerTitle }}</span>
        <span
          v-if="formattedDuration"
          class="step-time"
          :aria-live="status === 'streaming' || status === 'running' ? 'polite' : undefined"
        >
          {{ formattedDuration }}
        </span>
        <van-icon
          v-if="canCollapse"
          name="arrow-down"
          class="step-toggle"
          :class="{ 'step-toggle--expanded': isExpanded }"
          aria-hidden="true"
        />
      </div>

      <!-- Expandable content (collapsible) -->
      <Transition name="step-content">
        <div v-show="!canCollapse || isExpanded" :id="contentId" class="step-body">
          <!-- Reasoning content -->
          <div v-if="type === 'reasoning'" class="reasoning-content" :class="{ 'body-streaming': status === 'streaming' }">
            {{ filteredContent }}
          </div>

          <!-- Tool call content -->
          <template v-else-if="type === 'tool_call'">
          <!-- 状态过渡：使用绝对定位 + 独立 key 确保离开元素完全隐藏后进入元素才显示 -->
          <Transition name="tool-state" mode="out-in">
            <!-- Running 状态：参数 + 进度文本 -->
            <div v-if="status === 'running'" key="running" class="tool-state-container tool-state-running">
              <div class="tool-status-text" aria-live="polite">
                <span class="tool-status-inner">{{ statusText }}</span>
              </div>
              <!-- U1: Args hidden by default in compressed mode, shown when user expands -->
              <div v-if="!compressed || isExpanded" class="tool-args args-running">
                <span class="args-label">{{ t('aiProcess.argsLabel') }}</span>
                <span class="args-value">{{ argsSummary }}</span>
              </div>
            </div>
            <!-- Done/Error 状态：结果 -->
            <div v-else-if="status === 'done' || status === 'error' || status === 'failed'" :key="status" class="tool-state-container tool-state-result">
              <div class="tool-result" :class="resultClass">
                <span class="result-icon">{{ resultStatusIcon }}</span>
                <span class="result-text">{{ resultText }}</span>
              </div>
            </div>
          </Transition>
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
    </div><!-- /.step-content -->
  </div><!-- /.ai-step-block -->
</template>

<script setup lang="ts">
import { computed, onUnmounted, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { useStepCollapse } from '@/composables/useStepCollapse'
import { getToolDisplayInfo, formatArgsSummary } from '@/utils/toolDisplayMapping'
import { filterAIContent } from '@/utils/contentFilter'

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
  // DeerFlow pattern: isLast step (no connector line)
  isLast?: boolean
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
  isLast: false,
  content: undefined,
  name: undefined,
  displayName: undefined,
  icon: undefined,
  toolType: undefined,
  args: undefined,
  resultSummary: undefined,
  error: undefined,
  result: undefined,
  elapsedMs: undefined,
  progressMessage: undefined,
  title: undefined,
  description: undefined,
  taskId: undefined,
  url: undefined,
  path: undefined,
  kind: undefined,
  summaryText: undefined,
})

const { t } = useI18n()
const contentId = computed(() => `step-content-${props.id}`)

// Collapse logic: reasoning always, compressed tool_call can re-expand
const canCollapse = computed(
  () => props.type === 'reasoning' || (props.type === 'tool_call' && props.compressed),
)
const autoCollapseSignalRef = computed(() => props.autoCollapseSignal)
const statusRef = computed(() => props.status)

// DeerFlow pattern: display icon based on status and type
// 参考：deer-flow-reference/frontend/src/components/ai-elements/chain-of-thought.tsx
const displayIcon = computed(() => {
  // Status-based icons
  if (props.status === 'pending') return '○'
  if (props.status === 'streaming') return '💭'
  if (props.status === 'running') return props.icon || '⚙'
  if (props.status === 'error' || props.status === 'failed') return '✗'
  if (props.status === 'done') return props.icon || '✓'

  // Type-based icons
  if (props.type === 'reasoning') return '💭'
  if (props.type === 'artifact') return '📎'
  if (props.type === 'progress') return '▶'

  return props.icon || '○'
})

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

// Filtered reasoning content — prevent prompt leakage in thinking output
const filteredContent = computed(() => {
  if (props.type !== 'reasoning' || !props.content) return ''
  return filterAIContent(props.content)
})

// Duration ticker for active steps
const tickMs = ref(0)
let tickInterval: ReturnType<typeof setInterval> | null = null
// Track when the step became active, for elapsed calculation

function startTick() {
  if (tickInterval) return
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

// Live status text for running tool_call steps - dynamic generation using displayName
// CR-4 fix: Use i18n with action interpolation instead of hardcoded Chinese
const statusText = computed(() => {
  const baseName = props.displayName ?? props.name ?? t('aiProcess.defaultAction')
  if (props.status === 'running') return t('aiProcess.statusRunningAction', { action: baseName })
  if (props.status === 'done') return t('aiProcess.statusDoneAction', { action: baseName })
  if (props.status === 'error') return t('aiProcess.statusFailedAction', { action: baseName })
  if (props.status === 'streaming') return t('aiProcess.statusStreamingAction', { action: baseName })
  return baseName
})

const formattedDuration = computed(() => {
  const ms = props.elapsedMs ?? (isActive.value ? Math.floor((tickMs.value - Date.now()) / 1000) * 1000 : 0)
  if (ms <= 0) return ''
  if (ms < 1000) return `${ms}ms`
  const s = Math.floor(ms / 1000)
  if (props.type === 'reasoning') return t('aiProcess.reasoningDuration', { seconds: s })
  return `${s}s`
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
/* DeerFlow pattern: flat step with vertical connector line */
/* 参考：deer-flow-reference/frontend/src/components/ai-elements/chain-of-thought.tsx */
.ai-step-block {
  position: relative;
  display: flex;
  gap: 8px;
  padding: 6px 0; /* Reduced padding - connector spans between steps */
  transition: opacity 0.2s ease;
}

/* DeerFlow connector line: 1px vertical line from icon to next step */
.step-icon-wrapper {
  position: relative;
  flex-shrink: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  width: 24px;
  height: 24px;
}

/* Vertical connector line - deerflow pattern */
.step-connector {
  position: absolute;
  top: 24px; /* Below the icon */
  bottom: -6px; /* Extend to next step */
  left: 50%;
  width: 1px;
  background: var(--separator);
  transform: translateX(-50%);
}

/* Hide connector for last step or pending/error steps */
.ai-step-block--last .step-connector,
.ai-step-block--error .step-connector,
.ai-step-block--failed .step-connector {
  display: none;
}

/* Active connector - highlighted */
.ai-step-block--active .step-connector {
  background: var(--van-primary-color);
}

/* Status states - deerflow pattern */
.ai-step-block--pending { opacity: 0.5; }
.ai-step-block--streaming,
.ai-step-block--running { opacity: 1; }
.ai-step-block--done { opacity: 0.75; }
.ai-step-block--error,
.ai-step-block--failed { opacity: 1; }

/* Active step: gradient border effect */
.ai-step-block--active .step-icon-wrapper {
  border-radius: 4px;
  background: linear-gradient(
    90deg,
    var(--van-primary-color) 0%,
    var(--color-action-blue) 50%,
    var(--van-primary-color) 100%
  );
  background-size: 200% 100%;
  animation: gradient-sweep 2s linear infinite;
}

@keyframes gradient-sweep {
  from { background-position: 0% center; }
  to { background-position: 200% center; }
}

/* Compressed mode: inline layout for completed tool calls */
.ai-step-block--compressed {
  flex-direction: row;
  align-items: center;
  gap: 6px;
  padding: 4px 8px;
  background: var(--bg-secondary);
  border-radius: 6px;
  cursor: pointer;
  transition: background 0.15s ease;
}

.ai-step-block--compressed:hover {
  background: rgba(var(--color-action-blue-rgb), 0.08);
}

.ai-step-block--compressed .step-icon-wrapper {
  width: 16px;
  height: 16px;
}

.ai-step-block--compressed .step-connector {
  display: none;
}

/* Icon styling */
.step-icon {
  font-size: 14px;
  display: flex;
  align-items: center;
  justify-content: center;
}

/* Content area */
.step-content {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 4px;
}

/* Label row (deerflow: icon + label inline) */
.step-label {
  display: flex;
  align-items: center;
  gap: 8px;
  cursor: default;
}

.step-label[role='button'] {
  cursor: pointer;
  user-select: none;
  -webkit-user-select: none;
}

.step-label[role='button']:focus-visible {
  outline: 2px solid var(--van-primary-color);
  outline-offset: 2px;
  border-radius: 4px;
}

.step-title {
  font-size: 13px;
  font-weight: 500;
  color: var(--text-primary);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  flex: 1;
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
  flex-shrink: 0;
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

/* Tool state transition — out-in with absolute positioning to prevent overlap */
.tool-state-enter-active,
.tool-state-leave-active {
  transition: opacity 0.15s ease;
  position: absolute;
  width: 100%;
}

.tool-state-enter-from,
.tool-state-leave-to {
  opacity: 0;
}

.tool-state-enter-to,
.tool-state-leave-from {
  opacity: 1;
}

.tool-state-container {
  display: flex;
  flex-direction: column;
  gap: 6px;
  position: relative;
  /* Prevent height collapse during out-in transition with absolute children */
  min-height: 20px;
}

.tool-state-running {
  width: 100%;
}

.tool-state-result {
  width: 100%;
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

  .tool-state-enter-active,
  .tool-state-leave-active {
    transition: none;
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

/* U11: Mobile (≤428px) - tighter layout, truncated summaries */
@media (max-width: 428px) {
  .ai-step-block {
    padding: 6px 8px;
  }

  .step-header {
    gap: 6px;
  }

  /* Truncate long summaries on mobile */
  .step-summary {
    max-width: 120px;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .step-title {
    font-size: 11px;
  }

  .reasoning-content,
  .tool-args,
  .tool-result {
    padding: 4px 6px;
    font-size: 10px;
  }
}
</style>