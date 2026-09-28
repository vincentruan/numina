<template>
  <div v-if="topic" class="recommendation-card" @click="navigate">
    <div class="rec-header">
      <span class="rec-icon">🌟</span>
      <span class="rec-label">{{ t('learning.todayCard.recommended') }}</span>
      <span v-if="zoneLabel" class="rec-zone">{{ zoneLabel }}</span>
    </div>
    <p class="rec-topic">{{ topicName }}</p>
    <p class="rec-subject">{{ topic.subject }}</p>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { useLocalizedTopic } from '@/composables/useLocalizedTopic'
import type { TopicResponse } from '@/api/learning'

const props = defineProps<{
  topic: TopicResponse
  zone?: string
}>()

const { t } = useI18n()
const router = useRouter()
const { topicDisplayName } = useLocalizedTopic()

const topicName = computed(() => topicDisplayName(props.topic))

const zoneLabel = computed(() => {
  if (!props.zone) return ''
  return t(`learning.zone.${props.zone}`)
})

function navigate() {
  router.push(`/learning/topic/${props.topic.id}`)
}
</script>

<style scoped>
.recommendation-card {
  margin: 12px 0;
  padding: 14px 16px;
  background: var(--color-surface-card);
  border-radius: var(--radius-lg);
  cursor: pointer;
  transition: transform 0.1s;
}

.recommendation-card:active {
  transform: scale(0.98);
}

.rec-header {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-bottom: 6px;
}

.rec-icon {
  font-size: 16px;
}

.rec-label {
  font-family: Inter, sans-serif;
  font-size: 12px;
  color: var(--color-body);
}

.rec-zone {
  font-family: Inter, sans-serif;
  font-size: 11px;
  padding: 2px 6px;
  background: #e8f5e9;
  color: #2e7d32;
  border-radius: 8px;
  margin-left: auto;
}

[data-theme="dark"] .rec-zone {
  background: #1b5e20;
  color: #a5d6a7;
}

.rec-topic {
  font-family: Inter, sans-serif;
  font-size: 15px;
  font-weight: 600;
  color: var(--color-ink);
  margin: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.rec-subject {
  font-family: Inter, sans-serif;
  font-size: 12px;
  color: var(--color-body);
  margin: 4px 0 0;
}
</style>
