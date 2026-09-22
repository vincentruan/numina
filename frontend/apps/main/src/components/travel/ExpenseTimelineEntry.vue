<template>
  <div class="expense-entry" role="listitem" :aria-label="`${expense.description || 'Expense'}, ${expense.amount} ${expense.currency}`">
    <div class="expense-icon">
      <van-icon name="balance-o" size="18" />
    </div>
    <div class="expense-content">
      <div class="expense-desc">{{ expense.description || t('travel.itinerary.types.activity') }}</div>
    </div>
    <div class="expense-amount">
      {{ formatCost(expense.amount, expense.currency) }}
    </div>
  </div>
</template>

<script setup lang="ts">
import { useI18n } from 'vue-i18n'
import { useCurrency } from '@/composables/useCurrency'
import type { ExpenseEntry } from '@/types/travel'

defineProps<{
  expense: ExpenseEntry
}>()

const { t } = useI18n()
const { formatIn } = useCurrency()

function formatCost(amount: string, currency: string): string {
  return formatIn(amount, currency)
}
</script>

<style scoped>
.expense-entry {
  display: flex;
  align-items: center;
  padding: 8px 12px;
  margin: 4px 12px;
  gap: 8px;
  opacity: 0.75;
}

.expense-icon {
  width: 32px;
  height: 32px;
  border-radius: 8px;
  background: rgba(128, 128, 128, 0.1);
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--text-secondary);
  flex-shrink: 0;
}

.expense-content {
  flex: 1;
  min-width: 0;
}

.expense-desc {
  font-size: 13px;
  color: var(--text-secondary);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.expense-amount {
  font-size: 13px;
  font-weight: 500;
  color: var(--text-secondary);
  flex-shrink: 0;
}
</style>
