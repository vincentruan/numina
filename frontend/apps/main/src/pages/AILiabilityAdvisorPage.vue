<template>
  <div class="ai-liability-page">
    <PageHeader title="负债优化顾问" />

    <div v-if="loading && !data" class="loading-state">
      <van-loading size="32" type="spinner" />
    </div>

    <div v-else-if="!data" class="empty-state">
      <van-empty :description="t('liability.analyzePrompt')">
        <template #image>
          <svg width="80" height="80" viewBox="0 0 80 80" fill="none" xmlns="http://www.w3.org/2000/svg" aria-hidden="true">
            <rect x="8" y="8" width="64" height="64" rx="8" fill="rgba(189,187,255,0.10)" />
            <rect x="20" y="20" width="40" height="40" rx="4" stroke="#bdbbff" stroke-width="1.5" fill="rgba(189,187,255,0.08)" />
            <path d="M32 44l6-14 6 14" stroke="#bdbbff" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" fill="none"/>
            <path d="M34.5 39.5h7" stroke="#bdbbff" stroke-width="2" stroke-linecap="round"/>
            <rect x="44" y="26" width="12" height="12" rx="4" stroke="#bdbbff" stroke-width="1.5" fill="none"/>
            <path d="M50 29v6M47 32h6" stroke="#bdbbff" stroke-width="1.5" stroke-linecap="round"/>
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
        <van-button
          v-if="taskStatus !== 'running'"
          type="primary"
          block
          @click="onAnalyze"
        >{{ t('liability.startAnalyze') }}</van-button>
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
      <!-- No liabilities -->
      <div v-if="!data.has_liabilities" class="no-liability">
        <van-empty :description="t('liability.noLiabilityDesc')">
          <template #image>
            <svg width="80" height="80" viewBox="0 0 80 80" fill="none" xmlns="http://www.w3.org/2000/svg" aria-hidden="true">
              <rect x="8" y="8" width="64" height="64" rx="8" fill="rgba(189,187,255,0.10)" />
              <rect x="20" y="20" width="40" height="40" rx="4" stroke="#bdbbff" stroke-width="1.5" fill="rgba(189,187,255,0.08)" />
              <path d="M30 40l7 7 13-14" stroke="#bdbbff" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"/>
            </svg>
          </template>
        </van-empty>
      </div>

      <template v-else>
        <!-- Summary bar with reanalyze/cancel -->
        <div class="summary-bar">
          <span>{{ t('liability.title') }}</span>
          <van-button
            v-if="taskStatus !== 'running'"
            size="mini"
            plain
            @click="onAnalyze"
          >
            重新分析
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
            终止
          </van-button>
        </div>

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
          <TaskConsole
            :status="taskStatus"
            :chunks="taskChunks"
            :elapsed-seconds="taskElapsed"
            v-model="isConsoleOpen"
          />
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

async function onAnalyzeComplete() {
  await loadData()
  showToast(t('toast.aiAnalyzeComplete'))
}

const {
  status: taskStatus,
  chunks: taskChunks,
  elapsedSeconds: taskElapsed,
  isConsoleOpen,
  startStream,
  cancelTask,
} = useAITask('liability', '/ai/liability-advice/stream', onAnalyzeComplete)

async function onAnalyze() {
  await startStream()
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
.summary-bar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 10px 16px;
  font-size: 13px;
  color: var(--text-secondary);
}
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
