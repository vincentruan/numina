<template>
  <span class="money-display" :class="[colorClass, sizeClass]">
    <span class="money-sign">{{ sign }}</span>
    <span class="money-prefix">¥</span>
    <span class="money-value">{{ displayValue }}</span>
  </span>
</template>

<script setup lang="ts">
import { computed } from 'vue'

const props = withDefaults(defineProps<{
  amount: number
  size?: 'small' | 'normal' | 'large'
  showSign?: boolean
  colorful?: boolean
}>(), {
  size: 'normal',
  showSign: false,
  colorful: false
})

const displayValue = computed(() => {
  const abs = Math.abs(props.amount)
  if (abs >= 100000000) {
    return `${(abs / 100000000).toFixed(2)}亿`
  } else if (abs >= 10000) {
    return `${(abs / 10000).toFixed(2)}万`
  } else if (abs >= 1000) {
    return abs.toLocaleString('zh-CN', { minimumFractionDigits: 0, maximumFractionDigits: 0 })
  }
  return abs.toLocaleString('zh-CN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
})

const sign = computed(() => {
  if (!props.showSign) return ''
  return props.amount >= 0 ? '+' : '-'
})

const colorClass = computed(() => {
  if (!props.colorful) return ''
  return props.amount >= 0 ? 'money-positive' : 'money-negative'
})

const sizeClass = computed(() => `money-${props.size}`)
</script>

<style scoped>
.money-display {
  font-variant-numeric: tabular-nums;
  white-space: nowrap;
}
.money-prefix {
  margin-right: 1px;
}
.money-small {
  font-size: 12px;
}
.money-normal {
  font-size: 14px;
}
.money-large {
  font-size: 24px;
  font-weight: 600;
}
.money-positive {
  color: #07c160;
}
.money-negative {
  color: #ee0a24;
}
</style>
