<template>
  <div class="ai-liability-page">
    <PageHeader title="负债优化顾问" />

    <div v-if="loading" class="loading-state">
      <van-loading size="32" type="spinner" />
    </div>

    <div v-else-if="!data" class="empty-state">
      <van-empty description="点击分析负债状况">
        <template #image>
          <svg width="80" height="80" viewBox="0 0 80 80" fill="none" xmlns="http://www.w3.org/2000/svg" aria-hidden="true">
            <circle cx="40" cy="40" r="36" fill="rgba(99,102,241,0.08)" />
            <circle cx="40" cy="40" r="28" fill="rgba(99,102,241,0.10)" />
            <path d="M28 50l8-20 8 20" stroke="#6366f1" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" fill="none"/>
            <path d="M31 44h10" stroke="#6366f1" stroke-width="2" stroke-linecap="round"/>
            <circle cx="52" cy="34" r="8" stroke="#6366f1" stroke-width="2.5" fill="none"/>
            <path d="M52 31v6M49 34h6" stroke="#6366f1" stroke-width="2" stroke-linecap="round"/>
          </svg>
        </template>
      </van-empty>
      <div class="actions">
        <TaskConsole
          :status="taskStatus"
          :chunks="taskChunks"
          :elapsed-seconds="taskElapsed"
          v-model="isConsoleOpen"
        />
        <van-button type="primary" block :loading="taskStatus === 'running'" @click="onAnalyze">开始分析</van-button>
      </div>
    </div>

    <template v-else>
      <!-- No liabilities -->
      <div v-if="!data.has_liabilities" class="no-liability">
        <van-empty description="当前无活跃负债，财务状况良好">
          <template #image>
            <svg width="80" height="80" viewBox="0 0 80 80" fill="none" xmlns="http://www.w3.org/2000/svg" aria-hidden="true">
              <circle cx="40" cy="40" r="36" fill="rgba(74,222,128,0.08)" />
              <circle cx="40" cy="40" r="28" fill="rgba(74,222,128,0.10)" />
              <circle cx="40" cy="40" r="14" stroke="#4ade80" stroke-width="2.5" fill="none"/>
              <path d="M33 40l5 5 9-10" stroke="#4ade80" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"/>
            </svg>
          </template>
        </van-empty>
      </div>

      <template v-else>
        <!-- Summary -->
        <div class="summary-card">
          <div class="summary-row">
            <span class="label">负债总额</span>
            <span class="value">{{ formatMoney(data.total_remaining) }}</span>
          </div>
          <div class="summary-row">
            <span class="label">月还款额</span>
            <span class="value">{{ formatMoney(data.total_monthly_payment) }}</span>
          </div>
          <div class="summary-row">
            <span class="label">负债笔数</span>
            <span class="value">{{ data.liability_count }} 笔</span>
          </div>
        </div>

        <!-- AI Narrative -->
        <div v-if="data.narrative" class="narrative-card">
          <div class="narrative-label">AI 建议</div>
          <p class="narrative-text">{{ data.narrative }}</p>
        </div>

        <!-- Strategy Tabs -->
        <van-tabs v-model:active="activeTab" class="strategy-tabs" aria-label="还款策略">
          <van-tab
            v-for="strategy in data.strategies"
            :key="strategy.strategy"
            :title="strategyShortName(strategy.strategy)"
          >
            <div class="strategy-content">
              <div class="strategy-name">{{ strategy.strategy_name }}</div>
              <div v-if="strategy.estimated_interest_saved > 0" class="savings-hint">
                预计节省利息：¥{{ strategy.estimated_interest_saved.toLocaleString() }}
              </div>
              <div class="priority-hint">
                优先还款：<strong>{{ strategy.priority_debt }}</strong>
              </div>
              <div v-if="data.recommended_strategy === strategy.strategy" class="recommended-badge">
                <van-icon name="success" aria-hidden="true" /> 推荐方案
              </div>
              <div class="order-list">
                <div
                  v-for="(item, idx) in strategy.order"
                  :key="item.id"
                  class="order-item"
                >
                  <span class="order-num">{{ (idx as number) + 1 }}</span>
                  <span class="order-name">{{ item.category }}</span>
                  <span v-if="item.rate" class="order-rate">{{ item.rate }}%</span>
                </div>
              </div>
            </div>
          </van-tab>
        </van-tabs>

        <div class="reanalyze">
          <van-button plain block :loading="taskStatus === 'running'" @click="onAnalyze">重新分析</van-button>
        </div>
      </template>
    </template>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { showToast } from 'vant'
import { useI18n } from 'vue-i18n'
import { getLiabilityAdvice } from '@/api/ai'
import { useAITask } from '@/composables/useAITask'
import PageHeader from '@/components/common/PageHeader.vue'
import TaskConsole from '@/components/ai/TaskConsole.vue'

const { t } = useI18n()

const {
  status: taskStatus,
  chunks: taskChunks,
  elapsedSeconds: taskElapsed,
  isConsoleOpen,
  startStream,
} = useAITask('liability', '/ai/liability-advice/stream')

const loading = ref(false)
const data = ref<Record<string, unknown> | null>(null)
const activeTab = ref(0)

const STRATEGY_SHORT: Record<string, string> = {
  avalanche: '雪崩法',
  snowball: '滚雪球',
  hybrid: '混合法',
}

function strategyShortName(s: string) {
  return STRATEGY_SHORT[s] ?? s
}

function formatMoney(val: number | null | undefined) {
  if (val == null) return '-'
  return new Intl.NumberFormat('zh-CN', { style: 'currency', currency: 'CNY', maximumFractionDigits: 0 }).format(val)
}

async function loadData() {
  loading.value = true
  try {
    const res = await getLiabilityAdvice()
    data.value = res.data
    if (data.value?.recommended_strategy) {
      const idx = (data.value.strategies as { strategy: string }[] ?? []).findIndex(
        (s) => s.strategy === data.value?.recommended_strategy,
      )
      if (idx >= 0) activeTab.value = idx
    }
  } catch {
    // no data yet, show empty state
  } finally {
    loading.value = false
  }
}

async function onAnalyze() {
  await startStream()
  // Reload advice data after streaming completes
  try {
    const res = await getLiabilityAdvice()
    data.value = res.data
    if (data.value?.recommended_strategy) {
      const idx = (data.value.strategies as { strategy: string }[] ?? []).findIndex(
        (s) => s.strategy === data.value?.recommended_strategy,
      )
      if (idx >= 0) activeTab.value = idx
    }
  } catch {
    showToast(t('toast.aiAnalyzeFailed'))
  }
}

onMounted(loadData)
</script>

<style scoped>
.ai-liability-page {
  background: var(--bg-secondary);
  min-height: 100vh;
  padding-bottom: 24px;
}
.loading-state { display: flex; justify-content: center; padding: 60px; }
.empty-state, .no-liability { padding: 40px 16px; min-height: 240px; display: flex; flex-direction: column; align-items: center; justify-content: center; }
.actions { padding: 12px 16px 0; width: 100%; }
.summary-card {
  background: var(--bg-primary);
  margin: 12px 16px;
  border-radius: 12px;
  padding: 16px;
}
.summary-row {
  display: flex;
  justify-content: space-between;
  padding: 6px 0;
  font-size: 14px;
}
.label { color: var(--text-secondary); }
.value { font-weight: 600; color: var(--text-primary); }
.narrative-card {
  background: var(--bg-primary);
  margin: 0 16px 12px;
  border-radius: 12px;
  padding: 14px 16px;
}
.narrative-label {
  font-size: 12px;
  color: var(--van-primary-color);
  font-weight: 600;
  margin-bottom: 6px;
}
.narrative-text {
  font-size: 13px;
  color: var(--text-secondary);
  line-height: 1.6;
  margin: 0;
}
.strategy-tabs { margin: 0 16px; }
.strategy-content { padding: 16px 0; }
.strategy-name { font-size: 15px; font-weight: 600; color: var(--text-primary); margin-bottom: 8px; }
.savings-hint { font-size: 13px; color: #4caf50; margin-bottom: 4px; }
.priority-hint { font-size: 13px; color: var(--text-secondary); margin-bottom: 8px; }
.recommended-badge {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  font-size: 12px;
  padding: 2px 10px;
  border-radius: 10px;
  background: rgba(99, 102, 241, 0.15);
  color: var(--van-primary-color);
  margin-bottom: 12px;
}
.order-list { display: flex; flex-direction: column; gap: 6px; }
.order-item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 8px 12px;
  background: var(--bg-secondary);
  border-radius: 8px;
  font-size: 13px;
}
.order-num {
  width: 22px; height: 22px; border-radius: 50%;
  background: var(--van-primary-color); color: #fff;
  display: flex; align-items: center; justify-content: center;
  font-size: 12px; font-weight: 700; flex-shrink: 0;
}
.order-name { flex: 1; color: var(--text-primary); }
.order-rate { color: #f44336; font-size: 12px; }
.reanalyze { padding: 16px; }
</style>
