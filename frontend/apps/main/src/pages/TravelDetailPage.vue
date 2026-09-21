<template>
  <div class="travel-detail-page">
    <PageHeader :title="trip?.name || t('travel.tripDetail')">
      <template #right>
        <van-icon name="edit" size="20" @click="navigateToEdit" />
      </template>
    </PageHeader>

    <van-loading v-if="loading" class="page-loading" />

    <template v-else-if="trip">
      <!-- Status-adaptive layout -->
      <div class="status-section">
        <div v-if="trip.status === 'planning'" class="planning-layout">
          <div class="budget-breakdown">
            <div class="breakdown-item">
              <span class="label">{{ t('travel.plannedBudget') }}</span>
              <span class="value">{{ formatAmount(trip.planned_budget) }}</span>
            </div>
            <div class="breakdown-item">
              <span class="label">{{ t('travel.initialFunding') }}</span>
              <span class="value">{{ formatAmount(trip.initial_funding) }}</span>
            </div>
          </div>
        </div>

        <div v-else-if="trip.status === 'active'" class="active-layout">
          <div class="spend-vs-budget">
            <div class="budget-info">
              <span class="spent">{{ formatAmount(trip.actual_spend) }}</span>
              <span class="separator">/</span>
              <span class="total">{{ formatAmount(trip.planned_budget) }}</span>
            </div>
            <van-progress
              :percentage="budgetPercentage"
              :color="budgetPercentage > 100 ? '#ee0a24' : '#1989fa'"
              :stroke-width="8"
              :show-pivot="false"
            />
          </div>
        </div>

        <div v-else-if="trip.status === 'settled'" class="settled-layout">
          <div class="settled-summary">
            <van-icon name="success" color="#07c160" size="24" />
            <span>{{ t('travel.tripSettled') }}</span>
          </div>
          <!-- R14: Split summary above the fold for settled trips -->
          <div class="settled-split-summary">
            <div class="section-title">{{ t('travel.splitSummaryAboveFold') }}</div>
            <div class="budget-breakdown">
              <div class="breakdown-item">
                <span class="label">{{ t('travel.plannedBudget') }}</span>
                <span class="value">{{ formatAmount(trip.planned_budget) }}</span>
              </div>
              <div class="breakdown-item">
                <span class="label">{{ t('travel.actualSpend') }}</span>
                <span class="value">{{ formatAmount(trip.actual_spend) }}</span>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- Trip info card -->
      <van-cell-group inset class="info-card">
        <van-cell :title="t('travel.destination')" :value="trip.destination" />
        <van-cell v-if="trip.description" :title="t('travel.description')">
          <template #label>
            <span>{{ trip.description }}</span>
          </template>
        </van-cell>
        <van-cell :title="t('travel.departureDate')" :value="formatDate(trip.departure_date)" />
        <van-cell
          v-if="trip.return_date"
          :title="t('travel.returnDate')"
          :value="formatDate(trip.return_date)"
        />
        <van-cell :title="t('travel.currency')" :value="trip.currency" />
      </van-cell-group>

      <!-- Expense list section -->
      <van-cell-group inset class="expense-card">
        <van-cell :title="t('travel.expenses')">
          <template #label>
            <span class="expense-count">{{ expenses.length }} {{ t('travel.expenseEntries') }}</span>
          </template>
        </van-cell>
      </van-cell-group>
      <ExpenseListPanel :trip-id="trip.id" />

      <!-- Split group manager -->
      <SplitGroupManager :trip-id="trip.id" />

      <!-- Action buttons -->
      <div class="action-buttons">
        <van-button type="primary" block round @click="navigateToEdit">
          {{ t('common.edit') }}
        </van-button>
        <van-button
          v-if="trip.status === 'planning' || trip.status === 'active'"
          type="danger"
          block
          round
          @click="confirmCancel"
        >
          {{ t('travel.cancelTrip') }}
        </van-button>
      </div>

      <!-- FAB Button -->
      <div class="fab-button" @click="showActionSheet = true">
        <van-icon name="plus" size="24" color="#fff" />
      </div>

      <!-- Action Sheet -->
      <van-action-sheet v-model:show="showActionSheet" :actions="expenseActions" @select="onActionSelect" />

      <!-- Receipt Scan Popup -->
      <van-popup v-model:show="showReceiptScan" position="bottom" round destroy-on-close>
        <div style="padding: 16px;">
          <ReceiptScanButton :trip-id="trip!.id" />
        </div>
      </van-popup>
    </template>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { showSuccessToast, showFailToast, showConfirmDialog } from 'vant'
import { useTravelStore } from '@/stores/travel'
import { cancelTrip } from '@/api/travel'
import { useCurrency } from '@/composables/useCurrency'
import PageHeader from '@/components/common/PageHeader.vue'
import SplitGroupManager from '@/components/travel/SplitGroupManager.vue'
import ExpenseListPanel from '@/components/travel/ExpenseListPanel.vue'
import ReceiptScanButton from '@/components/travel/ReceiptScanButton.vue'

const { t, locale } = useI18n()
const route = useRoute()
const router = useRouter()
const store = useTravelStore()
const { formatIn } = useCurrency()

function formatAmount(amount: string | null): string {
  const currency = trip.value?.currency || 'CNY'
  if (!amount) return formatIn(0, currency)
  return formatIn(amount, currency)
}

const loading = ref(true)
const showActionSheet = ref(false)
const showReceiptScan = ref(false)

const trip = computed(() => store.currentTrip)
const expenses = computed(() => store.expenses)

const expenseActions = [
  { name: t('travel.photoReceipt'), value: 'photo' },
  { name: t('travel.manualEntry'), value: 'manual' },
]

const budgetPercentage = computed(() => {
  if (!trip.value?.planned_budget) return 0
  const spend = parseFloat(trip.value.actual_spend) || 0
  const budget = parseFloat(trip.value.planned_budget) || 0
  if (budget === 0) return 0
  return Math.min(Math.round((spend / budget) * 100), 100)
})

function formatDate(dateStr: string): string {
  const date = new Date(dateStr)
  return date.toLocaleDateString(locale.value, { year: 'numeric', month: 'long', day: 'numeric' })
}

function navigateToEdit() {
  if (trip.value) {
    router.push(`/travel/${trip.value.id}/edit`)
  }
}

function onActionSelect(action: { value: string }) {
  showActionSheet.value = false
  if (action.value === 'manual') {
    router.push(`/travel/${trip.value!.id}/expense/new`)
  } else if (action.value === 'photo') {
    showReceiptScan.value = true
  }
}

async function confirmCancel() {
  try {
    await showConfirmDialog({
      title: t('travel.cancelTrip'),
      message: t('travel.cancelTripConfirm'),
    })
    if (trip.value) {
      await cancelTrip(trip.value.id)
      await store.fetchTrip(trip.value.id)
      showSuccessToast(t('common.success'))
    }
  } catch {
    // user cancelled
  }
}

onMounted(async () => {
  const id = route.params.id as string
  if (id) {
    try {
      await Promise.all([
        store.fetchTrip(id),
        store.fetchExpenses(id),
      ])
    } catch {
      showFailToast(t('common.failed'))
    } finally {
      loading.value = false
    }
  } else {
    loading.value = false
  }
})
</script>

<style scoped>
.travel-detail-page {
  min-height: 100vh;
  background: var(--bg-secondary);
  padding-bottom: calc(16px + env(safe-area-inset-bottom));
}
.page-loading {
  display: flex;
  justify-content: center;
  padding: 40px 0;
}
.status-section {
  margin: 12px;
}
.planning-layout,
.active-layout {
  background: var(--card-bg);
  border-radius: 12px;
  padding: 16px;
  box-shadow: 0 1px 4px rgba(0, 0, 0, 0.06);
}
[data-theme='dark'] .planning-layout,
[data-theme='dark'] .active-layout {
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.28);
}
.budget-breakdown {
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.breakdown-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.breakdown-item .label {
  font-size: 14px;
  color: var(--text-secondary);
}
.breakdown-item .value {
  font-size: 16px;
  font-weight: 600;
  color: var(--text-primary);
}
.spend-vs-budget {
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.budget-info {
  display: flex;
  align-items: center;
  gap: 4px;
  font-size: 14px;
}
.budget-info .spent {
  font-size: 20px;
  font-weight: 700;
  color: var(--text-primary);
}
.budget-info .separator {
  color: var(--text-secondary);
}
.budget-info .total {
  color: var(--text-secondary);
}
.settled-layout {
  background: var(--card-bg);
  border-radius: 12px;
  padding: 16px;
  display: flex;
  align-items: center;
  gap: 12px;
  box-shadow: 0 1px 4px rgba(0, 0, 0, 0.06);
}
[data-theme='dark'] .settled-layout {
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.28);
}
.settled-summary {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 16px;
  font-weight: 600;
  color: var(--text-primary);
}
.info-card,
.budget-card,
.expense-card,
.split-card {
  margin: 12px;
}
.expense-count {
  font-size: 12px;
  color: var(--text-secondary);
}
.action-buttons {
  padding: 16px 12px;
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.fab-button {
  position: fixed;
  right: 20px;
  bottom: calc(80px + env(safe-area-inset-bottom));
  width: 56px;
  height: 56px;
  border-radius: 50%;
  background: var(--van-primary-color);
  display: flex;
  align-items: center;
  justify-content: center;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
  cursor: pointer;
  z-index: 100;
}
.fab-button:active {
  transform: scale(0.95);
}
</style>
