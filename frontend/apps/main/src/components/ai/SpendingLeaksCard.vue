<template>
  <div class="spending-leaks-card">
    <div v-if="loading" class="loading-state">
      <van-loading size="32" type="spinner" />
    </div>

    <div v-else-if="!leaks.length" class="empty-state">
      <div class="empty-illustration" aria-hidden="true">
        <svg width="120" height="120" viewBox="0 0 120 120" fill="none" xmlns="http://www.w3.org/2000/svg">
          <circle cx="60" cy="60" r="56" fill="var(--empty-bg-outer)" />
          <circle cx="60" cy="60" r="42" fill="var(--empty-bg-inner)" />
          <!-- Wallet body -->
          <rect x="28" y="42" width="64" height="44" rx="6" fill="var(--empty-icon-fill)" />
          <!-- Wallet flap -->
          <path d="M28 54h64" stroke="rgba(255,255,255,0.3)" stroke-width="1.5"/>
          <!-- Coin slot -->
          <rect x="76" y="56" width="16" height="12" rx="6" fill="rgba(255,255,255,0.25)" />
          <circle cx="84" cy="62" r="3" fill="rgba(255,255,255,0.6)" />
          <!-- Drip / leak -->
          <path d="M52 86c0 0-4-6-4-10a4 4 0 018 0c0 4-4 10-4 10z" fill="var(--empty-badge-bg)" />
          <path d="M68 90c0 0-3-5-3-8a3 3 0 016 0c0 3-3 8-3 8z" fill="var(--empty-badge-bg)" opacity="0.7"/>
          <!-- Warning badge -->
          <circle cx="84" cy="36" r="10" fill="#ff9500" />
          <rect x="82.5" y="30" width="3" height="7" rx="1.5" fill="#fff" />
          <circle cx="84" cy="40" r="1.5" fill="#fff" />
        </svg>
      </div>
      <p class="empty-title">{{ t('aiTask.emptyLeaks') }}</p>
      <p class="empty-desc">{{ t('aiTask.emptyLeaksDesc') }}</p>
      <div class="actions">
        <TaskConsole
          v-model="isConsoleOpen"
          :status="taskStatus"
          :phase="taskPhase"
          :think-content="taskThinkContent"
          :think-done="taskThinkDone"
          :think-seconds="taskThinkSeconds"
          :answer-content="taskAnswerContent"
          :elapsed-seconds="taskElapsed"
          :queue-position="taskQueuePosition"
        />
        <van-button
          v-if="taskStatus !== 'running' && taskStatus !== 'queued'"
          type="primary"
          block
          @click="onRefresh"
        >
          {{ t('aiTask.emptyLeaksBtn') }}
        </van-button>
        <van-button
          v-else
          type="danger"
          block
          class="cancel-btn"
          @click="cancelTask"
        >
          <span class="stop-icon-wrapper">
            <van-icon name="stop-circle-o" class="stop-icon" />
            <van-loading size="14" type="spinner" class="spinning-ring" />
          </span>
          {{ t('aiTask.cancelBtn') }}
        </van-button>
      </div>
    </div>

    <template v-else>
      <div class="summary-bar">
        <span>{{ t('aiTask.leaksSummary', { count: leaks.length }) }}</span>
        <van-button
          v-if="taskStatus !== 'running' && taskStatus !== 'queued'"
          size="mini"
          plain
          @click="onRefresh"
        >
          {{ t('aiTask.rescanLeaks') }}
        </van-button>
        <van-button
          v-else
          size="mini"
          type="danger"
          class="cancel-btn-mini"
          @click="cancelTask"
        >
          <span class="stop-icon-wrapper-mini">
            <van-icon name="stop-circle-o" class="stop-icon-mini" />
            <van-loading size="12" type="spinner" class="spinning-ring-mini" />
          </span>
          {{ t('aiTask.cancelBtn') }}
        </van-button>
      </div>

      <van-swipe-cell v-for="leak in leaks" :key="leak.id" class="leak-item">
        <div class="leak-card" :class="`severity-${leak.severity}`">
          <div class="leak-header">
            <span class="leak-type-badge">{{ leakTypeLabel(leak.leak_type) }}</span>
            <van-tag :type="severityTagType(leak.severity)">{{ severityLabel(leak.severity) }}</van-tag>
          </div>
          <div class="leak-name">{{ leak.asset_name }}</div>
          <div v-if="leak.estimated_annual_waste != null" class="leak-meta">
            {{ t('spendingLeaks.estimatedWaste', { amount: leak.estimated_annual_waste.toFixed(0) }) }}
          </div>
          <p v-if="leak.suggestion" class="leak-suggestion">{{ leak.suggestion }}</p>
        </div>
        <template #right>
          <van-button square type="warning" :text="t('spendingLeaks.dismiss')" class="dismiss-btn" @click="onDismiss(leak.id)" />
        </template>
      </van-swipe-cell>
    </template>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { showToast } from 'vant'
import { useI18n } from 'vue-i18n'
import { getSpendingLeaks, dismissSpendingLeak } from '@/api/aiSpendingLeaks'
import type { SpendingLeakItem } from '@/api/aiSpendingLeaks'
import { useAITask } from '@/composables/useAITask'
import TaskConsole from '@/components/ai/TaskConsole.vue'

const { t } = useI18n()

async function onScanComplete() {
  await loadLeaks()
  showToast(t('toast.aiScanComplete'))
}

const {
  status: taskStatus,
  phase: taskPhase,
  thinkContent: taskThinkContent,
  thinkDone: taskThinkDone,
  thinkSeconds: taskThinkSeconds,
  answerContent: taskAnswerContent,
  elapsedSeconds: taskElapsed,
  isConsoleOpen,
  queuePosition: taskQueuePosition,
  startStream,
  cancelTask,
} = useAITask('spending_leak', '/ai/spending-leaks/refresh/events', onScanComplete)

const loading = ref(false)
const leaks = ref<SpendingLeakItem[]>([])

function leakTypeLabel(type: string) {
  const labels: Record<string, string> = {
    high_idle_cost: t('spendingLeaks.leakTypeHighIdleCost'),
    redundant: t('spendingLeaks.leakTypeRedundant'),
    high_maintenance: t('spendingLeaks.leakTypeHighMaintenance'),
  }
  return labels[type] ?? type
}

function severityTagType(severity: string): 'danger' | 'warning' | 'primary' {
  if (severity === 'high') return 'danger'
  if (severity === 'medium') return 'warning'
  return 'primary'
}

function severityLabel(severity: string) {
  if (severity === 'high') return t('spendingLeaks.severityHigh')
  if (severity === 'medium') return t('spendingLeaks.severityMedium')
  return t('spendingLeaks.severityLow')
}

async function loadLeaks() {
  loading.value = true
  try {
    const res = await getSpendingLeaks()
    leaks.value = res.data
  } catch {
    showToast(t('toast.loadFailed'))
  } finally {
    loading.value = false
  }
}

async function onRefresh() {
  await startStream()
}

async function onDismiss(id: string) {
  try {
    await dismissSpendingLeak(id)
    leaks.value = leaks.value.filter(l => l.id !== id)
  } catch {
    showToast(t('toast.operationFailed'))
  }
}

onMounted(loadLeaks)
</script>

<style scoped>
.spending-leaks-card {
  background: var(--bg-secondary);
}
.loading-state {
  display: flex;
  justify-content: center;
  padding: 60px;
}
.empty-state {
  padding: 48px 24px 32px;
  display: flex;
  flex-direction: column;
  align-items: center;
  text-align: center;
  --empty-bg-outer: rgba(25, 137, 250, 0.08);
  --empty-bg-inner: rgba(25, 137, 250, 0.12);
  --empty-icon-fill: var(--van-primary-color, #1989fa);
  --empty-badge-bg: #34c759;
}
.empty-illustration {
  margin-bottom: 20px;
  filter: drop-shadow(0 4px 12px rgba(1, 1, 32, 0.1));
}
.empty-title {
  font-size: 17px;
  font-weight: 600;
  color: var(--text-primary);
  margin: 0 0 8px;
  letter-spacing: -0.2px;
}
.empty-desc {
  font-size: 13px;
  color: var(--text-secondary);
  line-height: 1.6;
  margin: 0 0 24px;
  max-width: 260px;
}
.actions { padding: 0; width: 100%; }
.summary-bar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 10px 16px;
  font-size: 13px;
  color: var(--text-secondary);
}
.leak-item { margin: 8px 16px; border-radius: 12px; overflow: hidden; }
.leak-card {
  background: var(--bg-primary);
  padding: 14px 16px;
  border-left: 4px solid transparent;
}
.severity-high { border-left-color: #f44336; }
.severity-medium { border-left-color: #ff9800; }
.severity-low { border-left-color: #2196f3; }
.leak-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 6px;
}
.leak-type-badge {
  font-size: 11px;
  padding: 2px 8px;
  border-radius: 10px;
  background: var(--bg-secondary);
  color: var(--text-secondary);
}
.leak-name { font-size: 15px; font-weight: 600; color: var(--text-primary); margin-bottom: 4px; }
.leak-meta { font-size: 12px; color: var(--text-secondary); }
.leak-suggestion { font-size: 13px; color: var(--text-secondary); margin: 8px 0 0; line-height: 1.5; }
.dismiss-btn { height: 100%; }
.cancel-btn {
  position: relative;
}
.stop-icon-wrapper {
  position: relative;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  margin-right: 6px;
}
.stop-icon { font-size: 16px; }
.spinning-ring {
  position: absolute;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
  color: rgba(255, 255, 255, 0.6);
}
.cancel-btn-mini {
  position: relative;
}
.stop-icon-wrapper-mini {
  position: relative;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  margin-right: 4px;
}
.stop-icon-mini { font-size: 14px; }
.spinning-ring-mini {
  position: absolute;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
  color: rgba(244, 67, 54, 0.4);
}
</style>
