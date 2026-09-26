<template>
  <div v-if="displayMode" class="today-learning-card" @click="navigate">
    <div class="today-learning-card__content">
      <span class="today-learning-card__icon">{{ icon }}</span>
      <div class="today-learning-card__text">
        <p class="today-learning-card__label">{{ label }}</p>
        <p class="today-learning-card__topic">{{ topicName }}</p>
      </div>
      <van-icon name="arrow" size="16" color="var(--color-muted-soft)" />
    </div>
    <p class="today-learning-card__footer">
      {{ t('learning.todayCard.footer', { minutes: data.study_minutes_today }) }}
    </p>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { useLocalizedTopic } from '@/composables/useLocalizedTopic'
import type { TodayLearningResponse } from '@/api/learning'

const props = defineProps<{
  data: TodayLearningResponse
}>()

const { t } = useI18n()
const router = useRouter()
const { topicDisplayName } = useLocalizedTopic()

type DisplayMode = 'assignment' | 'current' | 'recommended' | 'explore'

const displayMode = computed<DisplayMode>(() => {
  if (props.data.pending_assignment) return 'assignment'
  if (props.data.current_topic) return 'current'
  if (props.data.recommended_topic) return 'recommended'
  return 'explore'
})

const icon = computed(() => {
  switch (displayMode.value) {
    case 'assignment': return '📝'
    case 'current': return '📖'
    case 'recommended': return '🌟'
    case 'explore': return '📚'
    default: return ''
  }
})

const label = computed(() => t(`learning.todayCard.${displayMode.value}`))

const topicName = computed(() => {
  switch (displayMode.value) {
    case 'assignment': return props.data.pending_assignment?.topic ? topicDisplayName(props.data.pending_assignment.topic) : ''
    case 'current': return props.data.current_topic ? topicDisplayName(props.data.current_topic) : ''
    case 'recommended': return props.data.recommended_topic ? topicDisplayName(props.data.recommended_topic) : ''
    case 'explore': return t('learning.todayCard.exploreSub')
    default: return ''
  }
})

const targetTopicId = computed(() => {
  if (props.data.pending_assignment) return props.data.pending_assignment.topic?.id
  if (props.data.current_topic) return props.data.current_topic.id
  if (props.data.recommended_topic) return props.data.recommended_topic.id
  return null
})

function navigate() {
  if (targetTopicId.value) {
    router.push(`/learning/topic/${targetTopicId.value}`)
  } else {
    router.push('/learning')
  }
}
</script>

<style scoped>
.today-learning-card {
  margin: 12px 0;
  padding: 14px 16px;
  background: var(--color-surface-card);
  border-radius: var(--radius-lg);
  cursor: pointer;
  transition: transform 0.1s;
}

.today-learning-card:active {
  transform: scale(0.98);
}

.today-learning-card__content {
  display: flex;
  align-items: center;
  gap: 12px;
}

.today-learning-card__icon {
  font-size: 24px;
  flex-shrink: 0;
}

.today-learning-card__text {
  flex: 1;
  min-width: 0;
}

.today-learning-card__label {
  font-family: Inter, sans-serif;
  font-size: 13px;
  color: var(--color-body);
  margin: 0;
}

.today-learning-card__topic {
  font-family: Inter, sans-serif;
  font-size: 15px;
  font-weight: 600;
  color: var(--color-ink);
  margin: 2px 0 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.today-learning-card__footer {
  font-family: Inter, sans-serif;
  font-size: 12px;
  color: var(--color-body);
  margin: 8px 0 0;
  padding-top: 8px;
  border-top: 1px solid var(--color-hairline);
}
</style>
