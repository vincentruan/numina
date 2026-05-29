<template>
  <div class="ai-process-block" :class="{ 'is-collapsed': !isExpanded }">
    <!-- Header -->
    <div class="process-header" @click="toggleExpand">
      <div class="process-icon" :class="statusClass">
        <AiLogo :state="logoState" />
      </div>
      <div class="process-info">
        <span class="process-title" :class="{ 'is-thinking': isShimmerActive }">{{ titleLabel }}</span>
        <span class="process-status">{{ subtitleLabel }}</span>
      </div>
      <span class="process-elapsed">{{ formattedElapsed }}</span>
      <van-icon :name="isExpanded ? 'arrow-down' : 'arrow-up'" class="process-toggle" />
    </div>

    <!-- Body (collapsible) — unified steps rendering preserves arrival order between reasoning and tool calls (spec §3.3). U3: fade+slide collapse transition. -->
    <Transition name="process-body">
      <div v-show="isExpanded" class="process-body">
      <template v-for="step in steps" :key="step.id">
        <AiProcessStep
          v-if="step.type === 'reasoning'"
          type="reasoning"
          :content="step.content"
          :status="step.status"
          :elapsed-ms="step.elapsedMs"
        />
        <AiToolCallStep
          v-else-if="step.type === 'tool_call'"
          :tool-call-id="step.id"
          :tool-name="step.name"
          :display-name="step.displayName"
          :icon="step.icon"
          :tool-type="step.toolType"
          :args="step.args"
          :status="step.status"
          :result-summary="step.resultSummary"
          :error="step.error"
          :elapsed-ms="step.elapsedMs"
        />
        <div
          v-else-if="step.type === 'subagent'"
          class="step-subagent"
          :class="`step-subagent--${step.status}`"
        >
          <span class="step-subagent-icon" aria-hidden="true">{{ subagentIcon(step.status) }}</span>
          <div class="step-subagent-body">
            <div class="step-subagent-title">{{ step.title || step.taskId }}</div>
            <div v-if="step.description" class="step-subagent-desc">{{ step.description }}</div>
            <div v-if="step.result" class="step-subagent-result">{{ step.result }}</div>
            <div v-if="step.error" class="step-subagent-error">{{ step.error }}</div>
          </div>
        </div>
        <a
          v-else-if="step.type === 'artifact'"
          class="step-artifact"
          :href="step.url || '#'"
          :target="step.url ? '_blank' : undefined"
          :rel="step.url ? 'noopener noreferrer' : undefined"
        >
          <span class="step-artifact-icon" aria-hidden="true">📎</span>
          <span class="step-artifact-title">{{ step.title }}</span>
          <span v-if="step.path" class="step-artifact-path">{{ step.path }}</span>
        </a>
        <div
          v-else-if="step.type === 'progress'"
          class="step-progress"
          :class="`step-progress--${step.status}`"
        >
          <span class="step-progress-icon" aria-hidden="true">{{ progressIcon(step.status) }}</span>
          <div class="step-progress-body">
            <div class="step-progress-title">{{ step.title }}</div>
            <div v-if="step.description" class="step-progress-desc">{{ step.description }}</div>
          </div>
        </div>
      </template>

      <!-- Empty running state -->
      <div v-if="status === 'running' && steps.length === 0" class="process-empty">
        <van-loading size="14" type="spinner" />
        <span>{{ t('aiProcess.connecting') }}</span>
      </div>

      <!-- Error state (spec §5.4): error message + retry button -->
      <div v-if="status === 'error'" class="process-error">
        <p class="process-error-msg">{{ errorMessage || t('aiProcess.errorMessage') }}</p>
        <button class="process-retry-btn" @click="onRetry">
          <van-icon name="replay" />
          <span>{{ t('aiProcess.retry') }}</span>
        </button>
      </div>
    </div>
    </Transition>
  </div>
</template>

<script setup lang="ts">
import { computed, onUnmounted, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import AiProcessStep from './AiProcessStep.vue'
import AiToolCallStep from './AiToolCallStep.vue'
import AiLogo from './AiLogo.vue'
import type { ProcessStep } from '@/types/agent-stream'

const props = defineProps<{
  status: 'running' | 'done' | 'error'
  elapsedMs: number
  steps: ProcessStep[]
  defaultExpanded?: boolean
  errorMessage?: string
  phase?: 'connecting' | 'thinking' | 'answering' | 'done' | 'error'
  reasoningStartTime?: number | null
}>()

const emit = defineEmits<{
  (e: 'toggle-expand', expanded: boolean): void
  (e: 'retry'): void
}>()

const { t } = useI18n()
const isExpanded = ref(props.defaultExpanded ?? props.status === 'running')

// U3: thinking-phase auto-collapse runs exactly once after thinking ends.
// Subsequent toggles by the user are not re-collapsed automatically.
const hasAutoCollapsed = ref(false)
let autoCollapseTimer: ReturnType<typeof setTimeout> | null = null

function clearAutoCollapseTimer() {
  if (autoCollapseTimer) {
    clearTimeout(autoCollapseTimer)
    autoCollapseTimer = null
  }
}

function toggleExpand() {
  isExpanded.value = !isExpanded.value
  // User interaction cancels any pending auto-collapse and disables future ones,
  // so we never undo an explicit user action.
  clearAutoCollapseTimer()
  hasAutoCollapsed.value = true
  emit('toggle-expand', isExpanded.value)
}

function onRetry() {
  emit('retry')
}

// Auto-collapse rules (U3 spec):
// - Status running → done while phase was thinking: collapse after 1s, once.
// - Status running → done from non-thinking path: collapse immediately.
// - Status → error: keep expanded so the retry button stays visible.
watch(
  () => props.status,
  (val, prev) => {
    if (val === 'running' && prev !== 'running') {
      isExpanded.value = true
      hasAutoCollapsed.value = false
      clearAutoCollapseTimer()
      return
    }
    if (val === 'done' && prev === 'running') {
      const fromThinking = props.phase === 'thinking' || props.reasoningStartTime != null
      if (fromThinking && !hasAutoCollapsed.value) {
        clearAutoCollapseTimer()
        autoCollapseTimer = setTimeout(() => {
          isExpanded.value = false
          hasAutoCollapsed.value = true
          autoCollapseTimer = null
        }, 1000)
      } else {
        isExpanded.value = false
      }
      return
    }
    if (val === 'error') {
      clearAutoCollapseTimer()
      isExpanded.value = true
    }
  },
)

// Tick once per second while phase is thinking, so the elapsed-seconds
// subtitle updates without per-token re-renders.
const nowMs = ref(Date.now())
let tickInterval: ReturnType<typeof setInterval> | null = null

function startTick() {
  if (tickInterval) return
  tickInterval = setInterval(() => {
    nowMs.value = Date.now()
  }, 1000)
}

function stopTick() {
  if (tickInterval) {
    clearInterval(tickInterval)
    tickInterval = null
  }
}

watch(
  () => props.phase,
  (val) => {
    if (val === 'thinking') {
      nowMs.value = Date.now()
      startTick()
    } else {
      stopTick()
    }
  },
  { immediate: true },
)

onUnmounted(() => {
  stopTick()
  clearAutoCollapseTimer()
})

const logoState = computed<'idle' | 'thinking' | 'done' | 'error'>(() => {
  if (props.status === 'error') return 'error'
  if (props.status === 'done') return 'done'
  if (props.phase === 'thinking' || props.phase === 'connecting') return 'thinking'
  return 'idle'
})

// U3: Shimmer animation runs only while the agent is actively thinking.
// Status transitions away from running stop the shimmer immediately so the
// settled "done"/"error" state reads as static.
const isShimmerActive = computed(
  () => props.status === 'running' && (props.phase === 'thinking' || props.phase === 'connecting'),
)

const statusClass = computed(() => {
  switch (props.status) {
    case 'running': return 'status-running'
    case 'done': return 'status-done'
    case 'error': return 'status-error'
    default: return ''
  }
})

const titleLabel = computed(() => {
  if (props.status === 'error') return t('aiProcess.errorTitle')
  if (props.phase === 'thinking' || props.phase === 'connecting') return t('aiProcess.thinkingTitle')
  if (props.phase === 'answering') return t('aiProcess.answeringTitle')
  return t('aiProcess.title')
})

const subtitleLabel = computed(() => {
  if (props.phase === 'thinking' && props.reasoningStartTime != null) {
    const seconds = Math.max(0, Math.floor((nowMs.value - props.reasoningStartTime) / 1000))
    return t('aiProcess.elapsedSeconds', { seconds })
  }
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

function subagentIcon(status: 'running' | 'done' | 'failed'): string {
  switch (status) {
    case 'running': return '⏳'
    case 'done': return '✓'
    case 'failed': return '✕'
  }
}

function progressIcon(status: 'running' | 'done' | 'error'): string {
  switch (status) {
    case 'running': return '⏳'
    case 'done': return '✓'
    case 'error': return '✕'
  }
}
</script>

<style scoped>
.ai-process-block {
  margin: 12px 0;
  border-radius: 8px;
  background: var(--card-bg);
  border: 1px solid var(--color-card-border);
  overflow: hidden;
}

.is-collapsed {
  background: var(--bg-secondary);
  border-color: var(--color-card-border);
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
  border-radius: 4px;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.status-running {
  background: var(--color-action-blue);
  animation: pulse 1.5s ease-in-out infinite;
}

.status-done {
  background: var(--color-success);
}

.status-error {
  background: var(--color-error);
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
  color: var(--text-primary);
}

.process-status {
  font-size: 12px;
  color: var(--text-secondary);
}

.process-elapsed {
  font-size: 12px;
  color: var(--text-tertiary);
  font-variant-numeric: tabular-nums;
}

.process-toggle {
  color: var(--text-secondary);
  font-size: 16px;
}

.process-body {
  padding: 10px 14px;
  border-top: 1px solid var(--separator);
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.process-empty {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 13px;
  color: var(--text-secondary);
}

.process-error {
  display: flex;
  flex-direction: column;
  gap: 8px;
  padding: 10px 12px;
  border-radius: 4px;
  background: rgba(var(--color-error-rgb), 0.08);
  border: 1px solid var(--color-error);
}

.process-error-msg {
  margin: 0;
  font-size: 13px;
  color: var(--color-error);
  line-height: 1.5;
  word-break: break-word;
}

.process-retry-btn {
  align-self: flex-start;
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 6px 12px;
  font-size: 13px;
  color: var(--color-error);
  background: var(--card-bg);
  border: 1px solid var(--color-error);
  border-radius: 4px;
  cursor: pointer;
}

.process-retry-btn:hover {
  background: rgba(var(--color-error-rgb), 0.08);
}

.step-subagent,
.step-progress {
  display: flex;
  gap: 8px;
  padding: 8px 10px;
  border-radius: 4px;
  background: var(--card-bg);
  border: 1px solid var(--color-card-border);
  font-size: 12px;
}

.step-subagent--running .step-subagent-icon,
.step-progress--running .step-progress-icon {
  animation: pulse 1.5s ease-in-out infinite;
}

.step-subagent--failed,
.step-progress--error {
  border-color: var(--color-error);
  background: rgba(var(--color-error-rgb), 0.08);
}

.step-subagent-body,
.step-progress-body {
  flex: 1;
  min-width: 0;
}

.step-subagent-title,
.step-progress-title {
  font-size: 13px;
  font-weight: 500;
  color: var(--text-primary);
}

.step-subagent-desc,
.step-progress-desc {
  margin-top: 2px;
  color: var(--text-secondary);
}

.step-subagent-result {
  margin-top: 4px;
  color: var(--text-secondary);
  white-space: pre-wrap;
  word-break: break-word;
}

.step-subagent-error {
  margin-top: 4px;
  color: var(--color-error);
  word-break: break-word;
}

.step-artifact {
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

.step-artifact:hover {
  background: rgba(var(--color-action-blue-rgb), 0.08);
}

.step-artifact-path {
  color: var(--text-tertiary);
  font-family: var(--font-mono);
  font-size: 11px;
}

/* U3: Shimmer animation on thinking title — CSS gradient sweep, 2s loop */
.process-title.is-thinking {
  background-image: linear-gradient(
    90deg,
    var(--text-primary) 0%,
    var(--text-primary) 40%,
    var(--color-action-blue) 50%,
    var(--text-primary) 60%,
    var(--text-primary) 100%
  );
  background-size: 200% 100%;
  background-clip: text;
  -webkit-background-clip: text;
  color: transparent;
  animation: shimmer-sweep 2s ease-in-out infinite;
}

@keyframes shimmer-sweep {
  from { background-position: 100% center; }
  to { background-position: 0% center; }
}

/* Reduced-motion: show static text, no animation */
@media (prefers-reduced-motion: reduce) {
  .process-title.is-thinking {
    background-image: none;
    background-clip: unset;
    -webkit-background-clip: unset;
    color: var(--text-primary);
    animation: none;
  }
}

/* U3: fade+slide transition for process-body collapse */
.process-body-enter-active,
.process-body-leave-active {
  transition: max-height 0.3s ease, opacity 0.2s ease;
  overflow: hidden;
}

.process-body-enter-from,
.process-body-leave-to {
  max-height: 0;
  opacity: 0;
}

.process-body-enter-to,
.process-body-leave-from {
  max-height: 800px;
  opacity: 1;
}

/* U4: vertical line connector between steps */
.process-body > :deep(.ai-tool-call-step),
.process-body > :deep(.ai-process-step),
.process-body > :deep(.step-subagent),
.process-body > :deep(.step-progress) {
  position: relative;
  padding-left: 14px;
}

.process-body > :deep(.ai-tool-call-step)::before,
.process-body > :deep(.ai-process-step)::before,
.process-body > :deep(.step-subagent)::before,
.process-body > :deep(.step-progress)::before {
  content: '';
  position: absolute;
  left: 9px;
  top: -5px;
  bottom: -5px;
  width: 1px;
  background: var(--separator);
}

/* Error steps get a dashed red connector segment */
.process-body > :deep(.ai-tool-call-step.marker-error-connector)::before {
  background: none;
  border-left: 1px dashed var(--color-error);
}

/* Remove connector line from the first step */
.process-body > :deep(:first-child)::before {
  display: none;
}

/* Mobile responsive (spec §8 mobile risk mitigation) */
@media (max-width: 768px) {
  .ai-process-block {
    margin: 8px 0;
  }

  .process-header {
    padding: 10px 12px;
    gap: 8px;
  }

  .process-icon {
    width: 24px;
    height: 24px;
  }

  .process-info {
    min-width: 0;
  }

  .process-title {
    font-size: 12px;
  }

  .process-status,
  .process-elapsed {
    font-size: 11px;
  }

  .process-body {
    padding: 8px 10px;
    gap: 8px;
  }

  .process-error {
    padding: 8px 10px;
  }

  .process-error-msg {
    font-size: 12px;
  }

  .process-retry-btn {
    font-size: 12px;
    padding: 6px 10px;
  }
}
</style>