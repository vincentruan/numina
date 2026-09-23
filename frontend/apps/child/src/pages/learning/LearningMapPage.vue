<template>
  <div class="learning-map-page">
    <!-- Skeleton during initial load -->
    <RoleShimmer v-if="loading && !refreshing && mapItems.length === 0" variant="clay-pulse" />

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

        <!-- Empty state -->
        <EmptyState
          v-else-if="mapItems.length === 0"
          :illustration="noRecordsSvg"
          :text="t('learning.empty')"
        />

        <template v-else>
          <!-- Subject tabs -->
          <SubjectTabs
            v-model="selectedSubject"
            :tabs="subjectTabs"
          />

          <!-- Topic grid for selected subject -->
          <div class="map-content">
            <TopicGrid
              :items="filteredItems"
              @topic-click="onTopicClick"
            />

            <!-- Today recommendation -->
            <div v-if="recommended" class="recommendation-card">
              <div class="recommendation-card__header">
                <span class="recommendation-card__icon">🎯</span>
                <span class="recommendation-card__title">{{ t('learning.todayRecommend') }}</span>
              </div>
              <p class="recommendation-card__name">{{ topicDisplayName(recommended.topic) }}</p>
              <p class="recommendation-card__desc">{{ topicDescription(recommended.topic) }}</p>
              <button class="recommendation-card__btn" @click="onTopicClick(recommended.topic.id)">
                {{ t('learning.startLearning') }}
              </button>
            </div>
          </div>
        </template>
      </van-pull-refresh>
    </template>
  </div>
</template>

<script setup lang="ts">
defineOptions({ name: 'LearningMap' })

import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { useLocalizedTopic } from '@/composables/useLocalizedTopic'
import { usePageLoading } from '@/composables/usePageLoading'
import { getMyLearningMap, getTopicsBatch, type ProgressResponse, type TopicResponse } from '@/api/learning'
import type { ProgressWithTopic } from '@/api/learning'
import SubjectTabs from '@/components/learning/SubjectTabs.vue'
import type { SubjectTab } from '@/components/learning/SubjectTabs.vue'
import TopicGrid from '@/components/learning/TopicGrid.vue'
import RoleShimmer from '@/components/RoleShimmer.vue'
import EmptyState from '@/components/EmptyState.vue'
import { noRecordsSvg } from '@numina/assets/empty-states'

const { t, locale } = useI18n()
const { topicDisplayName, topicDescription } = useLocalizedTopic()
const router = useRouter()
const { increment, decrement } = usePageLoading()

const loading = ref(true)
const refreshing = ref(false)
const error = ref('')
const selectedSubject = ref('')
const progressList = ref<ProgressResponse[]>([])
const topicMap = ref<Map<string, TopicResponse>>(new Map())

// Composite items: progress + topic
const mapItems = computed<ProgressWithTopic[]>(() =>
  progressList.value
    .filter((p) => topicMap.value.has(p.topic_id))
    .map((p) => ({
      ...p,
      topic: topicMap.value.get(p.topic_id)!,
    })),
)

// Subject tabs derived from items
const subjectTabs = computed<SubjectTab[]>(() => {
  const counts = new Map<string, number>()
  for (const item of mapItems.value) {
    const s = item.topic.subject
    counts.set(s, (counts.get(s) || 0) + 1)
  }
  const tabs: SubjectTab[] = Array.from(counts.entries())
    .filter(([, count]) => count > 0)
    .map(([subject, count]) => ({ subject, count }))
    .sort((a, b) => a.subject.localeCompare(b.subject))

  // Auto-select first subject if current selection is invalid
  if (tabs.length > 0 && !tabs.find((t) => t.subject === selectedSubject.value)) {
    selectedSubject.value = tabs[0].subject
  }
  return tabs
})

const filteredItems = computed(() =>
  mapItems.value.filter((item) => item.topic.subject === selectedSubject.value),
)

// Today recommendation: pick first non-mastered topic
const recommended = computed(() => {
  const candidates = mapItems.value.filter(
    (item) => item.mastery_level !== 'mastered' && item.mastery_level !== 'locked',
  )
  return candidates[0] || mapItems.value[0] || null
})

function onTopicClick(topicId: string) {
  router.push(`/learning/${topicId}`)
}

async function load() {
  loading.value = true
  error.value = ''
  try {
    // Fetch progress list
    const progress = await getMyLearningMap()
    progressList.value = progress

    // Fetch topic details for each unique topic_id (batch)
    const uniqueTopicIds = [...new Set(progress.map((p) => p.topic_id))]
    const topicDetails = uniqueTopicIds.length > 0
      ? await getTopicsBatch(uniqueTopicIds)
      : []
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
.learning-map-page {
  padding: var(--space-md);
  background: var(--color-canvas);
  min-height: 100vh;
}

.map-content {
  padding-top: 12px;
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

/* ── Recommendation card ── */
.recommendation-card {
  margin-top: 20px;
  padding: 16px;
  background: var(--color-surface-soft);
  border: 1px solid var(--color-hairline);
  border-radius: var(--radius-lg);
}

.recommendation-card__header {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 10px;
}

.recommendation-card__icon {
  font-size: 20px;
  line-height: 1;
}

.recommendation-card__title {
  font-family: Inter, sans-serif;
  font-size: 14px;
  font-weight: 600;
  color: var(--color-brand-ochre);
  margin: 0;
}

.recommendation-card__name {
  font-family: Inter, sans-serif;
  font-size: 16px;
  font-weight: 600;
  color: var(--color-ink);
  margin: 0 0 6px;
}

.recommendation-card__desc {
  font-family: Inter, sans-serif;
  font-size: 14px;
  color: var(--color-body);
  margin: 0 0 14px;
  line-height: 1.5;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.recommendation-card__btn {
  width: 100%;
  background: var(--color-primary);
  color: var(--color-on-dark);
  border: none;
  border-radius: var(--radius-md);
  padding: 12px;
  font-family: Inter, sans-serif;
  font-size: 14px;
  font-weight: 600;
  cursor: pointer;
  min-height: 44px;
  transition: transform 0.1s;
}

.recommendation-card__btn:active {
  transform: scale(0.97);
}
</style>
