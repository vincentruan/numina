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