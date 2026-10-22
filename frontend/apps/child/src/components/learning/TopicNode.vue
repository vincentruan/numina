<template>
  <button
    class="topic-node-wrapper"
    :class="[`topic-node-wrapper--${masteryStatus}`]"
    :data-topic-id="item.topic.id"
    @click="$emit('tap', item)"
  >
    <div
      class="topic-node"
      :class="[
        `topic-node--${masteryStatus}`,
        { 'topic-node--frontier': isFrontier },
      ]"
      :title="topicDisplayName(item.topic)"
    >
      <span v-if="isFrontier" class="topic-node__here" aria-hidden="true">📍</span>
      <span class="topic-node__label">{{ topicDisplayName(item.topic) }}</span>
    </div>
  </button>
</template>

<script setup lang="ts">
defineOptions({ name: 'TopicNode' })

import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import type { ProgressWithTopic } from '@/api/learning'

const { locale } = useI18n()

const props = defineProps<{
  item: ProgressWithTopic
  isFrontier?: boolean
}>()

defineEmits<{
  tap: [item: ProgressWithTopic]
}>()

type MasteryStatus = 'mastered' | 'learning' | 'available' | 'locked' | 'review'

const masteryStatus = computed<MasteryStatus>(() => {
  const level = props.item.mastery_level
  if (level === 'mastered') {
    if (props.item.next_review_at) {
      const reviewDate = new Date(props.item.next_review_at)
      if (reviewDate <= new Date()) return 'review'
    }
    return 'mastered'
  }
  if (level === 'learning' || level === 'assessing') return 'learning'
  if (level === 'locked') return 'locked'
  return 'available'
})

function topicDisplayName(topic: ProgressWithTopic['topic']): string {
  if (locale.value.startsWith('zh') && topic.name_zh) return topic.name_zh
  return topic.name || topic.topic_key
}
</script>

<style scoped>
.topic-node-wrapper {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  /* 44px minimum touch target */
  min-width: 44px;
  min-height: 44px;
  padding: 2px;
  border: none;
  background: transparent;
  cursor: pointer;
  -webkit-tap-highlight-color: transparent;
}

.topic-node-wrapper:active {
  transform: scale(0.93);
}

.topic-node {
  position: relative;
  width: 40px;
  height: 40px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: box-shadow 0.2s, border-color 0.2s;
  overflow: hidden;
}

.topic-node__label {
  position: absolute;
  width: 1px;
  height: 1px;
  overflow: hidden;
  clip: rect(0, 0, 0, 0);
  white-space: nowrap;
}

.topic-node__here {
  font-size: 14px;
  line-height: 1;
  position: absolute;
  top: -2px;
  right: -2px;
  z-index: 2;
}

/* ── Mastery states ── */

.topic-node--mastered {
  background: var(--color-brand-ochre);
  border: 2px solid var(--color-brand-ochre);
  box-shadow: 0 0 8px rgba(var(--color-brand-ochre-rgb), 0.5);
}

.topic-node--learning {
  background: var(--color-primary);
  border: 2px solid var(--color-primary);
  animation: node-pulse 2s ease-in-out infinite;
}

.topic-node--available {
  background: var(--color-brand-lavender);
  border: 2px solid var(--color-brand-lavender);
}

.topic-node--locked {
  background: var(--color-body);
  border: 2px solid var(--color-body);
  opacity: 0.5;
}

.topic-node--review {
  background: var(--color-brand-peach);
  border: 2px solid var(--color-brand-coral);
}

/* ── Frontier highlight ── */

.topic-node--frontier {
  border: 2px dashed var(--color-brand-coral);
  animation: frontier-ring 2s ease-in-out infinite;
}

@keyframes node-pulse {
  0%, 100% { box-shadow: 0 0 0 0 rgba(10, 10, 10, 0.2); }
  50% { box-shadow: 0 0 0 6px rgba(10, 10, 10, 0); }
}

@keyframes frontier-ring {
  0%, 100% { box-shadow: 0 0 0 0 rgba(var(--color-brand-coral-rgb), 0.4); }
  50% { box-shadow: 0 0 0 6px rgba(var(--color-brand-coral-rgb), 0); }
}

/* ── Reduced motion ── */

@media (prefers-reduced-motion: reduce) {
  .topic-node--learning,
  .topic-node--frontier {
    animation: none;
  }
}

/* ── Dark mode adjustments ── */

[data-theme="dark"] .topic-node--locked {
  opacity: 0.4;
}

[data-theme="dark"] .topic-node--mastered {
  box-shadow: 0 0 10px rgba(var(--color-brand-ochre-rgb), 0.35);
}
</style>
