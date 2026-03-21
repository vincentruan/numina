<template>
  <div class="net-worth-card">
    <div class="nw-label">净资产</div>
    <div class="nw-amount">
      <MoneyDisplay :amount="netWorth" size="large" />
    </div>
    <div class="nw-change" :class="changeClass">
      {{ changeText }} vs 上月
    </div>
    <van-grid :column-num="2" :border="false" class="nw-grid">
      <van-grid-item>
        <div class="grid-label">总资产</div>
        <div class="grid-value positive">
          <MoneyDisplay :amount="totalAssets" />
        </div>
      </van-grid-item>
      <van-grid-item>
        <div class="grid-label">总负债</div>
        <div class="grid-value negative">
          <MoneyDisplay :amount="totalLiabilities" />
        </div>
      </van-grid-item>
    </van-grid>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import MoneyDisplay from '@/components/common/MoneyDisplay.vue'

const props = defineProps<{
  netWorth: number
  totalAssets: number
  totalLiabilities: number
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
.net-worth-card {
  background: linear-gradient(135deg, #1989fa 0%, #2b5cff 100%);
  padding: 24px 16px 16px;
  color: #fff;
}
.nw-label {
  font-size: 13px;
  opacity: 0.8;
}
.nw-amount {
  margin: 4px 0;
}
.nw-amount :deep(.money-display) {
  color: #fff;
}
.nw-change {
  font-size: 13px;
  margin-bottom: 12px;
}
.nw-change.positive {
  color: #a8f0c6;
}
.nw-change.negative {
  color: #ffb3b3;
}
.nw-grid {
  background: rgba(255, 255, 255, 0.15);
  border-radius: 8px;
}
.nw-grid :deep(.van-grid-item__content) {
  background: transparent;
  padding: 12px;
}
.grid-label {
  font-size: 12px;
  opacity: 0.8;
  color: #fff;
}
.grid-value {
  margin-top: 4px;
}
.grid-value :deep(.money-display) {
  color: #fff;
  font-size: 16px;
  font-weight: 500;
}
</style>