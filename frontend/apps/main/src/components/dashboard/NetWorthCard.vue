<template>
  <div class="overview-card">
    <div class="ov-main">
      <div class="ov-label">总资产</div>
      <div class="ov-amount">
        <MoneyDisplay :amount="totalAssets" size="large" />
      </div>
      <div class="ov-sub-row">
        <span v-if="totalDailyCost > 0" class="ov-daily">日均 {{ currency.format(totalDailyCost) }}</span>
        <span class="ov-count">共 {{ assetCount }} 件</span>
        <span v-if="monthOverMonthChange != null" class="ov-change" :class="changeClass">
          {{ changeText }} vs 上月
        </span>
      </div>
    </div>
    <div class="ov-detail">
      <div class="ov-detail-item">
        <div class="ov-detail-label">净资产</div>
        <div class="ov-detail-value">
          <MoneyDisplay :amount="netWorth" />
        </div>
      </div>
      <div class="ov-detail-divider" />
      <div class="ov-detail-item">
        <div class="ov-detail-label">总负债</div>
        <div class="ov-detail-value">
          <MoneyDisplay :amount="totalLiabilities" />
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import MoneyDisplay from '@/components/common/MoneyDisplay.vue'
import { useCurrency } from '@/composables/useCurrency'

const props = defineProps<{
  netWorth: number
  totalAssets: number
  totalLiabilities: number
  totalDailyCost: number
  assetCount: number
  monthOverMonthChange?: number | null
}>()

const currency = useCurrency()

const changeClass = computed(() => {
  const pct = props.monthOverMonthChange || 0
  return pct >= 0 ? 'positive' : 'negative'
})

const changeText = computed(() => {
  const pct = props.monthOverMonthChange || 0
  const arrow = pct >= 0 ? '↑' : '↓'
  return `${arrow} ${Math.abs(pct).toFixed(1)}%`
})
</script>

<style scoped>
.overview-card {
  background: var(--color-primary);
  padding: 20px 16px 16px;
  color: var(--color-on-primary);
}
[data-theme='dark'] .overview-card {
  background: #010120;
}
.ov-main {
  display: flex;
  flex-direction: column;
}
.ov-label {
  font-size: 13px;
  font-weight: 500;
  letter-spacing: 0.5px;
  opacity: 0.65;
  text-transform: uppercase;
}
.ov-amount {
  margin: 6px 0 8px;
}
.ov-amount :deep(.money-display) {
  color: #fff;
  font-size: 36px;
  font-weight: 500;
  letter-spacing: -0.03em;
}
.ov-sub-row {
  display: flex;
  align-items: center;
  gap: 10px;
  font-size: 13px;
  opacity: 0.85;
}
.ov-daily {
  background: rgba(255, 119, 89, 0.25);
  color: var(--color-coral-soft);
  padding: 3px 10px;
  border-radius: 4px;
  font-size: 12px;
  font-weight: 500;
}
.ov-count {
  font-size: 13px;
  opacity: 0.75;
}
.ov-change.positive {
  color: #6ee7a0;
  font-weight: 500;
}
.ov-change.negative {
  color: var(--color-coral-soft);
  font-weight: 500;
}
.ov-detail {
  display: flex;
  align-items: center;
  justify-content: space-between;
  background: rgba(255, 255, 255, 0.08);
  border: 1px solid rgba(255, 255, 255, 0.12);
  border-radius: var(--radius-sm);
  padding: 12px 16px;
  margin-top: 12px;
}
[data-theme='dark'] .ov-detail {
  background: rgba(255, 255, 255, 0.05);
  border-color: rgba(255, 255, 255, 0.08);
}
.ov-detail-item {
  flex: 1;
  text-align: center;
}
.ov-detail-label {
  font-size: 12px;
  opacity: 0.6;
  letter-spacing: 0.3px;
}
.ov-detail-value {
  margin-top: 4px;
}
.ov-detail-value :deep(.money-display) {
  color: #fff;
  font-size: 16px;
  font-weight: 500;
}
.ov-detail-divider {
  width: 1px;
  height: 28px;
  background: rgba(255, 255, 255, 0.15);
}
</style>
