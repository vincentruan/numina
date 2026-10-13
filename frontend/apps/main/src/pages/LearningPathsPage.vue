<template>
  <div class="learning-paths-page">
    <PageHeader :title="t('learning.pathsTitle')" />

    <van-skeleton v-if="loading && paths.length === 0" :rows="5" :round="true" />

    <template v-else>
      <van-pull-refresh v-model="refreshing" @refresh="onRefresh">
        <!-- Group by child -->
        <template v-for="group in groupedPaths" :key="group.childId">
          <van-cell-group inset class="child-paths-section">
            <template #title>
              <span class="group-title">{{ group.childName }}</span>
            </template>

            <div
              v-for="path in group.paths"
              :key="path.id"
              class="path-card"
              @click="router.push({ name: 'LearningPathDetail', params: { pathId: path.id } })"
            >
              <div class="path-card__header">
                <span class="path-card__name">{{ displayName(path) }}</span>
                <van-tag :type="statusTagType(path.status)" class="path-card__status">
                  {{ statusLabel(path.status) }}
                </van-tag>
              </div>

              <div class="path-card__progress">
                <van-progress
                  :percentage="pathPercent(path)"
                  :show-pivot="true"
                  color="var(--van-primary-color)"
                  stroke-width="8"
                />
                <span class="path-card__count">
                  {{ path.completed_count }} / {{ path.total_count }}
                </span>
              </div>

              <div v-if="path.due_date" class="path-card__meta">
                <van-icon name="clock-o" />
                {{ t('learning.pathDue', { date: path.due_date }) }}
              </div>
            </div>
          </van-cell-group>
        </template>

        <!-- No active paths -->
        <EmptyState
          v-if="activePaths.length === 0"
          :description="t('learning.noActivePaths')"
        >
          <van-button type="primary" size="small" @click="goToAssign">
            {{ t('learning.createPath') }}
          </van-button>
        </EmptyState>
      </van-pull-refresh>
    </template>
  </div>
</template>

<script setup lang="ts">
defineOptions({ name: 'LearningPaths' })

import { ref, computed, onMounted, onActivated } from 'vue'
import { useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { showFailToast, type TagType } from 'vant'
import { usePageLoading } from '@/composables/usePageLoading'
import { getPaths, getLearningChildren, type PathResponse, type ChildLearningOverview } from '@/api/learning'
import PageHeader from '@/components/common/PageHeader.vue'
import EmptyState from '@/components/common/EmptyState.vue'

const { t, locale } = useI18n()
const router = useRouter()
const { increment, decrement } = usePageLoading()

const loading = ref(true)
const refreshing = ref(false)
const paths = ref<PathResponse[]>([])
const children = ref<Map<string, string>>(new Map())

let hasActivated = false

async function loadData() {
  try {
    const [childrenData, pathsData] = await Promise.all([
      getLearningChildren(),
      getPaths(),
    ])
    children.value = new Map(childrenData.map(c => [String(c.child_id), c.child_name]))
    paths.value = pathsData
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

const activePaths = computed(() =>
  paths.value.filter(p => p.status === 'active'),
)

const archivedPaths = computed(() =>
  paths.value.filter(p => p.status === 'archived'),
)

interface ChildPathGroup {
  childId: string
  childName: string
  paths: PathResponse[]
}

const groupedPaths = computed<ChildPathGroup[]>(() => {
  const map = new Map<string, PathResponse[]>()
  for (const p of activePaths.value) {
    const cid = p.child_id
    if (!map.has(cid)) map.set(cid, [])
    map.get(cid)!.push(p)
  }
  return Array.from(map.entries()).map(([childId, ps]) => ({
    childId,
    childName: children.value.get(childId) || childId,
    paths: ps,
  }))
})

function displayName(path: PathResponse): string {
  if (locale.value.startsWith('zh') && path.name_zh) return path.name_zh
  return path.name
}

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

function pathPercent(path: PathResponse): number {
  if (path.total_count === 0) return 0
  return Math.round((path.completed_count / path.total_count) * 100)
}

function goToAssign() {
  router.push('/baby/learning/assign')
}

onMounted(async () => {
  increment()
  try {
    await loadData()
  } finally {
    decrement()
  }
})

onActivated(() => {
  if (!hasActivated) {
    hasActivated = true
    return
  }
  loadData()
})
</script>

<style scoped>
.learning-paths-page {
  min-height: 100vh;
  background: var(--bg-primary);
}

.child-paths-section {
  margin-bottom: 12px;
}

.group-title {
  font-weight: 600;
  font-size: 15px;
  color: var(--text-primary);
}

.path-card {
  padding: 12px 16px;
  border-bottom: 1px solid var(--van-border-color);
  cursor: pointer;
  transition: background 0.15s;
}

.path-card:last-child {
  border-bottom: none;
}

.path-card:active {
  background: var(--van-active-color);
}

.path-card__header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 8px;
}

.path-card__name {
  font-weight: 600;
  font-size: 15px;
  color: var(--text-primary);
  flex: 1;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  margin-right: 8px;
}

.path-card__status {
  flex-shrink: 0;
}

.path-card__progress {
  display: flex;
  align-items: center;
  gap: 8px;
}

.path-card__progress :deep(.van-progress) {
  flex: 1;
}

.path-card__count {
  font-size: 13px;
  color: var(--text-secondary);
  white-space: nowrap;
  flex-shrink: 0;
  min-width: 48px;
  text-align: right;
}

.path-card__meta {
  display: flex;
  align-items: center;
  gap: 4px;
  margin-top: 6px;
  font-size: 12px;
  color: var(--text-secondary);
}
</style>
