<template>
  <van-cell-group v-if="childMembers.length > 0 && familyStore.aiEnabled" inset class="chart-section literacy-status-card">
    <van-collapse v-model="expanded">
      <van-collapse-item name="literacy">
        <template #title>
          <div class="literacy-header">
            <span class="literacy-title">
              <span class="literacy-icon">
                <van-loading v-if="loading" size="16px" type="spinner" color="#1989fa" />
                <IIcon v-else :icon="'lucide:book-open'" size="18" class="literacy-icon__svg" />
              </span>
              <span class="literacy-title__text">{{ t('dashboard.literacyReport') }}</span>
            </span>
            <span v-if="loading" class="literacy-summary literacy-summary--loading">
              <van-loading size="12px" type="spinner" />
            </span>
            <span v-else-if="error" class="literacy-summary literacy-summary--error">
              <van-button plain type="danger" size="mini" @click.stop="onRetry">
                {{ t('aiTask.retry') }}
              </van-button>
            </span>
            <span v-else class="literacy-summary">
              {{ readyCount }}/{{ childMembers.length }}
            </span>
          </div>
        </template>

        <template v-if="loading">
          <div v-for="child in childMembers" :key="child.id" class="literacy-skeleton-row">
            <div class="literacy-skeleton-avatar" />
            <div class="literacy-skeleton-name" />
            <div class="literacy-skeleton-badge" />
          </div>
        </template>

        <div v-else-if="error" class="literacy-error-state">
          <p class="literacy-error-text">{{ t('dashboard.literacyLoadError') }}</p>
          <van-button plain type="primary" size="small" @click="onRetry">
            {{ t('aiTask.retry') }}
          </van-button>
        </div>

        <template v-else>
          <div
            v-for="child in childMembers"
            :key="child.id"
            class="literacy-status-row"
          >
            <UserAvatar
              :avatar-url="child.avatar_url ?? null"
              :avatar-color="child.avatar_color || '#FF6B6B'"
              :display-name="child.display_name || '?'"
              :size="32"
            />
            <span class="literacy-status-name">{{ child.display_name }}</span>
            <span
              class="literacy-status-badge"
              :class="statusClass(child.id)"
            >
              {{ statusLabel(child.id) }}
            </span>
          </div>
          <div class="literacy-footer">
            <router-link to="/baby/literacy-report" class="literacy-view-all">
              {{ t('dashboard.literacyViewAll') }}<van-icon name="arrow" size="12" />
            </router-link>
          </div>
        </template>
      </van-collapse-item>
    </van-collapse>
  </van-cell-group>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onActivated } from 'vue'
import { useI18n } from 'vue-i18n'
import { useFamilyStore } from '@/stores/family'
import { getReportStatus, type ReportStatus } from '@/api/literacyReport'
import IIcon from '@/components/IIcon.vue'
import UserAvatar from '@/components/common/UserAvatar.vue'

const { t } = useI18n()
const familyStore = useFamilyStore()

const statusMap = ref<Record<string, ReportStatus>>({})
const loading = ref(true)
const error = ref(false)
const expanded = ref<string[]>([])

const childMembers = computed(() =>
  familyStore.members.filter(m => m.role === 'child' && m.is_active),
)

const readyCount = computed(() =>
  childMembers.value.filter(c => statusMap.value[String(c.id)]?.status === 'ready').length,
)

const STATUS_TIMEOUT_MS = 15_000

/** Wrap a promise with a timeout — rejects if not settled in time. */
function withTimeout<T>(promise: Promise<T>, ms: number): Promise<T> {
  return new Promise<T>((resolve, reject) => {
    const timer = setTimeout(() => reject(new Error('timeout')), ms)
    promise.then(
      (v) => { clearTimeout(timer); resolve(v) },
      (e) => { clearTimeout(timer); reject(e) },
    )
  })
}

async function loadStatuses() {
  if (!familyStore.aiEnabled || !childMembers.value.length) {
    loading.value = false
    return
  }
  loading.value = true
  error.value = false
  try {
    const results = await Promise.allSettled(
      childMembers.value.map(child =>
        withTimeout(
          getReportStatus(String(child.id)).then(r => ({ id: String(child.id), data: r.data })),
          STATUS_TIMEOUT_MS,
        ),
      ),
    )
    for (const result of results) {
      if (result.status === 'fulfilled') {
        statusMap.value[result.value.id] = result.value.data
      }
    }
    // If ALL requests failed/timed-out, mark as error so the UI shows a retry button
    if (results.every(r => r.status === 'rejected')) {
      error.value = true
    }
  } catch {
    error.value = true
  } finally {
    loading.value = false
  }
}

function onRetry() {
  void loadStatuses()
}

function statusClass(childId: string | number): string {
  const s = statusMap.value[String(childId)]
  if (!s) return 'none'
  return s.status
}

function statusLabel(childId: string | number): string {
  const s = statusMap.value[String(childId)]
  if (!s) return t('dashboard.literacyNone')
  switch (s.status) {
    case 'ready': return t('dashboard.literacyReady')
    case 'generating': return t('dashboard.literacyGenerating')
    default: return t('dashboard.literacyNone')
  }
}

onMounted(() => {
  void loadStatuses()
})

// Dashboard is KeepAlive-cached; re-check statuses when navigating back.
onActivated(() => {
  if (!loading.value) {
    void loadStatuses()
  }
})

defineExpose({ loadStatuses })
</script>

<style scoped>
.literacy-status-card {
  display: block;
  margin: 8px 0;
}
.literacy-status-card :deep(.van-collapse-item__title) {
  justify-content: flex-start;
}
.literacy-status-card :deep(.van-cell__title) {
  flex: 1;
  display: flex;
  min-width: 0;
}
.literacy-status-card :deep(.van-cell__value) {
  flex: none;
  width: 0;
}
.literacy-header {
  display: flex;
  align-items: center;
  width: 100%;
  min-width: 0;
  gap: 8px;
}
.literacy-title {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  flex: 1;
  min-width: 0;
}
.literacy-icon {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 1.4em;
  height: 1.4em;
  flex-shrink: 0;
}
.literacy-icon__svg {
  color: #1989fa;
}
.literacy-title__text {
  font-weight: 600;
}
.literacy-summary {
  margin-left: 8px;
  font-size: 12px;
  color: var(--van-text-color-2);
}
.literacy-summary--loading {
  display: inline-flex;
  align-items: center;
}
.literacy-summary--error {
  display: inline-flex;
  align-items: center;
}

/* Skeleton rows */
.literacy-skeleton-row {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 8px 0;
}
.literacy-skeleton-avatar {
  width: 24px;
  height: 24px;
  border-radius: 50%;
  background: var(--van-skeleton-row-background, #f2f3f5);
  flex-shrink: 0;
}
.literacy-skeleton-name {
  flex: 1;
  height: 14px;
  border-radius: 4px;
  background: var(--van-skeleton-row-background, #f2f3f5);
}
.literacy-skeleton-badge {
  width: 48px;
  height: 20px;
  border-radius: 10px;
  background: var(--van-skeleton-row-background, #f2f3f5);
  flex-shrink: 0;
}

/* Status rows */
.literacy-status-row {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 8px 0;
}
.literacy-status-row + .literacy-status-row {
  border-top: 1px solid var(--separator, #eee);
}
.literacy-status-avatar {
  width: 24px;
  height: 24px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 12px;
  font-weight: 700;
  color: #fff;
  flex-shrink: 0;
}
.literacy-status-name {
  flex: 1;
  font-size: 14px;
  color: var(--text-primary, #0a0a0a);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.literacy-status-badge {
  font-size: 12px;
  font-weight: 500;
  padding: 2px 8px;
  border-radius: 10px;
  flex-shrink: 0;
}
.literacy-status-badge.ready {
  background: rgba(34, 197, 94, 0.12);
  color: #16a34a;
}
.literacy-status-badge.generating {
  background: rgba(245, 158, 11, 0.12);
  color: #d97706;
}
.literacy-status-badge.none {
  background: rgba(0, 0, 0, 0.05);
  color: var(--text-secondary, #616161);
}
[data-theme='dark'] .literacy-status-badge.ready {
  background: rgba(34, 197, 94, 0.2);
  color: #4ade80;
}
[data-theme='dark'] .literacy-status-badge.generating {
  background: rgba(245, 158, 11, 0.2);
  color: #fbbf24;
}
[data-theme='dark'] .literacy-status-badge.none {
  background: rgba(255, 255, 255, 0.08);
  color: var(--text-secondary, #c8c8d0);
}

.literacy-footer {
  display: flex;
  justify-content: flex-end;
  padding-top: 8px;
  margin-top: 4px;
  border-top: 1px solid var(--separator, #eee);
}
.literacy-view-all {
  font-size: 13px;
  color: var(--text-secondary, #616161);
  display: flex;
  align-items: center;
  gap: 2px;
  text-decoration: none;
}

.literacy-error-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 8px;
  padding: 16px 0;
}
.literacy-error-text {
  font-size: 13px;
  color: var(--van-text-color-2);
  margin: 0;
  text-align: center;
}
</style>
