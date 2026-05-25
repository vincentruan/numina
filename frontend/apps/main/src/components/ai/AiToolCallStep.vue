<template>
  <div class="ai-tool-call-step">
    <div class="step-marker" :class="markerClass">
      <span class="marker-icon">{{ statusIcon }}</span>
    </div>
    <div class="step-content">
      <div class="step-header">
        <div class="step-title-row">
          <span class="tool-icon">{{ displayIcon }}</span>
          <span class="step-title">{{ toolDisplayName }}</span>
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
const toolDisplayName = displayInfo.displayName
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

.marker-pending { background: var(--color-muted); }
.marker-running { background: var(--color-action-blue); animation: pulse 1s infinite; }
.marker-done { background: var(--color-success); }
.marker-error { background: var(--color-error); }

@keyframes pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.6; }
}

.marker-icon {
  font-size: 10px;
  color: #ffffff;
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
  color: var(--text-primary);
}

.tool-badge {
  font-size: 11px;
  color: var(--color-action-blue);
  background: rgba(24, 99, 220, 0.08);
  padding: 2px 6px;
  border-radius: 4px;
}

.step-time {
  font-size: 11px;
  color: var(--text-tertiary);
}

.step-args {
  padding: 8px 10px;
  background: var(--bg-secondary);
  border-radius: 4px;
  border: 1px solid var(--color-card-border);
  margin-bottom: 6px;
  font-size: 12px;
}

.args-running {
  animation: shimmer 1.5s infinite;
  background: linear-gradient(
    90deg,
    var(--bg-secondary) 25%,
    rgba(24, 99, 220, 0.08) 50%,
    var(--bg-secondary) 75%
  );
  background-size: 200%;
}

@keyframes shimmer {
  0% { background-position: 200% center; }
  100% { background-position: -200% center; }
}

.args-label {
  color: var(--text-secondary);
  margin-right: 4px;
}

.args-value {
  color: var(--text-primary);
}

.args-raw {
  margin: 4px 0 6px;
  padding: 8px 10px;
  background: var(--bg-secondary);
  border: 1px solid var(--color-card-border);
  border-radius: 4px;
  font-family: var(--font-mono);
  font-size: 11px;
  color: var(--text-secondary);
  max-height: 240px;
  overflow: auto;
  white-space: pre-wrap;
  word-break: break-all;
}

.step-result {
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
  background: rgba(179, 0, 0, 0.06);
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

.expand-btn {
  flex-shrink: 0;
  padding: 4px 8px;
  font-size: 11px;
  color: var(--color-action-blue);
  background: none;
  border: none;
  cursor: pointer;
}

.expand-btn:hover {
  text-decoration: underline;
}

/* Mobile responsive (spec §8 mobile risk mitigation) */
@media (max-width: 768px) {
  .ai-tool-call-step {
    gap: 10px;
  }

  .step-marker {
    width: 18px;
    height: 18px;
  }

  .marker-icon {
    font-size: 9px;
  }

  .step-content {
    min-width: 0;
  }

  .step-header {
    flex-wrap: wrap;
    gap: 4px;
  }

  .step-title-row {
    gap: 4px;
    min-width: 0;
    flex: 1;
  }

  .step-title {
    font-size: 12px;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .tool-badge {
    font-size: 10px;
    padding: 1px 4px;
  }

  .step-time {
    font-size: 10px;
  }

  .step-args {
    padding: 6px 8px;
    font-size: 11px;
    overflow: hidden;
  }

  .args-value {
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
    display: inline-block;
    max-width: 100%;
    vertical-align: bottom;
  }

  .args-raw {
    max-height: 160px;
    font-size: 10px;
    padding: 6px 8px;
  }

  .step-result {
    padding: 6px 8px;
    font-size: 11px;
  }

  .expand-btn {
    font-size: 10px;
    padding: 4px 6px;
  }
}
</style>