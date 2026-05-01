<template>
  <div class="ai-alerts-page">
    <PageHeader title="资产老化预警" />

    <div v-if="loading" class="loading-state">
      <van-loading size="32" type="spinner" />
    </div>

    <div v-else-if="!alerts.length" class="empty-state">
      <van-empty image="success" description="暂无资产预警" />
      <div class="actions">
        <van-button plain block :loading="refreshing" @click="onRefresh">扫描资产状态</van-button>
      </div>
    </div>

    <template v-else>
      <div class="summary-bar">
        <span>共 {{ alerts.length }} 条预警</span>
        <van-button size="mini" plain :loading="refreshing" @click="onRefresh">重新扫描</van-button>
      </div>

      <van-swipe-cell v-for="alert in alerts" :key="alert.id" class="alert-item">
        <div class="alert-card" :class="`severity-${alert.severity}`">
          <div class="alert-header">
            <span class="alert-type-badge">{{ alertTypeLabel(alert.alert_type) }}</span>
          <span class="severity-dot" :class="`dot-${alert.severity}`" :aria-label="({ high: '高严重度', medium: '中严重度', low: '低严重度' } as Record<string, string>)[alert.severity]" role="img" />
          </div>
          <div class="alert-name">{{ alert.asset_name }}</div>
          <div v-if="alert.remaining_life_days != null" class="alert-meta">
            剩余寿命：{{ alert.remaining_life_days }} 天
          </div>
          <div v-if="alert.daily_cost" class="alert-meta">
            日均成本：¥{{ alert.daily_cost.toFixed(1) }}/天
          </div>
          <p v-if="alert.suggestion" class="alert-suggestion">{{ alert.suggestion }}</p>
        </div>
        <template #right>
          <van-button square type="warning" text="忽略" class="dismiss-btn" @click="onDismiss(alert.id)" />
        </template>
      </van-swipe-cell>
    </template>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { showToast } from 'vant'
import { useI18n } from 'vue-i18n'
import { getAssetAlerts, refreshAssetAlerts, dismissAssetAlert } from '@/api/ai'
import PageHeader from '@/components/common/PageHeader.vue'

interface Alert {
  id: number
  alert_type: string
  asset_name: string
  message: string
  [key: string]: unknown
}

const { t } = useI18n()

const loading = ref(false)
const refreshing = ref(false)
const alerts = ref<Alert[]>([])

const ALERT_TYPE_LABELS: Record<string, string> = {
  aging: '即将到期',
  high_maintenance: '维护成本高',
  idle_cost: '闲置损耗',
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

async function onRefresh() {
  refreshing.value = true
  try {
    await refreshAssetAlerts()
    await loadAlerts()
    showToast(t('toast.aiScanComplete'))
  } catch {
    showToast(t('toast.aiScanFailed'))
  } finally {
    refreshing.value = false
  }
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
.empty-state { padding: 40px 16px; }
.actions { padding: 0 16px; }
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
</style>
