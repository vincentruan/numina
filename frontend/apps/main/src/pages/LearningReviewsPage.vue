<template>
  <div class="learning-reviews-page">
    <PageHeader :title="t('learning.allReviews')" />

    <van-skeleton v-if="loading && reviews.length === 0" :rows="5" :round="true" />

    <template v-else>
      <van-pull-refresh v-model="refreshing" @refresh="onRefresh">
        <!-- Empty state -->
        <EmptyState v-if="reviews.length === 0" :description="t('learning.noPendingReviews')">
          <template #image>
            <span class="empty-celebration">🎉</span>
          </template>
        </EmptyState>

        <template v-else>
          <div class="reviews-list">
            <div
              v-for="review in reviews"
              :key="review.progress_id"
              class="review-card"
            >
              <!-- Header -->
              <div class="review-card-header">
                <div class="review-child-info">
                  <span class="review-child-name">{{ review.child_name }}</span>
                  <span class="review-topic-name">{{ review.topic_name }}</span>
                </div>
                <van-tag type="warning">{{ t('learning.pendingReview') }}</van-tag>
              </div>

              <!-- Meta row -->
              <div class="review-meta">
                <span>{{ t('learning.attempts', { count: review.attempts }) }}</span>
                <span>{{ t('learning.studyDuration', { seconds: review.study_duration_seconds }) }}</span>
                <span>{{ formatTime(review.submitted_at) }}</span>
              </div>

              <!-- Evidence toggle (anti-rubber-stamp) -->
              <div
                class="evidence-toggle"
                @click="toggleEvidence(review.progress_id)"
              >
                <span>{{ t('learning.viewEvidence') }}</span>
                <van-icon
                  :name="expandedIds.has(review.progress_id) ? 'arrow-up' : 'arrow-down'"
                  size="14"
                />
              </div>

              <!-- Evidence content (collapsed by default) -->
              <div v-if="expandedIds.has(review.progress_id)" class="evidence-content">
                <p class="evidence-desc">{{ topicDescription(review) }}</p>
                <ul class="evidence-list">
                  <li
                    v-for="(item, idx) in evidenceItems(review)"
                    :key="idx"
                    class="evidence-item"
                  >
                    {{ item }}
                  </li>
                </ul>

                <!-- Action buttons (only visible when evidence is expanded) -->
                <div class="review-actions">
                  <van-button
                    size="small"
                    type="success"
                    :loading="actioningId === review.progress_id"
                    @click.stop="doApprove(review)"
                  >
                    {{ t('learning.approve') }}
                  </van-button>
                  <van-button
                    size="small"
                    type="danger"
                    :loading="actioningId === review.progress_id"
                    @click.stop="doReject(review)"
                  >
                    {{ t('learning.reject') }}
                  </van-button>
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
defineOptions({ name: 'LearningReviews' })

import { ref, onMounted, onActivated } from 'vue'
import { useI18n } from 'vue-i18n'
import { showSuccessToast, showFailToast, showConfirmDialog } from 'vant'
import { usePageLoading } from '@/composables/usePageLoading'
import {
  getReviews,
  approveReview,
  rejectReview,
  type ReviewItem,
} from '@/api/learning'
import PageHeader from '@/components/common/PageHeader.vue'
import EmptyState from '@/components/common/EmptyState.vue'

const { t, locale } = useI18n()
const { increment, decrement } = usePageLoading()

const loading = ref(true)
const refreshing = ref(false)
const reviews = ref<ReviewItem[]>([])
const actioningId = ref<string | null>(null)
const expandedIds = ref<Set<string>>(new Set())

// Skip first onActivated
let hasActivated = false

function toggleEvidence(progressId: string) {
  const newSet = new Set(expandedIds.value)
  if (newSet.has(progressId)) {
    newSet.delete(progressId)
  } else {
    newSet.add(progressId)
  }
  expandedIds.value = newSet
}

function evidenceItems(review: ReviewItem): string[] {
  if (locale.value.startsWith('zh') && review.evidence_zh && review.evidence_zh.length > 0) {
    return review.evidence_zh
  }
  return review.evidence
}

function topicDescription(review: ReviewItem): string {
  return review.topic_description || ''
}

function formatTime(dateStr: string): string {
  const date = new Date(dateStr)
  return date.toLocaleDateString(locale.value, {
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  })
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
    // Remove from list
    reviews.value = reviews.value.filter(r => r.progress_id !== review.progress_id)
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
    // Remove from list
    reviews.value = reviews.value.filter(r => r.progress_id !== review.progress_id)
  } catch {
    showFailToast(t('toast.operationFailed'))
  } finally {
    actioningId.value = null
  }
}

async function loadData() {
  try {
    const data = await getReviews()
    reviews.value = data
  } catch {
    showFailToast(t('toast.operationFailed'))
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
.learning-reviews-page {
  min-height: 100vh;
  padding-bottom: 20px;
}

.empty-celebration {
  font-size: 48px;
}

.reviews-list {
  padding: 12px;
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.review-card {
  background: var(--card-bg);
  border-radius: 12px;
  padding: 16px;
  box-shadow: var(--shadow-elevated, 0 2px 8px rgba(1, 1, 32, 0.06));
}

.review-card-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  margin-bottom: 8px;
}

.review-child-info {
  display: flex;
  flex-direction: column;
  gap: 4px;
  flex: 1;
  min-width: 0;
}

.review-child-name {
  font-size: 15px;
  font-weight: 600;
  color: var(--text-primary);
}

.review-topic-name {
  font-size: 14px;
  color: var(--text-secondary);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.review-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 8px 12px;
  font-size: 12px;
  color: var(--text-secondary);
  margin-bottom: 12px;
}

.evidence-toggle {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 10px 12px;
  background: var(--bg-secondary, #f5f5f5);
  border-radius: 8px;
  cursor: pointer;
  font-size: 13px;
  color: var(--van-primary-color);
  font-weight: 500;
  transition: background 0.15s;
}

.evidence-toggle:active {
  background: var(--separator, #ebedf0);
}

.evidence-content {
  margin-top: 12px;
  padding-top: 12px;
  border-top: 1px solid var(--separator, #f5f5f5);
}

.evidence-desc {
  font-size: 13px;
  color: var(--text-secondary);
  line-height: 1.5;
  margin: 0 0 12px;
}

.evidence-list {
  margin: 0 0 16px;
  padding: 0 0 0 20px;
}

.evidence-item {
  font-size: 13px;
  color: var(--text-primary);
  line-height: 1.6;
  margin-bottom: 4px;
}

.review-actions {
  display: flex;
  gap: 8px;
}

.review-actions .van-button {
  flex: 1;
}
</style>
