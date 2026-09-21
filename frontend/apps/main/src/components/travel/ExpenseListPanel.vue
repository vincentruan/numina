<template>
  <div class="expense-list-panel">
    <van-pull-refresh v-model="refreshing" @refresh="onRefresh">
      <template v-if="expenses.length === 0">
        <van-empty :description="t('travel.noExpenses')" />
      </template>

      <template v-else>
        <div v-for="(group, date) in groupedExpenses" :key="date" class="expense-group">
          <div class="group-header">{{ formatDate(date as string) }}</div>
          <van-swipe-cell v-for="expense in group" :key="expense.id">
            <van-cell
              :title="getCategoryName(expense.category_id)"
              :label="expense.description || ''"
              :value="formatAmount(expense.amount, expense.currency)"
              class="expense-item"
            >
              <template #icon>
                <van-icon :name="getCategoryIcon(expense.category_id)" size="24" class="category-icon" />
              </template>
            </van-cell>
            <template #right>
              <van-button
                square
                type="danger"
                :text="t('common.delete')"
                class="delete-button"
                @click="confirmDelete(expense.id)"
              />
            </template>
          </van-swipe-cell>
        </div>
      </template>
    </van-pull-refresh>
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { showSuccessToast, showFailToast, showConfirmDialog } from 'vant'
import { useTravelStore } from '@/stores/travel'
import { deleteExpense } from '@/api/travel'
import type { ExpenseEntry } from '@/types/travel'

const props = defineProps<{
  tripId: string
}>()

const { t, locale } = useI18n()
const store = useTravelStore()

const refreshing = ref(false)

const expenses = computed(() => store.expenses)

const groupedExpenses = computed(() => {
  const groups: Record<string, ExpenseEntry[]> = {}
  expenses.value.forEach(expense => {
    const date = expense.expense_date
    if (!groups[date]) {
      groups[date] = []
    }
    groups[date].push(expense)
  })
  return groups
})

function formatDate(dateStr: string): string {
  const date = new Date(dateStr)
  return date.toLocaleDateString(locale.value, { year: 'numeric', month: 'long', day: 'numeric' })
}

function formatAmount(amount: string, currency: string): string {
  const num = parseFloat(amount) || 0
  return `${currency} ${num.toLocaleString(locale.value, { minimumFractionDigits: 0, maximumFractionDigits: 0 })}`
}

function getCategoryName(categoryId: string | null): string {
  if (!categoryId) return '其他'
  const cat = store.categories.find(c => c.id === categoryId)
  return cat?.name || '其他'
}

function getCategoryIcon(categoryId: string | null): string {
  if (!categoryId) return 'balance-o'
  const cat = store.categories.find(c => c.id === categoryId)
  return cat?.icon || 'balance-o'
}

async function onRefresh() {
  try {
    await store.fetchExpenses(props.tripId)
  } finally {
    refreshing.value = false
  }
}

async function confirmDelete(expenseId: string) {
  try {
    await showConfirmDialog({
      title: t('travel.deleteExpense'),
      message: t('travel.deleteExpenseConfirm'),
    })
    await deleteExpense(props.tripId, expenseId)
    await store.fetchExpenses(props.tripId)
    showSuccessToast(t('common.success'))
  } catch {
    // user cancelled or error
  }
}
</script>

<style scoped>
.expense-list-panel {
  background: transparent;
}
.expense-group {
  margin: 12px;
}
.group-header {
  font-size: 14px;
  font-weight: 600;
  color: var(--text-secondary);
  padding: 8px 0;
  margin-bottom: 8px;
}
.expense-item {
  background: var(--card-bg);
  margin-bottom: 1px;
}
.category-icon {
  margin-right: 12px;
  color: var(--van-primary-color);
}
.delete-button {
  height: 100%;
}
</style>
