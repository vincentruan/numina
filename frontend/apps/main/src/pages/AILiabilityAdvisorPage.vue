<template>
  <div class="ai-liability-page">
    <PageHeader :title="t('aiLiability.title')" />

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
          v-model="isConsoleOpen"
          :status="taskStatus"
          :phase="taskPhase"
          :think-content="taskThinkContent"
          :think-done="taskThinkDone"
          :think-seconds="taskThinkSeconds"
          :answer-content="taskAnswerContent"
          :queue-position="taskQueuePosition"
          :elapsed-seconds="taskElapsed"
        />
        <van-button
          v-if="taskStatus !== 'running' && taskStatus !== 'queued'"
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
        <div class="empty-illustration" aria-hidden="true">
          <svg width="120" height="120" viewBox="0 0 120 120" fill="none" xmlns="http://www.w3.org/2000/svg">
            <circle cx="60" cy="60" r="56" fill="var(--empty-bg-outer)" />
            <circle cx="60" cy="60" r="42" fill="var(--empty-bg-inner)" />
            <!-- Shield body -->
            <path d="M60 28l-22 9v16c0 13 9.5 25 22 28 12.5-3 22-15 22-28V37L60 28z" fill="var(--empty-icon-fill)" />
            <!-- Checkmark -->
            <path d="M50 60l7 7 13-14" stroke="#fff" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"/>
            <!-- Sparkle top-right -->
            <circle cx="86" cy="34" r="10" fill="var(--empty-badge-bg)" />
            <path d="M86 29v10M81 34h10" stroke="#fff" stroke-width="2" stroke-linecap="round"/>
          </svg>
        </div>
        <p class="empty-title">{{ t('liability.noLiabilityTitle') }}</p>
        <p class="empty-desc">{{ t('liability.noLiabilityDesc') }}</p>
        <div class="actions">
          <TaskConsole
            v-model="isConsoleOpen"
            :status="taskStatus"
          :phase="taskPhase"
          :think-content="taskThinkContent"
          :think-done="taskThinkDone"
          :think-seconds="taskThinkSeconds"
          :answer-content="taskAnswerContent"
            :queue-position="taskQueuePosition"
            :elapsed-seconds="taskElapsed"
          />
          <van-button
            v-if="taskStatus !== 'running' && taskStatus !== 'queued'"
            plain
            block
            @click="onAnalyze"
          >{{ t('liability.reanalyzeBtn') }}</van-button>
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
        <!-- Summary bar with reanalyze/cancel -->
        <div class="summary-bar">
          <span>{{ t('aiLiability.title') }}</span>
          <van-button
            v-if="taskStatus !== 'running' && taskStatus !== 'queued'"
            size="mini"
            plain
            @click="onAnalyze"
          >
            {{ t('liability.reanalyzeBtn') }}
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

        <!-- Summary -->
        <div class="summary-card">
          <div class="summary-row">
            <span class="label">{{ t('aiLiability.totalRemaining') }}</span>
            <span class="value">{{ formatMoney(data.total_remaining) }}</span>
          </div>
          <div class="summary-row">
            <span class="label">{{ t('aiLiability.monthlyPayment') }}</span>
            <span class="value">{{ formatMoney(data.total_monthly_payment) }}</span>
          </div>
          <div class="summary-row">
            <span class="label">负债笔数</span>
            <span class="value">{{ t('aiLiability.liabilityCount', { count: data.liability_count }) }}</span>
          </div>
        </div>

        <!-- AI Narrative -->
        <div v-if="data.narrative" class="narrative-card">
          <div class="narrative-label">AI 建议</div>
          <p class="narrative-text">{{ data.narrative }}</p>
        </div>

        <!-- Strategy Tabs -->
        <van-tabs v-model:active="activeTab" class="strategy-tabs" :aria-label="t('aiLiability.strategyTabsAria')">
          <van-tab
            v-for="strategy in data.strategies"
            :key="strategy.strategy"
            :title="strategyShortName(strategy.strategy)"
          >
            <div class="strategy-content">
              <div class="strategy-name">{{ strategy.strategy_name }}</div>
              <div v-if="strategy.estimated_interest_saved > 0" class="savings-hint">
                {{ t('aiLiability.savingsHint', { amount: strategy.estimated_interest_saved.toLocaleString() }) }}
              </div>
              <div class="priority-hint">
                {{ t('aiLiability.priorityHint', { debt: strategy.priority_debt }) }}
              </div>
              <div v-if="data.recommended_strategy === strategy.strategy" class="recommended-badge">
                <van-icon name="success" aria-hidden="true" /> {{ t('aiLiability.recommendedBadge') }}
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
            v-model="isConsoleOpen"
            :status="taskStatus"
          :phase="taskPhase"
          :think-content="taskThinkContent"
          :think-done="taskThinkDone"
          :think-seconds="taskThinkSeconds"
          :answer-content="taskAnswerContent"
            :queue-position="taskQueuePosition"
            :elapsed-seconds="taskElapsed"
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
  avalanche: 'strategyAvalanche',
  snowball: 'strategySnowball',
  hybrid: 'strategyHybrid',
}

function strategyShortName(s: string) {
  const key = STRATEGY_SHORT[s]
  return key ? t(`aiLiability.${key}`) : s
}

function formatMoney(val: number | null | undefined) {
  if (val == null) return '-'
  return new Intl.NumberFormat('zh-CN', { style: 'currency', currency: 'CNY', maximumFractionDigits: 0 }).format(val)
}

async function loadData(): Promise<boolean> {
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
    return true
  } catch {
    // no data yet, show empty state
    return false
  } finally {
    loading.value = false
  }
}

async function onAnalyzeComplete() {
  const ok = await loadData()
  if (ok) showToast(t('toast.aiAnalyzeComplete'))
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
} = useAITask('liability', '/ai/liability-advice/events', onAnalyzeComplete)

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
.empty-state {
  padding: 40px 16px;
  min-height: 240px;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
}
.no-liability {
  padding: 48px 24px 32px;
  display: flex;
  flex-direction: column;
  align-items: center;
  text-align: center;
  --empty-bg-outer: rgba(76, 175, 80, 0.08);
  --empty-bg-inner: rgba(76, 175, 80, 0.12);
  --empty-icon-fill: #4caf50;
  --empty-badge-bg: var(--van-primary-color, #1989fa);
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
