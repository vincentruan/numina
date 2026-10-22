<template>
  <button
    v-if="topic && !loading"
    type="button"
    class="next-up-card"
    @click="onTap"
  >
    <span class="next-up-card__label">{{ t('learning.recommendPath.nextStep', { topic: topicName }) }}</span>
    <span class="next-up-card__arrow">{{ t('learning.recommendPath.startPractice') }}</span>
  </button>
</template>

<script setup lang="ts">
defineOptions({ name: 'NextUpCard' })

import { useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import type { ProgressWithTopic } from '@/api/learning'

const { t } = useI18n()
const router = useRouter()

const props = defineProps<{
  topic: ProgressWithTopic | null
  topicName: string
  loading?: boolean
}>()

function onTap() {
  if (!props.topic) return
  const status = props.topic.mastery_level
  if (status === 'learning' || status === 'available' || status === 'assessing') {
    router.push(`/learning/topic/${props.topic.topic.id}?action=practice`)
  } else if (status === 'mastered') {
    router.push(`/learning/topic/${props.topic.topic.id}?action=review`)
  } else {
    router.push(`/learning/topic/${props.topic.topic.id}`)
  }
}
</script>

<style scoped>
.next-up-card {
  display: flex;
  align-items: center;
  justify-content: space-between;
  width: 100%;
  min-height: 44px;
  padding: 12px 16px;
  background: var(--color-surface-card);
  border: 1px solid var(--color-brand-ochre);
  border-radius: var(--radius-md);
  cursor: pointer;
  -webkit-tap-highlight-color: transparent;
  transition: transform 0.1s;
  text-align: left;
  font-family: inherit;
}

.next-up-card:active {
  transform: scale(0.98);
  background: rgba(var(--color-brand-ochre-rgb), 0.08);
}

.next-up-card__label {
  font-family: Inter, sans-serif;
  font-size: 14px;
  font-weight: 600;
  color: var(--color-ink);
  flex: 1;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.next-up-card__arrow {
  font-family: Inter, sans-serif;
  font-size: 16px;
  font-weight: 600;
  color: var(--color-brand-ochre);
  flex-shrink: 0;
  margin-left: 8px;
}
</style>
