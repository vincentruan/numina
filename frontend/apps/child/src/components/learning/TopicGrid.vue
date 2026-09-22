<template>
  <div class="topic-grid">
    <div
      v-for="group in domainGroups"
      :key="group.domain"
      class="domain-group"
    >
      <h3 class="domain-group__title">{{ group.domain }}</h3>
      <div class="domain-group__cards">
        <button
          v-for="item in group.items"
          :key="item.topic.id"
          class="topic-card"
          :class="`topic-card--${masteryStatus(item)}`"
          @click="$emit('topicClick', item.topic.id)"
        >
          <span class="topic-card__status" aria-hidden="true">{{ statusIcon(masteryStatus(item)) }}</span>
          <div class="topic-card__info">
            <p class="topic-card__name">{{ topicDisplayName(item.topic) }}</p>
            <p v-if="item.progress" class="topic-card__meta">
              {{ t('learning.attempts', { count: item.progress.attempts }) }}
            </p>
          </div>
        </button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
defineOptions({ name: 'TopicGrid' })

import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import type { ProgressWithTopic } from '@/api/learning'

const { t, locale } = useI18n()

const props = defineProps<{
  items: ProgressWithTopic[]
}>()

defineEmits<{
  topicClick: [topicId: string]
}>()

type MasteryStatus = 'mastered' | 'learning' | 'available' | 'locked' | 'review'

function masteryStatus(item: ProgressWithTopic): MasteryStatus {
  const level = item.progress?.mastery_level
  if (level === 'mastered') {
    // Check if due for review
    if (item.progress?.next_review_at) {
      const reviewDate = new Date(item.progress.next_review_at)
      if (reviewDate <= new Date()) return 'review'
    }
    return 'mastered'
  }
  if (level === 'learning' || level === 'assessing') return 'learning'
  if (level === 'locked') return 'locked'
  return 'available'
}

function statusIcon(status: MasteryStatus): string {
  const icons: Record<MasteryStatus, string> = {
    available: '✅',
    learning: '🔵',
    mastered: '⭐',
    locked: '🔒',
    review: '🟡',
  }
  return icons[status]
}

function topicDisplayName(topic: ProgressWithTopic['topic']): string {
  if (locale.value.startsWith('zh') && topic.name_zh) return topic.name_zh
  return topic.name || topic.topic_key
}

interface DomainGroup {
  domain: string
  items: ProgressWithTopic[]
}

const domainGroups = computed<DomainGroup[]>(() => {
  const map = new Map<string, ProgressWithTopic[]>()
  for (const item of props.items) {
    const domain = item.topic.domain || t('learning.general')
    if (!map.has(domain)) map.set(domain, [])
    map.get(domain)!.push(item)
  }
  return Array.from(map.entries()).map(([domain, items]) => ({ domain, items }))
})
</script>

<style scoped>
.topic-grid {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.domain-group__title {
  font-family: Inter, sans-serif;
  font-size: 16px;
  font-weight: 600;
  color: var(--color-ink);
  margin: 0 0 10px;
  padding-left: 2px;
}

.domain-group__cards {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 10px;
}

.topic-card {
  display: flex;
  align-items: flex-start;
  gap: 10px;
  padding: 14px 12px;
  background: var(--color-surface-card);
  border: 1px solid var(--color-hairline);
  border-radius: var(--radius-md);
  cursor: pointer;
  transition: transform 0.1s, box-shadow 0.15s;
  text-align: left;
  min-height: 72px;
}

.topic-card:active {
  transform: scale(0.97);
}

.topic-card--locked {
  opacity: 0.5;
}

.topic-card--mastered {
  border-color: var(--color-brand-ochre);
  background: var(--color-surface-soft);
}

.topic-card--review {
  border-color: var(--color-brand-ochre);
}

.topic-card--learning {
  border-color: var(--color-primary);
}

.topic-card__status {
  font-size: 20px;
  line-height: 1;
  flex-shrink: 0;
}

.topic-card__info {
  flex: 1;
  min-width: 0;
}

.topic-card__name {
  font-family: Inter, sans-serif;
  font-size: 14px;
  font-weight: 600;
  color: var(--color-ink);
  margin: 0;
  line-height: 1.3;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.topic-card__meta {
  font-family: Inter, sans-serif;
  font-size: 12px;
  color: var(--color-muted-soft);
  margin: 4px 0 0;
}
</style>
