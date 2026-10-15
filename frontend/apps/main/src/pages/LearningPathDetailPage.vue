<template>
  <div class="path-detail-page">
    <van-nav-bar :title="displayTitle" left-arrow @click-left="router.back()" />

    <van-skeleton v-if="loading" :rows="6" :round="true" />

    <template v-else-if="path">
      <van-pull-refresh v-model="refreshing" @refresh="onRefresh">
        <!-- Header -->
        <div class="detail-header">
          <h2>{{ displayTitle }}</h2>
          <p v-if="displayDescription" class="detail-desc">{{ displayDescription }}</p>
          <div class="detail-meta">
            <van-tag :type="statusTagType(path.status)">
              {{ statusLabel(path.status) }}
            </van-tag>
            <span v-if="path.due_date" class="meta-due">
              <van-icon name="clock-o" />
              {{ t('learning.pathDue', { date: path.due_date }) }}
            </span>
          </div>
        </div>

        <!-- Progress -->
        <van-cell-group inset>
          <div class="progress-section">
            <div class="progress-label">
              <span>{{ t('learning.pathProgress') }}</span>
              <span>{{ path.completed_count }} / {{ path.total_count }}</span>
            </div>
            <van-progress
              :percentage="pathPercent"
              :show-pivot="true"
              color="var(--van-primary-color)"
            />
          </div>
        </van-cell-group>

        <!-- Next milestone -->
        <van-cell-group inset v-if="path.next_milestone">
          <div class="milestone-section">
            <span class="milestone-icon">🏆</span>
            <span class="milestone-text">
              {{ t('learning.pathDetail.milestone', { threshold: path.next_milestone.threshold, bonus: path.next_milestone.bonus }) }}
            </span>
          </div>
        </van-cell-group>

        <!-- Score breakdown -->
        <van-cell-group inset>
          <template #title>
            <span>{{ t('learning.pathRewards') }}</span>
          </template>
          <van-cell :title="t('learning.pathDetail.perTask', { score: path.per_task_score })" />
          <van-cell v-if="path.bonus_score > 0" :title="t('learning.pathDetail.bonus', { score: path.bonus_score })" />
          <van-cell v-if="path.milestone_scores && path.milestone_scores.length > 0">
            <template #title>
              <span>{{ t('learning.milestoneRewards') }}</span>
            </template>
            <template #label>
              <span class="milestone-list">
                <span
                  v-for="(ms, idx) in path.milestone_scores"
                  :key="idx"
                  class="milestone-item"
                  :class="{ achieved: path.completed_count >= ms.threshold }"
                >
                  {{ ms.threshold }} → +{{ ms.bonus }}
                </span>
              </span>
            </template>
          </van-cell>
        </van-cell-group>

        <!-- Items list -->
        <van-cell-group inset>
          <template #title>
            <span>{{ t('learning.pathItems') }}</span>
          </template>
          <div
            v-for="item in path.items"
            :key="item.id"
            class="path-item"
            :class="{ completed: item.status === 'completed', current: item.status === 'in_progress' }"
          >
            <span class="item-icon">{{ itemIcon(item.status) }}</span>
            <span class="item-name">{{ itemDisplayName(item) }}</span>
            <van-tag v-if="item.completed_at" type="success" size="medium">
              {{ item.completed_at.split('T')[0] }}
            </van-tag>
            <span v-else class="item-status">{{ itemStatusLabel(item.status) }}</span>
          </div>
        </van-cell-group>

        <!-- Archive button -->
        <div class="archive-section" v-if="canArchive">
          <van-button
            type="default"
            block
            plain
            @click="doArchive"
          >
            {{ t('learning.pathDetail.archive') }}
          </van-button>
        </div>
      </van-pull-refresh>
    </template>

    <van-empty v-else :description="t('common.notFound')" />
  </div>
</template>

<script setup lang="ts">
defineOptions({ name: 'LearningPathDetail' })

import { ref, computed, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { showSuccessToast, showFailToast, showConfirmDialog, type TagType } from 'vant'
import { getPath, archivePath, type PathResponse } from '@/api/learning'
import { usePageLoading } from '@/composables/usePageLoading'

const { t, locale } = useI18n()
const route = useRoute()
const router = useRouter()
const { increment, decrement } = usePageLoading()

const loading = ref(true)
const refreshing = ref(false)
const path = ref<PathResponse | null>(null)

const pathId = computed(() => route.params.pathId as string)

async function loadData() {
  try {
    path.value = await getPath(pathId.value)
  } catch {
    showFailToast(t('toast.loadFailed'))
  } finally {
    loading.value = false
  }
}

async function onRefresh() {
  refreshing.value = true
  await loadData()
  refreshing.value = false
}

const displayTitle = computed(() => {
  if (!path.value) return ''
  if (locale.value.startsWith('zh') && path.value.name_zh) return path.value.name_zh
  return path.value.name
})

const displayDescription = computed(() => {
  if (!path.value) return ''
  if (locale.value.startsWith('zh') && path.value.description_zh) return path.value.description_zh
  return path.value.description || ''
})

function statusLabel(status: string): string {
  const map: Record<string, string> = {
    active: t('learning.pathStatusActive'),
    completed: t('learning.pathStatusCompleted'),
    archived: t('learning.pathStatusArchived'),
  }
  return map[status] || status
}

function statusTagType(status: string): TagType {
  const map: Record<string, TagType> = {
    active: 'primary',
    completed: 'success',
    archived: 'default',
  }
  return map[status] || 'default'
}

const pathPercent = computed(() => {
  if (!path.value || path.value.total_count === 0) return 0
  return Math.round((path.value.completed_count / path.value.total_count) * 100)
})

function itemDisplayName(item: PathResponse['items'][number]): string {
  if (locale.value.startsWith('zh') && item.topic_name_zh) return item.topic_name_zh
  return item.topic_name || item.topic_id
}

function itemIcon(status: string): string {
  const icons: Record<string, string> = {
    completed: '✅',
    in_progress: '🔵',
    pending: '⬜',
    skipped: '️',
  }
  return icons[status] || '⬜'
}

function itemStatusLabel(status: string): string {
  const map: Record<string, string> = {
    completed: t('learning.pathDetail.itemCompleted'),
    in_progress: t('learning.pathDetail.itemInProgress'),
    pending: t('learning.pathDetail.itemPending'),
    skipped: t('learning.pathDetail.itemSkipped'),
  }
  return map[status] || status
}

const canArchive = computed(() => {
  if (!path.value) return false
  return path.value.status === 'active' && path.value.completed_count === path.value.total_count && path.value.total_count > 0
})

async function doArchive() {
  try {
    await showConfirmDialog({
      title: t('learning.pathDetail.archive'),
      message: t('learning.pathDetail.archiveConfirm', { name: displayTitle.value }),
    })
  } catch {
    return
  }
  try {
    path.value = await archivePath(pathId.value)
    showSuccessToast(t('learning.pathDetail.archived'))
  } catch {
    showFailToast(t('toast.operationFailed'))
  }
}

onMounted(async () => {
  increment()
  try {
    await loadData()
  } finally {
    decrement()
  }
})
</script>

<style scoped>
.path-detail-page {
  min-height: 100vh;
  background: var(--bg-primary);
}

.detail-header {
  padding: 16px;
}

.detail-header h2 {
  font-size: 18px;
  font-weight: 700;
  color: var(--text-primary);
  margin: 0 0 6px;
}

.detail-desc {
  font-size: 14px;
  color: var(--text-secondary);
  margin: 0 0 10px;
  line-height: 1.5;
}

.detail-meta {
  display: flex;
  align-items: center;
  gap: 8px;
}

.meta-due {
  font-size: 12px;
  color: var(--text-secondary);
  display: flex;
  align-items: center;
  gap: 3px;
}

.progress-section {
  padding: 12px 0;
}

.progress-label {
  display: flex;
  justify-content: space-between;
  font-size: 13px;
  color: var(--text-secondary);
  margin-bottom: 8px;
}

.milestone-section {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 12px 0;
}

.milestone-icon {
  font-size: 20px;
}

.milestone-text {
  font-size: 14px;
  color: var(--text-primary);
  font-weight: 500;
}

.milestone-list {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.milestone-item {
  font-size: 12px;
  color: var(--text-secondary);
  background: var(--card-bg);
  border: 1px solid var(--van-border-color);
  border-radius: 4px;
  padding: 2px 8px;
}

.milestone-item.achieved {
  background: var(--van-success-color);
  color: #fff;
  border-color: var(--van-success-color);
}

.path-item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 12px 16px;
  border-bottom: 1px solid var(--van-border-color);
}

.path-item:last-child {
  border-bottom: none;
}

.path-item.completed {
  background: rgba(var(--van-success-color-rgb, 7, 193, 96), 0.04);
}

.item-icon {
  font-size: 18px;
  flex-shrink: 0;
}

.item-name {
  flex: 1;
  font-size: 14px;
  color: var(--text-primary);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.item-status {
  font-size: 12px;
  color: var(--text-secondary);
  flex-shrink: 0;
}

.archive-section {
  padding: 24px 16px;
}
</style>
