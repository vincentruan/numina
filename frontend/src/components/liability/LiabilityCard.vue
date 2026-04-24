<template>
  <div class="liability-card" @click="$emit('click')">
    <div class="card-header">
      <div class="card-icon" :style="{ background: categoryColor }">
        <svg class="icon-svg" aria-hidden="true">
          <use :href="`#${categoryIcon}`" />
        </svg>
      </div>
      <div class="card-header-text">
        <div class="card-title">
          <span class="name">{{ liability.name }}</span>
          <van-tag :type="liability.is_active ? 'danger' : 'success'" size="small" class="status-tag">
            {{ liability.is_active ? '还款中' : '已结清' }}
          </van-tag>
        </div>
        <div class="card-meta">
          <span class="meta-item">{{ categoryText }}</span>
          <span v-if="liability.institution" class="meta-item meta-divider">{{ liability.institution }}</span>
        </div>
      </div>
    </div>

    <div class="card-body">
      <div class="amount-section">
        <div class="amount-label">剩余本金</div>
        <div class="amount-value">¥{{ formatAmount(liability.remaining_amount) }}</div>
      </div>
      <div class="details-grid">
        <div class="detail-item">
          <span class="detail-label">月供</span>
          <span class="detail-value">¥{{ formatAmount(liability.monthly_payment) }}</span>
        </div>
        <div class="detail-item">
          <span class="detail-label">年利率</span>
          <span class="detail-value">{{ liability.interest_rate }}%</span>
        </div>
      </div>
    </div>

    <div v-if="liability.is_active" class="card-footer">
      <div class="progress-bar">
        <div class="progress-fill" :style="{ width: repaidPercent + '%' }" />
      </div>
      <div class="progress-text">
        <span class="progress-label">已还 {{ repaidPercent }}%</span>
        <span class="progress-remaining">剩余 ¥{{ formatAmount(liability.remaining_amount) }}</span>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import type { Liability } from '@/types'

const props = defineProps<{
  liability: Liability
}>()

defineEmits<{
  click: []
}>()

const categoryMap: Record<string, { text: string; icon: string; color: string }> = {
  mortgage: { text: '房贷', icon: 'icon-mortgage', color: '#d97706' },
  car_loan: { text: '车贷', icon: 'icon-car-loan', color: '#0891b2' },
  credit_card: { text: '信用卡', icon: 'icon-credit-card', color: '#dc2626' },
  personal_loan: { text: '个人贷款', icon: 'icon-personal-loan', color: '#ea580c' },
  other: { text: '其他', icon: 'icon-other-liability', color: '#64748b' }
}

const categoryText = computed(() => categoryMap[props.liability.category]?.text || props.liability.category)
const categoryIcon = computed(() => categoryMap[props.liability.category]?.icon || 'icon-other-liability')
const categoryColor = computed(() => categoryMap[props.liability.category]?.color || '#64748b')

const repaidPercent = computed(() => {
  const { original_amount, remaining_amount } = props.liability
  if (!original_amount) return 0
  return Math.round(((original_amount - remaining_amount) / original_amount) * 100)
})

function formatAmount(amount: number): string {
  if (amount >= 10000) {
    return (amount / 10000).toFixed(1) + '万'
  }
  return amount.toLocaleString('zh-CN')
}
</script>

<style scoped>
@import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Sans:wght@400;500;600&family=Crimson+Pro:wght@600&display=swap');

.liability-card {
  background: var(--card-bg);
  border-radius: 16px;
  padding: 16px;
  margin-bottom: 12px;
  cursor: pointer;
  transition: all 0.2s cubic-bezier(0.4, 0, 0.2, 1);
  border: 1px solid rgba(0, 0, 0, 0.06);
}

[data-theme='dark'] .liability-card {
  border-color: rgba(255, 255, 255, 0.08);
}

.liability-card:active {
  transform: scale(0.98);
}

.card-header {
  display: flex;
  align-items: flex-start;
  gap: 12px;
  margin-bottom: 16px;
}

.card-icon {
  width: 44px;
  height: 44px;
  border-radius: 12px;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.12);
}

[data-theme='dark'] .card-icon {
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.3);
}

.icon-svg {
  width: 24px;
  height: 24px;
  fill: white;
  color: white;
}

.card-header-text {
  flex: 1;
  min-width: 0;
}

.card-title {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 6px;
}

.name {
  font-family: 'IBM Plex Sans', -apple-system, sans-serif;
  font-size: 16px;
  font-weight: 600;
  color: var(--text-primary);
  flex: 1;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.status-tag {
  flex-shrink: 0;
}

.card-meta {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 13px;
  color: var(--text-tertiary);
}

.meta-item {
  white-space: nowrap;
}

.meta-divider::before {
  content: '·';
  margin-right: 8px;
  color: var(--text-quaternary);
}

.card-body {
  padding: 16px 0;
  border-top: 1px solid rgba(0, 0, 0, 0.06);
  border-bottom: 1px solid rgba(0, 0, 0, 0.06);
}

[data-theme='dark'] .card-body {
  border-color: rgba(255, 255, 255, 0.08);
}

.amount-section {
  margin-bottom: 16px;
}

.amount-label {
  font-size: 12px;
  color: var(--text-tertiary);
  margin-bottom: 4px;
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

.amount-value {
  font-family: 'Crimson Pro', Georgia, serif;
  font-size: 32px;
  font-weight: 600;
  color: #dc2626;
  line-height: 1.2;
  letter-spacing: -0.5px;
}

[data-theme='dark'] .amount-value {
  color: #f87171;
}

.details-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 16px;
}

.detail-item {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.detail-label {
  font-size: 12px;
  color: var(--text-tertiary);
}

.detail-value {
  font-family: 'IBM Plex Sans', -apple-system, sans-serif;
  font-size: 15px;
  font-weight: 500;
  color: var(--text-primary);
}

.card-footer {
  margin-top: 16px;
}

.progress-bar {
  height: 8px;
  background: rgba(220, 38, 38, 0.1);
  border-radius: 4px;
  overflow: hidden;
  margin-bottom: 8px;
}

[data-theme='dark'] .progress-bar {
  background: rgba(248, 113, 113, 0.15);
}

.progress-fill {
  height: 100%;
  background: linear-gradient(90deg, #10b981 0%, #059669 100%);
  border-radius: 4px;
  transition: width 0.6s cubic-bezier(0.4, 0, 0.2, 1);
}

.progress-text {
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-size: 12px;
}

.progress-label {
  color: #059669;
  font-weight: 500;
}

[data-theme='dark'] .progress-label {
  color: #34d399;
}

.progress-remaining {
  color: var(--text-tertiary);
}
</style>
