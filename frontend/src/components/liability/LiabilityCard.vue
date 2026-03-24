<template>
  <van-cell class="liability-card" clickable @click="$emit('click')">
    <template #icon>
      <div class="card-icon" :style="{ background: categoryColor }">
        {{ categoryIcon }}
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
  mortgage: { text: '房贷', icon: '🏠', color: '#1989fa' },
  car_loan: { text: '车贷', icon: '🚗', color: '#07c160' },
  credit_card: { text: '信用卡', icon: '💳', color: '#ff976a' },
  personal_loan: { text: '个人贷款', icon: '💰', color: '#ee0a24' },
  other: { text: '其他', icon: '📋', color: '#969799' }
}

const categoryText = computed(() => categoryMap[props.liability.category]?.text || props.liability.category)
const categoryIcon = computed(() => categoryMap[props.liability.category]?.icon || '📋')
const categoryColor = computed(() => categoryMap[props.liability.category]?.color || '#969799')
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
  font-size: 18px;
  margin-right: 10px;
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
</style>
