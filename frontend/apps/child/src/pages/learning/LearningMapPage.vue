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

          <!-- View mode toggle -->
          <div class="view-mode-toggle">
            <button
              class="view-mode-btn"
              :class="{ 'view-mode-btn--active': viewMode === 'list' }"
              @click="viewMode = 'list'"
            >
              {{ t('learning.graphMap.viewList') }}
            </button>
            <button
              class="view-mode-btn"
              :class="{ 'view-mode-btn--active': viewMode === 'graph' }"
              @click="viewMode = 'graph'"
            >
              {{ t('learning.graphMap.viewGraph') }}
            </button>
          </div>

          <!-- Cluster map for selected subject -->
          <div class="map-content">
            <ClusterMap
              v-if="viewMode === 'list'"
              :items="mapItems"
              :selected-subject="selectedSubject"
              :path-topic-ids="pathTopicIds"
              :path-reasons="pathReasons"
              :next-topic="nextTopic"
              :is-loading="recLoading"
              @switch-subject="onSwitchSubject"
            />

            <!-- Graph view (Cytoscape.js) -->
            <GraphMap
              v-else
              :items="mapItems"
              :selected-subject="selectedSubject"
              @switch-subject="onSwitchSubject"
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

import { ref, computed, watch, onMounted, onActivated, nextTick } from 'vue'
import { useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { showToast } from 'vant'
import { useLocalizedTopic } from '@/composables/useLocalizedTopic'
import { usePageLoading } from '@/composables/usePageLoading'
import { useRecommendationPath } from '@/composables/useRecommendationPath'
import { getMyLearningMapIndex, getTopicsBatch, type TopicResponse } from '@/api/learning'
import type { ProgressWithTopic } from '@/api/learning'
import SubjectTabs from '@/components/learning/SubjectTabs.vue'
import type { SubjectTab } from '@/components/learning/SubjectTabs.vue'
import ClusterMap from '@/components/learning/ClusterMap.vue'
import GraphMap from '@/components/learning/GraphMap.vue'
import RoleShimmer from '@/components/RoleShimmer.vue'
import EmptyState from '@/components/EmptyState.vue'
import { noRecordsSvg } from '@numina/assets/empty-states'

const { t } = useI18n()
const { topicDisplayName, topicDescription } = useLocalizedTopic()
const router = useRouter()
const { increment, decrement } = usePageLoading()
const { allPathTopics, isLoading: recLoading, refresh: refreshRecommendations } = useRecommendationPath()

const loading = ref(true)
const refreshing = ref(false)
const error = ref('')
const selectedSubject = ref('')
const viewMode = ref<'list' | 'graph'>('list')
const progressList = ref<Array<{
  topic_id: string
  mastery_level: string
  next_review_at: string | null
  subject?: string | null
  domain?: string | null
  age_group?: string | null
}>>([])
const topicMap = ref<Map<string, TopicResponse>>(new Map())
// Subjects whose topic details have been fetched (R10 progressive loading).
const loadedSubjects = ref<Set<string>>(new Set())
// In-flight fetches, so the selectedSubject watcher and load() don't both fire
// the same batch request (a duplicate round trip on a throttled link).
const inflightSubjects = new Map<string, Promise<void>>()

// Composite items: progress + topic
const mapItems = computed<ProgressWithTopic[]>(() =>
  progressList.value
    .filter((p) => topicMap.value.has(p.topic_id))
    .map((p) => ({
      id: p.topic_id,
      child_id: '',
      topic_id: p.topic_id,
      mastery_level: p.mastery_level,
      mastery_score: null,
      completed_via: null,
      attempts: 0,
      xp_earned: 0,
      last_practice_at: null,
      first_mastered_at: null,
      stability: null,
      next_review_at: p.next_review_at,
      ability_dimensions_score: null,
      topic: topicMap.value.get(p.topic_id)!,
    })),
)

// Recommendation path: all topic IDs (unfiltered — ClusterMap filters by subject)
const pathTopicIds = computed(() => allPathTopics.value.map((t) => t.topic_id))

// Map topic_id → reasons[] so ClusterMap can show "why recommended" on tap
const pathReasons = computed<Record<string, string[]>>(() => {
  const map: Record<string, string[]> = {}
  for (const rec of allPathTopics.value) {
    map[rec.topic_id] = [...rec.reasons]
  }
  return map
})

// Next topic: first recommended topic matching current subject
const nextTopic = computed<ProgressWithTopic | null>(() => {
  for (const rec of allPathTopics.value) {
    const match = mapItems.value.find(
      (m) => m.topic.id === rec.topic_id && m.topic.subject === selectedSubject.value,
    )
    if (match) return match
  }
  return null
})

// Subject tabs derived from the progress index (subject is joined into
// /child/learning/map/index), so tabs render before any topic detail is fetched.
const subjectTabs = computed<SubjectTab[]>(() => {
  const counts = new Map<string, number>()
  for (const p of progressList.value) {
    const s = p.subject
    if (!s) continue
    counts.set(s, (counts.get(s) || 0) + 1)
  }
  return Array.from(counts.entries())
    .filter(([, count]) => count > 0)
    .map(([subject, count]) => ({ subject, count }))
    .sort((a, b) => a.subject.localeCompare(b.subject))
})

// Auto-select first subject if current selection is invalid
watch(subjectTabs, (tabs) => {
  if (tabs.length > 0 && !tabs.find((t) => t.subject === selectedSubject.value)) {
    selectedSubject.value = tabs[0].subject
  }
})

// Fetch topic details for one subject only, then merge into the topic map.
// R10: the selected subject loads first; other subjects load on tab switch.
function loadSubjectTopics(subject: string): Promise<void> {
  if (!subject || loadedSubjects.value.has(subject)) return Promise.resolve()
  const inflight = inflightSubjects.get(subject)
  if (inflight) return inflight
  // Snapshot IDs from the current progressList — safe because load() awaits
  // the index before calling us, and the watcher fires only after it is set.
  const ids = progressList.value
    .filter((p) => p.subject === subject)
    .map((p) => p.topic_id)
  const task = getTopicsBatch(ids)
    .then((topics) => {
      const next = new Map(topicMap.value)
      for (const topic of topics) next.set(topic.id, topic)
      topicMap.value = next
      loadedSubjects.value = new Set([...loadedSubjects.value, subject])
    })
    .catch(() => {
      // Leave the subject unmarked so a later switch retries.
    })
    .finally(() => {
      inflightSubjects.delete(subject)
    })
  inflightSubjects.set(subject, task)
  return task
}

// Load details for the selected subject whenever the selection changes.
watch(selectedSubject, (subject) => {
  void loadSubjectTopics(subject)
})

// Bridge navigation: switch subject tab
function onSwitchSubject(subject: string) {
  // Tabs are derived from the child's progress items, but bridge targets come
  // from cluster domains. A bridge can point at a subject the child has no
  // progress in — that subject has no tab, and setting it here would leave
  // every tab inactive with no way back. Keep the current tab and explain.
  if (subjectTabs.value.some((tab) => tab.subject === subject)) {
    selectedSubject.value = subject
    return
  }
  showToast(t('learning.cluster.bridgeNoContent'))
}

// Today recommendation: pick first non-mastered topic
const recommended = computed(() => {
  const candidates = mapItems.value.filter(
    (item) => item.mastery_level !== 'mastered' && item.mastery_level !== 'locked',
  )
  return candidates[0] || mapItems.value[0] || null
})

function onTopicClick(topicId: string) {
  router.push(`/learning/topic/${topicId}`)
}

async function load() {
  loading.value = true
  error.value = ''
  try {
    // Fetch the slim progress index (only topic_id, mastery_level,
    // next_review_at, subject, domain, age_group) so the cluster map can
    // render subject tabs and mastery-coloured nodes without the heavy
    // ProgressResponse payload (evidence, standards, assessment_prompt, …).
    progressList.value = await getMyLearningMapIndex()

    await nextTick()
    const subject =
      selectedSubject.value || subjectTabs.value[0]?.subject || ''
    if (subject) {
      selectedSubject.value = subject
      await loadSubjectTopics(subject)
    }
  } catch {
    error.value = t('toast.loadFailed')
  } finally {
    loading.value = false
  }
}

async function onRefresh() {
  // Drop per-subject caches so pull-to-refresh re-fetches topic detail
  // (name/description/evidence) alongside the slim mastery index.
  // in-flight promises continue to their natural conclusion; subsequent
  // loads will start fresh batches.
  loadedSubjects.value = new Set()
  inflightSubjects.clear()
  topicMap.value = new Map()
  await Promise.all([load(), refreshRecommendations()])
  refreshing.value = false
}

onMounted(async () => {
  increment()
  try {
    await Promise.all([load(), refreshRecommendations()])
  } finally {
    decrement()
  }
})

// R10/KTD4: re-fetch recommendation path when page re-activates from
// KeepAlive cache (e.g. after returning from practice).
// Also re-fetch the progress index so ClusterMap can detect frontier changes
// (new topic became the recommendation after practice updated mastery).
onActivated(async () => {
  // Drop per-subject caches so the progress re-fetch pulls fresh topic detail.
  loadedSubjects.value = new Set()
  inflightSubjects.clear()
  topicMap.value = new Map()
  await Promise.all([load(), refreshRecommendations()])
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

/* ── View mode toggle ── */

.view-mode-toggle {
  display: flex;
  gap: 4px;
  margin-top: 12px;
  padding: 3px;
  background: var(--color-surface-card);
  border-radius: var(--radius-md, 8px);
  width: fit-content;
}

.view-mode-btn {
  padding: 6px 14px;
  border: none;
  border-radius: var(--radius-sm, 6px);
  background: transparent;
  color: var(--color-muted);
  font-family: Inter, sans-serif;
  font-size: 13px;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.2s;
  min-height: 32px;
}

.view-mode-btn--active {
  background: var(--color-canvas);
  color: var(--color-ink);
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.08);
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
