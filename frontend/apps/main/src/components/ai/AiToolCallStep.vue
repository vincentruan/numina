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