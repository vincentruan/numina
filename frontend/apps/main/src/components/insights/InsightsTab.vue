<template>
  <div class="insights-tab">
    <div v-if="loading" class="loading-state">
      <van-loading size="24px" />
    </div>
    <template v-else>
    <!-- S0 智能发现 -->
    <div v-if="smartDiscovery" class="section-card">
      <div class="section-header">
        <div class="section-title gradient-title">
          <span class="gradient-icon">✦</span>
          <span class="gradient-text">{{ t('insights.smartDiscovery.title') }}</span>
        </div>
      </div>
      <div class="insight-grid">
        <!-- 购入同比上月 -->
        <div class="insight-stat-card isc-card--yoy">
          <div class="isc-header">
            <div class="isc-icon">🛍️</div>
            <div class="isc-label">{{ t('insights.smartDiscovery.purchaseYoY') }}</div>
          </div>
          <div class="isc-value" :class="(smartDiscovery.purchase_yoy ?? 0) >= 0 ? 'up' : 'down'">
            {{ smartDiscovery.purchase_yoy !== null ? (smartDiscovery.purchase_yoy >= 0 ? '+' : '') + smartDiscovery.purchase_yoy + '%' : '--' }}
          </div>
          <div v-if="smartDiscovery.purchase_yoy !== null" class="isc-sub">
            <span class="isc-badge" :class="smartDiscovery.purchase_yoy >= 0 ? 'up' : 'down'">
              {{ smartDiscovery.purchase_yoy >= 0 ? '▲' : '▼' }} {{ Math.abs(smartDiscovery.purchase_yoy) }}%
            </span>
            <span class="isc-sub-meta">{{ t('insights.smartDiscovery.vsLastMonth') }}</span>
          </div>
          <div class="isc-bg-icon">🛍️</div>
        </div>

        <!-- 最高日均成本 -->
        <div class="insight-stat-card isc-card--high">
          <div class="isc-header">
            <div class="isc-icon">📈</div>
            <div class="isc-label">{{ t('insights.smartDiscovery.highestDailyCost') }}</div>
          </div>
          <div v-if="smartDiscovery.highest_daily_cost" class="isc-name">{{ smartDiscovery.highest_daily_cost.name }}</div>
          <div v-if="smartDiscovery.highest_daily_cost" class="isc-sub">
            <span class="isc-cost-val">{{ format(smartDiscovery.highest_daily_cost.cost) }} <span class="isc-cost-unit">/ {{ t('analyticsPage.perDay').replace('/', '') }}</span></span>
          </div>
          <div v-if="smartDiscovery.highest_daily_cost" class="isc-bg-icon">
            <SvgIcon v-if="smartDiscovery.highest_daily_cost.icon?.startsWith('icon-')" :name="getIconId(smartDiscovery.highest_daily_cost.icon)" class="icon-svg-bg" />
            <span v-else>{{ smartDiscovery.highest_daily_cost.icon }}</span>
          </div>
        </div>

        <!-- 最低日均成本 -->
        <div class="insight-stat-card isc-card--low">
          <div class="isc-header">
            <div class="isc-icon">📉</div>
            <div class="isc-label">{{ t('insights.smartDiscovery.lowestDailyCost') }}</div>
          </div>
          <div v-if="smartDiscovery.lowest_daily_cost" class="isc-name">{{ smartDiscovery.lowest_daily_cost.name }}</div>
          <div v-if="smartDiscovery.lowest_daily_cost" class="isc-sub">
            <span class="isc-cost-val green">{{ format(smartDiscovery.lowest_daily_cost.cost) }} <span class="isc-cost-unit">/ {{ t('analyticsPage.perDay').replace('/', '') }}</span></span>
          </div>
          <div v-if="smartDiscovery.lowest_daily_cost" class="isc-bg-icon">
            <SvgIcon v-if="smartDiscovery.lowest_daily_cost.icon?.startsWith('icon-')" :name="getIconId(smartDiscovery.lowest_daily_cost.icon)" class="icon-svg-bg" />
            <span v-else>{{ smartDiscovery.lowest_daily_cost.icon }}</span>
          </div>
        </div>

        <!-- 持有最久 -->
        <div class="insight-stat-card isc-card--long">
          <div class="isc-header">
            <div class="isc-icon">⏳</div>
            <div class="isc-label">{{ t('insights.smartDiscovery.longestHeld') }}</div>
          </div>
          <div v-if="smartDiscovery.longest_held" class="isc-name">{{ smartDiscovery.longest_held.name }}</div>
          <div v-if="smartDiscovery.longest_held" class="isc-sub">
            <span class="isc-days-val">{{ smartDiscovery.longest_held.days }} <span class="isc-days-unit">{{ t('insights.smartDiscovery.daysUnit') }}</span></span>
          </div>
          <div v-if="smartDiscovery.longest_held" class="isc-bg-icon">
            <SvgIcon v-if="smartDiscovery.longest_held.icon?.startsWith('icon-')" :name="getIconId(smartDiscovery.longest_held.icon)" class="icon-svg-bg" />
            <span v-else>{{ smartDiscovery.longest_held.icon }}</span>
          </div>
        </div>

        <!-- 占比最高分类 -->
        <div class="insight-stat-card isc-card--top">
          <div class="isc-header">
            <div class="isc-icon">🏆</div>
            <div class="isc-label">{{ t('insights.smartDiscovery.topCategoryByValue') }}</div>
          </div>
          <div v-if="smartDiscovery.top_category" class="isc-category-row">
            <div>
              <div class="isc-category-name">{{ smartDiscovery.top_category.name }}</div>
              <div class="isc-category-sub">{{ t('insights.smartDiscovery.byValue') }}</div>
            </div>
            <div class="isc-category-pct">{{ smartDiscovery.top_category.percentage }}%</div>
          </div>
          <div v-if="smartDiscovery.top_category" class="isc-bg-icon">
            <SvgIcon v-if="smartDiscovery.top_category.icon?.startsWith('icon-')" :name="getIconId(smartDiscovery.top_category.icon)" class="icon-svg-bg" />
            <span v-else>{{ smartDiscovery.top_category.icon }}</span>
          </div>
        </div>
      </div>
    </div>

    <!-- S1 日均成本排行 -->
    <div v-if="dailyCostItems.length > 0" class="section-card">
      <div class="section-header">
        <div class="section-title">
          <span class="title-icon">📉</span>{{ t('insights.dailyCostRank.title') }}
        </div>
        <div class="rank-sort-group">
          <div :class="['rank-sort-btn', { active: costRankOrder === 'highest' }]" role="button" tabindex="0" @click="costRankOrder = 'highest'" @keydown.enter="costRankOrder = 'highest'" @keydown.space.prevent="costRankOrder = 'highest'">{{ t('insights.dailyCostRank.highest') }}</div>
          <div :class="['rank-sort-btn', { active: costRankOrder === 'lowest' }]" role="button" tabindex="0" @click="costRankOrder = 'lowest'" @keydown.enter="costRankOrder = 'lowest'" @keydown.space.prevent="costRankOrder = 'lowest'">{{ t('insights.dailyCostRank.lowest') }}</div>
        </div>
      </div>
      <div class="rank-list">
        <div v-for="(item, idx) in dailyCostItems" :key="idx" class="rank-item">
          <div class="rank-img">
            <SvgIcon v-if="item.icon?.startsWith('icon-')" :name="getIconId(item.icon)" class="icon-svg" />
            <span v-else>{{ item.icon || '📦' }}</span>
          </div>
          <div class="rank-info">
            <div class="rank-name">{{ item.name }}</div>
            <div class="rank-service-row">
              <span class="rank-service-text">{{ t('insights.dailyCostRank.serviceDays', { days: item.days }) }}</span>
              <div class="rank-bar-track">
                <div class="rank-bar-fill" :style="{ width: item.pct + '%' }"></div>
              </div>
            </div>
          </div>
          <div class="rank-cost">
            <span class="rank-cost-val">{{ format(item.cost) }}</span>
            <span class="rank-cost-unit">{{ t('analyticsPage.perDay') }}</span>
          </div>
        </div>
      </div>
      <div class="view-all-row" role="button" tabindex="0" @click="showAllCostRank = true" @keydown.enter="showAllCostRank = true" @keydown.space.prevent="showAllCostRank = true">{{ t('insights.dailyCostRank.viewAll') }} <span class="view-all-arrow">›</span></div>
    </div>

    <!-- S1 查看全部弹出层 -->
    <van-popup v-model:show="showAllCostRank" position="bottom" round safe-area-inset-bottom>
      <div class="popup-header">
        <span class="popup-title">{{ t('insights.dailyCostRank.title') }}</span>
        <div class="popup-close" role="button" tabindex="0" :aria-label="t('common.close')" @click="showAllCostRank = false" @keydown.enter="showAllCostRank = false" @keydown.space.prevent="showAllCostRank = false">✕</div>
      </div>
      <div class="popup-rank-list">
        <div v-for="(item, idx) in allCostRankItems" :key="idx" class="rank-item">
          <div class="rank-img">
            <SvgIcon v-if="item.icon?.startsWith('icon-')" :name="getIconId(item.icon)" class="icon-svg" />
            <span v-else>{{ item.icon || '📦' }}</span>
          </div>
          <div class="rank-info">
            <div class="rank-name">{{ item.name }}</div>
            <div class="rank-service-row">
              <span class="rank-service-text">{{ t('insights.dailyCostRank.serviceDays', { days: item.days }) }}</span>
              <div class="rank-bar-track">
                <div class="rank-bar-fill" :style="{ width: item.pct + '%' }"></div>
              </div>
            </div>
          </div>
          <div class="rank-cost">
            <span class="rank-cost-val">{{ format(item.cost) }}</span>
            <span class="rank-cost-unit">{{ t('analyticsPage.perDay') }}</span>
          </div>
        </div>
      </div>
    </van-popup>

    <!-- S2 目标进度总览 -->
    <div v-if="goalProgress" class="section-card">
      <div class="section-header">
        <div class="section-title">
          <span class="title-icon">🎯</span>{{ t('insights.goalProgress.title') }}
        </div>
      </div>
      <div class="goal-chips">
        <div class="goal-chip selected-green">
          <div class="gc-val green">{{ goalProgress.summary.healthy }}</div>
          <div class="gc-label">{{ t('insights.goalProgress.healthy') }}</div>
        </div>
        <div class="goal-chip selected-orange">
          <div class="gc-val orange">{{ goalProgress.summary.near_end }}</div>
          <div class="gc-label">{{ t('insights.goalProgress.nearEnd') }}</div>
        </div>
        <div class="goal-chip selected-red">
          <div class="gc-val red">{{ goalProgress.summary.overdue }}</div>
          <div class="gc-label">{{ t('insights.goalProgress.overdue') }}</div>
        </div>
      </div>
      <div class="goal-list">
        <div v-for="(item, idx) in goalItems" :key="idx" class="goal-item">
          <div class="goal-row">
            <div class="goal-name">
              <div class="cat-dot" :style="{ background: item.color }"></div>{{ item.name }}
            </div>
            <div class="status-chip" :class="item.statusClass">{{ item.statusLabel }}</div>
          </div>
          <div class="goal-track-wrap">
            <div class="goal-track">
              <div class="goal-fill" :class="item.fillClass" :style="{ width: item.pct + '%' }"></div>
            </div>
            <div class="goal-pct" :class="item.pctClass">{{ item.pct }}%</div>
          </div>
          <div class="goal-meta">
            <span>{{ t('insights.goalProgress.daysHeld', { days: item.daysHeld }) }}</span>
            <span>{{ t('insights.goalProgress.expectedDays', { days: item.expectedDays, years: item.expectedYears }) }}</span>
          </div>
        </div>
      </div>
    </div>

    <!-- S3 资产类型分布 -->
    <div v-if="typeDistribution" class="section-card">
      <div class="section-header">
        <div class="section-title">
          <span class="title-icon">📊</span>{{ t('insights.typeDistribution.title') }}
        </div>
        <div class="toggle-group">
          <div :class="['toggle-btn', { active: distMode === 'value' }]" role="button" tabindex="0" @click="distMode = 'value'" @keydown.enter="distMode = 'value'" @keydown.space.prevent="distMode = 'value'">{{ t('insights.typeDistribution.byValue') }}</div>
          <div :class="['toggle-btn', { active: distMode === 'count' }]" role="button" tabindex="0" @click="distMode = 'count'" @keydown.enter="distMode = 'count'" @keydown.space.prevent="distMode = 'count'">{{ t('insights.typeDistribution.byCount') }}</div>
        </div>
      </div>
      <div class="dist-summary">
        <div class="ds-label">{{ distMode === 'value' ? t('insights.typeDistribution.totalValue') : t('insights.typeDistribution.totalCount') }}</div>
        <div class="ds-total">{{ distMode === 'value' ? format(typeDistribution.total_value) : typeDistribution.total_count + ' ' + t('insights.common.items') }}</div>
      </div>
      <div class="stacked-bar-row">
        <div
          v-for="(cat, idx) in categories"
          :key="idx"
          class="stacked-segment"
          :style="{ background: cat.color, width: cat.pct + '%' }"
        >{{ cat.pct >= 10 ? cat.pct + '%' : '' }}</div>
      </div>
      <div class="type-legend-grid">
        <div v-for="(cat, idx) in categories" :key="idx" class="type-legend-item">
          <div class="tl-bar" :style="{ background: cat.color }"></div>
          <div class="tl-info">
            <div class="tl-header">
              <span class="tl-name">{{ cat.name }}</span>
              <span class="tl-pct">{{ cat.pct }}%</span>
            </div>
            <div class="tl-sub">{{ distMode === 'value' ? format(cat.amount) : t('insights.typeDistribution.itemsUnit', { count: cat.count }) }}</div>
          </div>
        </div>
      </div>
    </div>

    <!-- S4 持有时长分布 -->
    <div v-if="durationDistribution" class="section-card">
      <div class="section-header">
        <div class="section-title">
          <span class="title-icon">⏱️</span>{{ t('insights.durationDistribution.title') }}
        </div>
      </div>
      <div class="dur-summary">
        <div class="dur-stat">
          <div class="dur-stat-label">{{ t('insights.durationDistribution.avgHeld') }}</div>
          <div class="dur-stat-val">{{ Math.round(durationDistribution.avg_days) }} {{ t('insights.common.days') }}</div>
        </div>
        <div class="dur-stat">
          <div class="dur-stat-label">{{ t('insights.durationDistribution.maxHeld') }}</div>
          <div class="dur-stat-val">{{ durationDistribution.max_days }} {{ t('insights.common.days') }}</div>
        </div>
      </div>
      <div class="dur-chart">
        <div v-for="(bucket, idx) in durationBuckets" :key="idx" class="dur-row">
          <div class="dur-label">{{ bucket.label }}</div>
          <div class="dur-track">
            <div class="dur-bar" :style="{ width: bucket.pct + '%' }">
              <span v-if="bucket.count > 0" class="dur-bar-count">{{ t('insights.durationDistribution.itemsUnit', { count: bucket.count }) }}</span>
            </div>
          </div>
          <div class="dur-count">{{ bucket.count }}</div>
        </div>
      </div>
    </div>

    <!-- S5 实物保值率 -->
    <div v-if="retentionRate" class="section-card">
      <div class="section-header">
        <div class="section-title">
          <span class="title-icon">📈</span>{{ t('insights.retentionRate.physicalTitle') }}
        </div>
        <div class="physical-only-badge">{{ t('insights.retentionRate.physicalOnly') }}</div>
      </div>
      <div class="pres-summary">
        <div class="pres-row">
          <div class="pres-stat">
            <div class="pres-label">{{ t('insights.retentionRate.totalBought') }}</div>
            <div class="pres-val purple">{{ formatCompact(retentionRate.total_bought) }}</div>
          </div>
          <div class="pres-stat">
            <div class="pres-label">{{ t('insights.retentionRate.sold') }}</div>
            <div class="pres-val green">{{ formatCompact(retentionRate.total_sold) }}</div>
          </div>
          <div class="pres-stat">
            <div class="pres-label">{{ t('insights.retentionRate.avgRate') }}</div>
            <div class="pres-val purple">{{ retentionRate.avg_rate.toFixed(1) }}%</div>
          </div>
        </div>
        <div class="pres-row pres-row-2">
          <div class="pres-profit-big">
            <span class="ppb-label">{{ t('insights.retentionRate.totalProfitLoss') }}</span>
            <span class="ppb-val" :class="retentionRate.total_profit_loss >= 0 ? 'green' : 'red'">{{ formatCompact(retentionRate.total_profit_loss) }}</span>
          </div>
        </div>
      </div>
      <div class="podium-label">{{ t('insights.retentionRate.top3') }}</div>
      <div v-if="top3Items.length >= 3" class="top3-row">
        <!-- 2nd -->
        <div class="podium-item rank2">
          <div class="podium-thumb">
            <SvgIcon v-if="top3Items[1]?.icon?.startsWith('icon-')" :name="getIconId(top3Items[1]?.icon)" class="icon-svg" />
            <span v-else>{{ top3Items[1]?.icon || '📦' }}</span>
          </div>
          <div class="podium-name">{{ top3Items[1]?.name }}</div>
          <div class="podium-service">{{ t('insights.retentionRate.serviceDays', { days: top3Items[1]?.service_days }) }}</div>
          <div class="podium-rate" :class="top3Items[1]?.retention_rate >= 80 ? 'green' : 'red'">{{ top3Items[1]?.retention_rate.toFixed(1) }}%</div>
          <div class="podium-base silver">
            <span class="podium-profit-base" :class="top3Items[1]?.profit_loss >= 0 ? 'green' : 'red'">{{ formatCompact(top3Items[1]?.profit_loss) }}</span>
          </div>
        </div>
        <!-- 1st -->
        <div class="podium-item rank1">
          <div class="podium-thumb">
            <SvgIcon v-if="top3Items[0]?.icon?.startsWith('icon-')" :name="getIconId(top3Items[0]?.icon)" class="icon-svg" />
            <span v-else>{{ top3Items[0]?.icon || '📦' }}</span>
          </div>
          <div class="podium-name">{{ top3Items[0]?.name }}</div>
          <div class="podium-service">{{ t('insights.retentionRate.serviceDays', { days: top3Items[0]?.service_days }) }}</div>
          <div class="podium-rate" :class="top3Items[0]?.retention_rate >= 80 ? 'green' : 'red'">{{ top3Items[0]?.retention_rate.toFixed(1) }}%</div>
          <div class="podium-base gold">
            <span class="podium-profit-base" :class="top3Items[0]?.profit_loss >= 0 ? 'green' : 'red'">{{ formatCompact(top3Items[0]?.profit_loss) }}</span>
          </div>
        </div>
        <!-- 3rd -->
        <div class="podium-item rank3">
          <div class="podium-thumb">
            <SvgIcon v-if="top3Items[2]?.icon?.startsWith('icon-')" :name="getIconId(top3Items[2]?.icon)" class="icon-svg" />
            <span v-else>{{ top3Items[2]?.icon || '📦' }}</span>
          </div>
          <div class="podium-name">{{ top3Items[2]?.name }}</div>
          <div class="podium-service">{{ t('insights.retentionRate.serviceDays', { days: top3Items[2]?.service_days }) }}</div>
          <div class="podium-rate" :class="top3Items[2]?.retention_rate >= 80 ? 'green' : 'red'">{{ top3Items[2]?.retention_rate.toFixed(1) }}%</div>
          <div class="podium-base bronze">
            <span class="podium-profit-base" :class="top3Items[2]?.profit_loss >= 0 ? 'green' : 'red'">{{ formatCompact(top3Items[2]?.profit_loss) }}</span>
          </div>
        </div>
      </div>
      <div class="pres-list">
        <div v-for="(item, idx) in retentionItems" :key="idx" class="pres-list-item">
          <div class="pres-rank">{{ item.rank }}</div>
          <div class="pres-thumb">
            <SvgIcon v-if="item.icon?.startsWith('icon-')" :name="getIconId(item.icon)" class="icon-svg" />
            <span v-else>{{ item.icon }}</span>
          </div>
          <div class="pres-info">
            <div class="pres-name">{{ item.name }}</div>
            <div class="pres-service">{{ t('insights.retentionRate.serviceDays', { days: item.days }) }}</div>
            <div class="pres-sub">
              <span>{{ t('insights.retentionRate.bought') }} {{ format(item.bought) }}</span>
              <span>{{ t('insights.retentionRate.current') }} {{ format(item.current) }}</span>
            </div>
          </div>
          <div class="pres-right">
            <div class="pres-rate-val" :class="item.rateClass">{{ item.rate.toFixed(1) }}%</div>
            <div class="pres-profit" :class="item.profitClass">{{ format(item.profit) }}</div>
          </div>
        </div>
      </div>
    </div>

    <!-- D8 金融年化收益率 -->
    <div v-if="investmentReturns" class="section-card">
      <div class="section-header">
        <div class="section-title">
          <span class="title-icon">💰</span>{{ t('insights.investmentReturns.title') }}
        </div>
        <div class="physical-only-badge">{{ t('insights.investmentReturns.financialOnly') }}</div>
      </div>
      <div class="pres-summary">
        <div class="pres-row">
          <div class="pres-stat">
            <div class="pres-label">{{ t('insights.investmentReturns.annualizedRate') }}</div>
            <div v-if="investmentReturns.annualized_rate !== null" class="pres-val purple" :class="(investmentReturns.annualized_rate ?? 0) >= 0 ? 'green' : 'red'">
              {{ (investmentReturns.annualized_rate ?? 0) >= 0 ? '+' : '' }}{{ investmentReturns.annualized_rate?.toFixed(2) }}%
            </div>
            <div v-else class="pres-val insufficient">{{ t('insights.investmentReturns.insufficientDays') }}</div>
          </div>
          <div class="pres-stat">
            <div class="pres-label">{{ t('insights.investmentReturns.assetCount') }}</div>
            <div class="pres-val purple">{{ investmentReturns.asset_count }}</div>
          </div>
        </div>
        <div class="pres-row pres-row-2">
          <div class="pres-profit-big">
            <span class="ppb-label">{{ t('insights.investmentReturns.description') }}</span>
          </div>
        </div>
      </div>
    </div>
  </template>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { useCurrency } from '@/composables/useCurrency'
import { formatCurrency, CURRENCY_SYMBOLS } from '@/utils/format'
import { getInsights, type InsightsResponse, type GoalProgressItem, type TypeDistributionItem, type DurationBucket, type RetentionItem } from '@/api/dashboard'
import type { DailyCostItem } from '@/types'
import { getIconId } from '@/utils/icon'

const { t } = useI18n()
const { format, currency } = useCurrency()

const loading = ref(true)
const insightsData = ref<InsightsResponse | null>(null)
const distMode = ref<'value' | 'count'>('value')
const costRankOrder = ref<'highest' | 'lowest'>('highest')
const showAllCostRank = ref(false)

// Compact formatter for large numbers (K format)
function formatCompact(amount: number): string {
  const absAmount = Math.abs(amount)
  const sign = amount < 0 ? '-' : ''
  const symbol = CURRENCY_SYMBOLS[currency.value] || currency.value
  if (absAmount >= 100000) {
    return `${sign}${symbol}${(absAmount / 1000).toFixed(0)}K`
  }
  return formatCurrency(amount, currency.value)
}

// Computed properties for each section
const smartDiscovery = computed(() => insightsData.value?.smart_discovery)
const dailyCostItems = computed(() => {
  if (!insightsData.value?.daily_cost_ranking) return []
  const sorted = costRankOrder.value === 'lowest'
    ? [...insightsData.value.daily_cost_ranking].reverse()
    : insightsData.value.daily_cost_ranking
  const maxCost = sorted[0]?.daily_cost || 1
  return sorted.map((item: DailyCostItem) => ({
    icon: item.icon,
    name: item.name,
    days: item.days_used,
    cost: item.daily_cost,
    pct: Math.round((item.daily_cost / maxCost) * 100)
  }))
})

const allCostRankItems = computed(() => dailyCostItems.value)

const goalProgress = computed(() => insightsData.value?.goal_progress)

const goalItems = computed(() => {
  if (!insightsData.value?.goal_progress?.items) return []
  const data = insightsData.value.goal_progress
  const statusLabels: Record<string, string> = {
    'on-track': t('insights.goalProgress.healthy'),
    'near-end': t('insights.goalProgress.nearEnd'),
    'overdue': t('insights.goalProgress.overdue'),
  }
  return data.items.map((item: GoalProgressItem) => ({
    name: item.name,
    color: item.category_color,
    statusClass: item.status === 'overdue' ? 'over' : (item.status === 'near-end' ? 'warn' : 'good'),
    statusLabel: statusLabels[item.status] || item.status,
    fillClass: item.status === 'overdue' ? 'overdue' : (item.status === 'near-end' ? 'near-end' : 'on-track'),
    pctClass: item.status === 'overdue' ? 'overdue' : (item.status === 'near-end' ? 'near-end' : 'on-track'),
    pct: Math.min(item.progress_pct, 110),
    daysHeld: item.days_held,
    expectedDays: item.expected_days,
    expectedYears: item.expected_years,
  }))
})

const typeDistribution = computed(() => insightsData.value?.type_distribution)

const categories = computed(() => {
  if (!insightsData.value?.type_distribution?.categories) return []
  return insightsData.value.type_distribution.categories.map((cat: TypeDistributionItem) => ({
    name: cat.name,
    color: cat.color,
    pct: cat.percentage,
    amount: cat.amount,
    count: cat.count,
  }))
})

const durationDistribution = computed(() => insightsData.value?.duration_distribution)

const durationBuckets = computed(() => {
  if (!insightsData.value?.duration_distribution?.buckets) return []
  const labelMap: Record<string, string> = {
    'less_than_1_year': t('insights.durationDistribution.lessThan1Year'),
    'range_1_to_2_years': t('insights.durationDistribution.range1to2Years'),
    'range_2_to_4_years': t('insights.durationDistribution.range2to4Years'),
    'range_4_to_6_years': t('insights.durationDistribution.range4to6Years'),
    'range_6_to_8_years': t('insights.durationDistribution.range6to8Years'),
    'more_than_8_years': t('insights.durationDistribution.moreThan8Years'),
  }
  return insightsData.value.duration_distribution.buckets.map((bucket: DurationBucket) => ({
    label: labelMap[bucket.label_key] || bucket.label_key,
    count: bucket.count,
    pct: bucket.percentage,
  }))
})

const retentionRate = computed(() => insightsData.value?.retention_rate)

const investmentReturns = computed(() => insightsData.value?.investment_returns)

const retentionItems = computed(() => {
  if (!insightsData.value?.retention_rate?.top_items) return []
  return insightsData.value.retention_rate.top_items
    .filter((item: RetentionItem) => item.rank > 3)
    .sort((a: RetentionItem, b: RetentionItem) => a.rank - b.rank)
    .map((item: RetentionItem) => ({
      rank: item.rank,
      icon: item.icon || '📦',
      name: item.name,
      days: item.service_days,
      bought: item.bought_amount,
      current: item.current_amount,
      rate: item.retention_rate,
      rateClass: item.retention_rate >= 80 ? 'green' : 'red',
      profit: item.profit_loss,
      profitClass: item.profit_loss >= 0 ? 'green' : 'red',
    }))
})

const top3Items = computed(() => {
  if (!insightsData.value?.retention_rate?.top_items) return []
  return insightsData.value.retention_rate.top_items
    .filter((item: RetentionItem) => item.rank <= 3)
    .sort((a: RetentionItem, b: RetentionItem) => a.rank - b.rank)
})

// Fetch data on mount
onMounted(async () => {
  try {
    const res = await getInsights()
    insightsData.value = res.data
  } catch (error) {
    console.error('Failed to fetch insights:', error)
  } finally {
    loading.value = false
  }
})
</script>

<style scoped>
.insights-tab {
  display: flex;
  flex-direction: column;
  gap: 12px;
  padding: 12px;
}

.loading-state {
  display: flex;
  justify-content: center;
  align-items: center;
  padding: 48px 0;
}

.section-card {
  background: var(--card-bg);
  border-radius: 16px;
  padding: 16px;
  box-shadow: 0 2px 12px rgba(1, 1, 32, 0.08);
}

[data-theme='dark'] .section-card {
  box-shadow: 0 2px 12px rgba(0, 0, 0, 0.28);
}

.section-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 14px;
}

.section-title {
  font-size: 15px;
  font-weight: 700;
  color: var(--text-primary);
  display: flex;
  align-items: center;
  gap: 6px;
}

.title-icon {
  font-size: 16px;
}

/* Gradient title for Smart Discovery */
.gradient-title .gradient-icon {
  background: linear-gradient(135deg, #7B61FF, #FF6B9D, #FFB340);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  font-size: 18px;
}

.gradient-title .gradient-text {
  background: linear-gradient(135deg, #7B61FF 0%, #FF6B9D 60%, #FFB340 100%);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  font-weight: 800;
}

/* S0 智能发现 */
.insight-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 10px;
}

.insight-stat-card {
  border-radius: 12px;
  padding: 12px 12px 10px;
  display: flex;
  flex-direction: column;
  gap: 8px;
  position: relative;
  overflow: hidden;
}

/* Light-mode card backgrounds — colored pastel gradients per category */
.isc-card--yoy   { background: linear-gradient(135deg, #f3f0ff, #e8f4ff); }
.isc-card--high  { background: linear-gradient(135deg, #fff8f0, #fff3e0); }
.isc-card--low   { background: linear-gradient(135deg, #f0fff8, #e6faf2); }
.isc-card--long  { background: linear-gradient(135deg, #f5f0ff, #ede4ff); }
.isc-card--top   { background: linear-gradient(135deg, #fff0f8, #ffe6f2); grid-column: span 2; }

/* Light-mode isc-icon backgrounds — match each card's hue */
.isc-card--yoy  .isc-icon { background: #ede9ff; }
.isc-card--high .isc-icon { background: #ffefd9; }
.isc-card--low  .isc-icon { background: #d5f5e8; }
.isc-card--long .isc-icon { background: #ede0ff; }
.isc-card--top  .isc-icon { background: #ffdaee; }

.isc-header {
  display: flex;
  align-items: center;
  gap: 6px;
}

.isc-icon {
  width: 28px;
  height: 28px;
  border-radius: 8px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 15px;
  flex-shrink: 0;
}

.isc-label {
  font-size: 11px;
  color: var(--text-secondary);
  font-weight: 500;
  line-height: 1.2;
}

.isc-value {
  font-size: 20px;
  font-weight: 800;
  line-height: 1;
  color: var(--text-primary);
}

.isc-value.up { color: var(--color-trend-up); }
.isc-value.down { color: var(--color-trend-down); }
.isc-value.purple { color: var(--van-primary-color); }

.isc-sub {
  font-size: 11px;
  color: var(--text-tertiary);
  display: flex;
  align-items: center;
  gap: 3px;
}

.isc-sub-meta { color: var(--text-tertiary); }

.isc-badge {
  display: inline-flex;
  align-items: center;
  gap: 2px;
  font-size: 11px;
  font-weight: 600;
  padding: 2px 6px;
  border-radius: 5px;
}

.isc-badge.up { background: #FFE8E8; color: var(--color-trend-up); }
.isc-badge.down { background: #E2FBF0; color: var(--color-trend-down); }

[data-theme='dark'] .isc-badge.up { background: rgba(252, 165, 165, 0.15); color: var(--color-trend-up); }
[data-theme='dark'] .isc-badge.down { background: rgba(110, 231, 160, 0.15); color: var(--color-trend-down); }

.isc-name {
  font-size: 14px;
  font-weight: 800;
  color: var(--text-primary);
  margin-top: 2px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.isc-cost-val {
  font-size: 13px;
  font-weight: 700;
  color: var(--color-trend-warn);
}

.isc-cost-val.green { color: var(--color-trend-down); }

[data-theme='dark'] .isc-cost-val { color: var(--color-trend-warn); }
[data-theme='dark'] .isc-cost-val.green { color: var(--color-trend-down); }

.isc-cost-unit {
  font-size: 10px;
  font-weight: 400;
  color: var(--text-tertiary);
}

.isc-days-val {
  font-size: 13px;
  font-weight: 700;
  color: var(--van-primary-color);
}

.isc-days-unit {
  font-size: 10px;
  font-weight: 400;
  color: var(--text-tertiary);
}

.isc-bg-icon {
  position: absolute;
  right: -4px;
  bottom: -4px;
  font-size: 40px;
  opacity: 0.07;
  display: flex;
  align-items: center;
  justify-content: center;
}

.isc-bg-icon .icon-svg-bg {
  width: 40px;
  height: 40px;
  color: var(--text-primary);
}

[data-theme='dark'] .isc-bg-icon { opacity: 0.12; }

/* Dark mode card backgrounds — deep navy base from --card-bg + low-opacity tint
 * of each category's hue. Apple HIG dark mode pattern: keep categorical color
 * semantics without lifting luminance above ~#1c1d2e.
 *
 * No !important is needed here — the modifier classes own the background, so
 * normal cascade specificity ([data-theme='dark'] adds 1 attribute selector =
 * specificity (0,2,0)) wins over the bare class rule (0,1,0).
 */
[data-theme='dark'] .isc-card--yoy {
  background: linear-gradient(135deg, rgba(189, 187, 255, 0.14), rgba(147, 197, 253, 0.08));
}
[data-theme='dark'] .isc-card--high {
  background: linear-gradient(135deg, rgba(251, 191, 36, 0.14), rgba(251, 191, 36, 0.07));
}
[data-theme='dark'] .isc-card--low {
  background: linear-gradient(135deg, rgba(110, 231, 160, 0.14), rgba(110, 231, 160, 0.07));
}
[data-theme='dark'] .isc-card--long {
  background: linear-gradient(135deg, rgba(189, 187, 255, 0.16), rgba(167, 139, 255, 0.09));
}
[data-theme='dark'] .isc-card--top {
  background: linear-gradient(135deg, rgba(255, 107, 157, 0.14), rgba(255, 107, 157, 0.07));
}

/* Dark mode isc-icon backgrounds — same hue family at slightly higher alpha */
[data-theme='dark'] .isc-card--yoy  .isc-icon { background: rgba(189, 187, 255, 0.22); }
[data-theme='dark'] .isc-card--high .isc-icon { background: rgba(251, 191, 36, 0.22); }
[data-theme='dark'] .isc-card--low  .isc-icon { background: rgba(110, 231, 160, 0.22); }
[data-theme='dark'] .isc-card--long .isc-icon { background: rgba(189, 187, 255, 0.26); }
[data-theme='dark'] .isc-card--top  .isc-icon { background: rgba(255, 107, 157, 0.22); }

/* Dark mode secondary labels — intentionally dimmer than --text-secondary
 * (#c8c8d0 ≈ 0.78 opacity equivalent on dark). Card surfaces already carry a
 * colored tint, so we step the label/caption down to keep the colored chip and
 * primary value visually dominant. Computed contrast ≈ 5:1 on the tinted
 * backgrounds — meets WCAG AA for the 11–12px text size used here.
 *
 * .isc-name and .isc-category-name keep var(--text-primary) (#f5f5f5 in dark)
 * — no override needed; the bug was never about text color, only about the
 * card background being overridden by inline style.
 */
[data-theme='dark'] .isc-label { color: rgba(255, 255, 255, 0.6); }
[data-theme='dark'] .isc-category-sub { color: rgba(255, 255, 255, 0.55); }

/* Dark mode for gradient title */
[data-theme='dark'] .gradient-title .gradient-icon {
  background: linear-gradient(135deg, #bdbbff, #ff6b9d, #fbbf24);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
}

[data-theme='dark'] .gradient-title .gradient-text {
  background: linear-gradient(135deg, #bdbbff 0%, #ff6b9d 60%, #fbbf24 100%);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
}

/* Dark mode for isc-category-pct */
[data-theme='dark'] .isc-category-pct { color: #ff6b9d; }

/* Dark mode for isc-sub separator text */
[data-theme='dark'] .isc-sub-meta { color: var(--text-tertiary); }

/* Dark mode for isc-cost-unit and isc-days-unit */
[data-theme='dark'] .isc-cost-unit { color: var(--text-tertiary); }
[data-theme='dark'] .isc-days-unit { color: var(--text-tertiary); }

.isc-category-row {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-top: 2px;
}

.isc-category-name {
  font-size: 18px;
  font-weight: 800;
  color: var(--text-primary);
}

.isc-category-sub {
  font-size: 12px;
  color: var(--text-secondary);
  margin-top: 2px;
}

.isc-category-pct {
  font-size: 26px;
  font-weight: 900;
  color: #FF6B9D;
  margin-left: auto;
}

/* S1 日均成本排行 */
.rank-list {
  display: flex;
  flex-direction: column;
}

.rank-item {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 13px;
}

.rank-item:last-of-type { margin-bottom: 0; }

.rank-img {
  width: 40px;
  height: 40px;
  border-radius: 10px;
  background: var(--bg-secondary);
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 20px;
  flex-shrink: 0;
  overflow: hidden;
}

.rank-img .icon-svg {
  width: 24px;
  height: 24px;
  color: var(--text-primary);
}

.rank-info { flex: 1; min-width: 0; }

.rank-name {
  font-size: 13px;
  font-weight: 600;
  color: var(--text-primary);
  margin-bottom: 6px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.rank-service-row {
  display: flex;
  align-items: center;
  gap: 6px;
}

.rank-service-text {
  font-size: 11px;
  color: var(--text-secondary);
  white-space: nowrap;
  flex-shrink: 0;
  min-width: 90px;
  text-align: left;
}

.rank-bar-track {
  height: 5px;
  background: var(--bg-secondary);
  border-radius: 3px;
  overflow: hidden;
  width: 80px;
  min-width: 80px;
  max-width: 80px;
  flex-shrink: 0;
  flex-grow: 0;
}

.rank-bar-fill {
  height: 100%;
  border-radius: 3px;
  background: linear-gradient(90deg, var(--van-primary-color), #A78BFF);
}

[data-theme='dark'] .rank-bar-fill {
  background: linear-gradient(90deg, var(--color-lavender), #d0d0ff);
}

.rank-cost {
  text-align: right;
  flex-shrink: 0;
  display: flex;
  align-items: baseline;
  gap: 2px;
}

.rank-cost-val {
  font-size: 18px;
  font-weight: 800;
  color: var(--van-primary-color);
}

[data-theme='dark'] .rank-cost-val { color: var(--color-lavender); }

.rank-cost-unit {
  font-size: 11px;
  color: var(--text-tertiary);
}

.rank-sort-group {
  display: flex;
  gap: 6px;
}

.rank-sort-btn {
  font-size: 11px;
  padding: 4px 10px;
  border-radius: 6px;
  background: var(--bg-secondary);
  color: var(--text-secondary);
  cursor: pointer;
  font-weight: 500;
}

.rank-sort-btn.active {
  background: var(--van-primary-color);
  color: #fff;
  font-weight: 600;
}

[data-theme='dark'] .rank-sort-btn.active {
  background: var(--color-lavender);
  color: #010120;
}

.popup-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 16px 16px 12px;
  border-bottom: 0.5px solid var(--separator);
}

.popup-title {
  font-size: 16px;
  font-weight: 700;
  color: var(--text-primary);
}

.popup-close {
  width: 28px;
  height: 28px;
  border-radius: 50%;
  background: var(--bg-secondary);
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 12px;
  color: var(--text-secondary);
  cursor: pointer;
}

.popup-rank-list {
  padding: 12px 16px 24px;
  max-height: 65vh;
  overflow-y: auto;
}

.view-all-row {
  display: flex;
  justify-content: center;
  align-items: center;
  padding-top: 12px;
  border-top: 0.5px solid var(--separator);
  margin-top: 12px;
  font-size: 13px;
  color: var(--text-secondary);
  gap: 2px;
  cursor: pointer;
}

.view-all-arrow {
  color: var(--text-tertiary);
  font-size: 14px;
}

/* S2 目标进度总览 */
.goal-chips {
  display: flex;
  gap: 8px;
  margin-bottom: 14px;
}

.goal-chip {
  flex: 1;
  background: var(--bg-secondary);
  border-radius: 10px;
  padding: 9px 8px;
  text-align: center;
  cursor: pointer;
  transition: background 0.15s;
}

.goal-chip.selected-green { background: rgba(5, 150, 105, 0.08); }
.goal-chip.selected-orange { background: rgba(250, 140, 22, 0.08); }
.goal-chip.selected-red { background: rgba(220, 38, 38, 0.08); }

[data-theme='dark'] .goal-chip.selected-green { background: rgba(110, 231, 160, 0.12); }
[data-theme='dark'] .goal-chip.selected-orange { background: rgba(251, 191, 36, 0.12); }
[data-theme='dark'] .goal-chip.selected-red { background: rgba(252, 165, 165, 0.12); }

.gc-val {
  font-size: 18px;
  font-weight: 800;
  line-height: 1.1;
}

.gc-val.green { color: var(--color-trend-down); }
.gc-val.orange { color: var(--color-trend-warn); }
.gc-val.red { color: var(--color-trend-up); }

.gc-label {
  font-size: 11px;
  color: var(--text-secondary);
  margin-top: 2px;
}

.goal-list {
  display: flex;
  flex-direction: column;
}

.goal-item { margin-bottom: 13px; }
.goal-item:last-of-type { margin-bottom: 0; }

.goal-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 6px;
}

.goal-name {
  font-size: 13px;
  font-weight: 600;
  color: var(--text-primary);
  display: flex;
  align-items: center;
  gap: 6px;
}

.cat-dot {
  width: 7px;
  height: 7px;
  border-radius: 50%;
  flex-shrink: 0;
}

.status-chip {
  font-size: 10px;
  font-weight: 600;
  padding: 2px 7px;
  border-radius: 5px;
  cursor: pointer;
  transition: transform 0.1s, box-shadow 0.1s;
}

.status-chip:hover {
  transform: scale(1.05);
  box-shadow: 0 1px 4px rgba(0, 0, 0, 0.12);
}

.status-chip.good { background: rgba(5, 150, 105, 0.08); color: var(--color-trend-down); }
.status-chip.warn { background: rgba(250, 140, 22, 0.08); color: var(--color-trend-warn); }
.status-chip.over { background: rgba(220, 38, 38, 0.08); color: var(--color-trend-up); }

[data-theme='dark'] .status-chip.good { background: rgba(110, 231, 160, 0.15); color: var(--color-trend-down); }
[data-theme='dark'] .status-chip.warn { background: rgba(251, 191, 36, 0.15); color: var(--color-trend-warn); }
[data-theme='dark'] .status-chip.over { background: rgba(252, 165, 165, 0.15); color: var(--color-trend-up); }

.goal-track-wrap {
  display: flex;
  align-items: center;
  gap: 8px;
}

.goal-track {
  flex: 1;
  height: 7px;
  background: var(--bg-secondary);
  border-radius: 4px;
  overflow: hidden;
}

.goal-pct {
  font-size: 13px;
  font-weight: 700;
  color: var(--text-primary);
  min-width: 36px;
  text-align: right;
  flex-shrink: 0;
}

.goal-pct.on-track { color: var(--color-trend-down); }
.goal-pct.near-end { color: var(--color-trend-warn); }
.goal-pct.overdue { color: var(--color-trend-up); }

.goal-fill {
  height: 100%;
  border-radius: 4px;
}

.goal-fill.on-track { background: linear-gradient(90deg, var(--color-trend-down), #00E090); }
.goal-fill.near-end { background: linear-gradient(90deg, var(--color-trend-warn), #FFB340); }
.goal-fill.overdue { background: linear-gradient(90deg, var(--color-trend-up), #FF7070); }

[data-theme='dark'] .goal-fill.on-track { background: linear-gradient(90deg, #22C55E, var(--color-trend-down)); }
[data-theme='dark'] .goal-fill.near-end { background: linear-gradient(90deg, #F59E0B, var(--color-trend-warn)); }
[data-theme='dark'] .goal-fill.overdue { background: linear-gradient(90deg, #EF4444, var(--color-trend-up)); }

.goal-meta {
  display: flex;
  justify-content: space-between;
  margin-top: 4px;
  font-size: 10px;
  color: var(--text-secondary);
}

/* S3 资产类型分布 */
.toggle-group {
  display: flex;
  background: var(--bg-secondary);
  border-radius: 8px;
  padding: 2px;
}

.toggle-btn {
  padding: 4px 10px;
  border-radius: 6px;
  font-size: 12px;
  color: var(--text-secondary);
  cursor: pointer;
  font-weight: 500;
}

.toggle-btn.active {
  background: var(--card-bg);
  color: var(--van-primary-color);
  font-weight: 600;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.09);
}

[data-theme='dark'] .toggle-btn.active { color: var(--color-lavender); }

.dist-summary {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 4px;
  margin-bottom: 10px;
}

.ds-label {
  font-size: 12px;
  font-weight: 500;
  color: var(--text-secondary);
}

.ds-total {
  font-size: 18px;
  font-weight: 700;
  color: var(--text-primary);
}

.stacked-bar-row {
  display: flex;
  height: 32px;
  border-radius: 8px;
  overflow: hidden;
  margin-bottom: 12px;
}

.stacked-segment {
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 11px;
  font-weight: 700;
  color: #fff;
  cursor: pointer;
  transition: filter 0.15s;
  min-width: 20px;
}

.stacked-segment:hover { filter: brightness(1.1); }

.stacked-segment:first-child { border-radius: 8px 0 0 8px; }
.stacked-segment:last-child { border-radius: 0 8px 8px 0; }

.type-legend-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 8px;
}

.type-legend-item {
  display: flex;
  align-items: stretch;
  gap: 8px;
  padding: 8px 10px;
  background: rgba(123, 97, 255, 0.04);
  border-radius: 10px;
  cursor: pointer;
  transition: background 0.15s;
}

[data-theme='dark'] .type-legend-item { background: rgba(189, 187, 255, 0.08); }

.type-legend-item:hover { background: rgba(123, 97, 255, 0.08); }

[data-theme='dark'] .type-legend-item:hover { background: rgba(189, 187, 255, 0.12); }

.tl-bar {
  width: 4px;
  border-radius: 2px;
  flex-shrink: 0;
}

.tl-info {
  flex: 1;
  min-width: 0;
}

.tl-header {
  display: flex;
  align-items: baseline;
  gap: 6px;
}

.tl-name {
  font-size: 12px;
  font-weight: 500;
  color: var(--text-secondary);
}

.tl-pct {
  font-size: 12px;
  font-weight: 500;
  color: var(--text-secondary);
}

.tl-sub {
  font-size: 13px;
  font-weight: 700;
  color: var(--text-primary);
  margin-top: 2px;
}

/* S4 持有时长分布 */
.dur-summary {
  display: flex;
  justify-content: flex-start;
  margin-bottom: 12px;
}

.dur-stat {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 4px;
}

.dur-stat:nth-child(2) {
  margin-left: calc(50% - 80px);
}

.dur-stat-label {
  font-size: 12px;
  font-weight: 500;
  color: var(--text-secondary);
}

.dur-stat-val {
  font-size: 18px;
  font-weight: 700;
  color: var(--text-primary);
}

.dur-chart {
  display: flex;
  flex-direction: column;
  gap: 9px;
  padding: 4px 0;
}

.dur-row {
  display: flex;
  align-items: center;
  gap: 8px;
}

.dur-label {
  width: 58px;
  font-size: 11px;
  color: var(--text-secondary);
  text-align: right;
  flex-shrink: 0;
}

.dur-track {
  flex: 1;
  height: 22px;
  background: var(--bg-secondary);
  border-radius: 5px;
  overflow: hidden;
}

.dur-bar {
  height: 100%;
  border-radius: 5px;
  background: linear-gradient(90deg, var(--van-primary-color), #A78BFF);
  display: flex;
  align-items: center;
  padding-left: 8px;
  min-width: 28px;
}

[data-theme='dark'] .dur-bar { background: linear-gradient(90deg, var(--color-lavender), #d0d0ff); }

.dur-bar-count {
  font-size: 11px;
  font-weight: 700;
  color: #fff;
  white-space: nowrap;
}

/* Dark-mode bar fill is light lavender, so white count text is illegible —
   step the text down to the same dark navy used on other lavender fills. */
[data-theme='dark'] .dur-bar-count { color: #010120; }

.dur-count {
  width: 28px;
  font-size: 12px;
  font-weight: 600;
  color: var(--text-primary);
  text-align: right;
  flex-shrink: 0;
}

/* S5 资产保值率 */
.physical-only-badge {
  font-size: 11px;
  color: var(--text-secondary);
  background: var(--bg-secondary);
  padding: 3px 8px;
  border-radius: 6px;
}

.pres-summary {
  display: flex;
  flex-direction: column;
  gap: 8px;
  padding: 12px 14px;
  background: rgba(123, 97, 255, 0.04);
  border-radius: 12px;
  margin-bottom: 14px;
}

[data-theme='dark'] .pres-summary { background: rgba(189, 187, 255, 0.08); }

.pres-row {
  display: flex;
  align-items: center;
  gap: 12px;
}

.pres-row-2 {
  justify-content: flex-start;
  padding-top: 6px;
  border-top: 0.5px solid rgba(123, 97, 255, 0.1);
}

.pres-stat {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 2px;
  flex: 1;
}

.pres-label {
  font-size: 12px;
  font-weight: 500;
  color: var(--text-secondary);
}

.pres-val {
  font-size: 17px;
  font-weight: 700;
  color: var(--text-primary);
  line-height: 1.2;
}

.pres-val.purple { color: var(--van-primary-color); }
.pres-val.red { color: var(--color-trend-up); }
.pres-val.green { color: var(--color-trend-down); }
.pres-val.insufficient { font-size: 14px; font-weight: 600; color: var(--text-secondary); }

[data-theme='dark'] .pres-val.purple { color: var(--color-lavender); }

.pres-profit-big {
  display: flex;
  align-items: baseline;
  gap: 4px;
}

.ppb-label {
  font-size: 12px;
  font-weight: 500;
  color: var(--text-secondary);
}

.ppb-val {
  font-size: 22px;
  font-weight: 800;
  color: var(--color-trend-up);
}

.podium-label {
  font-size: 12px;
  color: var(--text-secondary);
  font-weight: 500;
  margin-bottom: 10px;
}

.top3-row {
  display: flex;
  align-items: flex-end;
  justify-content: center;
  gap: 8px;
  margin-bottom: 14px;
}

.podium-item {
  flex: 1;
  max-width: 110px;
  display: flex;
  flex-direction: column;
  align-items: center;
  cursor: pointer;
}

.podium-item.rank1 { order: 2; }
.podium-item.rank2 { order: 1; }
.podium-item.rank3 { order: 3; }

.podium-thumb {
  /* Multi-color conic-gradient ring (border-box) wraps a neutral inner fill
     (padding-box). Each rank overrides --podium-ring below to give Top 1-3
     distinct, high-saturation color bands and lift the podium's colorfulness. */
  --podium-ring: conic-gradient(from 0deg, #FF6B9D, #FFD93D, #6BCB77, #4D96FF, #9D72FF, #FF6B9D);
  width: 48px;
  height: 48px;
  border-radius: 12px;
  background:
    linear-gradient(var(--bg-secondary), var(--bg-secondary)) padding-box,
    var(--podium-ring) border-box;
  border: 3px solid transparent;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 24px;
  margin-bottom: 6px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.08);
  overflow: hidden;
}

.podium-thumb .icon-svg {
  width: 28px;
  height: 28px;
  color: var(--text-primary);
}

[data-theme='dark'] .podium-thumb { box-shadow: 0 2px 8px rgba(0, 0, 0, 0.3); }

/* 冠军 — 暖色火环 (金/橙/红/绯) */
.podium-item.rank1 .podium-thumb {
  --podium-ring: conic-gradient(from 0deg, #FFD700, #FF9100, #FF3D00, #FF1744, #FFD700);
  width: 56px;
  height: 56px;
  border-radius: 14px;
  font-size: 28px;
}

.podium-item.rank1 .podium-thumb .icon-svg {
  width: 32px;
  height: 32px;
}

/* 亚军 — 冷色极光环 (青/蓝/紫/品红) */
.podium-item.rank2 .podium-thumb {
  --podium-ring: conic-gradient(from 0deg, #00E5FF, #2979FF, #7C4DFF, #E040FB, #00E5FF);
}

/* 季军 — 宝石环 (青/绿/琥/珊瑚) */
.podium-item.rank3 .podium-thumb {
  --podium-ring: conic-gradient(from 0deg, #26A69A, #9CCC65, #FFCA28, #FF7043, #26A69A);
}

.podium-name {
  font-size: 12px;
  font-weight: 600;
  color: var(--text-primary);
  text-align: center;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  max-width: 100%;
  margin-bottom: 2px;
}

.podium-item.rank1 .podium-name { font-size: 13px; }

.podium-service {
  font-size: 10px;
  color: var(--text-secondary);
  margin-bottom: 3px;
}

.podium-rate {
  font-size: 14px;
  font-weight: 800;
  line-height: 1;
  margin-bottom: 4px;
}

.podium-item.rank1 .podium-rate { font-size: 16px; }

.podium-rate.green { color: var(--color-trend-down); }
.podium-rate.red { color: var(--color-trend-up); }

.podium-base {
  width: 100%;
  border-radius: 8px 8px 0 0;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 6px 4px;
}

.podium-base.gold { background: linear-gradient(180deg, #FFE57A, #F5C518); height: 56px; }
.podium-base.silver { background: linear-gradient(180deg, #E8E8E8, #C8C8C8); height: 44px; }
.podium-base.bronze { background: linear-gradient(180deg, #FFCBA0, #E8945A); height: 36px; }

.podium-profit-base {
  font-size: 11px;
  color: rgba(0, 0, 0, 0.6);
  font-weight: 600;
}

.pres-list {
  display: flex;
  flex-direction: column;
}

.pres-list-item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 12px 0;
  border-top: 0.5px solid var(--separator);
}

.pres-rank {
  width: 22px;
  font-size: 14px;
  font-weight: 700;
  color: var(--text-tertiary);
  text-align: center;
  flex-shrink: 0;
}

.pres-thumb {
  width: 44px;
  height: 44px;
  border-radius: 10px;
  background: var(--bg-secondary);
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 22px;
  flex-shrink: 0;
  overflow: hidden;
}

.pres-thumb .icon-svg {
  width: 26px;
  height: 26px;
  color: var(--text-primary);
}

.pres-info { flex: 1; min-width: 0; }

.pres-name {
  font-size: 13px;
  font-weight: 600;
  color: var(--text-primary);
  margin-bottom: 4px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.pres-service {
  font-size: 11px;
  color: var(--text-secondary);
  margin-bottom: 2px;
}

.pres-sub {
  font-size: 11px;
  color: var(--text-secondary);
  display: flex;
  gap: 6px;
}

.pres-right { text-align: right; flex-shrink: 0; }

.pres-rate-val {
  font-size: 16px;
  font-weight: 800;
  margin-bottom: 2px;
}

.pres-rate-val.green { color: var(--color-trend-down); }
.pres-rate-val.red { color: var(--color-trend-up); }

.pres-profit {
  font-size: 12px;
  font-weight: 600;
}

.pres-profit.red { color: var(--color-trend-up); }
.pres-profit.green { color: var(--color-trend-down); }
</style>