<template>
  <van-cell class="liability-card" clickable @click="$emit('click')">
    <template #icon>
      <div class="card-icon" :style="{ background: categoryColor }">
        <svg class="icon-svg" aria-hidden="true">
          <use :href="`#${categoryIcon}`" />
        </svg>
      </div>
    </template>
    <template #title>
      <div class="card-title">
        <span class="name">{{ liability.name }}</span>
        <van-tag :type="liability.is_active ? 'primary' : 'default'" size="medium">
          {{ liability.is_active ? '还款中' : '已结清' }}
        </van-tag>
      </div>
    </template>
    <template #label>
      <div class="card-label">
        <span>{{ categoryText }}</span>
        <span v-if="liability.institution">{{ liability.institution }}</span>
        <span>月供 {{ currency.format(liability.monthly_payment) }}</span>
      </div>
    </template>
    <template #value>
      <div class="card-value">
        <MoneyDisplay :amount="liability.remaining_amount" size="normal" />
        <span class="rate">{{ liability.interest_rate }}%</span>
      </div>
    </template>
    <template #extra>
      <div class="card-progress">
        <van-progress
          :percentage="repaidPercent"
          color="linear-gradient(to right, #07c160, #34d058)"
          track-color="#f0f0f0"
          :show-pivot="false"
          stroke-width="4"
        />
        <div class="progress-label">
          <span>已还 {{ repaidPercent }}%</span>
          <span>剩余 {{ remainingWan }}</span>
        </div>
      </div>
    </template>
  </van-cell>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import type { Liability } from '@/types'
import MoneyDisplay from '@/components/common/MoneyDisplay.vue'
import { useCurrency } from '@/composables/useCurrency'

const props = defineProps<{
  liability: Liability
}>()

defineEmits<{
  click: []
}>()

const currency = useCurrency()

const categoryMap: Record<string, { text: string; icon: string; color: string }> = {
  mortgage: { text: '房贷', icon: 'icon-mortgage', color: '#1989fa' },
  car_loan: { text: '车贷', icon: 'icon-car-loan', color: '#07c160' },
  credit_card: { text: '信用卡', icon: 'icon-credit-card', color: '#ff976a' },
  personal_loan: { text: '个人贷款', icon: 'icon-personal-loan', color: '#ee0a24' },
  other: { text: '其他', icon: 'icon-other-liability', color: '#969799' }
}

const categoryText = computed(() => categoryMap[props.liability.category]?.text || props.liability.category)
const categoryIcon = computed(() => categoryMap[props.liability.category]?.icon || 'icon-other-liability')
const categoryColor = computed(() => categoryMap[props.liability.category]?.color || '#969799')

const repaidPercent = computed(() => {
  const { original_amount, remaining_amount } = props.liability
  if (!original_amount) return 0
  return Math.round(((original_amount - remaining_amount) / original_amount) * 100)
})

const remainingWan = computed(() => {
  const val = props.liability.remaining_amount
  if (val >= 10000) return `¥${(val / 10000).toFixed(1)}万`
  return `¥${val.toLocaleString()}`
})
</script>

<style scoped>
.liability-card {
  margin-bottom: 8px;
  border-radius: 8px;
}
.card-icon {
  width: 36px;
  height: 36px;
  border-radius: 8px;
  display: flex;
  align-items: center;
  justify-content: center;
  margin-right: 10px;
}
.icon-svg {
  width: 20px;
  height: 20px;
  fill: white;
  color: white;
}
.card-title {
  display: flex;
  align-items: center;
  gap: 6px;
}
.name {
  font-size: 14px;
  font-weight: 500;
  color: var(--text-primary);
}
.card-label {
  display: flex;
  gap: 8px;
  font-size: 12px;
  color: var(--text-tertiary);
  margin-top: 2px;
}
.card-value {
  text-align: right;
}
.rate {
  font-size: 11px;
  color: var(--text-tertiary);
  display: block;
  margin-top: 2px;
}
.card-progress {
  padding: 8px 0 2px;
}
.progress-label {
  display: flex;
  justify-content: space-between;
  font-size: 11px;
  color: var(--text-tertiary);
  margin-top: 4px;
}
</style>
