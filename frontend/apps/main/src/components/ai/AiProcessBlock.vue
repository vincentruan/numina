<template>
  <div class="ai-process-block" :class="{ 'is-collapsed': !isExpanded }">
    <!-- Header -->
    <div class="process-header" @click="toggleExpand">
      <div class="process-icon" :class="statusClass">
        <AiLogo :state="logoState" />
      </div>
      <div class="process-info">
        <span class="process-title">{{ titleLabel }}</span>
        <span class="process-status">{{ subtitleLabel }}</span>
      </div>
      <span class="process-elapsed">{{ formattedElapsed }}</span>
      <van-icon :name="isExpanded ? 'arrow-down' : 'arrow-up'" class="process-toggle" />
    </div>

    <!-- Body (collapsible) — unified steps rendering preserves arrival order between reasoning and tool calls (spec §3.3) -->
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
          :args="step.args"
          :status="step.status"
          :result-summary="step.resultSummary"
          :error="step.error"
          :elapsed-ms="step.elapsedMs"
        />
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

function toggleExpand() {
  isExpanded.value = !isExpanded.value
  emit('toggle-expand', isExpanded.value)
}

function onRetry() {
  emit('retry')
}

// Auto-collapse when status changes to done; keep expanded on error so user sees the retry button
watch(
  () => props.status,
  (val, prev) => {
    if (val === 'done' && prev === 'running') {
      isExpanded.value = false
    }
    if (val === 'running' && prev !== 'running') {
      isExpanded.value = true
    }
    if (val === 'error') {
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

onUnmounted(stopTick)

const logoState = computed<'idle' | 'thinking' | 'done' | 'error'>(() => {
  if (props.status === 'error') return 'error'
  if (props.status === 'done') return 'done'
  if (props.phase === 'thinking' || props.phase === 'connecting') return 'thinking'
  return 'idle'
})

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