<template>
  <div class="learning-path-page">
    <van-nav-bar
      :title="displayName"
      left-arrow
      @click-left="router.back()"
    />

    <van-loading v-if="loading" class="page-loading" />

    <template v-else-if="path">
      <!-- Header -->
      <div class="path-header">
        <h2>{{ displayName }}</h2>
        <p v-if="displayDescription" class="path-desc">{{ displayDescription }}</p>
        <div class="path-meta">
          <van-tag type="primary">{{ t('learning.path.progress', { completed: path.completed_count, total: path.total_count }) }}</van-tag>
          <van-tag v-if="path.due_date" type="warning">截止: {{ path.due_date }}</van-tag>
        </div>
      </div>

      <!-- Progress bar -->
      <div class="progress-section">
        <van-progress
          :percentage="progressPercent"
          :show-pivot="true"
          color="var(--van-primary-color)"
        />
        <p v-if="path.next_milestone" class="next-milestone">
          🏆 {{ t('learning.path.milestone', { threshold: path.next_milestone.threshold, bonus: path.next_milestone.bonus }) }}
        </p>
      </div>

      <!-- Reward rules -->
      <div class="rewards-section">
        <h3>{{ t('learning.path.rewards') }}</h3>
        <p>{{ t('learning.path.perTask', { score: path.per_task_score }) }}</p>
        <p>{{ t('learning.path.bonus', { score: path.bonus_score }) }}</p>
      </div>

      <!-- Items list -->
      <div class="items-section">
        <div
          v-for="item in path.items"
          :key="item.id"
          class="path-item"
          :class="{ completed: item.status === 'completed', current: item.status === 'pending' && isNext(item) }"
          @click="navigateToTopic(item)"
        >
          <span class="item-icon">{{ statusIcon(item.status) }}</span>
          <span class="item-name">{{ itemTopicName(item) }}</span>
          <van-icon name="arrow" />
        </div>
      </div>
    </template>

    <van-empty v-else :description="t('common.notFound')" />
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { getMyPath, type PathResponse, type PathItemResponse } from '@/api/learning'
import { usePageLoading } from '@/composables/usePageLoading'

const router = useRouter()
const route = useRoute()
const { t, locale } = useI18n()
const { increment, decrement } = usePageLoading()

const path = ref<PathResponse | null>(null)
const loading = ref(true)

const displayName = computed(() => {
  if (!path.value) return ''
  return locale.value.startsWith('zh') && path.value.name_zh
    ? path.value.name_zh
    : path.value.name
})

const displayDescription = computed(() => {
  if (!path.value) return ''
  return path.value.description || undefined
})

const progressPercent = computed(() => {
  if (!path.value || path.value.total_count === 0) return 0
  return Math.round((path.value.completed_count / path.value.total_count) * 100)
})

function statusIcon(status: string) {
  switch (status) {
    case 'completed': return '✅'
    case 'in_progress': return '📖'
    default: return '📋'
  }
}

function isNext(item: PathItemResponse) {
  if (!path.value) return false
  const items = path.value.items
  const idx = items.findIndex(i => i.id === item.id)
  // Next is the first non-completed item
  return items.findIndex(i => i.status !== 'completed') === idx
}

function itemTopicName(item: PathItemResponse) {
  return locale.value.startsWith('zh') && item.topic_name_zh
    ? item.topic_name_zh
    : item.topic_name || `Topic ${item.topic_id}`
}

function navigateToTopic(item: PathItemResponse) {
  router.push(`/learning/topic/${item.topic_id}`)
}

async function load() {
  loading.value = true
  increment()
  try {
    const pathId = route.params.id as string
    path.value = await getMyPath(pathId)
  } catch {
    path.value = null
  } finally {
    loading.value = false
    decrement()
  }
}

onMounted(load)
</script>

<style scoped>
.learning-path-page {
  padding-bottom: env(safe-area-inset-bottom);
}
.path-header {
  padding: 16px;
}
.path-header h2 {
  margin: 0 0 8px;
  font-size: 20px;
}
.path-desc {
  color: var(--van-text-color-2);
  margin: 0 0 8px;
}
.path-meta {
  display: flex;
  gap: 8px;
}
.progress-section {
  padding: 0 16px 16px;
}
.next-milestone {
  margin: 8px 0 0;
  font-size: 13px;
  color: var(--van-orange);
}
.rewards-section {
  padding: 12px 16px;
  background: var(--van-background-2);
}
.rewards-section h3 {
  margin: 0 0 8px;
  font-size: 15px;
}
.rewards-section p {
  margin: 4px 0;
  font-size: 13px;
  color: var(--van-text-color-2);
}
.items-section {
  padding: 8px 0;
}
.path-item {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 12px 16px;
  cursor: pointer;
  transition: background 0.2s;
}
.path-item:active {
  background: var(--van-active-color);
}
.path-item.current {
  background: var(--van-primary-color-light, rgba(0, 128, 255, 0.05));
}
.path-item.completed .item-name {
  text-decoration: line-through;
  color: var(--van-text-color-3);
}
.item-icon {
  font-size: 20px;
}
.item-name {
  flex: 1;
  font-size: 15px;
}
</style>
