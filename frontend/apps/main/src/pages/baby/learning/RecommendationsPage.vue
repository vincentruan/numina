<template>
  <div class="recommendations-page">
    <PageHeader :title="t('learning.fineTunePath')">
      <template #right>
        <van-button
          size="small"
          type="primary"
          :disabled="orderedTopics.length === 0"
          :loading="confirming"
          @click="handleConfirm"
        >
          {{ t('learning.confirmAssign') }}
        </van-button>
      </template>
    </PageHeader>

    <van-pull-refresh v-model="loading" @refresh="fetchRecommendations">
      <van-skeleton v-if="loading && orderedTopics.length === 0" :rows="5" round style="padding: 16px;" />
      <EmptyState
        v-else-if="orderedTopics.length === 0"
        :description="t('learning.noRecommendations')"
      >
        <van-button type="primary" plain style="margin-top: 16px;" @click="router.push(`/baby/learning/${childId}/map`)">
          {{ t('learning.addFromGraph') }}
        </van-button>
      </EmptyState>
      <div v-else class="topic-list">
        <van-swipe-cell
          v-for="(topic, index) in orderedTopics"
          :key="topic.topic_id"
        >
          <div class="topic-card" @click="handleCardClick(topic)">
            <div class="topic-card__left">
              <span class="topic-card__emoji">{{ reasonEmoji(topic.reasons) }}</span>
              <div class="topic-card__content">
                <span class="topic-card__name">{{ topic.topic_name }}</span>
                <div class="topic-card__footer">
                  <van-tag
                    :type="centralityType(index)"
                    size="medium"
                    plain
                    round
                  >
                    {{ centralityLabel(index) }}
                  </van-tag>
                  <span class="topic-card__reasons">{{ t('learning.reasonsCount', { count: topic.reasons.length }) }}</span>
                </div>
              </div>
            </div>
            <van-icon name="arrow" class="topic-card__arrow" />
          </div>
          <template #right>
            <van-button
              type="danger"
              square
              class="topic-card__delete"
              @click="removeTopic(topic)"
            >
              {{ t('common.remove') }}
            </van-button>
          </template>
        </van-swipe-cell>
      </div>
    </van-pull-refresh>

    <div v-if="orderedTopics.length > 0" class="bottom-bar">
      <van-button block plain type="primary" @click="router.push(`/baby/learning/${childId}/map`)">
        {{ t('learning.addFromGraph') }}
      </van-button>
    </div>
  </div>
</template>

<script setup lang="ts">
defineOptions({ name: 'Recommendations' })

import { ref, computed, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRouter } from 'vue-router'
import { showSuccessToast, showFailToast, showConfirmDialog } from 'vant'
import { useBabyStore } from '@/stores/baby'
import { getRecommendations, createAssignment, type RecommendationTopicItem } from '@/api/learning'
import PageHeader from '@/components/common/PageHeader.vue'
import EmptyState from '@/components/common/EmptyState.vue'

const { t } = useI18n()
const router = useRouter()
const babyStore = useBabyStore()

const loading = ref(true)
const confirming = ref(false)
const topics = ref<RecommendationTopicItem[]>([])

const childId = computed(() => babyStore.selectedChildId ?? '')
const orderedTopics = computed(() => topics.value)

function reasonEmoji(reasons: string[]): string {
  if (reasons.includes('prerequisite')) return '🔗'
  if (reasons.includes('mastery_gained')) return '🔄'
  if (reasons.includes('high_centrality')) return '⭐'
  return '📚'
}

function centralityType(index: number): 'warning' | 'primary' | 'default' {
  if (index < 3) return 'warning'
  if (index < 6) return 'primary'
  return 'default'
}

function centralityLabel(index: number): string {
  if (index < 3) return t('learning.centralityHigh')
  if (index < 6) return t('learning.centralityMedium')
  return t('learning.centralityLow')
}

function handleCardClick(_topic: RecommendationTopicItem) {
  // Reserved for future: show alternatives or detail
}

function removeTopic(topic: RecommendationTopicItem) {
  topics.value = topics.value.filter((item) => item.topic_id !== topic.topic_id)
  showSuccessToast(t('learning.topicRemoved'))
}

async function fetchRecommendations() {
  const id = childId.value
  if (!id) {
    loading.value = false
    return
  }
  loading.value = true
  try {
    const res = await getRecommendations(id)
    topics.value = res.path?.topics ?? []
  } catch {
    topics.value = []
  } finally {
    loading.value = false
  }
}

async function handleConfirm() {
  if (orderedTopics.value.length === 0) {
    showFailToast(t('learning.noTopicsToAssign'))
    return
  }
  const id = childId.value
  if (!id) {
    showFailToast(t('learning.childRequired'))
    return
  }

  try {
    await showConfirmDialog({
      title: t('learning.confirmAssign'),
      message: t('learning.confirmAssignDesc', { count: orderedTopics.value.length }),
    })
  } catch {
    return
  }

  confirming.value = true
  try {
    await Promise.all(
      orderedTopics.value.map((topic, index) =>
        createAssignment({
          child_id: id,
          topic_id: topic.topic_id,
          priority: index < 3 ? 2 : 1,
        }),
      ),
    )
    showSuccessToast(t('learning.assignAllSuccess', { count: orderedTopics.value.length }))
    router.push({ name: 'BabyLearning' })
  } catch {
    showFailToast(t('toast.operationFailed'))
  } finally {
    confirming.value = false
  }
}

onMounted(() => {
  fetchRecommendations()
})
</script>

<style scoped>
.recommendations-page {
  min-height: 100vh;
  padding-bottom: 80px;
}

.topic-list {
  padding: 16px;
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.topic-card {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 14px;
  background: var(--card-bg);
  border-radius: 12px;
  cursor: pointer;
  gap: 10px;
}

.topic-card__left {
  display: flex;
  align-items: flex-start;
  gap: 10px;
  flex: 1;
  min-width: 0;
}

.topic-card__emoji {
  font-size: 24px;
  flex-shrink: 0;
  line-height: 1;
}

.topic-card__content {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.topic-card__name {
  font-size: 15px;
  font-weight: 500;
  color: var(--text-primary);
  line-height: 1.4;
  overflow: hidden;
  text-overflow: ellipsis;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
}

.topic-card__footer {
  display: flex;
  align-items: center;
  gap: 8px;
}

.topic-card__reasons {
  font-size: 12px;
  color: var(--text-secondary);
}

.topic-card__arrow {
  color: var(--text-secondary);
  flex-shrink: 0;
}

.topic-card__delete {
  height: 100%;
}

.bottom-bar {
  position: fixed;
  bottom: 0;
  left: 0;
  right: 0;
  padding: 12px 16px;
  background: var(--card-bg);
  border-top: 1px solid var(--van-border-color);
}
</style>
