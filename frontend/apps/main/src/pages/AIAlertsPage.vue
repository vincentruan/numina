<template>
  <div class="ai-alerts-page">
    <PageHeader :title="t('aiAlerts.title')" />

    <div v-if="loading" class="loading-state">
      <van-loading size="32" type="spinner" />
    </div>

    <div v-else-if="!alerts.length" class="empty-state">
      <div class="empty-illustration" aria-hidden="true">
        <svg width="120" height="120" viewBox="0 0 120 120" fill="none" xmlns="http://www.w3.org/2000/svg">
          <circle cx="60" cy="60" r="56" fill="var(--empty-bg-outer)" />
          <circle cx="60" cy="60" r="42" fill="var(--empty-bg-inner)" />
          <!-- Bell body -->
          <path d="M60 28c-11 0-20 9-20 20v14l-4 6h48l-4-6V48c0-11-9-20-20-20z" fill="var(--empty-icon-fill)" />
          <!-- Bell clapper -->
          <path d="M55 68a5 5 0 0010 0" fill="var(--empty-icon-fill)" />
          <!-- Exclamation mark -->
          <rect x="57.5" y="38" width="5" height="16" rx="2.5" fill="var(--empty-icon-accent)" />
          <circle cx="60" cy="60" r="3" fill="var(--empty-icon-accent)" />
          <!-- Checkmark badge -->
          <circle cx="84" cy="36" r="10" fill="var(--empty-badge-bg)" />
          <path d="M79 36l3.5 3.5 6-6" stroke="#fff" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
        </svg>
      </div>
      <p class="empty-title">{{ t('aiTask.emptyAlerts') }}</p>
      <p class="empty-desc">{{ t('aiTask.emptyAlertsDesc') }}</p>
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
          :error-code="taskErrorCode"
          @retry="onRefresh"
        />
        <van-button
          v-if="taskStatus !== 'running' && taskStatus !== 'queued'"
          type="primary"
          block
          @click="onRefresh"
        >
          {{ t('aiTask.emptyAlertsBtn') }}
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
        <span>{{ t('aiTask.alertsSummary', { count: alerts.length }) }}</span>
        <van-button
          v-if="taskStatus !== 'running' && taskStatus !== 'queued'"
          size="mini"
          plain
          @click="onRefresh"
        >
          {{ t('aiTask.rescanAlerts') }}
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

      <van-swipe-cell v-for="alert in alerts" :key="alert.id" class="alert-item">
        <div class="alert-card" :class="`severity-${alert.severity}`">
          <div class="alert-header">
            <span class="alert-type-badge">{{ alertTypeLabel(alert.alert_type) }}</span>
          <span class="severity-dot" :class="`dot-${alert.severity}`" :aria-label="({ high: t('aiAlerts.severityHigh'), medium: t('aiAlerts.severityMedium'), low: t('aiAlerts.severityLow') } as Record<string, string>)[alert.severity]" role="img" />
          </div>
          <div class="alert-name">{{ alert.asset_name }}</div>
          <div v-if="alert.remaining_life_days != null" class="alert-meta">
            {{ t('aiAlerts.remainingLife', { days: alert.remaining_life_days }) }}
          </div>
          <div v-if="alert.daily_cost" class="alert-meta">
            {{ t('aiAlerts.dailyCost', { cost: alert.daily_cost.toFixed(1) }) }}
          </div>
          <p v-if="alert.suggestion" class="alert-suggestion">{{ alert.suggestion }}</p>
        </div>
        <template #right>
          <van-button square type="warning" :text="t('aiAlerts.dismiss')" class="dismiss-btn" @click="onDismiss(alert.id)" />
        </template>
      </van-swipe-cell>
    </template>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { showToast } from 'vant'
import { useI18n } from 'vue-i18n'
import { getAssetAlerts, dismissAssetAlert } from '@/api/ai'
import { useAITask } from '@/composables/useAITask'
import PageHeader from '@/components/common/PageHeader.vue'
import TaskConsole from '@/components/ai/TaskConsole.vue'

interface Alert {
  id: number
  alert_type: string
  asset_name: string
  message: string
  [key: string]: unknown
}

const { t } = useI18n()

const loading = ref(false)
const alerts = ref<Alert[]>([])

const ALERT_TYPE_LABELS: Record<string, string> = {
  aging: t('aiAlerts.agingType'),
  high_maintenance: t('aiAlerts.highMaintenanceType'),
  idle_cost: t('aiAlerts.idleCostType'),
}

function alertTypeLabel(type: string) {
  return ALERT_TYPE_LABELS[type] ?? type
}

async function loadAlerts() {
  loading.value = true
  try {
    const res = await getAssetAlerts()
    alerts.value = res.data
  } catch {
    showToast(t('toast.loadFailed'))
  } finally {
    loading.value = false
  }
}

async function onScanComplete() {
  await loadAlerts()
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
  errorCode: taskErrorCode,
  startStream,
  cancelTask,
} = useAITask('alerts', '/ai/asset-alerts/refresh/events', onScanComplete)

async function onRefresh() {
  await startStream()
}

async function onDismiss(id: string) {
  try {
    await dismissAssetAlert(id)
    alerts.value = alerts.value.filter(a => a.id !== id)
  } catch {
    showToast(t('toast.operationFailed'))
  }
}

onMounted(loadAlerts)
</script>

<style scoped>
.ai-alerts-page {
  background: var(--bg-secondary);
  min-height: 100vh;
  padding-bottom: 24px;
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
  --empty-icon-stroke: var(--van-primary-color, #1989fa);
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
.alert-item { margin: 8px 16px; border-radius: 12px; overflow: hidden; }
.alert-card {
  background: var(--bg-primary);
  padding: 14px 16px;
  border-left: 4px solid transparent;
}
.severity-high { border-left-color: #f44336; }
.severity-medium { border-left-color: #ff9800; }
.severity-low { border-left-color: #2196f3; }
.alert-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 6px;
}
.alert-type-badge {
  font-size: 11px;
  padding: 2px 8px;
  border-radius: 10px;
  background: var(--bg-secondary);
  color: var(--text-secondary);
}
.severity-dot {
  width: 8px; height: 8px; border-radius: 50%;
}
.dot-high { background: #f44336; }
.dot-medium { background: #ff9800; }
.dot-low { background: #2196f3; }
.alert-name { font-size: 15px; font-weight: 600; color: var(--text-primary); margin-bottom: 4px; }
.alert-meta { font-size: 12px; color: var(--text-secondary); }
.alert-suggestion { font-size: 13px; color: var(--text-secondary); margin: 8px 0 0; line-height: 1.5; }
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
