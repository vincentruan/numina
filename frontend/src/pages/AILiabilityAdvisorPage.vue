<template>
  <div class="ai-liability-page">
    <PageHeader title="负债优化顾问" />

    <div v-if="loading" class="loading-state">
      <van-loading size="32" type="spinner" />
    </div>

    <div v-else-if="!data" class="empty-state">
      <van-empty image="search" description="点击分析负债状况" />
      <div class="actions">
        <van-button type="primary" block :loading="analyzing" @click="onAnalyze">开始分析</van-button>
      </div>
    </div>

    <template v-else>
      <!-- No liabilities -->
      <div v-if="!data.has_liabilities" class="no-liability">
        <van-empty image="success" description="当前无活跃负债，财务状况良好" />
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
        <van-tabs v-model:active="activeTab" class="strategy-tabs">
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
                ✓ 推荐方案
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
          <van-button plain block :loading="analyzing" @click="onAnalyze">重新分析</van-button>
        </div>
      </template>
    </template>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { showToast } from 'vant'
import { getLiabilityAdvice } from '@/api/ai'
import PageHeader from '@/components/common/PageHeader.vue'

const loading = ref(false)
const analyzing = ref(false)
const data = ref<any>(null)
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

async function onAnalyze() {
  analyzing.value = true
  try {
    const res = await getLiabilityAdvice()
    data.value = res.data
    // Default to recommended strategy tab
    if (data.value?.recommended_strategy) {
      const idx = (data.value.strategies ?? []).findIndex((s: any) => s.strategy === data.value.recommended_strategy)
      if (idx >= 0) activeTab.value = idx
    }
  } catch {
    showToast('分析失败，请检查 AI 配置')
  } finally {
    analyzing.value = false
  }
}

onMounted(async () => {
  loading.value = true
  try {
    const res = await getLiabilityAdvice()
    data.value = res.data
  } catch {
    // no data yet, show empty state
  } finally {
    loading.value = false
  }
})
</script>

<style scoped>
.ai-liability-page {
  background: var(--bg-secondary);
  min-height: 100vh;
  padding-bottom: 24px;
}
.loading-state { display: flex; justify-content: center; padding: 60px; }
.empty-state, .no-liability { padding: 40px 16px; }
.actions { padding: 0 16px; }
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
  display: inline-block;
  font-size: 11px;
  padding: 2px 10px;
  border-radius: 10px;
  background: color-mix(in srgb, var(--van-primary-color) 15%, transparent);
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
