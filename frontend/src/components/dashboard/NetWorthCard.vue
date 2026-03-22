<template>
  <div class="overview-card">
    <div class="ov-main">
      <div class="ov-label">总资产</div>
      <div class="ov-amount">
        <MoneyDisplay :amount="totalAssets" size="large" />
      </div>
      <div class="ov-sub-row">
        <span v-if="totalDailyCost > 0" class="ov-daily">日均 ¥{{ totalDailyCost.toFixed(2) }}</span>
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

const props = defineProps<{
  netWorth: number
  totalAssets: number
  totalLiabilities: number
  totalDailyCost: number
  assetCount: number
  monthOverMonthChange?: number | null
}>()

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
  background: linear-gradient(135deg, #1677ff 0%, #0052d9 50%, #2b3a8e 100%);
  padding: 24px 20px 16px;
  color: #fff;
}
.ov-label {
  font-size: 14px;
  opacity: 0.85;
  letter-spacing: 0.5px;
}
.ov-amount {
  margin: 6px 0 8px;
}
.ov-amount :deep(.money-display) {
  color: #fff;
}
.ov-sub-row {
  display: flex;
  align-items: center;
  gap: 10px;
  font-size: 12px;
  opacity: 0.9;
  margin-bottom: 14px;
}
.ov-daily {
  background: rgba(255, 255, 255, 0.2);
  padding: 2px 10px;
  border-radius: 10px;
  font-size: 11px;
  backdrop-filter: blur(4px);
}
.ov-count {
  font-size: 12px;
}
.ov-change.positive {
  color: #7dffa8;
}
.ov-change.negative {
  color: #ffb3b3;
}
.ov-detail {
  display: flex;
  align-items: center;
  background: rgba(255, 255, 255, 0.12);
  border-radius: 10px;
  padding: 12px 0;
}
.ov-detail-item {
  flex: 1;
  text-align: center;
}
.ov-detail-label {
  font-size: 12px;
  opacity: 0.75;
}
.ov-detail-value {
  margin-top: 4px;
}
.ov-detail-value :deep(.money-display) {
  color: #fff;
  font-size: 16px;
  font-weight: 600;
}
.ov-detail-divider {
  width: 1px;
  height: 30px;
  background: rgba(255, 255, 255, 0.25);
}
</style>
