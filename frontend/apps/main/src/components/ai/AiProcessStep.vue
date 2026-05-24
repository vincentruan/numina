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
  background: #fbbf24;
  animation: pulse 1s infinite;
}

.marker-done {
  background: #22c55e;
}

@keyframes pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.6; }
}

.marker-icon {
  font-size: 11px;
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

.step-title {
  font-size: 13px;
  font-weight: 500;
  color: #374151;
}

.step-time {
  font-size: 11px;
  color: #94a3b8;
}

.step-body {
  padding: 8px 10px;
  background: white;
  border-radius: 6px;
  border: 1px solid #e2e8f0;
  font-size: 12px;
  color: #6b7280;
  line-height: 1.6;
  white-space: pre-wrap;
  word-break: break-word;
}

.reasoning-truncated {
  color: #6b7280;
}

.reasoning-full {
  color: #374151;
}

.expand-btn {
  margin-top: 6px;
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