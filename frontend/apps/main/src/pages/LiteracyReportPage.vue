<template>
  <div class="literacy-report-page">
    <PageHeader :title="t('literacyReport.title')" />

    <!-- Loading skeleton -->
    <van-skeleton v-if="loading" :rows="6" animated class="page-skeleton" />

    <!-- Load failed -->
    <div v-else-if="loadError" class="failed-state">
      <EmptyState image="error" :description="t('literacyReport.loadFailed')" />
      <van-button plain type="primary" size="small" @click="reload">
        {{ t('literacyReport.retry') }}
      </van-button>
    </div>

    <!-- No children -->
    <div v-else-if="children.length === 0" class="empty-state">
      <EmptyState image="search" :description="t('literacyReport.noChildren')" />
    </div>

    <!-- Main content -->
    <template v-else>
      <ChildSelector
        :children="children"
        :selected-child-id="selectedChildId"
        @update:selected-child-id="onChildChange"
      />

      <!-- Week navigation -->
      <div v-if="history.length > 0" class="week-nav">
        <van-button
          size="small"
          icon="arrow-left"
          plain
          :disabled="!canGoPrev"
          @click="goPrev"
        />
        <span class="week-label">{{ currentWeekStart ? formatWeekStart(currentWeekStart) : '' }}</span>
        <van-button
          size="small"
          icon="arrow"
          plain
          :disabled="!canGoNext"
          @click="goNext"
        />
      </div>

      <!-- Report content -->
      <WeeklyReportCard v-if="report" :report="report" />

      <!-- No report for this week -->
      <div v-else class="empty-state">
        <EmptyState image="search" :description="t('literacyReport.noReport')" />
      </div>
    </template>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { showFailToast } from 'vant'
import PageHeader from '@/components/common/PageHeader.vue'
import EmptyState from '@/components/common/EmptyState.vue'
import ChildSelector from '@/components/literacy/ChildSelector.vue'
import WeeklyReportCard from '@/components/literacy/WeeklyReportCard.vue'
import {
  getReportChildren,
  getReport,
  getReportHistory,
} from '@/api/literacy'
import type { ReportChild, WeeklyReportResponse, ReportHistoryWeek } from '@/api/literacy'

defineOptions({ name: 'LiteracyReportPage' })

const { t } = useI18n()

const loading = ref(true)
const loadError = ref(false)
const children = ref<ReportChild[]>([])
const selectedChildId = ref('')
const report = ref<WeeklyReportResponse | null>(null)
const history = ref<ReportHistoryWeek[]>([])
const currentWeekStart = ref<string | null>(null)

const reportLoading = ref(false)

const currentHistoryIndex = computed(() => {
  if (!currentWeekStart.value) return -1
  return history.value.findIndex(w => w.week_start === currentWeekStart.value)
})

const canGoPrev = computed(() => {
  const idx = currentHistoryIndex.value
  return idx > 0 && history.value.slice(0, idx).some(w => w.has_report)
})

const canGoNext = computed(() => {
  const idx = currentHistoryIndex.value
  if (idx < 0 || idx >= history.value.length - 1) return false
  return history.value.slice(idx + 1).some(w => w.has_report)
})

async function init() {
  loading.value = true
  loadError.value = false
  try {
    const childListRes = await getReportChildren()
    children.value = childListRes.children
    if (children.value.length > 0) {
      selectedChildId.value = children.value[0].child_id
    }
  } catch {
    loadError.value = true
    showFailToast(t('literacyReport.loadFailed'))
  } finally {
    loading.value = false
  }
}

async function loadReport() {
  if (!selectedChildId.value) return
  reportLoading.value = true
  try {
    const [reportRes, historyRes] = await Promise.all([
      getReport(selectedChildId.value, currentWeekStart.value ?? undefined).catch(() => null),
      getReportHistory(selectedChildId.value),
    ])
    report.value = reportRes
    history.value = historyRes.weeks ?? []
    if (!currentWeekStart.value && history.value.length > 0) {
      const firstWithReport = history.value.find(w => w.has_report)
      currentWeekStart.value = firstWithReport?.week_start ?? history.value[0].week_start
      if (firstWithReport && !reportRes) {
        const retry = await getReport(selectedChildId.value, currentWeekStart.value).catch(() => null)
        report.value = retry
      }
    }
  } catch {
    report.value = null
    showFailToast(t('literacyReport.loadFailed'))
  } finally {
    reportLoading.value = false
  }
}

function onChildChange(childId: string) {
  selectedChildId.value = childId
  currentWeekStart.value = null
}

async function reload() {
  await init()
  if (children.value.length > 0) {
    await loadReport()
  }
}

function goPrev() {
  const idx = currentHistoryIndex.value
  for (let i = idx - 1; i >= 0; i--) {
    if (history.value[i]?.has_report) {
      currentWeekStart.value = history.value[i].week_start
      return
    }
  }
}

function goNext() {
  const idx = currentHistoryIndex.value
  for (let i = idx + 1; i < history.value.length; i++) {
    if (history.value[i]?.has_report) {
      currentWeekStart.value = history.value[i].week_start
      return
    }
  }
}

function formatWeekStart(weekStart: string): string {
  try {
    const d = new Date(weekStart)
    return `${d.getFullYear()}/${String(d.getMonth() + 1).padStart(2, '0')}/${String(d.getDate()).padStart(2, '0')}`
  } catch {
    return weekStart
  }
}

watch(selectedChildId, () => {
  if (skipNextWatch) { skipNextWatch = false; return }
  loadReport()
})

watch(currentWeekStart, (val, oldVal) => {
  if (val !== oldVal && val) {
    loadReport()
  }
})

let skipNextWatch = true

onMounted(() => {
  init().then(() => {
    if (children.value.length > 0) {
      loadReport()
    }
  })
})
</script>

<style scoped>
.literacy-report-page {
  min-height: 100vh;
  padding-bottom: 24px;
  background: var(--bg-primary);
}

.page-skeleton {
  padding: 16px;
}

.failed-state,
.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 48px 24px;
  gap: 12px;
}

.week-nav {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 16px;
  padding: 8px 16px 4px;
}

.week-label {
  font-size: 14px;
  color: var(--text-primary);
  font-weight: 500;
  min-width: 100px;
  text-align: center;
}
</style>
