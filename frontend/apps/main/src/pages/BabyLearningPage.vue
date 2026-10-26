<template>
  <div class="baby-learning-page">
    <PageHeader :title="t('learning.parentTitle')" />

    <!-- Child switcher tabs (spec §2.3) -->
    <van-tabs
      v-if="children.length > 0"
      v-model:active="childTabIndex"
      class="child-tabs"
      shrink
    >
      <van-tab
        v-for="child in children"
        :key="child.child_id"
        :title="child.child_name"
      />
    </van-tabs>

    <van-skeleton v-if="loading && children.length === 0" :rows="5" :round="true" />

    <template v-else>
      <van-pull-refresh v-model="refreshing" @refresh="onRefresh">
        <!-- Empty state -->
        <EmptyState v-if="children.length === 0" :description="t('learning.noChildren')">
          <van-button type="primary" size="small" @click="$router.push('/settings/family/members')">
            {{ t('baby.addChildren') }}
          </van-button>
        </EmptyState>

        <template v-else>
          <!-- Module 1: Smart Recommendations (default expanded) -->
          <div class="module-card">
            <div class="module-header" @click="toggleModule('recommendations')">
              <div class="module-title-row">
                <IIcon icon="mdi:star-shooting" size="20" color="var(--van-warning-color)" />
                <span class="module-title">{{ t('learning.smartRecommendations') }}</span>
              </div>
              <van-icon :name="isExpanded('recommendations') ? 'arrow-up' : 'arrow-down'" />
            </div>
            <div v-show="isExpanded('recommendations')">
              <van-skeleton v-if="recommendationsLoading" :rows="3" :round="true" />
              <template v-else>
                <div v-if="recommendations.length === 0" class="module-empty">
                  <EmptyState :description="t('learning.noRecommendations')" />
                </div>
                <template v-else>
                  <div class="summary-line">
                    {{ t('learning.recommendationSummary', { count: recommendations.length }) }}
                  </div>
                  <div class="topic-tags">
                    <van-tag
                      v-for="topic in recommendations.slice(0, 5)"
                      :key="topic.topic_id"
                      :type="reasonToTagType(topic.reasons)"
                      round
                      class="topic-tag"
                    >
                      {{ getReasonEmoji(topic.reasons) }} {{ topic.topic_name }}
                    </van-tag>
                  </div>
                  <div class="module-actions">
                    <van-button size="small" type="primary" @click="handleConfirmAssign">
                      {{ t('learning.confirmAssign') }}
                    </van-button>
                    <van-button size="small" @click="router.push('/baby/learning/recommendations')">
                      {{ t('learning.fineTunePath') }}
                    </van-button>
                    <van-button size="small" plain @click="refreshRecommendations">
                      {{ t('learning.refreshBatch') }}
                    </van-button>
                  </div>
                </template>
              </template>
            </div>
          </div>

          <!-- Module 2: Review Queue (default expanded) -->
          <div class="module-card">
            <div class="module-header" @click="toggleModule('reviews')">
              <div class="module-title-row">
                <IIcon icon="mdi:clipboard-check-outline" size="20" color="var(--van-primary-color)" />
                <span class="module-title">{{ t('learning.reviewQueue') }}</span>
                <van-badge v-if="reviews.length > 0" :content="reviews.length" />
              </div>
              <van-icon :name="isExpanded('reviews') ? 'arrow-up' : 'arrow-down'" />
            </div>
            <div v-show="isExpanded('reviews')">
              <van-skeleton v-if="reviewsLoading" :rows="3" :round="true" />
              <template v-else>
                <div v-if="reviews.length === 0" class="module-empty">
                  <EmptyState :description="t('learning.noPendingReviews')" image-size="48" />
                </div>
                <template v-else>
                  <div
                    v-for="review in (showAllReviews ? reviews : reviews.slice(0, 3))"
                    :key="review.progress_id"
                    class="review-item"
                  >
                    <div class="review-item-header">
                      <span class="review-child-name">{{ review.child_name }}</span>
                      <span class="review-topic-name">{{ review.topic_name }}</span>
                    </div>
                    <div class="review-meta">
                      <span>{{ t('learning.attempts', { count: review.attempts }) }}</span>
                      <span>{{ t('learning.studyDuration', { seconds: review.study_duration_seconds }) }}</span>
                      <van-button
                        size="mini"
                        plain
                        @click="openEvidenceSheet(review)"
                      >
                        {{ t('learning.expandEvidence') }}
                      </van-button>
                    </div>
                  </div>
                  <van-button
                    v-if="reviews.length > 3"
                    size="small"
                    plain
                    block
                    class="view-all-btn"
                    @click="showAllReviews = !showAllReviews"
                  >
                    {{ showAllReviews ? t('learning.collapseReviews') : t('learning.viewAllReviews') }}
                  </van-button>
                </template>
              </template>
            </div>
          </div>

          <!-- Module 3: Preset Paths (default collapsed) -->
          <van-collapse v-model="expandedModules">
            <van-collapse-item name="presetPaths">
              <template #title>
                <div class="collapse-title-row">
                  <IIcon icon="mdi:book-open-page-variant-outline" size="18" color="var(--van-primary-color)" />
                  <span>{{ t('learning.presetPaths') }}</span>
                  <span v-if="presetPaths.length > 0" class="collapse-count">{{ presetPaths.length }} {{ t('learning.availablePaths') }}</span>
                </div>
              </template>
              <van-skeleton v-if="presetPathsLoading" :rows="2" :round="true" />
              <template v-else>
                <div v-if="presetPaths.length === 0" class="module-empty">
                  <EmptyState :description="t('learning.presetPathsEmpty')" image-size="48" />
                </div>
                <template v-else>
                  <div
                    v-for="pp in presetPaths.slice(0, 3)"
                    :key="pp.id"
                    class="preset-path-item"
                    @click="router.push('/baby/learning/preset-paths')"
                  >
                    <span class="preset-path-name">{{ presetPathDisplayName(pp) }}</span>
                    <van-tag plain type="primary">{{ pp.topic_count }} {{ t('learning.mastered') }}</van-tag>
                  </div>
                </template>
              </template>
            </van-collapse-item>

            <!-- Module 4: Active Paths (default collapsed) -->
            <van-collapse-item name="activePaths">
              <template #title>
                <div class="collapse-title-row">
                  <IIcon icon="mdi:road-variant" size="18" color="var(--van-success-color)" />
                  <span>{{ t('learning.activePaths') }}</span>
                </div>
              </template>
              <van-skeleton v-if="pathsLoading" :rows="2" :round="true" />
              <template v-else>
                <div v-if="activePaths.length === 0" class="module-empty">
                  <EmptyState :description="t('learning.paths.empty')" image-size="48" />
                </div>
                <template v-else>
                  <div
                    v-for="path in activePaths.slice(0, 3)"
                    :key="path.id"
                    class="path-row"
                    @click="router.push(`/baby/learning/paths/${path.id}`)"
                  >
                    <div class="path-row-main">
                      <span class="path-row-name">{{ pathDisplayName(path) }}</span>
                      <span class="path-row-child">{{ pathChildName(path.child_id) }}</span>
                    </div>
                    <div class="path-row-meta">
                      <van-tag type="primary">{{ pathStatusLabel(path.status) }}</van-tag>
                      <span class="path-row-progress">
                        {{ t('learning.paths.progress', { completed: path.completed_count, total: path.total_count }) }}
                      </span>
                    </div>
                  </div>
                </template>
              </template>
            </van-collapse-item>

            <!-- Module 5: Knowledge Map / Graph view (default collapsed) -->
            <van-collapse-item name="dnaGraph">
              <template #title>
                <div class="collapse-title-row">
                  <IIcon icon="mdi:account-tree" size="18" color="var(--van-danger-color)" />
                  <span>{{ t('learning.dnaGraph') }}</span>
                </div>
              </template>
              <!-- View mode toggle -->
              <div class="view-mode-toggle">
                <button
                  class="view-mode-btn"
                  :class="{ 'view-mode-btn--active': graphViewMode === 'dna' }"
                  @click="graphViewMode = 'dna'"
                >
                  {{ t('learning.viewModeDna') }}
                </button>
                <button
                  class="view-mode-btn"
                  :class="{ 'view-mode-btn--active': graphViewMode === 'cluster' }"
                  @click="graphViewMode = 'cluster'"
                >
                  {{ t('learning.viewModeCluster') }}
                </button>
              </div>
              <DnaGraph2D v-if="graphViewMode === 'dna'" :items="dnaGraphItems" :loading="dnaGraphLoading" />
              <ParentClusterMap
                v-else
                :items="clusterMapItems"
                :child-id="babyStore.selectedChildId"
                :loading="clusterMapLoading"
              />
            </van-collapse-item>
          </van-collapse>
        </template>
      </van-pull-refresh>
    </template>

    <!-- Evidence bottom sheet -->
    <van-popup v-model:show="showEvidencePopup" position="bottom" round :style="{ height: '60%' }">
      <div v-if="selectedReview" class="evidence-panel">
        <div class="evidence-panel-header">
          <span class="evidence-panel-title">{{ t('learning.evidenceTitle') }}</span>
          <van-icon name="cross" class="evidence-close" @click="showEvidencePopup = false" />
        </div>
        <div class="evidence-panel-body">
          <div class="evidence-topic">
            <span class="evidence-label">{{ selectedReview.topic_name }}</span>
            <span class="evidence-desc">{{ selectedReview.topic_description }}</span>
          </div>
          <div class="evidence-meta">
            <span>{{ t('learning.attempts', { count: selectedReview.attempts }) }}</span>
            <span>{{ t('learning.studyDuration', { seconds: selectedReview.study_duration_seconds }) }}</span>
          </div>
          <div v-if="selectedReview.evidence.length > 0" class="evidence-list">
            <div v-for="(ev, idx) in selectedReview.evidence" :key="idx" class="evidence-item">
              {{ ev }}
            </div>
          </div>
        </div>
        <div class="evidence-panel-actions">
          <van-button
            size="small"
            type="success"
            :loading="actioningId === selectedReview.progress_id"
            @click="doApprove(selectedReview)"
          >
            {{ t('learning.approve') }}
          </van-button>
          <van-button
            size="small"
            type="danger"
            :loading="actioningId === selectedReview.progress_id"
            @click="doReject(selectedReview)"
          >
            {{ t('learning.reject') }}
          </van-button>
        </div>
      </div>
    </van-popup>
  </div>
</template>

<script setup lang="ts">
defineOptions({ name: 'BabyLearning' })

import { ref, computed, watch, onMounted, onActivated } from 'vue'
import { useRouter } from 'vue-router'
import { showSuccessToast, showFailToast, showConfirmDialog } from 'vant'
import { useI18n } from 'vue-i18n'
import { usePageLoading } from '@/composables/usePageLoading'
import { useBabyStore } from '@/stores/baby'
import {
  getLearningChildren,
  getReviews,
  approveReview,
  rejectReview,
  getPaths,
  getRecommendations,
  getPresetPaths,
  getChildMap,
  getTopicsBatch,
  type ChildLearningOverview,
  type ReviewItem,
  type PathResponse,
  type PresetPathResponse,
  type RecommendationTopicItem,
  type ProgressResponse,
  type ProgressWithTopic,
  type TopicResponse,
} from '@/api/learning'
import PageHeader from '@/components/common/PageHeader.vue'
import EmptyState from '@/components/common/EmptyState.vue'
import IIcon from '@/components/IIcon.vue'
import DnaGraph2D from '@/components/learning/DnaGraph2D.vue'
import ParentClusterMap from '@/components/learning/ParentClusterMap.vue'

const { t, locale } = useI18n()
const router = useRouter()
const { increment, decrement } = usePageLoading()
const babyStore = useBabyStore()

const loading = ref(true)
const refreshing = ref(false)
const children = ref<ChildLearningOverview[]>([])
const reviews = ref<ReviewItem[]>([])
const paths = ref<PathResponse[]>([])
const presetPaths = ref<PresetPathResponse[]>([])
const recommendations = ref<RecommendationTopicItem[]>([])
const recommendationsLoading = ref(false)
const reviewsLoading = ref(false)
const presetPathsLoading = ref(false)
const pathsLoading = ref(false)
const actioningId = ref<string | null>(null)
const dnaGraphItems = ref<ProgressWithTopic[]>([])
const dnaGraphLoading = ref(false)

// Graph view mode: 'dna' (DnaGraph2D) or 'cluster' (ParentClusterMap)
const graphViewMode = ref<'dna' | 'cluster'>('dna')

// Cluster map data: compose ProgressWithTopic[] from progress + topic details
const clusterMapItems = ref<ProgressWithTopic[]>([])
const clusterMapLoading = ref(false)
const clusterMapTopicCache = ref<Map<string, TopicResponse>>(new Map())

// Review expand state
const showAllReviews = ref(false)

// Module expand state
const expandedModules = ref<string[]>(['recommendations', 'reviews'])

function isExpanded(name: string): boolean {
  return expandedModules.value.includes(name)
}

function toggleModule(name: string) {
  const idx = expandedModules.value.indexOf(name)
  if (idx >= 0) {
    expandedModules.value.splice(idx, 1)
  } else {
    expandedModules.value.push(name)
  }
}

// Evidence popup
const showEvidencePopup = ref(false)
const selectedReview = ref<ReviewItem | null>(null)

function openEvidenceSheet(review: ReviewItem) {
  selectedReview.value = review
  showEvidencePopup.value = true
}

// Computed
const activePaths = computed(() => paths.value.filter(p => p.status === 'active'))

// Child switcher (spec §2.3): tab index synced with babyStore.selectedChildId
const childTabIndex = ref(0)

watch(childTabIndex, (idx) => {
  const child = children.value[idx]
  if (child && child.child_id !== babyStore.selectedChildId) {
    babyStore.selectChild(child.child_id, child.child_name)
  }
})

// Keep tab index in sync when selection changes from outside (BabyPage / auto-select)
watch(() => babyStore.selectedChildId, (id) => {
  const idx = children.value.findIndex(c => c.child_id === id)
  if (idx >= 0) childTabIndex.value = idx
})

// Display helpers
function pathDisplayName(path: PathResponse): string {
  return locale.value.startsWith('zh') && path.name_zh ? path.name_zh : path.name
}

function presetPathDisplayName(pp: PresetPathResponse): string {
  return locale.value.startsWith('zh') && pp.name_zh ? pp.name_zh : pp.name
}

function pathChildName(childId: string): string {
  return children.value.find((c) => c.child_id === childId)?.child_name ?? ''
}

function pathStatusLabel(status: string): string {
  switch (status) {
    case 'active': return t('learning.paths.statusActive')
    case 'completed': return t('learning.paths.statusCompleted')
    case 'archived': return t('learning.paths.statusArchived')
    default: return status
  }
}

// Recommendation helpers
function reasonToTagType(reasons: string[]): 'primary' | 'success' | 'warning' | 'default' {
  if (reasons.includes('weak_point')) return 'warning'
  if (reasons.includes('mastery_gained')) return 'success'
  return 'primary'
}

function getReasonEmoji(reasons: string[]): string {
  if (reasons.includes('weak_point')) return '⚠️'
  if (reasons.includes('mastery_gained')) return '✅'
  if (reasons.includes('recommended')) return '💡'
  return '📌'
}

// Data loading
async function loadRecommendations() {
  const childId = babyStore.selectedChildId
  if (!childId) return
  recommendationsLoading.value = true
  try {
    const res = await getRecommendations(childId)
    recommendations.value = res.path?.topics ?? []
  } catch {
    // best-effort: clear on failure
    recommendations.value = []
  } finally {
    recommendationsLoading.value = false
  }
}

async function loadReviews() {
  reviewsLoading.value = true
  try {
    reviews.value = await getReviews()
  } catch {
    reviews.value = []
  } finally {
    reviewsLoading.value = false
  }
}

async function loadPresetPaths() {
  presetPathsLoading.value = true
  try {
    presetPaths.value = await getPresetPaths()
  } catch {
    presetPaths.value = []
  } finally {
    presetPathsLoading.value = false
  }
}

async function loadPaths() {
  pathsLoading.value = true
  try {
    paths.value = await getPaths()
  } catch {
    paths.value = []
  } finally {
    pathsLoading.value = false
  }
}

// Shared progress rows from getChildMap — avoids duplicate fetch between DNA graph and cluster map
const sharedProgressRows = ref<ProgressResponse[]>([])

async function loadDnaGraph() {
  dnaGraphItems.value = sharedProgressRows.value as ProgressWithTopic[]
}

async function loadClusterMap() {
  const childId = babyStore.selectedChildId
  if (!childId) return
  clusterMapLoading.value = true
  try {
    const progressRows = sharedProgressRows.value
    // Batch-fetch topic details for all progress rows
    const topicIds = [...new Set(progressRows.map((r) => r.topic_id))]
    // Use cached topics to avoid redundant fetches
    const uncachedIds = topicIds.filter((id) => !clusterMapTopicCache.value.has(id))
    if (uncachedIds.length > 0) {
      const topics = await getTopicsBatch(uncachedIds)
      const next = new Map(clusterMapTopicCache.value)
      for (const topic of topics) next.set(topic.id, topic)
      clusterMapTopicCache.value = next
    }
    // Compose ProgressWithTopic[]
    clusterMapItems.value = progressRows
      .filter((r) => clusterMapTopicCache.value.has(r.topic_id))
      .map((r) => ({
        ...r,
        topic: clusterMapTopicCache.value.get(r.topic_id)!,
      }))
  } catch {
    clusterMapItems.value = []
  } finally {
    clusterMapLoading.value = false
  }
}

async function loadChildren() {
  try {
    children.value = await getLearningChildren()
  } catch {
    children.value = []
  }
}

async function loadChildDependentData() {
  const childId = babyStore.selectedChildId
  // Fetch progress rows once — shared between DNA graph and cluster map
  if (childId) {
    try {
      sharedProgressRows.value = await getChildMap(childId)
    } catch {
      sharedProgressRows.value = []
    }
  }
  dnaGraphLoading.value = true
  try {
    await loadDnaGraph()
  } finally {
    dnaGraphLoading.value = false
  }
  await loadRecommendations()
  // Cluster map is loaded lazily when user switches to cluster view
}

// Lazy-load cluster data when user switches to cluster view
let clusterMapLoaded = false
watch(graphViewMode, async (mode) => {
  if (mode === 'cluster' && !clusterMapLoaded) {
    clusterMapLoaded = true
    await loadClusterMap()
  }
})

async function loadData() {
  await Promise.all([
    loadChildren(),
    loadReviews(),
    loadPaths(),
    loadPresetPaths(),
  ])
}

// Actions
async function doApprove(review: ReviewItem) {
  try {
    await showConfirmDialog({
      title: t('learning.approve'),
      message: t('learning.approveConfirm', { name: review.child_name, topic: review.topic_name }),
    })
  } catch {
    return
  }
  actioningId.value = review.progress_id
  try {
    await approveReview(review.progress_id)
    showSuccessToast(t('learning.approved'))
    showEvidencePopup.value = false
    await loadReviews()
  } catch {
    showFailToast(t('toast.operationFailed'))
  } finally {
    actioningId.value = null
  }
}

async function doReject(review: ReviewItem) {
  try {
    await showConfirmDialog({
      title: t('learning.reject'),
      message: t('learning.rejectConfirm', { name: review.child_name, topic: review.topic_name }),
    })
  } catch {
    return
  }
  actioningId.value = review.progress_id
  try {
    await rejectReview(review.progress_id)
    showSuccessToast(t('learning.rejected'))
    showEvidencePopup.value = false
    await loadReviews()
  } catch {
    showFailToast(t('toast.operationFailed'))
  } finally {
    actioningId.value = null
  }
}

async function handleConfirmAssign() {
  // Navigate to recommendations page for full assign flow
  router.push('/baby/learning/recommendations')
}

async function refreshRecommendations() {
  await loadRecommendations()
}

async function onRefresh() {
  await Promise.all([loadData(), loadChildDependentData()])
  refreshing.value = false
}

// Reload child-dependent data when selected child changes
watch(() => babyStore.selectedChildId, (newId) => {
  if (newId) {
    clusterMapLoaded = false
    loadChildDependentData()
  }
})

// Skip first onActivated — Vue 3 fires both onMounted and onActivated on first mount
let hasActivated = false

onMounted(async () => {
  increment()
  try {
    await loadData()
    // Auto-select first child if none selected
    if (!babyStore.selectedChildId && children.value.length > 0) {
      const first = children.value[0]
      babyStore.selectChild(first.child_id, first.child_name)
      await loadChildDependentData()
    }
  } finally {
    decrement()
  }
  loading.value = false
})

onActivated(async () => {
  if (!hasActivated) { hasActivated = true; return }
  increment()
  try {
    await Promise.all([loadData(), loadChildDependentData()])
  } finally {
    decrement()
  }
  loading.value = false
})
</script>

<style scoped>
.baby-learning-page {
  min-height: 100vh;
  padding-bottom: 20px;
}

/* Child switcher tabs (spec §2.3) */
.child-tabs {
  --van-tabs-bottom-bar-color: var(--van-primary-color);
  padding: 0 16px;
}

.module-card {
  margin: 12px;
  background: var(--card-bg, #f5f5ff);
  border-radius: 12px;
  overflow: hidden;
}

.module-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 14px 16px;
  cursor: pointer;
  user-select: none;
}

.module-title-row {
  display: flex;
  align-items: center;
  gap: 8px;
}

.module-title {
  font-size: 15px;
  font-weight: 600;
  color: var(--text-primary);
}

.module-empty {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 16px;
  color: var(--text-secondary);
  font-size: 13px;
  justify-content: center;
}

.empty-icon {
  font-size: 18px;
}

.summary-line {
  padding: 0 16px 8px;
  font-size: 13px;
  color: var(--text-secondary);
}

.topic-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  padding: 0 16px 12px;
}

.topic-tag {
  cursor: default;
}

.module-actions {
  display: flex;
  gap: 8px;
  padding: 0 16px 14px;
}

.review-item {
  padding: 12px 16px;
  border-bottom: 1px solid var(--separator, rgba(0, 0, 0, 0.06));
}

.review-item:last-child {
  border-bottom: none;
}

.review-item-header {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 6px;
}

.review-child-name {
  font-size: 14px;
  font-weight: 600;
  color: var(--text-primary);
}

.review-topic-name {
  font-size: 13px;
  color: var(--text-secondary);
}

.review-meta {
  display: flex;
  align-items: center;
  gap: 12px;
  font-size: 12px;
  color: var(--text-secondary);
}

.view-all-btn {
  margin: 8px 16px 14px;
}

.preset-path-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 10px 0;
  cursor: pointer;
}

.preset-path-name {
  font-size: 14px;
  color: var(--text-primary);
}

.path-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 10px 0;
  cursor: pointer;
}

.path-row-main {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.path-row-name {
  font-size: 14px;
  color: var(--text-primary);
  font-weight: 500;
}

.path-row-child {
  font-size: 12px;
  color: var(--text-secondary);
}

.path-row-meta {
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  gap: 4px;
}

.path-row-progress {
  font-size: 12px;
  color: var(--text-secondary);
}

/* Evidence panel */
.evidence-panel {
  display: flex;
  flex-direction: column;
  height: 100%;
}

.evidence-panel-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 16px;
  border-bottom: 1px solid var(--separator, rgba(0, 0, 0, 0.06));
}

.evidence-panel-title {
  font-size: 16px;
  font-weight: 600;
  color: var(--text-primary);
}

.evidence-close {
  font-size: 20px;
  cursor: pointer;
  color: var(--text-secondary);
}

.evidence-panel-body {
  flex: 1;
  overflow-y: auto;
  padding: 16px;
}

.evidence-topic {
  display: flex;
  flex-direction: column;
  gap: 6px;
  margin-bottom: 16px;
}

.evidence-label {
  font-size: 15px;
  font-weight: 600;
  color: var(--text-primary);
}

.evidence-desc {
  font-size: 13px;
  color: var(--text-secondary);
}

.evidence-meta {
  display: flex;
  gap: 12px;
  font-size: 13px;
  color: var(--text-secondary);
  margin-bottom: 16px;
}

.evidence-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.evidence-item {
  padding: 10px 12px;
  background: var(--bg-primary, #ffffff);
  border-radius: 8px;
  font-size: 13px;
  color: var(--text-primary);
  line-height: 1.5;
}

.evidence-panel-actions {
  display: flex;
  gap: 12px;
  padding: 16px;
  border-top: 1px solid var(--separator, rgba(0, 0, 0, 0.06));
}

.evidence-panel-actions .van-button {
  flex: 1;
}

/* van-collapse style overrides */
:deep(.van-collapse) {
  margin: 0 12px;
}

:deep(.van-collapse-item__title) {
  background: var(--card-bg, #f5f5ff);
  border-radius: 12px 12px 0 0;
  margin-bottom: 0;
  padding: 12px 16px;
}

:deep(.van-collapse-item__wrapper) {
  background: var(--card-bg, #f5f5ff);
  border-radius: 0 0 12px 12px;
}

:deep(.van-collapse-item__content) {
  background: transparent;
  padding: 8px 16px 16px;
}

:deep(.van-collapse-item + .van-collapse-item) {
  margin-top: 12px;
}

.collapse-title-row {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 15px;
  font-weight: 600;
  color: var(--text-primary);
}

.collapse-count {
  font-size: 12px;
  font-weight: 400;
  color: var(--text-secondary);
  margin-left: 4px;
}

/* View mode toggle (DNA Graph / Cluster Map) */
.view-mode-toggle {
  display: flex;
  gap: 0;
  margin-bottom: 12px;
  border-radius: 8px;
  overflow: hidden;
  border: 1px solid var(--van-gray-3, #dee0e3);
}

.view-mode-btn {
  flex: 1;
  padding: 6px 12px;
  border: none;
  background: var(--van-gray-1, #f7f8fa);
  color: var(--text-secondary);
  font-size: 13px;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.2s;
}

.view-mode-btn--active {
  background: var(--van-primary-color);
  color: #fff;
}

.view-mode-btn:active {
  opacity: 0.85;
}
</style>
