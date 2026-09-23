<template>
  <div class="baby-learning-page">
    <PageHeader :title="t('learning.parentTitle')" />

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
          <!-- Children overview cards -->
          <van-cell-group inset class="children-section">
            <div
              v-for="child in children"
              :key="child.child_id"
              class="child-card"
            >
              <div class="child-card-header">
                <span class="child-name">{{ child.child_name }}</span>
                <span class="child-study-time">{{ t('learning.studyMinutes', { minutes: child.total_study_minutes }) }}</span>
              </div>
              <div class="child-stats">
                <div class="stat-item">
                  <span class="stat-value stat-mastered">{{ child.mastered_count }}</span>
                  <span class="stat-label">{{ t('learning.mastered') }}</span>
                </div>
                <div class="stat-item">
                  <span class="stat-value stat-learning">{{ child.learning_count }}</span>
                  <span class="stat-label">{{ t('learning.learning') }}</span>
                </div>
                <div class="stat-item">
                  <span class="stat-value stat-available">{{ child.available_count }}</span>
                  <span class="stat-label">{{ t('learning.available') }}</span>
                </div>
                <div class="stat-item" v-if="child.review_count > 0">
                  <span class="stat-value stat-review">{{ child.review_count }}</span>
                  <span class="stat-label">{{ t('learning.reviewQueue') }}</span>
                </div>
              </div>
              <div class="child-actions">
                <van-button
                  size="small"
                  plain
                  type="primary"
                  @click="router.push(`/baby/learning/${child.child_id}/map`)"
                >
                  {{ t('learning.viewMap') }}
                </van-button>
                <van-button
                  size="small"
                  plain
                  type="primary"
                  @click="router.push({ path: '/baby/learning/assign', query: { child_id: child.child_id } })"
                >
                  {{ t('learning.assignTask') }}
                </van-button>
              </div>
            </div>
          </van-cell-group>

          <!-- Review queue section -->
          <van-cell-group inset class="reviews-section" v-if="reviews.length > 0">
            <template #title>
              <div class="section-title-row">
                <span>{{ t('learning.pendingReviews') }}</span>
                <van-badge :content="reviews.length" />
              </div>
            </template>
            <div
              v-for="review in reviews"
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
              </div>
              <div class="review-actions">
                <van-button
                  size="mini"
                  type="success"
                  :loading="actioningId === review.progress_id"
                  @click="doApprove(review)"
                >
                  {{ t('learning.approve') }}
                </van-button>
                <van-button
                  size="mini"
                  type="danger"
                  :loading="actioningId === review.progress_id"
                  @click="doReject(review)"
                >
                  {{ t('learning.reject') }}
                </van-button>
              </div>
            </div>
          </van-cell-group>

          <!-- Empty reviews state -->
          <van-cell-group inset class="reviews-section" v-else>
            <template #title>
              <span>{{ t('learning.pendingReviews') }}</span>
            </template>
            <div class="reviews-empty">
              <span class="reviews-empty-icon">🎉</span>
              <span>{{ t('learning.noPendingReviews') }}</span>
            </div>
          </van-cell-group>

          <!-- Navigation to full pages -->
          <van-cell-group inset class="nav-section">
            <van-cell
              :title="t('learning.allReviews')"
              is-link
              @click="router.push('/baby/learning/reviews')"
            />
          </van-cell-group>
        </template>
      </van-pull-refresh>
    </template>
  </div>
</template>

<script setup lang="ts">
defineOptions({ name: 'BabyLearning' })

import { ref, onMounted, onActivated } from 'vue'
import { useRouter } from 'vue-router'
import { showSuccessToast, showFailToast, showConfirmDialog } from 'vant'
import { useI18n } from 'vue-i18n'
import { usePageLoading } from '@/composables/usePageLoading'
import {
  getLearningChildren,
  getReviews,
  approveReview,
  rejectReview,
  type ChildLearningOverview,
  type ReviewItem,
} from '@/api/learning'
import PageHeader from '@/components/common/PageHeader.vue'
import EmptyState from '@/components/common/EmptyState.vue'

const { t } = useI18n()
const router = useRouter()
const { increment, decrement } = usePageLoading()

const loading = ref(true)
const refreshing = ref(false)
const children = ref<ChildLearningOverview[]>([])
const reviews = ref<ReviewItem[]>([])
const actioningId = ref<string | null>(null)

// Skip first onActivated — Vue 3 fires both onMounted and onActivated on first mount
let hasActivated = false

async function loadData() {
  try {
    const [childrenData, reviewsData] = await Promise.all([
      getLearningChildren(),
      getReviews(),
    ])
    children.value = childrenData
    reviews.value = reviewsData.slice(0, 5) // Show only first 5 on overview
  } catch {
    showFailToast(t('toast.operationFailed'))
  }
}

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
    await loadData()
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
    await loadData()
  } catch {
    showFailToast(t('toast.operationFailed'))
  } finally {
    actioningId.value = null
  }
}

async function onRefresh() {
  await loadData()
  refreshing.value = false
}

onMounted(async () => {
  increment()
  try {
    await loadData()
  } finally {
    decrement()
  }
  loading.value = false
})

onActivated(async () => {
  if (!hasActivated) { hasActivated = true; return }
  increment()
  try {
    await loadData()
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

.children-section {
  margin-top: 12px;
}

.child-card {
  padding: 16px;
  border-bottom: 1px solid var(--separator, #f5f5f5);
}

.child-card:last-child {
  border-bottom: none;
}

.child-card-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 12px;
}

.child-name {
  font-size: 16px;
  font-weight: 600;
  color: var(--text-primary);
}

.child-study-time {
  font-size: 13px;
  color: var(--text-secondary);
}

.child-stats {
  display: flex;
  gap: 16px;
  margin-bottom: 12px;
}

.stat-item {
  display: flex;
  flex-direction: column;
  align-items: center;
  flex: 1;
}

.stat-value {
  font-size: 20px;
  font-weight: 700;
  line-height: 1.2;
}

.stat-mastered {
  color: var(--color-success, #4CAF50);
}

.stat-learning {
  color: var(--color-warning, #FF9800);
}

.stat-available {
  color: var(--text-secondary);
}

.stat-review {
  color: var(--van-danger-color, #ee0a24);
}

.stat-label {
  font-size: 12px;
  color: var(--text-secondary);
  margin-top: 4px;
}

.child-actions {
  display: flex;
  gap: 8px;
}

.child-actions .van-button {
  flex: 1;
}

.reviews-section {
  margin-top: 12px;
}

.section-title-row {
  display: flex;
  align-items: center;
  gap: 8px;
}

.review-item {
  padding: 12px 16px;
  border-bottom: 1px solid var(--separator, #f5f5f5);
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
  font-size: 14px;
  color: var(--text-secondary);
}

.review-meta {
  display: flex;
  gap: 12px;
  font-size: 12px;
  color: var(--text-secondary);
  margin-bottom: 8px;
}

.review-actions {
  display: flex;
  gap: 8px;
}

.reviews-empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 24px 16px;
  gap: 8px;
}

.reviews-empty-icon {
  font-size: 32px;
}

.nav-section {
  margin-top: 12px;
}
</style>
