<template>
  <van-cell-group inset class="upcoming-payments-card">
    <div class="card-header">
      <span class="card-title">{{ t('dashboard.upcomingPayments.title') }}</span>
    </div>
    <div
      v-for="item in payments"
      :key="item.liability_id"
      class="payment-row"
      :class="urgencyClass(daysUntil(item.due_date))"
      @click="$router.push(`/liabilities/${item.liability_id}`)"
    >
      <div class="payment-info">
        <div class="payment-name">{{ item.name }}</div>
        <div class="payment-date">{{ item.due_date }}</div>
      </div>
      <div class="payment-right">
        <div class="payment-amount">¥{{ (item.amount ?? 0).toLocaleString() }}</div>
        <div class="payment-days" :class="urgencyClass(daysUntil(item.due_date))">
          {{ daysLabel(daysUntil(item.due_date)) }}
        </div>
      </div>
    </div>
  </van-cell-group>
</template>

<script setup lang="ts">
import { useI18n } from 'vue-i18n'
import { useRouter } from 'vue-router'
import type { UpcomingPaymentItem } from '@/api/dashboard'

defineProps<{
  payments: UpcomingPaymentItem[]
}>()

const { t } = useI18n()
const router = useRouter()

function daysUntil(dueDateStr: string): number {
  const today = new Date()
  today.setHours(0, 0, 0, 0)
  const due = new Date(dueDateStr)
  due.setHours(0, 0, 0, 0)
  return Math.max(0, Math.round((due.getTime() - today.getTime()) / 86_400_000))
}

function urgencyClass(days: number): string {
  if (days <= 3) return 'urgency--danger'
  if (days <= 7) return 'urgency--warning'
  return 'urgency--default'
}

function daysLabel(days: number): string {
  if (days === 0) return t('liability.countdown.today')
  return t('liability.countdown.daysLeft', { days })
}
</script>

<style scoped>
.upcoming-payments-card {
  margin: 8px 12px;
}

.card-header {
  padding: 12px 16px 8px;
  border-bottom: 1px solid rgba(0, 0, 0, 0.06);
}

[data-theme='dark'] .card-header {
  border-color: rgba(255, 255, 255, 0.08);
}

.card-title {
  font-size: 14px;
  font-weight: 600;
  color: var(--text-primary);
}

.payment-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 10px 16px;
  cursor: pointer;
  border-bottom: 1px solid rgba(0, 0, 0, 0.04);
  gap: 12px;
  min-height: 44px;
}

.payment-row:last-child {
  border-bottom: none;
}

.payment-row:active {
  background: rgba(0, 0, 0, 0.03);
}

[data-theme='dark'] .payment-row:active {
  background: rgba(255, 255, 255, 0.04);
}

.payment-info {
  flex: 1;
  min-width: 0;
}

.payment-name {
  font-size: 14px;
  font-weight: 500;
  color: var(--text-primary);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.payment-date {
  font-size: 12px;
  color: var(--text-tertiary);
  margin-top: 2px;
}

.payment-right {
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  gap: 4px;
  flex-shrink: 0;
}

.payment-amount {
  font-size: 14px;
  font-weight: 600;
  color: var(--text-primary);
}

.payment-days {
  font-size: 11px;
  font-weight: 500;
  padding: 2px 6px;
  border-radius: 4px;
}

.urgency--danger .payment-days,
.payment-days.urgency--danger {
  background: rgba(220, 38, 38, 0.08);
  color: #dc2626;
}

[data-theme='dark'] .urgency--danger .payment-days,
[data-theme='dark'] .payment-days.urgency--danger {
  background: rgba(248, 113, 113, 0.15);
  color: #f87171;
}

.urgency--warning .payment-days,
.payment-days.urgency--warning {
  background: rgba(217, 119, 6, 0.08);
  color: #d97706;
}

[data-theme='dark'] .urgency--warning .payment-days,
[data-theme='dark'] .payment-days.urgency--warning {
  background: rgba(251, 191, 36, 0.15);
  color: #fbbf24;
}

.urgency--default .payment-days,
.payment-days.urgency--default {
  background: rgba(0, 0, 0, 0.04);
  color: var(--text-secondary);
}

[data-theme='dark'] .urgency--default .payment-days,
[data-theme='dark'] .payment-days.urgency--default {
  background: rgba(255, 255, 255, 0.06);
  color: var(--text-secondary);
}
</style>
