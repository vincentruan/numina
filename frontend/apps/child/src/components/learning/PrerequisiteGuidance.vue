<template>
  <van-popup
    v-model:show="visible"
    position="bottom"
    round
    :style="{ maxHeight: '60vh' }"
    @close="$emit('close')"
  >
    <div class="prereq-guidance">
      <h3 class="prereq-guidance__title">
        {{ t('learning.cluster.prereqTitle', { topic: topicDisplayName }) }}
      </h3>

      <div v-if="unmetPrereqs.length === 0" class="prereq-guidance__all-met">
        {{ t('learning.cluster.prereqAllMet') }}
      </div>

      <div v-else class="prereq-guidance__list">
        <div
          v-for="prereq in unmetPrereqs"
          :key="prereq.topic.id"
          class="prereq-item"
        >
          <span class="prereq-item__status">{{ prereq.topic.mastery === 'mastered' ? '✅' : '❌' }}</span>
          <span class="prereq-item__name">{{ localizedTopicName(prereq.topic) }}</span>
          <button class="prereq-item__go" @click="$emit('goTo', prereq.topic.id)">
            {{ t('learning.cluster.prereqGoTo') }}
          </button>
        </div>
      </div>
    </div>
  </van-popup>
</template>

<script setup lang="ts">
defineOptions({ name: 'PrerequisiteGuidance' })

import { ref, computed, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import type { ProgressWithTopic, TopicGraphResponse } from '@/api/learning'
import { getTopicGraph } from '@/api/learning'

const { t, locale } = useI18n()

const props = defineProps<{
  topic: ProgressWithTopic
}>()

defineEmits<{
  close: []
  goTo: [topicId: string]
}>()

const visible = ref(true)
const graph = ref<TopicGraphResponse | null>(null)

const topicDisplayName = computed(() => {
  const topic = props.topic.topic
  if (locale.value.startsWith('zh') && topic.name_zh) return topic.name_zh
  return topic.name || topic.topic_key
})

function localizedTopicName(topic: TopicGraphResponse['topic']): string {
  if (locale.value.startsWith('zh') && topic.name_zh) return topic.name_zh
  return topic.name || topic.topic_key
}

interface PrereqWithMastery {
  topic: TopicGraphResponse['topic'] & { mastery?: string }
}

const unmetPrereqs = computed<PrereqWithMastery[]>(() => {
  if (!graph.value) return []
  return graph.value.prerequisites
    .filter((p) => p.topic.id !== props.topic.topic.id)
    .map((p) => ({
      ...p,
      topic: { ...p.topic, mastery: prereqMasteryMap.value.get(p.topic.id) || 'locked' },
    }))
    .filter((p) => p.topic.mastery !== 'mastered')
})

const prereqMasteryMap = computed(() => {
  const map = new Map<string, string>()
  // Use progress items from parent to determine prereq mastery
  // For simplicity, mark all prereqs as unmet (locked) unless we have data
  return map
})

onMounted(async () => {
  try {
    graph.value = await getTopicGraph(props.topic.topic.id)
  } catch {
    graph.value = null
  }
})
</script>

<style scoped>
.prereq-guidance {
  padding: 20px 16px 24px;
}

.prereq-guidance__title {
  font-family: Inter, sans-serif;
  font-size: 16px;
  font-weight: 600;
  color: var(--color-ink);
  margin: 0 0 16px;
  line-height: 1.4;
}

.prereq-guidance__all-met {
  text-align: center;
  padding: 20px;
  font-family: Inter, sans-serif;
  font-size: 14px;
  color: var(--color-body);
}

.prereq-guidance__list {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.prereq-item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 12px;
  background: var(--color-surface-soft);
  border-radius: var(--radius-md);
}

.prereq-item__status {
  font-size: 16px;
  flex-shrink: 0;
}

.prereq-item__name {
  flex: 1;
  font-family: Inter, sans-serif;
  font-size: 14px;
  color: var(--color-ink);
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.prereq-item__go {
  flex-shrink: 0;
  padding: 6px 12px;
  border: 1px solid var(--color-hairline);
  border-radius: var(--radius-md);
  background: var(--color-surface-card);
  font-family: Inter, sans-serif;
  font-size: 12px;
  font-weight: 500;
  color: var(--color-primary);
  cursor: pointer;
  min-height: 32px;
}

.prereq-item__go:active {
  transform: scale(0.96);
}
</style>
