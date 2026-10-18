<template>
  <div v-if="pathInfo" class="today-path-card" @click="router.push(`/learning/path/${pathInfo.pathId}`)">
    <div class="path-card-header">
      <span class="path-emoji">📋</span>
      <span class="path-name">{{ pathInfo.name }}</span>
    </div>
    <div class="path-card-progress">
      <van-progress :percentage="pathInfo.percent" :show-pivot="false" stroke-width="6" />
      <span class="path-count">{{ pathInfo.completed }}/{{ pathInfo.total }}</span>
    </div>
  </div>

  <div v-else-if="displayMode" class="today-learning-card" @click="navigate">
    <div class="today-learning-card__content">
      <span class="today-learning-card__icon">{{ icon }}</span>
      <div class="today-learning-card__text">
        <p class="today-learning-card__label">{{ label }}</p>
        <p class="today-learning-card__topic">{{ topicName }}</p>
      </div>
      <van-icon name="arrow" size="16" color="var(--color-muted-soft)" />
    </div>
    <div v-if="sourceTag" class="today-learning-card__source">
      <van-tag :type="sourceTagType" size="medium">{{ sourceTag }}</van-tag>
    </div>
    <div v-if="rejectionFeedback" class="today-learning-card__rejection">
      <div class="rejection-banner">
        <span class="rejection-icon">❌</span>
        <span class="rejection-text">{{ rejectionFeedback.weakness }}</span>
      </div>
      <div class="rejection-actions">
        <van-button size="mini" type="primary" @click.stop="relearn">{{ t('learning.rejection.relearn') }}</van-button>
        <van-button size="mini" plain @click.stop="goPractice">{{ t('learning.rejection.goPractice') }}</van-button>
      </div>
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
  pathInfo?: {
    name: string
    completed: number
    total: number
    percent: number
    pathId: string
  } | null
}>()

const { t } = useI18n()
const router = useRouter()
const { topicDisplayName } = useLocalizedTopic()

type DisplayMode = 'assignment' | 'review_due' | 'current' | 'recommended' | 'explore'

const displayMode = computed<DisplayMode>(() => {
  if (props.data.pending_assignment) return 'assignment'
  if (props.data.review_due_topic) return 'review_due'
  if (props.data.current_topic) return 'current'
  if (props.data.recommended_topic) return 'recommended'
  return 'explore'
})

const icon = computed(() => {
  switch (displayMode.value) {
    case 'assignment': return '📝'
    case 'review_due': return '🔄'
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
    case 'review_due': return props.data.review_due_topic ? topicDisplayName(props.data.review_due_topic) : ''
    case 'current': return props.data.current_topic ? topicDisplayName(props.data.current_topic) : ''
    case 'recommended': return props.data.recommended_topic ? topicDisplayName(props.data.recommended_topic) : ''
    case 'explore': return t('learning.todayCard.exploreSub')
    default: return ''
  }
})

const targetTopicId = computed(() => {
  if (props.data.pending_assignment) return props.data.pending_assignment.topic?.id
  if (props.data.review_due_topic) return props.data.review_due_topic.id
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

// Source tag: show where this topic came from
const sourceTag = computed(() => {
  if (props.data.pending_assignment) {
    const assignmentType = props.data.pending_assignment.assignment_type
    if (assignmentType === 'parent_assigned') return t('learning.source.parentAssigned')
    if (assignmentType === 'self_selected') return t('learning.source.selfSelected')
  }
  if (props.data.recommended_topic) return t('learning.source.systemRecommended')
  return null
})

const sourceTagType = computed<'primary' | 'success' | 'warning'>(() => {
  if (props.data.pending_assignment?.assignment_type === 'parent_assigned') return 'primary'
  if (props.data.pending_assignment?.assignment_type === 'self_selected') return 'success'
  return 'warning'
})

// Rejection feedback: show when topic failed assessment
const rejectionFeedback = computed(() => {
  const topic = props.data.current_topic || props.data.review_due_topic
  if (!topic) return null

  // Check if this topic has parent_review mastery (indicates failed assessment)
  // We need to check the progress data, but TodayLearningResponse doesn't include mastery_level
  // For now, we'll show a generic message if there's a current_topic after a review_due
  if (props.data.current_topic && props.data.review_due_topic) {
    return {
      weakness: t('learning.rejection.needsPractice'),
    }
  }
  return null
})

function relearn() {
  if (targetTopicId.value) {
    router.push(`/learning/topic/${targetTopicId.value}`)
  }
}

function goPractice() {
  router.push('/learning/practice')
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

.today-learning-card__source {
  margin-top: 8px;
  padding-left: 36px;
}

.today-learning-card__rejection {
  margin-top: 10px;
  padding: 10px 12px;
  background: var(--color-brand-coral-light, rgba(255, 107, 107, 0.1));
  border-radius: var(--radius-md);
}

.rejection-banner {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 8px;
}

.rejection-icon {
  font-size: 16px;
  flex-shrink: 0;
}

.rejection-text {
  font-family: Inter, sans-serif;
  font-size: 13px;
  color: var(--color-ink);
  flex: 1;
}

.rejection-actions {
  display: flex;
  gap: 8px;
}

.rejection-actions :deep(.van-button) {
  min-width: 80px;
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

.today-path-card {
  margin: 12px 0;
  padding: 14px 16px;
  background: var(--color-surface-card);
  border-radius: var(--radius-lg);
  cursor: pointer;
  transition: transform 0.1s;
}

.today-path-card:active {
  transform: scale(0.98);
}

.path-card-header {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 10px;
}

.path-emoji {
  font-size: 20px;
}

.path-name {
  font-family: Inter, sans-serif;
  font-size: 15px;
  font-weight: 600;
  color: var(--color-ink);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.path-card-progress {
  display: flex;
  align-items: center;
  gap: 10px;
}

.path-card-progress :deep(.van-progress) {
  flex: 1;
}

.path-count {
  font-family: Inter, sans-serif;
  font-size: 13px;
  color: var(--color-body);
  white-space: nowrap;
}
</style>
