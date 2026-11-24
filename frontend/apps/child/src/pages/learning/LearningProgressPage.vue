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
import { usePageLoading } from '@/composables/usePageLoading'
import { useRecommendationPath } from '@/composables/useRecommendationPath'
import { getMyLearningMap, type ProgressResponse } from '@/api/learning'
import RoleShimmer from '@/components/RoleShimmer.vue'

const { t, locale } = useI18n()
const { increment, decrement } = usePageLoading()
const { allPathTopics, refresh: refreshRecommendations } = useRecommendationPath()

const loading = ref(true)
const refreshing = ref(false)
const error = ref('')
const progressList = ref<ProgressResponse[]>([])
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
    const progress = await getMyLearningMap()
    progressList.value = progress

    await refreshRecommendations()
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
