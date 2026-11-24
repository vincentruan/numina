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
          <!-- Page title — child-friendly wording -->
          <h1 class="page-title">{{ t('learning.progress.childTitle') }}</h1>

          <!-- Castle entry card — kept as primary visual -->
          <button
            type="button"
            class="castle-entry-card"
            data-test="progress-castle-entry"
            @click="router.push('/learning/castle')"
          >
            <span class="castle-entry-card__icon" aria-hidden="true">🏰</span>
            <span class="castle-entry-card__text">
              <span class="castle-entry-card__title">{{ t('learning.castle.entryTitle') }}</span>
              <span class="castle-entry-card__cta">{{ t('learning.castle.entryCta') }}</span>
            </span>
          </button>

          <!-- Up next recommendation card -->
          <div
            v-if="nextRecommendation"
            class="next-up-card"
            data-test="next-up-card"
            @click="goToTopic(nextRecommendation.topic_id)"
          >
            <div class="next-up-card__header">
              <span class="next-up-card__icon" aria-hidden="true">🎯</span>
              <span class="next-up-card__label">{{ t('learning.progress.nextUp') }}</span>
            </div>
            <p class="next-up-card__name">{{ nextRecommendation.topic_name }}</p>
            <p v-if="nextRecommendation.reasons.length > 0" class="next-up-card__reason">
              {{ formatReasons(nextRecommendation.reasons) }}
            </p>
            <button class="next-up-card__cta">
              {{ t('learning.startLearning') }}
            </button>
          </div>

          <!-- 7-day learning heatmap -->
          <div class="streak-section" data-test="streak-section">
            <h2 class="section-title">{{ t('learning.progress.streakTitle') }}</h2>
            <div class="streak-dots">
              <div
                v-for="day in last7Days"
                :key="day.date"
                class="streak-dot"
                :class="{
                  'streak-dot--active': day.active,
                  'streak-dot--today': day.isToday,
                }"
              >
                <span class="streak-dot__day">{{ day.dayLabel }}</span>
                <span v-if="day.active" class="streak-dot__fire" aria-hidden="true">🔥</span>
              </div>
            </div>
            <p class="streak-summary">{{ streakSummary }}</p>
          </div>

          <!--
            Sections below are commented out for child view — moved to parent view later.
            Code kept intact, not deleted.
          -->

          <!--
          <div v-if="learningStats" class="xp-level-section xp-level-section--secondary">
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
          -->
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
import { useRecommendationPath } from '@/composables/useRecommendationPath'
import { getMyLearningMap, getMyProgress, getMyLearningStats, getTopicsBatch, type ProgressResponse, type TopicResponse, type ChildProgressOverview, type LearningStatsResponse } from '@/api/learning'
import RoleShimmer from '@/components/RoleShimmer.vue'

const { t, locale } = useI18n()
const { topicDisplayName } = useLocalizedTopic()
const { increment, decrement } = usePageLoading()
const { allPathTopics, refresh: refreshRecommendations } = useRecommendationPath()

const loading = ref(true)
const refreshing = ref(false)
const error = ref('')
const progressList = ref<ProgressResponse[]>([])
const topicMap = ref<Map<string, TopicResponse>>(new Map())
const progressOverview = ref<ChildProgressOverview | null>(null)
const learningStats = ref<LearningStatsResponse | null>(null)
const router = useRouter()

// --- Up next recommendation ---
const masteredIds = computed(() =>
  new Set(progressList.value.filter(p => p.mastery_level === 'mastered').map(p => p.topic_id))
)

const nextRecommendation = computed(() => {
  return allPathTopics.value.find(
    rec => !masteredIds.value.has(rec.topic_id)
  ) ?? null
})

function formatReasons(reasons: readonly string[]): string {
  return reasons.join(' · ')
}

function goToTopic(topicId: string) {
  router.push(`/learning/topic/${topicId}`)
}

// --- 7-day heatmap ---
const last7Days = computed(() => {
  const practiceDates = new Set<string>()
  for (const p of progressList.value) {
    if (p.last_practice_at) {
      practiceDates.add(p.last_practice_at.slice(0, 10))
    }
  }
  const days: Array<{
    date: string
    dayLabel: string
    active: boolean
    isToday: boolean
  }> = []
  const now = new Date()
  for (let i = 6; i >= 0; i--) {
    const d = new Date(now)
    d.setDate(d.getDate() - i)
    const dateStr = d.toISOString().slice(0, 10)
    days.push({
      date: dateStr,
      dayLabel: d.toLocaleDateString(locale.value, { weekday: 'short' }),
      active: practiceDates.has(dateStr),
      isToday: i === 0,
    })
  }
  return days
})

const streakSummary = computed(() => {
  const activeDays = last7Days.value.filter(d => d.active).length
  return t('learning.progress.streakSummary', { days: activeDays })
})

async function load() {
  loading.value = true
  error.value = ''
  try {
    const [progress, overview, stats] = await Promise.all([
      getMyLearningMap(),
      getMyProgress(),
      getMyLearningStats(),
    ])
    progressList.value = progress
    progressOverview.value = overview
    learningStats.value = stats

    // Fetch recommendations for "up next" card
    await refreshRecommendations()

    // Fetch topic details for display names — batch in chunks to avoid
    // URL length limits and single-point failures from Promise.all.
    const uniqueTopicIds = [...new Set(progress.map((p) => p.topic_id))]
    const CHUNK = 50
    const newMap = new Map<string, TopicResponse>()
    for (let i = 0; i < uniqueTopicIds.length; i += CHUNK) {
      const chunk = uniqueTopicIds.slice(i, i + CHUNK)
      try {
        const topics = await getTopicsBatch(chunk)
        for (const topic of topics) {
          newMap.set(topic.id, topic)
        }
      } catch {
        // Individual chunk failure should not break the entire map.
      }
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

/* Castle entry card */
.castle-entry-card {
  display: flex;
  align-items: center;
  gap: 14px;
  width: 100%;
  margin-bottom: 16px;
  padding: 18px 16px;
  border: 2px solid var(--color-brand-ochre, #e8b94a);
  border-radius: var(--radius-lg);
  background: var(--color-surface-card);
  text-align: left;
  cursor: pointer;
}
.castle-entry-card:active {
  transform: scale(0.97);
}
.castle-entry-card__icon {
  font-size: 34px;
  line-height: 1;
}
.castle-entry-card__text {
  display: flex;
  flex-direction: column;
}
.castle-entry-card__title {
  font-size: 16px;
  font-weight: 600;
  color: var(--color-ink);
}
.castle-entry-card__cta {
  margin-top: 2px;
  font-size: 13px;
  color: var(--color-muted);
}

/* Up next recommendation card */
.next-up-card {
  margin-bottom: 20px;
  padding: 16px;
  background: var(--color-surface-card);
  border-radius: var(--radius-lg);
  cursor: pointer;
  transition: transform 0.1s;
}
.next-up-card:active {
  transform: scale(0.98);
}
.next-up-card__header {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-bottom: 10px;
}
.next-up-card__icon {
  font-size: 18px;
  line-height: 1;
}
.next-up-card__label {
  font-family: Inter, sans-serif;
  font-size: 13px;
  font-weight: 600;
  color: var(--color-body);
  text-transform: uppercase;
  letter-spacing: 0.5px;
}
.next-up-card__name {
  font-family: Inter, sans-serif;
  font-size: 18px;
  font-weight: 700;
  color: var(--color-ink);
  margin: 0 0 6px;
}
.next-up-card__reason {
  font-family: Inter, sans-serif;
  font-size: 13px;
  color: var(--color-body);
  margin: 0 0 14px;
  line-height: 1.4;
}
.next-up-card__cta {
  display: block;
  width: 100%;
  min-height: 44px;
  padding: 10px 16px;
  border: none;
  border-radius: var(--radius-md);
  background: var(--color-brand-ochre, #e8b94a);
  color: var(--color-ink);
  font-family: Inter, sans-serif;
  font-size: 15px;
  font-weight: 600;
  cursor: pointer;
  transition: opacity 0.1s;
}
.next-up-card__cta:active {
  opacity: 0.85;
}

/* 7-day streak heatmap */
.streak-section {
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
  margin: 0 0 12px;
}

.streak-dots {
  display: flex;
  justify-content: space-between;
  gap: 6px;
  margin-bottom: 10px;
}

.streak-dot {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 6px;
  flex: 1;
}

.streak-dot__day {
  font-family: Inter, sans-serif;
  font-size: 11px;
  color: var(--color-body);
  text-transform: capitalize;
}

.streak-dot__day::after {
  content: '';
  display: block;
  width: 28px;
  height: 28px;
  margin-top: 4px;
  border-radius: 50%;
  background: var(--color-canvas);
  border: 2px solid var(--color-muted);
}

.streak-dot--active .streak-dot__day::after {
  background: var(--color-brand-ochre, #e8b94a);
  border-color: var(--color-brand-ochre, #e8b94a);
}

.streak-dot--today .streak-dot__day::after {
  border-width: 3px;
  border-color: var(--color-ink);
}

.streak-dot--active.streak-dot--today .streak-dot__day::after {
  border-color: var(--color-ink);
}

.streak-dot__fire {
  position: absolute;
  font-size: 14px;
  line-height: 1;
  margin-top: 22px;
}

.streak-dot {
  position: relative;
}

.streak-summary {
  font-family: Inter, sans-serif;
  font-size: 14px;
  font-weight: 600;
  color: var(--color-ink);
  text-align: center;
  margin: 0;
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

/* Dark mode support */
[data-theme="dark"] .next-up-card__cta {
  color: var(--color-canvas);
}

[data-theme="dark"] .streak-dot__day {
  color: var(--color-body);
}
</style>
