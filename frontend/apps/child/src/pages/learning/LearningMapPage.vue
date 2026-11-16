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

        <!-- Empty state — only when there is nothing to explore at all -->
        <EmptyState
          v-else-if="mapItems.length === 0 && topicIndex.length === 0"
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
              :class="{ 'view-mode-btn--active': viewMode === 'ocean' }"
              @click="viewMode = 'ocean'"
            >
              {{ t('learning.graphMap.viewOcean') }}
            </button>
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

          <!-- Knowledge ocean (default view — R1): three-level zoomable map -->
          <KnowledgeOcean
            v-if="viewMode === 'ocean'"
            :subjects="oceanSubjects"
            :domains="oceanDomains"
            :topics="oceanTopics"
            :edges="oceanEdges"
            :selected-subject="oceanSubject"
            :selected-domain="oceanDomain"
            @preview-subject="onPreviewSubject"
            @select-subject="onOceanSelectSubject"
            @preview-domain="onPreviewDomain"
            @select-domain="onOceanSelectDomain"
            @select-topic="onOceanSelectTopic"
            @zoom-out="onOceanZoomOut"
            @zoomed="exploration.recordZoom"
            @interacted="exploration.recordInteraction"
          />

          <!-- Cluster map for selected subject -->
          <div v-else class="map-content">
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

      <!-- Subject preview (R6/AE2 — a fogged island tap yields a preview,
           never a refusal; the child can continue into the subject).
           overlay=false (#2 fix): a dimming scrim intercepts the second tap of
           an R8 double-tap, so we drop the overlay and rely on swipe-to-dismiss
           or the Explore button. teleport="body" matches the popup-clipping
           learning in docs/solutions/ui-bugs/action-sheet-clipped-in-transformed-container.md. -->
      <van-popup
        :show="!!previewSubjectId"
        position="bottom"
        round
        :overlay="false"
        teleport="body"
        :style="{ padding: '16px', maxWidth: '400px', margin: '0 auto' }"
        @update:show="previewSubjectId = ''"
      >
        <div v-if="previewSubject" class="ocean-preview">
          <div class="ocean-preview__header">
            <span class="ocean-preview__icon">{{ previewSubject.icon }}</span>
            <span class="ocean-preview__title">{{ previewSubject.displayName }}</span>
          </div>
          <p class="ocean-preview__stats">
            {{ t('learning.ocean.previewMastered', {
              mastered: previewSubject.masteredCount,
              total: previewSubject.topicCount,
            }) }}
          </p>
          <button class="ocean-preview__btn" @click="onOceanSelectSubject(previewSubject.id)">
            {{ t('learning.ocean.exploreSubject', { subject: previewSubject.displayName }) }}
          </button>
        </div>
      </van-popup>

      <!-- Domain preview (R6 — same contract at region level).
           overlay=false for the same #2 fix as the subject preview. -->
      <van-popup
        :show="!!previewDomainRef"
        position="bottom"
        round
        :overlay="false"
        teleport="body"
        :style="{ padding: '16px', maxWidth: '400px', margin: '0 auto' }"
        @update:show="previewDomainRef = null"
      >
        <div v-if="previewDomain" class="ocean-preview">
          <div class="ocean-preview__header">
            <span class="ocean-preview__title">{{ previewDomain.displayName }}</span>
          </div>
          <p class="ocean-preview__stats">
            {{ t('learning.ocean.topics', { count: previewDomain.topicCount }) }}
          </p>
          <button
            class="ocean-preview__btn"
            @click="onOceanSelectDomain({ subject: previewDomain.subject, domain: previewDomain.domain })"
          >
            {{ t('learning.ocean.exploreDomain') }}
          </button>
        </div>
      </van-popup>
    </template>
  </div>
</template>

<script setup lang="ts">
defineOptions({ name: 'LearningMap' })

import { ref, computed, watch, onMounted, onActivated, onDeactivated, onUnmounted, nextTick } from 'vue'
import { useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { showToast } from 'vant'
import { useLocalizedTopic } from '@/composables/useLocalizedTopic'
import { usePageLoading } from '@/composables/usePageLoading'
import { useRecommendationPath } from '@/composables/useRecommendationPath'
import { useMapExploration } from '@/composables/useMapExploration'
import {
  getMyLearningMapIndex,
  getTopicsBatch,
  getTopicIndex,
  refreshTopicIndex,
  getSubjectDependencies,
  type TopicResponse,
  type TopicIndexRow,
  type DependencyEdge,
} from '@/api/learning'
import type { ProgressWithTopic } from '@/api/learning'
import SubjectTabs from '@/components/learning/SubjectTabs.vue'
import type { SubjectTab } from '@/components/learning/SubjectTabs.vue'
import ClusterMap from '@/components/learning/ClusterMap.vue'
import KnowledgeOcean from '@/components/learning/KnowledgeOcean.vue'
import type {
  OceanSubject,
  OceanDomain,
  OceanTopic,
} from '@/components/learning/KnowledgeOcean.vue'
import GraphMap from '@/components/learning/GraphMap.vue'
import RoleShimmer from '@/components/RoleShimmer.vue'
import EmptyState from '@/components/EmptyState.vue'
import { noRecordsSvg } from '@numina/assets/empty-states'
import { getContinentTheme } from '@/data/continentThemes'
import { domainLabel } from '@/utils/domainLabel'

const { t, locale } = useI18n()
const { topicDisplayName, topicDescription } = useLocalizedTopic()
const router = useRouter()
const { increment, decrement } = usePageLoading()
const { allPathTopics, isLoading: recLoading, refresh: refreshRecommendations } = useRecommendationPath()

const loading = ref(true)
const refreshing = ref(false)
const error = ref('')
const selectedSubject = ref('')
const viewMode = ref<'ocean' | 'list' | 'graph'>('ocean')
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

// ── Knowledge ocean data (#208) ──

// Full topic index — subjects exist as islands even with zero progress (R2).
const topicIndex = ref<TopicIndexRow[]>([])

// Ocean zoom state — separate from the list view's subject tab so the two
// views do not fight over one selection.
const oceanSubject = ref('')
const oceanDomain = ref('')

/** Progress row by topic id — one pass, so domain/topic level lookups stay
 *  O(1) instead of O(topics × progress) at 1600-topic scale. */
const progressByTopicId = computed<Map<string, { mastery_level: string }>>(() => {
  const map = new Map<string, { mastery_level: string }>()
  for (const p of progressList.value) {
    map.set(p.topic_id, { mastery_level: p.mastery_level })
  }
  return map
})

/** Subject mastery per subject key. Denominator is the topic index (so the
 *  island fog and the preview caption share one set — #10 fix: previously
 *  `masteryBySubject` counted only progress rows, producing '1/50 mastered'
 *  next to a fully clear island). */
const masteryBySubject = computed<Map<string, { total: number; mastered: number }>>(() => {
  const bySubject = new Map<string, { total: number; mastered: number }>()
  for (const row of topicIndex.value) {
    const entry = bySubject.get(row.subject) ?? { total: 0, mastered: 0 }
    entry.total++
    const p = progressByTopicId.value.get(row.id)
    if (p?.mastery_level === 'mastered') entry.mastered++
    bySubject.set(row.subject, entry)
  }
  return bySubject
})

/** Islands for the ocean — every subject in the topic index (R2, AE1). */
const oceanSubjects = computed<OceanSubject[]>(() => {
  const countBySubject = new Map<string, number>()
  for (const row of topicIndex.value) {
    countBySubject.set(row.subject, (countBySubject.get(row.subject) ?? 0) + 1)
  }
  return Array.from(countBySubject.entries())
    .map(([subject, topicCount]) => {
      const stats = masteryBySubject.value.get(subject)
      const theme = getContinentTheme(subject)
      return {
        id: subject,
        terrain: theme.terrain,
        displayName: t(`learning.subject.${subject}`, subject),
        icon: theme.icon,
        topicCount,
        masteryRatio: stats && stats.total > 0 ? stats.mastered / stats.total : 0,
      }
    })
    .sort((a, b) => a.displayName.localeCompare(b.displayName))
})

/** Regions for the zoomed-in subject (R4 domain level). */
const oceanDomains = computed<OceanDomain[]>(() => {
  if (!oceanSubject.value) return []
  const stats = new Map<string, { total: number; mastered: number }>()
  for (const row of topicIndex.value) {
    if (row.subject !== oceanSubject.value) continue
    const domain = row.domain || '__other__'
    const entry = stats.get(domain) ?? { total: 0, mastered: 0 }
    entry.total++
    const p = progressByTopicId.value.get(row.id)
    if (p?.mastery_level === 'mastered') entry.mastered++
    stats.set(domain, entry)
  }
  return Array.from(stats.entries()).map(([domain, s]) => ({
    id: `${oceanSubject.value}:${domain}`,
    subject: oceanSubject.value,
    domain,
    displayName: domainLabel(t, domain),
    topicCount: s.total,
    masteryRatio: s.total > 0 ? s.mastered / s.total : 0,
  }))
})

/** Topics of the zoomed-in domain (R4 topic level, R9 constellation input). */
const oceanTopics = computed<OceanTopic[]>(() => {
  if (!oceanSubject.value || !oceanDomain.value) return []
  return topicIndex.value
    .filter(
      (row) =>
        row.subject === oceanSubject.value && (row.domain || '__other__') === oceanDomain.value,
    )
    .map((row) => {
      const p = progressByTopicId.value.get(row.id)
      return {
        id: row.id,
        subject: row.subject,
        domain: row.domain || '__other__',
        displayName:
          locale.value.startsWith('zh') && row.name_zh ? row.name_zh : row.name || row.id,
        masteryLevel: p?.mastery_level ?? 'available',
      }
    })
})

const oceanEdges = computed<DependencyEdge[]>(() => {
  const out: DependencyEdge[] = []
  for (const edges of edgesBySubject.value.values()) out.push(...edges)
  return out
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

// Load prerequisite edges when the ocean zooms into a subject (R9).
watch(oceanSubject, (subject) => {
  if (subject) void loadDependenciesFor(subject)
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

// ── Ocean navigation + preview (R6, R8) ──

/** Preview popup state — a tap on a fogged island/region yields this, never a refusal. */
const previewSubjectId = ref('')
const previewDomainRef = ref<{ subject: string; domain: string } | null>(null)

function onPreviewSubject(subject: string) {
  previewDomainRef.value = null
  previewSubjectId.value = subject
}

function onOceanSelectSubject(subject: string) {
  previewSubjectId.value = ''
  oceanSubject.value = subject
  oceanDomain.value = ''
  // Load this subject's topic details for the recommendation card / list view parity.
  void loadSubjectTopics(subject)
}

function onPreviewDomain(payload: { subject: string; domain: string }) {
  previewSubjectId.value = ''
  previewDomainRef.value = payload
}

function onOceanSelectDomain(payload: { subject: string; domain: string }) {
  previewDomainRef.value = null
  oceanSubject.value = payload.subject
  oceanDomain.value = payload.domain
}

function onOceanSelectTopic(payload: { id: string }) {
  exploration.recordTopicSelection(payload.id)
  onTopicClick(payload.id)
}

function onOceanZoomOut() {
  if (oceanDomain.value) {
    oceanDomain.value = ''
  } else {
    oceanSubject.value = ''
  }
}

/** Edges by subject, keyed so we can invalidate per subject on refresh.
 *  #5 fix: previously a single `loadedEdgeSubjects` Set + append-only
 *  `dependencyEdges` array could never be cleared, so after pull-to-refresh
 *  the prerequisite lines stayed from the previous fetch while the fog updated. */
const edgesBySubject = ref<Map<string, DependencyEdge[]>>(new Map())

async function loadDependenciesFor(subject: string) {
  if (!subject || edgesBySubject.value.has(subject)) return
  try {
    const edges = await getSubjectDependencies(subject)
    const next = new Map(edgesBySubject.value)
    next.set(subject, edges)
    edgesBySubject.value = next
  } catch {
    // retry on next visit
  }
}

/** Subject summary for the preview popup. */
const previewSubject = computed(() => {
  if (!previewSubjectId.value) return null
  const subject = oceanSubjects.value.find((s) => s.id === previewSubjectId.value)
  if (!subject) return null
  const stats = masteryBySubject.value.get(subject.id)
  return {
    ...subject,
    masteredCount: stats?.mastered ?? 0,
  }
})

/** Domain summary for the preview popup. */
const previewDomain = computed(() => {
  if (!previewDomainRef.value) return null
  return (
    oceanDomains.value.find(
      (d) =>
        d.subject === previewDomainRef.value!.subject &&
        d.domain === previewDomainRef.value!.domain,
    ) ?? null
  )
})

// ── Exploration instrumentation (R11, R12) ──
// #16 fix: construct once in setup. The previous version rebuilt the
// composable in onMounted (discarding the setup-time instance) and wrapped
// it in a ref for no reason; the ref forced `?.` at every call site.
const exploration = useMapExploration()

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
    // The topic index is fetched alongside it so the ocean shows every
    // subject as an island even with zero progress (R2, AE1).
    // The topic index is the authoritative subject list for the ocean (R2, AE1:
    // every subject appears even with zero progress). A failure silently
    // unfulfills R2, so propagate it into the error state — the child can retry
    // via pull-to-refresh.
    const [progress, index] = await Promise.all([
      getMyLearningMapIndex(),
      getTopicIndex(),
    ])
    progressList.value = progress
    topicIndex.value = index

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
  edgesBySubject.value = new Map()
  // #F14: the taxonomy index is cached module-level; drop it so an explicit
  // refresh actually picks up any taxonomy change.
  refreshTopicIndex()
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

// R11/R12: flush the exploration record when the child leaves the map.
// AE4: flush posts even when no topic was selected.
// With KeepAlive caching, onDeactivated fires on tab switch; onUnmounted on
// component destruction. Both paths flush.
onDeactivated(() => {
  exploration.flush()
})
onUnmounted(() => {
  exploration.flush()
})

// R10/KTD4: re-fetch recommendation path when page re-activates from
// KeepAlive cache (e.g. after returning from practice).
// Also re-fetch the progress index so ClusterMap can detect frontier changes
// (new topic became the recommendation after practice updated mastery).
// Note: onActivated fires on first mount too (inside KeepAlive), so the
// hasActivated guard prevents the data re-fetch from running twice on init.
let hasActivated = false
onActivated(async () => {
  if (!hasActivated) {
    hasActivated = true
    return // first activation coincides with onMounted — skip, onMounted handles it
  }
  // Drop per-subject caches so the progress re-fetch pulls fresh topic detail.
  loadedSubjects.value = new Set()
  inflightSubjects.clear()
  topicMap.value = new Map()
  edgesBySubject.value = new Map()
  // #L-1: clearing edgesBySubject does not re-fire the oceanSubject watcher
  // (the value is unchanged), so the topic-level constellation would keep
  // rendering without prerequisite edges. Re-fetch for the current subject.
  if (oceanSubject.value) void loadDependenciesFor(oceanSubject.value)
  // #L-2: re-arm the visit tracker — a reactivation is a new visit, so the
  // timer and counters must restart instead of carrying the previous visit's.
  exploration.start()
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

/* ── Ocean preview popup ── */

.ocean-preview__header {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 8px;
}

.ocean-preview__icon {
  font-size: 28px;
  line-height: 1;
}

.ocean-preview__title {
  font-family: Inter, sans-serif;
  font-size: 18px;
  font-weight: 600;
  color: var(--color-ink);
}

.ocean-preview__stats {
  font-family: Inter, sans-serif;
  font-size: 14px;
  color: var(--color-body);
  margin: 0 0 14px;
}

.ocean-preview__btn {
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
}

.ocean-preview__btn:active {
  transform: scale(0.97);
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
