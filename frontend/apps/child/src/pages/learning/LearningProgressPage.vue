<template>
  <div class="learning-progress-page">
    <RoleShimmer v-if="loading && !refreshing && progressList.length === 0" variant="clay-pulse" />

    <template v-else>
      <van-pull-refresh
        v-model="refreshing"
        :pulling-text="t('common.pullRefresh.pulling')"
        :loosing-text="t('common.pullRefresh.loosing')"
        :loading-text="t('common.pullRefresh.loading')"
        :success-text="t('common.pullRefresh.success')"
        @refresh="onRefresh"
      >
        <!-- Error state -->
        <div v-if="error" class="error-msg">{{ error }}</div>

        <template v-else>
          <!-- Page title -->
          <h1 class="page-title">{{ t('learning.progress.title') }}</h1>

          <!-- Stats summary cards -->
          <div class="stats-grid">
            <div class="stat-card stat-card--mastered">
              <span class="stat-card__count">{{ masteredCount }}</span>
              <span class="stat-card__label">{{ t('learning.status.mastered') }}</span>
            </div>
            <div class="stat-card stat-card--learning">
              <span class="stat-card__count">{{ learningCount }}</span>
              <span class="stat-card__label">{{ t('learning.status.learning') }}</span>
            </div>
            <div class="stat-card stat-card--available">
              <span class="stat-card__count">{{ availableCount }}</span>
              <span class="stat-card__label">{{ t('learning.status.available') }}</span>
            </div>
            <div class="stat-card stat-card--review">
              <span class="stat-card__count">{{ reviewCount }}</span>
              <span class="stat-card__label">{{ t('learning.status.review') }}</span>
            </div>
          </div>

          <!-- Study time -->
          <div class="study-section">
            <h2 class="section-title">{{ t('learning.progress.studyTime') }}</h2>
            <p class="study-value">{{ totalStudyMinutes }} {{ t('learning.progress.minutes') }}</p>
          </div>

          <!-- Recent activity -->
          <div class="activity-section">
            <h2 class="section-title">{{ t('learning.progress.recentActivity') }}</h2>
            <div v-if="recentActivity.length === 0" class="activity-empty">
              {{ t('learning.progress.noActivity') }}
            </div>
            <div v-else class="activity-list">
              <div
                v-for="item in recentActivity"
                :key="item.id"
                class="activity-item"
              >
                <div class="activity-item__info">
                  <span class="activity-item__topic">{{ getTopicName(item.topic_id) }}</span>
                  <span class="activity-item__status">
                    {{ t(`learning.status.${item.mastery_level}`) }}
                  </span>
                </div>
                <div class="activity-item__meta">
                  <span v-if="item.mastery_score != null">
                    {{ Math.round(item.mastery_score * 100) }}%
                  </span>
                  <span v-if="item.last_practice_at" class="activity-item__date">
                    {{ formatDate(item.last_practice_at) }}
                  </span>
                </div>
              </div>
            </div>
          </div>

          <!-- Coming soon placeholder for richer stats -->
          <div class="coming-soon">
            <p class="coming-soon__text">{{ t('learning.progress.comingSoon') }}</p>
          </div>
        </template>
      </van-pull-refresh>
    </template>
  </div>
</template>

<script setup lang="ts">
defineOptions({ name: 'LearningProgress' })

import { ref, computed, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { usePageLoading } from '@/composables/usePageLoading'
import { getMyLearningMap, getTopicDetail, type ProgressResponse, type TopicResponse } from '@/api/learning'
import RoleShimmer from '@/components/RoleShimmer.vue'

const { t, locale } = useI18n()
const { increment, decrement } = usePageLoading()

const loading = ref(true)
const refreshing = ref(false)
const error = ref('')
const progressList = ref<ProgressResponse[]>([])
const topicMap = ref<Map<string, TopicResponse>>(new Map())

// Computed stats
const masteredCount = computed(() =>
  progressList.value.filter((p) => p.mastery_level === 'mastered').length,
)

const learningCount = computed(() =>
  progressList.value.filter((p) => p.mastery_level === 'learning').length,
)

const availableCount = computed(() =>
  progressList.value.filter((p) => p.mastery_level === 'available').length,
)

const reviewCount = computed(() =>
  progressList.value.filter((p) => p.mastery_level === 'review').length,
)

const totalStudyMinutes = computed(() => {
  // Sum xp_earned as a proxy for study time (until backend provides study_minutes)
  return progressList.value.reduce((sum, p) => sum + (p.xp_earned || 0), 0)
})

// Recent activity: sort by last_practice_at descending, take top 10
const recentActivity = computed(() => {
  return [...progressList.value]
    .filter((p) => p.last_practice_at)
    .sort((a, b) => {
      const dateA = new Date(a.last_practice_at!).getTime()
      const dateB = new Date(b.last_practice_at!).getTime()
      return dateB - dateA
    })
    .slice(0, 10)
})

function getTopicName(topicId: string): string {
  const topic = topicMap.value.get(topicId)
  if (!topic) return topicId
  if (locale.value.startsWith('zh') && topic.name_zh) return topic.name_zh
  return topic.name || topic.topic_key
}

function formatDate(dateStr: string): string {
  const date = new Date(dateStr)
  return date.toLocaleDateString(locale.value, {
    month: 'short',
    day: 'numeric',
  })
}

async function load() {
  loading.value = true
  error.value = ''
  try {
    const progress = await getMyLearningMap()
    progressList.value = progress

    // Fetch topic details for display names
    const uniqueTopicIds = [...new Set(progress.map((p) => p.topic_id))]
    const topicDetails = await Promise.all(
      uniqueTopicIds.map((id) => getTopicDetail(id)),
    )
    const newMap = new Map<string, TopicResponse>()
    for (const topic of topicDetails) {
      newMap.set(topic.id, topic)
    }
    topicMap.value = newMap
  } catch {
    error.value = t('toast.loadFailed')
  } finally {
    loading.value = false
  }
}

async function onRefresh() {
  await load()
  refreshing.value = false
}

onMounted(async () => {
  increment()
  try {
    await load()
  } finally {
    decrement()
  }
})
</script>

<style scoped>
.learning-progress-page {
  padding: var(--space-md);
  background: var(--color-canvas);
  min-height: 100vh;
}

.page-title {
  font-family: Inter, sans-serif;
  font-size: 22px;
  font-weight: 700;
  color: var(--color-ink);
  margin: 0 0 20px;
}

.error-msg {
  background: var(--color-brand-coral);
  color: var(--color-on-dark);
  border-radius: var(--radius-md);
  padding: 10px 14px;
  margin-bottom: 12px;
  font-family: Inter, sans-serif;
  font-size: 14px;
}

/* Stats grid */
.stats-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 12px;
  margin-bottom: 24px;
}

.stat-card {
  padding: 16px;
  border-radius: var(--radius-lg);
  background: var(--color-surface-card);
  text-align: center;
}

.stat-card__count {
  display: block;
  font-family: Inter, sans-serif;
  font-size: 28px;
  font-weight: 700;
  line-height: 1.2;
}

.stat-card__label {
  display: block;
  font-family: Inter, sans-serif;
  font-size: 13px;
  margin-top: 4px;
}

.stat-card--mastered .stat-card__count {
  color: var(--color-brand-ochre);
}

.stat-card--learning .stat-card__count {
  color: var(--color-primary);
}

.stat-card--available .stat-card__count {
  color: var(--color-body);
}

.stat-card--review .stat-card__count {
  color: var(--color-brand-coral);
}

.stat-card--mastered .stat-card__label,
.stat-card--learning .stat-card__label,
.stat-card--available .stat-card__label,
.stat-card--review .stat-card__label {
  color: var(--color-body);
}

/* Study section */
.study-section {
  margin-bottom: 24px;
  padding: 16px;
  background: var(--color-surface-card);
  border-radius: var(--radius-lg);
}

.section-title {
  font-family: Inter, sans-serif;
  font-size: 15px;
  font-weight: 600;
  color: var(--color-ink);
  margin: 0 0 10px;
}

.study-value {
  font-family: Inter, sans-serif;
  font-size: 20px;
  font-weight: 700;
  color: var(--color-brand-ochre);
  margin: 0;
}

/* Activity section */
.activity-section {
  margin-bottom: 24px;
}

.activity-empty {
  font-family: Inter, sans-serif;
  font-size: 14px;
  color: var(--color-body);
  text-align: center;
  padding: 24px;
  background: var(--color-surface-soft);
  border-radius: var(--radius-md);
}

.activity-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.activity-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px 14px;
  background: var(--color-surface-card);
  border-radius: var(--radius-md);
}

.activity-item__info {
  display: flex;
  flex-direction: column;
  gap: 2px;
  min-width: 0;
  flex: 1;
}

.activity-item__topic {
  font-family: Inter, sans-serif;
  font-size: 14px;
  font-weight: 500;
  color: var(--color-ink);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.activity-item__status {
  font-family: Inter, sans-serif;
  font-size: 12px;
  color: var(--color-body);
}

.activity-item__meta {
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  gap: 2px;
  font-family: Inter, sans-serif;
  font-size: 13px;
  color: var(--color-brand-ochre);
  font-weight: 600;
}

.activity-item__date {
  font-size: 11px;
  color: var(--color-body);
  font-weight: 400;
}

/* Coming soon */
.coming-soon {
  text-align: center;
  padding: 20px;
  margin-top: 16px;
  background: var(--color-surface-soft);
  border-radius: var(--radius-md);
  border: 1px dashed var(--color-hairline);
}

.coming-soon__text {
  font-family: Inter, sans-serif;
  font-size: 14px;
  color: var(--color-body);
  margin: 0;
}
</style>
