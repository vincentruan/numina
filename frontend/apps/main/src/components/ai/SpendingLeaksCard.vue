<template>
  <div class="spending-leaks-card">
    <div v-if="loading" class="loading-state">
      <van-loading size="32" type="spinner" />
    </div>

    <div v-else-if="!leaks.length" class="empty-state">
      <van-empty image="success" description="暂无资金泄漏" />
      <div class="actions">
        <van-button plain block :loading="refreshing" @click="onRefresh">重新分析</van-button>
      </div>
    </div>

    <template v-else>
      <div class="summary-bar">
        <span>共 {{ leaks.length }} 条泄漏</span>
        <van-button size="mini" plain :loading="refreshing" @click="onRefresh">重新分析</van-button>
      </div>

      <van-swipe-cell v-for="leak in leaks" :key="leak.id" class="leak-item">
        <div class="leak-card" :class="`severity-${leak.severity}`">
          <div class="leak-header">
            <span class="leak-type-badge">{{ leakTypeLabel(leak.leak_type) }}</span>
            <van-tag :type="severityTagType(leak.severity)">{{ severityLabel(leak.severity) }}</van-tag>
          </div>
          <div class="leak-name">{{ leak.asset_name }}</div>
          <div v-if="leak.estimated_annual_waste != null" class="leak-meta">
            预计年损耗：¥{{ leak.estimated_annual_waste.toFixed(0) }}
          </div>
          <p v-if="leak.suggestion" class="leak-suggestion">{{ leak.suggestion }}</p>
        </div>
        <template #right>
          <van-button square type="warning" text="忽略" class="dismiss-btn" @click="onDismiss(leak.id)" />
        </template>
      </van-swipe-cell>
    </template>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { showToast } from 'vant'
import { useI18n } from 'vue-i18n'
import { getSpendingLeaks, refreshSpendingLeaks, dismissSpendingLeak } from '@/api/aiSpendingLeaks'
import type { SpendingLeakItem } from '@/api/aiSpendingLeaks'

const { t } = useI18n()

const loading = ref(false)
const refreshing = ref(false)
const leaks = ref<SpendingLeakItem[]>([])

const LEAK_TYPE_LABELS: Record<string, string> = {
  high_idle_cost: '高闲置成本',
  redundant: '冗余持有',
  high_maintenance: '高维护负担',
}

function leakTypeLabel(type: string) {
  return LEAK_TYPE_LABELS[type] ?? type
}

function severityTagType(severity: string): 'danger' | 'warning' | 'primary' {
  if (severity === 'high') return 'danger'
  if (severity === 'medium') return 'warning'
  return 'primary'
}

function severityLabel(severity: string) {
  if (severity === 'high') return '高'
  if (severity === 'medium') return '中'
  return '低'
}

async function loadLeaks() {
  loading.value = true
  try {
    leaks.value = await getSpendingLeaks()
  } catch {
    showToast(t('toast.loadFailed'))
  } finally {
    loading.value = false
  }
}

async function onRefresh() {
  refreshing.value = true
  try {
    await refreshSpendingLeaks()
    await loadLeaks()
    showToast(t('toast.aiScanComplete'))
  } catch {
    showToast(t('toast.aiScanFailed'))
  } finally {
    refreshing.value = false
  }
}

async function onDismiss(id: number) {
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
</style>
