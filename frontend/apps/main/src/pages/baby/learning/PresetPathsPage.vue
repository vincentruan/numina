<template>
  <div class="preset-paths-page">
    <PageHeader :title="t('learning.presetPaths')" />

    <!-- Grade tabs -->
    <van-tabs v-model:active="selectedGrade" shrink>
      <van-tab
        v-for="g in gradeOptions"
        :key="g"
        :name="g"
        :title="t('learning.grade') + g"
      />
    </van-tabs>

    <!-- Semester chips -->
    <div class="chip-row">
      <div
        v-for="s in semesterOptions"
        :key="s"
        class="chip"
        :class="{ 'chip--active': selectedSemester === s }"
        @click="selectedSemester = selectedSemester === s ? null : s"
      >
        {{ semesterLabel(s) }}
      </div>
    </div>

    <!-- Subject chips -->
    <div class="chip-row">
      <div
        v-for="sub in subjectOptions"
        :key="sub"
        class="chip"
        :class="{ 'chip--active': selectedSubject === sub }"
        @click="selectedSubject = selectedSubject === sub ? null : sub"
      >
        {{ subjectLabel(sub) }}
      </div>
    </div>

    <!-- Content -->
    <div class="content">
      <van-skeleton v-if="loading" :rows="5" round />
      <EmptyState
        v-else-if="paths.length === 0"
        :description="t('learning.noPresetPathsGrade')"
      />
      <div v-else class="path-list">
        <div
          v-for="path in paths"
          :key="path.id"
          class="path-card"
          :class="{ 'path-card--expanded': expandedId === path.id }"
        >
          <div class="path-card__header" @click="toggleExpand(path.id)">
            <div class="path-card__info">
              <span class="path-card__name">{{ displayName(path) }}</span>
              <span class="path-card__meta">
                <van-tag plain type="primary">{{ t('learning.topicCount', { count: path.topic_count }) }}</van-tag>
              </span>
            </div>
            <van-icon :name="expandedId === path.id ? 'arrow-up' : 'arrow-down'" />
          </div>

          <div v-if="expandedId === path.id" class="path-card__expanded">
            <p v-if="path.description" class="path-card__desc">{{ path.description }}</p>
            <div class="path-card__progress">
              <van-progress
                :percentage="Math.min(path.topic_count * 10, 100)"
                :show-pivot="true"
                :pivot-text="t('learning.topicCount', { count: path.topic_count })"
                color="var(--van-primary-color)"
              />
            </div>
            <van-button
              type="primary"
              block
              :loading="assigningId === path.id"
              @click="handleAssign(path)"
            >
              {{ t('learning.dispatchOneClick') }}
            </van-button>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
defineOptions({ name: 'PresetPaths' })

import { ref, watch, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRouter } from 'vue-router'
import { showSuccessToast, showFailToast, showConfirmDialog } from 'vant'
import { useBabyStore } from '@/stores/baby'
import { getPresetPaths, assignPresetPath, type PresetPathResponse } from '@/api/learning'
import PageHeader from '@/components/common/PageHeader.vue'
import EmptyState from '@/components/common/EmptyState.vue'

const { t, locale } = useI18n()
const router = useRouter()
const babyStore = useBabyStore()

const loading = ref(true)
const paths = ref<PresetPathResponse[]>([])
const expandedId = ref<string | null>(null)
const assigningId = ref<string | null>(null)

const gradeOptions = [1, 2, 3, 4, 5, 6] as const
const semesterOptions = ['fall', 'spring'] as const
const subjectOptions = ['mathematics', 'chinese', 'english', 'science'] as const

const selectedGrade = ref<number>(1)
const selectedSemester = ref<string | null>(null)
const selectedSubject = ref<string | null>(null)

function semesterLabel(s: string): string {
  return s === 'fall' ? t('learning.semesterFall') : t('learning.semesterSpring')
}

function subjectLabel(sub: string): string {
  const key = `learning.subject${sub.charAt(0).toUpperCase() + sub.slice(1)}`
  return t(key)
}

function displayName(pp: PresetPathResponse): string {
  return locale.value.startsWith('zh') && pp.name_zh ? pp.name_zh : pp.name
}

async function fetchPaths() {
  loading.value = true
  try {
    const params: Record<string, string | number> = { grade: selectedGrade.value }
    if (selectedSemester.value) params.semester = selectedSemester.value
    if (selectedSubject.value) params.subject = selectedSubject.value
    paths.value = await getPresetPaths(params)
  } catch {
    paths.value = []
  } finally {
    loading.value = false
  }
}

function toggleExpand(id: string) {
  expandedId.value = expandedId.value === id ? null : id
}

async function handleAssign(path: PresetPathResponse) {
  const childId = babyStore.selectedChildId
  if (!childId) {
    showFailToast(t('learning.childRequired'))
    return
  }

  try {
    await showConfirmDialog({
      title: t('learning.dispatchOneClick'),
      message: t('learning.topicCount', { count: path.topic_count }),
    })
  } catch {
    return
  }

  assigningId.value = path.id
  try {
    await assignPresetPath(path.id, childId)
    showSuccessToast(t('learning.dispatchSuccess'))
    router.push({ name: 'BabyLearning' })
  } catch {
    showFailToast(t('toast.operationFailed'))
  } finally {
    assigningId.value = null
  }
}

watch([selectedGrade, selectedSemester, selectedSubject], () => {
  expandedId.value = null
  fetchPaths()
})

onMounted(() => {
  fetchPaths()
})
</script>

<style scoped>
.preset-paths-page {
  min-height: 100vh;
  padding-bottom: 20px;
}

.chip-row {
  display: flex;
  gap: 8px;
  padding: 12px 16px 0;
  overflow-x: auto;
  scrollbar-width: none;
}

.chip-row::-webkit-scrollbar {
  display: none;
}

.chip {
  flex-shrink: 0;
  padding: 6px 14px;
  border-radius: 16px;
  font-size: 13px;
  background: var(--card-bg);
  color: var(--text-secondary);
  border: 1px solid var(--van-border-color);
  cursor: pointer;
  user-select: none;
  transition: all 0.2s;
}

.chip--active {
  background: var(--van-primary-color);
  color: #fff;
  border-color: var(--van-primary-color);
}

.content {
  padding: 16px;
}

.path-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.path-card {
  background: var(--card-bg);
  border-radius: 12px;
  padding: 14px;
  transition: all 0.2s;
}

.path-card--expanded {
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.08);
}

.path-card__header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  cursor: pointer;
  gap: 8px;
}

.path-card__info {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.path-card__name {
  font-size: 15px;
  font-weight: 500;
  color: var(--text-primary);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.path-card__expanded {
  margin-top: 12px;
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.path-card__desc {
  font-size: 13px;
  color: var(--text-secondary);
  margin: 0;
  line-height: 1.5;
}

.path-card__progress {
  padding: 0 4px;
}
</style>
