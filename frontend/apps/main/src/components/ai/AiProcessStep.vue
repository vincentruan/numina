<template>
  <div class="ai-process-step">
    <div class="step-marker" :class="markerClass">
      <span class="marker-icon">{{ markerIcon }}</span>
    </div>
    <div class="step-content">
      <div class="step-header">
        <span class="step-title">{{ t('aiProcess.stepReasoning') }}</span>
        <span v-if="elapsedMs" class="step-time">{{ formatElapsedMs(elapsedMs) }}</span>
      </div>
      <div class="step-body">
        <div v-if="showFullContent" class="reasoning-full">{{ content }}</div>
        <div v-else class="reasoning-truncated">{{ truncatedContent }}</div>
        <button
          v-if="isTruncated"
          class="expand-btn"
          @click="showFullContent = !showFullContent"
        >
          {{ showFullContent ? t('aiProcess.collapse') : t('aiProcess.expand') }}
        </button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { truncateContent } from '@/utils/contentTruncator'

const props = defineProps<{
  type: 'reasoning'
  content: string
  status: 'streaming' | 'done'
  elapsedMs?: number
}>()

const { t } = useI18n()
const showFullContent = ref(false)

const markerIcon = computed(() => {
  switch (props.status) {
    case 'streaming': return '💭'
    case 'done': return '✓'
    default: return '○'
  }
})

const markerClass = computed(() => {
  switch (props.status) {
    case 'streaming': return 'marker-streaming'
    case 'done': return 'marker-done'
    default: return ''
  }
})

const { truncated, isTruncated } = truncateContent(props.content, 150)
const truncatedContent = truncated

function formatElapsedMs(ms: number): string {
  if (ms < 1000) return `${ms}ms`
  return `${Math.floor(ms / 1000)}s`
}
</script>

<style scoped>
.ai-process-step {
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

.marker-streaming {
  background: var(--color-cost, #ffc04d);
  animation: pulse 1s infinite;
}

.marker-done {
  background: var(--color-success);
}

@keyframes pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.6; }
}

.marker-icon {
  font-size: 11px;
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

.step-title {
  font-size: 13px;
  font-weight: 500;
  color: var(--text-primary);
}

.step-time {
  font-size: 11px;
  color: var(--text-tertiary);
}

.step-body {
  padding: 8px 10px;
  background: var(--card-bg);
  border-radius: 4px;
  border: 1px solid var(--color-card-border);
  font-size: 12px;
  color: var(--text-secondary);
  line-height: 1.6;
  white-space: pre-wrap;
  word-break: break-word;
}

.reasoning-truncated {
  color: var(--text-secondary);
}

.reasoning-full {
  color: var(--text-primary);
}

.expand-btn {
  margin-top: 6px;
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
  .ai-process-step {
    gap: 10px;
  }

  .step-marker {
    width: 18px;
    height: 18px;
  }

  .marker-icon {
    font-size: 10px;
  }

  .step-content {
    min-width: 0;
  }

  .step-title {
    font-size: 12px;
  }

  .step-time {
    font-size: 10px;
  }

  .step-body {
    padding: 6px 8px;
    font-size: 11px;
    line-height: 1.5;
  }

  .expand-btn {
    font-size: 10px;
    padding: 4px 6px;
  }
}
</style>