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

          <!-- XP / Level / Streak section -->
          <div v-if="learningStats" class="xp-level-section">
            <div class="xp-level-header">
              <LevelBadge :emoji="learningStats.level_emoji" :name="locale === 'en-US' ? learningStats.level_name_en : learningStats.level_name_zh" />
              <LearningStreakBadge :days="learningStats.learning_streak_days" />
            </div>
            <XPProgressBar
              :current-xp="learningStats.cumulative_xp"
              :level="learningStats.level"
              :level-name="locale === 'en-US' ? learningStats.level_name_en : learningStats.level_name_zh"
              :emoji="learningStats.level_emoji"
              :next-threshold="learningStats.next_level_threshold"
            />
          </div>

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
            <div class="study-stats">
              <div class="study-stat">
                <span class="study-stat__value">{{ totalStudyMinutes }}</span>
                <span class="study-stat__label">{{ t('learning.progress.totalMinutes') }}</span>
              </div>
              <div class="study-stat">
                <span class="study-stat__value">{{ todayStudyMinutes }}</span>
                <span class="study-stat__label">{{ t('learning.progress.todayMinutes') }}</span>
              </div>
            </div>
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

          <!-- Weak topics card -->
          <div v-if="weakTopics.length > 0" class="weak-topics-section">
            <h2 class="section-title">{{ t('learning.progress.weakTopics') }}</h2>
            <div class="weak-topics-list">
              <div
                v-for="topic in weakTopics"
                :key="topic.topic_id"
                class="weak-topic-card"
                @click="navigateToPractice(topic.topic_id)"
              >
                <div class="weak-topic-card__header">
                  <span class="weak-topic-card__name">{{ getWeakTopicDisplayName(topic) }}</span>
                  <span class="weak-topic-card__accuracy">{{ Math.round(topic.accuracy * 100) }}%</span>
                </div>
                <div class="weak-topic-card__footer">
                  <span class="weak-topic-card__attempts">
                    {{ topic.total_attempts }} {{ t('learning.progress.attempts') }}
                  </span>
                  <span :class="['weak-topic-card__mastery', `mastery--${topic.mastery_level}`]">
                    {{ t(`learning.status.${topic.mastery_level}`) }}
                  </span>
                </div>
              </div>
            </div>
          </div>

          <!-- Recent practice sessions -->
          <div v-if="recentSessions.length > 0" class="sessions-section">
            <h2 class="section-title">{{ t('learning.progress.recentSessions') }}</h2>
            <div class="sessions-list">
              <div
                v-for="session in recentSessions"
                :key="session.id"
                class="session-card"
              >
                <div class="session-card__header">
                  <span class="session-card__topic">{{ getSessionTopicName(session) }}</span>
                  <span v-if="session.total_score != null" class="session-card__score">
                    {{ Math.round(session.total_score * 100) }}%
                  </span>
                </div>
                <div class="session-card__meta">
                  <span>{{ session.completed_count }}/{{ session.total_count }}</span>
                  <span>{{ formatDate(session.started_at) }}</span>
                </div>
              </div>
            </div>
          </div>
        </template>
      </van-pull-refresh>
    </template>
  </div>
</template>

<script setup lang="ts">
defineOptions({ name: 'LearningProgress' })

import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { useLocalizedTopic } from '@/composables/useLocalizedTopic'
import { usePageLoading } from '@/composables/usePageLoading'
import { getMyLearningMap, getMyProgress, getMyLearningStats, getTopicDetail, type ProgressResponse, type TopicResponse, type ChildProgressOverview, type LearningStatsResponse } from '@/api/learning'
import { getWeakTopics, listPracticeSessions, type WeakTopicResponse, type SessionListItem } from '@/api/practice'
import RoleShimmer from '@/components/RoleShimmer.vue'
import XPProgressBar from '@/components/learning/XPProgressBar.vue'
import LevelBadge from '@/components/learning/LevelBadge.vue'
import LearningStreakBadge from '@/components/learning/LearningStreakBadge.vue'

const { t, locale } = useI18n()
const { topicDisplayName } = useLocalizedTopic()
const { increment, decrement } = usePageLoading()

const loading = ref(true)
const refreshing = ref(false)
const error = ref('')
const progressList = ref<ProgressResponse[]>([])
const topicMap = ref<Map<string, TopicResponse>>(new Map())
const progressOverview = ref<ChildProgressOverview | null>(null)
const learningStats = ref<LearningStatsResponse | null>(null)
const weakTopics = ref<WeakTopicResponse[]>([])
const recentSessions = ref<SessionListItem[]>([])
const router = useRouter()

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
  progressList.value.filter((p) =>
    p.mastery_level === 'mastered' &&
    p.next_review_at &&
    new Date(p.next_review_at) <= new Date()
  ).length,
)

const totalStudyMinutes = computed(() => {
  return progressOverview.value?.total_study_minutes ?? 0
})

const todayStudyMinutes = computed(() => {
  return progressOverview.value?.today_study_minutes ?? 0
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
  return topicDisplayName(topic)
}

function formatDate(dateStr: string): string {
  const date = new Date(dateStr)
  return date.toLocaleDateString(locale.value, {
    month: 'short',
    day: 'numeric',
  })
}

function getWeakTopicDisplayName(item: { topic_name: string; topic_name_zh: string | null }): string {
  return locale.value === 'en-US' ? item.topic_name : (item.topic_name_zh || item.topic_name)
}

function getSessionTopicName(session: { topic_name: string; topic_name_zh: string | null }): string {
  return locale.value === 'en-US' ? session.topic_name : (session.topic_name_zh || session.topic_name)
}

function navigateToPractice(topicId: string) {
  router.push(`/learning/practice/${topicId}`)
}

async function load() {
  loading.value = true
  error.value = ''
  try {
    const [progress, overview, stats, weak, sessions] = await Promise.all([
      getMyLearningMap(),
      getMyProgress(),
      getMyLearningStats(),
      getWeakTopics(10, 1),
      listPracticeSessions(10),
    ])
    progressList.value = progress
    progressOverview.value = overview
    learningStats.value = stats
    weakTopics.value = weak
    recentSessions.value = sessions

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

/* XP/Level section */
.xp-level-section {
  margin-bottom: 20px;
  padding: 16px;
  background: var(--color-surface-card);
  border-radius: var(--radius-lg);
}

.xp-level-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
}

/* Learning section on home */
.learning-section {
  margin: 12px 0;
}

.learning-header {
  display: flex;
  justify-content: flex-end;
  margin-bottom: 4px;
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

.study-stats {
  display: flex;
  gap: 24px;
}

.study-stat {
  display: flex;
  flex-direction: column;
}

.study-stat__value {
  font-family: Inter, sans-serif;
  font-size: 20px;
  font-weight: 700;
  color: var(--color-brand-ochre);
}

.study-stat__label {
  font-family: Inter, sans-serif;
  font-size: 12px;
  color: var(--color-body);
  margin-top: 2px;
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

/* Weak topics section */
.weak-topics-section {
  margin-bottom: 24px;
}

.weak-topics-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.weak-topic-card {
  padding: 12px 14px;
  background: var(--color-surface-card);
  border-radius: var(--radius-md);
  cursor: pointer;
}

.weak-topic-card__header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 6px;
}

.weak-topic-card__name {
  font-family: Inter, sans-serif;
  font-size: 14px;
  font-weight: 500;
  color: var(--color-ink);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  flex: 1;
}

.weak-topic-card__accuracy {
  font-family: Inter, sans-serif;
  font-size: 14px;
  font-weight: 700;
  color: var(--color-brand-coral);
  margin-left: 8px;
}

.weak-topic-card__footer {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.weak-topic-card__attempts {
  font-family: Inter, sans-serif;
  font-size: 12px;
  color: var(--color-body);
}

.weak-topic-card__mastery {
  font-family: Inter, sans-serif;
  font-size: 11px;
  padding: 2px 8px;
  border-radius: 10px;
  background: var(--color-surface-soft);
  color: var(--color-body);
}

.mastery--learning {
  color: var(--color-primary);
}

.mastery--assessing {
  color: var(--color-brand-ochre);
}

.mastery--mastered {
  color: var(--color-brand-ochre);
}

.mastery--review {
  color: var(--color-brand-coral);
}

/* Sessions section */
.sessions-section {
  margin-bottom: 24px;
}

.sessions-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.session-card {
  padding: 12px 14px;
  background: var(--color-surface-card);
  border-radius: var(--radius-md);
}

.session-card__header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 4px;
}

.session-card__topic {
  font-family: Inter, sans-serif;
  font-size: 14px;
  font-weight: 500;
  color: var(--color-ink);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  flex: 1;
}

.session-card__score {
  font-family: Inter, sans-serif;
  font-size: 14px;
  font-weight: 700;
  color: var(--color-brand-ochre);
  margin-left: 8px;
}

.session-card__meta {
  display: flex;
  justify-content: space-between;
  font-family: Inter, sans-serif;
  font-size: 12px;
  color: var(--color-body);
}
</style>
