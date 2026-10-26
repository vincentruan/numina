<template>
  <div class="parent-cluster-map">
    <van-skeleton v-if="loading" :rows="5" :round="true" />
    <EmptyState v-else-if="allItems.length === 0" :description="t('learning.noGraphData')" />

    <template v-else>
      <!-- Subject filter chips -->
      <div v-if="availableSubjects.length > 1" class="subject-filter-chips">
        <van-tag
          v-for="subj in availableSubjects"
          :key="subj"
          :type="subj === selectedSubject ? 'primary' : 'default'"
          :plain="subj !== selectedSubject"
          class="filter-chip"
          @click="selectedSubject = subj"
        >
          {{ subjectLabel(t, subj) }} ({{ subjectItemCount(subj) }})
        </van-tag>
      </div>

      <!-- Progress bar -->
      <div v-if="currentItems.length > 0" class="progress-row">
        <div class="progress-bar">
          <div
            class="progress-fill"
            :class="{ 'progress-fill--complete': masteredCount === currentItems.length }"
            :style="{ width: progressPercent + '%' }"
          />
        </div>
        <span class="progress-text">
          {{ t('learning.clusterProgress', { mastered: masteredCount, total: currentItems.length }) }}
        </span>
      </div>

      <!-- Territory cards grouped by domain -->
      <div v-if="territories.length === 0 && !clustersLoading" class="empty-territories">
        <EmptyState :description="t('learning.clusterEmpty')" />
      </div>

      <div v-else class="territory-list">
        <van-collapse v-model="expandedDomains">
          <van-collapse-item
            v-for="territory in territories"
            :key="territory.domain"
            :name="territory.domain"
          >
            <template #title>
              <div class="territory-header">
                <span class="territory-domain">{{ domainLabel(t, territory.domain) }}</span>
                <van-tag size="medium" round>
                  {{ territory.masteredCount }}/{{ territory.items.length }}
                </van-tag>
              </div>
            </template>

            <!-- Territory card content -->
            <div class="territory-card">
              <!-- Summary text -->
              <p v-if="territory.summary" class="territory-summary">
                {{ territory.summary }}
              </p>

              <!-- Bridge badges -->
              <div v-if="territory.bridges.length > 0" class="bridge-badges">
                <span
                  v-for="bridge in territory.bridges.slice(0, 3)"
                  :key="`${bridge.to_subject}-${bridge.to_cluster_domain}`"
                  :class="['bridge-badge', { 'bridge-badge--inferred': bridge.source_type === 'inferred' }]"
                >
                  <span class="bridge-badge__icon">{{ bridge.source_type === 'inferred' ? '🔍' : '🔗' }}</span>
                  <span class="bridge-badge__label">
                    {{ subjectLabel(t, bridge.to_subject) }} → {{ domainLabel(t, bridge.to_cluster_domain) }}
                  </span>
                </span>
              </div>

              <!-- Topic nodes -->
              <div class="topic-nodes">
                <van-popover
                  v-for="item in territory.items"
                  :key="item.topic.id"
                  v-model:show="popoverState[item.topic.id]"
                  trigger="click"
                  placement="top"
                  :offset="[0, 8]"
                >
                  <div class="topic-popover-content">
                    <div class="topic-popover-name">{{ topicDisplayName(item.topic) }}</div>
                    <div class="topic-popover-meta">
                      <van-tag :type="masteryTagType(item)" size="medium">
                        {{ masteryLabel(item) }}
                      </van-tag>
                      <span v-if="item.attempts > 0" class="topic-popover-stat">
                        {{ t('learning.clusterAttempts', { count: item.attempts }) }}
                      </span>
                    </div>
                    <div v-if="item.last_practice_at" class="topic-popover-stat">
                      {{ t('learning.clusterLastPractice', { date: formatPracticeDate(item.last_practice_at) }) }}
                    </div>
                    <div class="topic-popover-stat">
                      {{ t('learning.clusterStudyDuration', { minutes: Math.round((item.xp_earned || 0) / 10) }) }}
                    </div>
                  </div>
                  <template #reference>
                    <button
                      class="topic-node-btn"
                      :class="[`topic-node-btn--${masteryStatus(item)}`]"
                      :title="topicDisplayName(item.topic)"
                    >
                      <span class="topic-node-btn__dot" />
                      <span class="topic-node-btn__label">{{ topicDisplayName(item.topic) }}</span>
                    </button>
                  </template>
                </van-popover>
              </div>
            </div>
          </van-collapse-item>
        </van-collapse>
      </div>

      <!-- Clusters loading indicator -->
      <div v-if="clustersLoading" class="clusters-loading">
        <van-loading size="20" />
      </div>
    </template>
  </div>
</template>

<script setup lang="ts">
defineOptions({ name: 'ParentClusterMap' })

import { ref, computed, watch, reactive, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import EmptyState from '@/components/common/EmptyState.vue'
import { domainLabel, subjectLabel } from '@/utils/domainLabel'
import type {
  ProgressWithTopic,
  ClusterResponse,
  BridgeResponse,
} from '@/api/learning'
import { getChildClusters, getChildBridges } from '@/api/learning'

const { t, locale } = useI18n()

const props = defineProps<{
  items: ProgressWithTopic[]
  childId: string | null
  loading?: boolean
}>()

// ── State ──

const selectedSubject = ref('')
const clusters = ref<ClusterResponse[]>([])
const bridges = ref<BridgeResponse[]>([])
const clustersLoading = ref(false)
const expandedDomains = ref<string[]>([])
const popoverState = reactive<Record<string, boolean>>({})

// ── Available subjects from items ──

const availableSubjects = computed(() => {
  const subjects = new Set(props.items.map((i) => i.topic.subject))
  return Array.from(subjects).sort()
})

// Auto-select first subject
watch(availableSubjects, (subjects) => {
  if (subjects.length > 0 && !subjects.includes(selectedSubject.value)) {
    selectedSubject.value = subjects[0]
  }
}, { immediate: true })

// Items for current subject
const allItems = computed(() => props.items)
const currentItems = computed(() =>
  props.items.filter((i) => i.topic.subject === selectedSubject.value),
)

const masteredCount = computed(() =>
  currentItems.value.filter((i) => i.mastery_level === 'mastered').length,
)

const progressPercent = computed(() =>
  currentItems.value.length > 0
    ? Math.round((masteredCount.value / currentItems.value.length) * 100)
    : 0,
)

function subjectItemCount(subject: string): number {
  return props.items.filter((i) => i.topic.subject === subject).length
}

// ── Cluster/bridge loading ──

async function loadClusters() {
  if (!props.childId || !selectedSubject.value) return
  clustersLoading.value = true
  try {
    const [clusterData, bridgeData] = await Promise.all([
      getChildClusters(props.childId, selectedSubject.value),
      getChildBridges(props.childId, selectedSubject.value),
    ])
    clusters.value = clusterData
    bridges.value = bridgeData
    // Auto-expand domains with active learning
    autoExpandDomains()
  } catch {
    clusters.value = []
    bridges.value = []
  } finally {
    clustersLoading.value = false
  }
}

watch(selectedSubject, () => {
  loadClusters()
})

onMounted(() => {
  if (selectedSubject.value) loadClusters()
})

// ── Territory computation ──

interface Territory {
  domain: string
  summary: string
  items: ProgressWithTopic[]
  masteredCount: number
  bridges: BridgeResponse[]
}

const AGE_GROUP_ORDER = ['low', 'mid', 'high']

const territories = computed<Territory[]>(() => {
  const items = currentItems.value
  if (items.length === 0) return []

  // Group items by domain
  const domainMap = new Map<string, ProgressWithTopic[]>()
  const unmatched: ProgressWithTopic[] = []

  const hasClusters = clusters.value.some((c) => c.subject === selectedSubject.value)

  for (const item of items) {
    const domain = item.topic.domain
    if (!hasClusters && !clustersLoading.value) {
      const target = domain || '__other__'
      if (!domainMap.has(target)) domainMap.set(target, [])
      domainMap.get(target)!.push(item)
      continue
    }

    const target =
      domain !== null && clusters.value.some((c) => c.domain === domain)
        ? domain
        : domain === null
          ? clusters.value.find((c) => c.subject === item.topic.subject)?.domain
          : undefined

    if (target === undefined) {
      unmatched.push(item)
      continue
    }
    if (!domainMap.has(target)) domainMap.set(target, [])
    domainMap.get(target)!.push(item)
  }

  // Build representative cluster per domain for summary text
  const representatives = new Map<string, ClusterResponse>()
  for (const c of clusters.value) {
    if (!domainMap.has(c.domain)) continue
    const kept = representatives.get(c.domain)
    if (!kept || (c.age_range_start !== null && (kept.age_range_start === null || c.age_range_start < kept.age_range_start))) {
      representatives.set(c.domain, c)
    }
  }

  const result: Territory[] = [...domainMap.entries()].map(([domain, domainItems]) => {
    const cluster = representatives.get(domain)
    const sorted = [...domainItems].sort(
      (a, b) => AGE_GROUP_ORDER.indexOf(a.topic.age_group) - AGE_GROUP_ORDER.indexOf(b.topic.age_group),
    )
    return {
      domain,
      summary: cluster?.summary ?? '',
      items: sorted,
      masteredCount: sorted.filter((i) => i.mastery_level === 'mastered').length,
      bridges: bridges.value.filter((b) => b.from_cluster_domain === domain),
    }
  })

  if (!clustersLoading.value && unmatched.length > 0) {
    result.push({
      domain: '__other__',
      summary: '',
      items: unmatched,
      masteredCount: unmatched.filter((i) => i.mastery_level === 'mastered').length,
      bridges: [],
    })
  }

  return result
})

function autoExpandDomains() {
  const toExpand: string[] = []
  for (const territory of territories.value) {
    const hasActive = territory.items.some((i) => {
      const level = i.mastery_level
      if (level === 'learning' || level === 'assessing' || level === 'available') return true
      if (level === 'mastered' && i.next_review_at && new Date(i.next_review_at) <= new Date()) return true
      return false
    })
    if (hasActive) toExpand.push(territory.domain)
  }
  expandedDomains.value = toExpand
}

// ── Mastery helpers ──

type MasteryStatus = 'mastered' | 'learning' | 'available' | 'locked' | 'review'

function masteryStatus(item: ProgressWithTopic): MasteryStatus {
  const level = item.mastery_level
  if (level === 'mastered') {
    if (item.next_review_at && new Date(item.next_review_at) <= new Date()) return 'review'
    return 'mastered'
  }
  if (level === 'learning' || level === 'assessing') return 'learning'
  if (level === 'locked') return 'locked'
  return 'available'
}

function masteryTagType(item: ProgressWithTopic): 'success' | 'primary' | 'warning' | 'default' {
  const status = masteryStatus(item)
  switch (status) {
    case 'mastered': return 'success'
    case 'learning': return 'primary'
    case 'review': return 'warning'
    default: return 'default'
  }
}

function masteryLabel(item: ProgressWithTopic): string {
  const status = masteryStatus(item)
  switch (status) {
    case 'mastered': return t('learning.mastered')
    case 'learning': return t('learning.learning')
    case 'available': return t('learning.available')
    case 'locked': return t('learning.locked')
    case 'review': return t('learning.pendingReview')
  }
}

function topicDisplayName(topic: ProgressWithTopic['topic']): string {
  if (locale.value.startsWith('zh') && topic.name_zh) return topic.name_zh
  return topic.name || topic.topic_key
}

function formatPracticeDate(dateStr: string): string {
  return new Date(dateStr).toLocaleDateString(locale.value, {
    month: 'short',
    day: 'numeric',
  })
}
</script>

<style scoped>
.parent-cluster-map {
  width: 100%;
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.subject-filter-chips {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  padding: 0 4px;
}

.filter-chip {
  cursor: pointer;
  transition: all 0.2s;
}

.filter-chip:active {
  transform: scale(0.95);
}

/* ── Progress bar ── */

.progress-row {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 0 4px;
}

.progress-bar {
  flex: 1;
  height: 6px;
  background: var(--van-gray-2, #ebedf0);
  border-radius: 3px;
  overflow: hidden;
}

.progress-fill {
  height: 100%;
  background: var(--van-primary-color);
  border-radius: 3px;
  transition: width 0.4s ease;
}

.progress-fill--complete {
  background: var(--van-success-color);
}

.progress-text {
  font-size: 13px;
  font-weight: 600;
  color: var(--text-primary);
  white-space: nowrap;
}

/* ── Territory list ── */

.territory-list {
  margin: 0;
}

.territory-header {
  display: flex;
  align-items: center;
  gap: 8px;
}

.territory-domain {
  font-size: 15px;
  font-weight: 600;
  color: var(--text-primary);
}

.territory-card {
  padding: 4px 0;
}

.territory-summary {
  font-size: 13px;
  color: var(--text-secondary);
  margin: 0 0 10px;
  line-height: 1.4;
}

/* ── Bridge badges ── */

.bridge-badges {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin-bottom: 10px;
}

.bridge-badge {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 3px 8px;
  border: 1px solid var(--van-gray-3, #dee0e3);
  border-radius: 12px;
  background: var(--van-gray-1, #f7f8fa);
  font-size: 12px;
  color: var(--text-secondary);
}

.bridge-badge--inferred {
  border-style: dashed;
  opacity: 0.75;
}

.bridge-badge__icon {
  font-size: 11px;
}

/* ── Topic nodes ── */

.topic-nodes {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.topic-node-btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-width: 36px;
  min-height: 36px;
  padding: 4px;
  border: none;
  background: transparent;
  cursor: pointer;
  -webkit-tap-highlight-color: transparent;
  position: relative;
}

.topic-node-btn:active {
  transform: scale(0.93);
}

.topic-node-btn__dot {
  width: 28px;
  height: 28px;
  border-radius: 50%;
  display: block;
  transition: box-shadow 0.2s;
}

.topic-node-btn__label {
  position: absolute;
  width: 1px;
  height: 1px;
  overflow: hidden;
  clip: rect(0, 0, 0, 0);
  white-space: nowrap;
}

/* Mastery colors — main app tokens */
.topic-node-btn--mastered .topic-node-btn__dot {
  background: var(--van-success-color, #07c160);
  box-shadow: 0 0 6px rgba(7, 193, 96, 0.4);
}

.topic-node-btn--learning .topic-node-btn__dot {
  background: var(--van-primary-color, #1989fa);
  animation: pcm-pulse 2s ease-in-out infinite;
}

.topic-node-btn--available .topic-node-btn__dot {
  background: var(--van-gray-4, #c8c9cc);
}

.topic-node-btn--locked .topic-node-btn__dot {
  background: var(--van-gray-5, #969799);
  opacity: 0.4;
}

.topic-node-btn--review .topic-node-btn__dot {
  background: var(--van-warning-color, #ff976a);
  animation: pcm-blink 1.5s ease-in-out infinite;
}

@keyframes pcm-pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.6; }
}

@keyframes pcm-blink {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.4; }
}

@media (prefers-reduced-motion: reduce) {
  .topic-node-btn--learning .topic-node-btn__dot,
  .topic-node-btn--review .topic-node-btn__dot {
    animation: none;
  }
}

/* ── Topic popover ── */

.topic-popover-content {
  padding: 8px 12px;
  min-width: 160px;
}

.topic-popover-name {
  font-size: 14px;
  font-weight: 600;
  color: var(--text-primary);
  margin-bottom: 6px;
}

.topic-popover-meta {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 4px;
}

.topic-popover-stat {
  font-size: 12px;
  color: var(--text-secondary);
  margin-top: 2px;
}

/* ── Misc ── */

.empty-territories {
  padding: 24px 0;
}

.clusters-loading {
  display: flex;
  justify-content: center;
  padding: 16px;
}

/* ── van-collapse overrides ── */

:deep(.van-collapse) {
  margin: 0;
}

:deep(.van-collapse-item__title) {
  background: var(--card-bg, #f5f5ff);
  border-radius: 8px;
  padding: 10px 12px;
}

:deep(.van-collapse-item__wrapper) {
  background: transparent;
}

:deep(.van-collapse-item__content) {
  background: transparent;
  padding: 8px 12px 12px;
}
</style>
