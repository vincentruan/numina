<template>
  <div class="liability-list-panel">
    <!-- Skeleton for initial loading -->
    <LiabilityListSkeleton v-if="liabilityStore.loading && liabilityStore.liabilities.length === 0" />

    <!-- Actual Content -->
    <template v-else>
      <van-tabs v-model:active="activeTab" @change="onTabChange">
        <van-tab :title="t('liability.tabActive')" name="active" />
        <van-tab :title="t('liability.tabInactive')" name="inactive" />
      </van-tabs>

      <!-- B1 教育奖励支出统计（归位于负债域：家庭支出流水；点击下钻活动明细） -->
      <EducationRewardCard />

      <!-- Filter / Sort bar -->
      <div class="filter-bar">
        <div class="filter-chips">
          <button
            class="chip"
            :class="{ active: filterCategory === '' }"
            @click="filterCategory = ''"
          >{{ t('liability.filterAll') }}</button>
          <button
            v-for="cat in categories"
            :key="cat.value"
            class="chip"
            :class="{ active: filterCategory === cat.value }"
            @click="filterCategory = cat.value"
          >
            <span class="chip-icon" :style="{ background: cat.color }">
              <SvgIcon :name="cat.icon" class="chip-svg" />
            </span>
            {{ cat.label }}
          </button>
        </div>
        <button class="sort-btn" @click="toggleSort">
          <van-icon name="sort" size="16" />
          <span>{{ sortLabel }}</span>
        </button>
      </div>

      <!-- Select-mode cancel (page-level PageHeader is gone in the panel) -->
      <div v-if="selectMode" class="panel-select-bar">
        <span class="select-cancel" role="button" tabindex="0" @click="exitSelectMode" @keydown.enter="exitSelectMode" @keydown.space.prevent="exitSelectMode">{{ t('liability.cancelSelect') }}</span>
      </div>

      <!-- L1 (Plan B T9): payoff strategy card (only when ≥2 active liabilities). -->
      <LiabilityStrategyCard :liabilities="liabilityStore.liabilities" @adopt="onStrategyAdopt" />

      <!-- Summary Banner -->
      <div v-if="liabilityStore.liabilities.length" class="summary-banner">
        <div class="summary-top">
          <div class="summary-main">
            <div class="summary-label">{{ activeTab === 'active' ? t('liability.summaryTotal') : t('liability.summarySettled') }}</div>
            <div class="summary-amount">{{ formatAmountDisplay(totalAmount) }}</div>
          </div>
          <div class="summary-count">
            <span class="count-num">{{ filteredLiabilities.length }}</span>
            <span class="count-unit">{{ t('liability.countUnit') }}</span>
          </div>
        </div>
        <template v-if="activeTab === 'active' && totalOriginal > 0">
          <div class="summary-progress-bar">
            <div class="summary-progress-fill" :style="{ width: repaidPercent + '%' }" />
          </div>
          <div class="summary-progress-text">
            <span>{{ t('liability.summaryProgress') }}</span>
            <span class="summary-percent">{{ repaidPercent }}%</span>
          </div>
        </template>
      </div>

      <!-- L3: Monthly payment total banner (active tab only; hide-if-zero) -->
      <div
        v-if="activeTab === 'active' && totalMonthlyPayment > 0"
        class="monthly-payment-banner"
      >
        <span class="mp-label">{{ t('liability.monthlyPaymentTotal') }}</span>
        <span class="mp-amount">{{ formatCurrencyAmount(totalMonthlyPayment) }}</span>
        <span v-if="hasEstimatedItems" class="mp-estimated">{{ t('liability.monthlyPaymentEstimated') }}</span>
      </div>

      <div v-if="filteredLiabilities.length" class="liability-list">
        <LiabilityCard
          v-for="item in filteredLiabilities"
          :key="item.id"
          :liability="item"
          :select-mode="selectMode"
          :selected="selectedIds.has(item.id)"
          @click="onCardClick(item)"
          @longpress="onLongPress(item)"
          @pay="openPayDialog"
          @edit="goEdit"
          @delete="confirmDelete"
        />
      </div>
      <EmptyState v-else :description="activeTab === 'active' ? t('liability.noLiabilityDesc') : t('liability.noSettledLiability')">
        <van-button v-if="activeTab === 'active'" size="small" type="primary" @click="$router.push('/liabilities/new')">
          {{ t('liability.addLiability') }}
        </van-button>
      </EmptyState>

      <!-- Batch action bar -->
      <Transition name="slide-up">
        <div v-if="selectMode" class="batch-bar">
          <span class="batch-count">{{ t('liability.batchCount', { count: selectedIds.size }) }}</span>
          <div class="batch-actions">
            <van-button size="small" plain @click="selectAll">{{ t('liability.batchSelectAll') }}</van-button>
            <van-button
              v-if="activeTab === 'active'"
              size="small"
              type="success"
              :disabled="selectedIds.size === 0"
              @click="batchSettle"
            >{{ t('liability.batchSettle') }}</van-button>
            <van-button
              size="small"
              type="danger"
              :disabled="selectedIds.size === 0"
              @click="batchDelete"
            >{{ t('liability.batchDelete') }}</van-button>
          </div>
        </div>
      </Transition>

      <!-- FAB (hidden in select mode) -->
      <div v-if="!selectMode" class="fab" role="button" tabindex="0" @click="$router.push('/liabilities/new')" @keydown.enter="$router.push('/liabilities/new')" @keydown.space.prevent="$router.push('/liabilities/new')">
        <van-icon name="plus" size="22" />
      </div>

      <!-- Quick payment dialog -->
      <van-dialog
        v-model:show="payDialogVisible"
        :title="t('liability.payDialogTitle', { name: payTarget?.name ?? '' })"
        show-cancel-button
        :confirm-button-text="t('liability.payConfirmBtn')"
        confirm-button-color="#059669"
        @confirm="submitPayment"
      >
        <div class="pay-dialog-body">
          <div class="pay-hint">{{ t('liability.payRemainingHint', { amount: payTarget ? formatAmountDisplay(payTarget.remaining_amount) : '' }) }}</div>
          <van-field
            v-model="payAmount"
            type="number"
            :placeholder="t('liability.payPlaceholder')"
            input-align="center"
            autofocus
            :formatter="(v: string) => v.replace(/[^0-9.]/g, '')"
          />
          <div class="pay-quick-btns">
            <button
              v-for="pct in [25, 50, 100]"
              :key="pct"
              class="quick-pct-btn"
              @click="setPayPercent(pct)"
            >{{ pct === 100 ? t('liability.payFull') : pct + '%' }}</button>
          </div>
        </div>
      </van-dialog>

      <!-- Destructive confirm: single delete -->
      <BottomSheetConfirm
        v-model:show="deleteSheet.show"
        :title="t('common.confirm')"
        :description="deleteSheet.description"
        :impact-preview="t('bottomSheet.impactLiabilityDelete')"
        @confirm="executeDelete"
      />

      <!-- Destructive confirm: batch settle -->
      <BottomSheetConfirm
        v-model:show="settleSheet.show"
        :title="t('common.confirm')"
        :description="settleSheet.description"
        :impact-preview="t('bottomSheet.impactLiabilityBatchSettle')"
        @confirm="executeBatchSettle"
      />

      <!-- Destructive confirm: batch delete -->
      <BottomSheetConfirm
        v-model:show="batchDeleteSheet.show"
        :title="t('common.confirm')"
        :description="batchDeleteSheet.description"
        :impact-preview="t('bottomSheet.impactLiabilityBatchDelete')"
        @confirm="executeBatchDelete"
      />
    </template>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, nextTick } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { showToast, showSuccessToast } from 'vant'
import BottomSheetConfirm from '@/components/BottomSheetConfirm.vue'
import { useI18n } from 'vue-i18n'
import { useCurrency } from '@/composables/useCurrency'
import { useLiabilityStore } from '@/stores/liability'
import type { Liability } from '@/types'
import EmptyState from '@/components/common/EmptyState.vue'
import LiabilityCard from '@/components/liability/LiabilityCard.vue'
import LiabilityListSkeleton from '@/components/liability/LiabilityListSkeleton.vue'
import LiabilityStrategyCard from '@/components/liability/LiabilityStrategyCard.vue'
import EducationRewardCard from '@/components/finance/EducationRewardCard.vue'
import SvgIcon from '@/components/SvgIcon.vue'

const { t } = useI18n()
const { format: formatCurrencyAmount } = useCurrency()
const router = useRouter()
const route = useRoute()
const liabilityStore = useLiabilityStore()

const activeTab = ref('active')

// --- Filter / Sort ---
const filterCategory = ref('')
const sortOrder = ref<'default' | 'asc' | 'desc'>('default')

const categories = computed(() => [
  { value: 'mortgage', label: t('liability.mortgage'), icon: 'mortgage', color: '#6366f1' },
  { value: 'car_loan', label: t('liability.carLoan'), icon: 'car-loan', color: '#0ea5e9' },
  { value: 'credit_card', label: t('liability.creditCard'), icon: 'credit-card', color: '#f59e0b' },
  { value: 'consumer_loan', label: t('liability.consumerLoan'), icon: 'wealth', color: '#10b981' },
  { value: 'personal_loan', label: t('liability.personalLoan'), icon: 'personal-loan', color: '#8b5cf6' },
  { value: 'other', label: t('liability.other'), icon: 'other-liability', color: '#6b7280' },
])

const sortLabel = computed(() => {
  if (sortOrder.value === 'asc') return t('liability.sortAsc')
  if (sortOrder.value === 'desc') return t('liability.sortDesc')
  return t('liability.sortLabel')
})

function toggleSort() {
  if (sortOrder.value === 'default') sortOrder.value = 'desc'
  else if (sortOrder.value === 'desc') sortOrder.value = 'asc'
  else sortOrder.value = 'default'
}

// U5: strategy-driven sort from LiabilityStrategyCard adoption.
const strategySort = ref<'avalanche' | 'snowball' | null>(null)

// Destructive confirm sheets
const deleteSheet = ref({ show: false, description: '', liabilityId: '' as string })
const settleSheet = ref({ show: false, description: '' })
const batchDeleteSheet = ref({ show: false, description: '' })

function onStrategyAdopt(strategy: 'avalanche' | 'snowball' | null) {
  strategySort.value = strategy
}

const filteredLiabilities = computed(() => {
  let list = liabilityStore.liabilities
  if (filterCategory.value) {
    list = list.filter(l => l.category === filterCategory.value)
  }
  // Strategy sort takes priority over manual sort when adopted.
  if (strategySort.value === 'avalanche') {
    list = [...list].sort((a, b) => (b.interest_rate ?? 0) - (a.interest_rate ?? 0))
  } else if (strategySort.value === 'snowball') {
    list = [...list].sort((a, b) => Number(a.remaining_amount ?? 0) - Number(b.remaining_amount ?? 0))
  } else if (sortOrder.value === 'desc') {
    list = [...list].sort((a, b) => Number(b.remaining_amount) - Number(a.remaining_amount))
  } else if (sortOrder.value === 'asc') {
    list = [...list].sort((a, b) => Number(a.remaining_amount) - Number(b.remaining_amount))
  }
  return list
})

// --- Summary ---
const totalAmount = computed(() =>
  liabilityStore.liabilities.reduce((sum, l) => sum + Number(l.remaining_amount), 0)
)
const totalOriginal = computed(() =>
  liabilityStore.liabilities.reduce((sum, l) => sum + Number(l.original_amount ?? l.remaining_amount), 0)
)
const repaidPercent = computed(() => {
  if (totalOriginal.value <= 0) return 0
  return Math.round(((totalOriginal.value - totalAmount.value) / totalOriginal.value) * 100)
})

// --- L3: Monthly payment total banner ---
// Interest-only estimate for liabilities without an explicit monthly_payment.
function monthlyInterest(l: Liability): number {
  const rate = (l.interest_rate ?? 0) / 100 / 12
  return Number(l.remaining_amount ?? 0) * rate
}
// Active liabilities only — inactive items would inflate the total.
const activeLiabilitiesForPayment = computed(() =>
  liabilityStore.liabilities.filter(l => l.is_active === true),
)
const totalMonthlyPayment = computed(() =>
  activeLiabilitiesForPayment.value.reduce(
    (sum, l) => sum + (l.monthly_payment != null ? Number(l.monthly_payment) : monthlyInterest(l)),
    0,
  ),
)
// When any active liability has a null monthly_payment, the total is an
// estimate (interest-only fallback) — annotate it honestly.
const hasEstimatedItems = computed(() =>
  activeLiabilitiesForPayment.value.some(l => l.monthly_payment == null),
)

function formatAmountDisplay(amount: number | string): string {
  const n = Number(amount)
  if (n >= 100000000) return (n / 100000000).toFixed(2) + t('common.unitHundredMillion')
  if (n >= 10000) return (n / 10000).toFixed(1) + t('common.unitTenThousand')
  if (n >= 1000) return (n / 1000).toFixed(1) + t('common.unitThousand')
  return n.toLocaleString('zh-CN')
}

// --- Tab ---
function onTabChange() {
  exitSelectMode()
  filterCategory.value = ''
  sortOrder.value = 'default'
  liabilityStore.fetchLiabilities({ is_active: activeTab.value === 'active' })
}

// --- Card actions ---
function onCardClick(item: Liability) {
  if (selectMode.value) {
    toggleSelect(item.id)
  } else {
    router.push(`/liabilities/${item.id}`)
  }
}

function goEdit(item: Liability) {
  router.push(`/liabilities/${item.id}/edit`)
}

function confirmDelete(item: Liability) {
  deleteSheet.value.description = t('toast.confirmDelete', { name: item.name })
  deleteSheet.value.liabilityId = item.id
  deleteSheet.value.show = true
}

async function executeDelete() {
  await liabilityStore.deleteLiability(deleteSheet.value.liabilityId)
  showSuccessToast(t('toast.deleteSuccess'))
  deleteSheet.value.show = false
}

// --- Quick payment ---
const payDialogVisible = ref(false)
const payTarget = ref<Liability | null>(null)
const payAmount = ref('')

function openPayDialog(item: Liability) {
  payTarget.value = item
  payAmount.value = ''
  payDialogVisible.value = true
}

function setPayPercent(pct: number) {
  if (!payTarget.value) return
  const val = (Number(payTarget.value.remaining_amount) * pct) / 100
  payAmount.value = val.toFixed(2)
}

async function submitPayment() {
  const amount = parseFloat(payAmount.value)
  if (!amount || amount <= 0) {
    showToast(t('toast.paymentAmountRequired'))
    return
  }
  if (payTarget.value && amount > Number(payTarget.value.remaining_amount)) {
    showToast(t('toast.paymentExceedsBalance'))
    return
  }
  await liabilityStore.recordPayment(payTarget.value!.id, amount)
  showSuccessToast(t('toast.paymentSuccess'))
  payDialogVisible.value = false
}

// --- Long-press multi-select ---
const selectMode = ref(false)
const selectedIds = ref(new Set<string>())

function onLongPress(item: Liability) {
  selectMode.value = true
  selectedIds.value = new Set([item.id])
}

function toggleSelect(id: string) {
  const next = new Set(selectedIds.value)
  if (next.has(id)) next.delete(id)
  else next.add(id)
  selectedIds.value = next
}

function selectAll() {
  selectedIds.value = new Set(filteredLiabilities.value.map(l => l.id))
}

function exitSelectMode() {
  selectMode.value = false
  selectedIds.value = new Set()
}

async function batchSettle() {
  if (selectedIds.value.size === 0) {
    showToast(t('toast.liabilitySelectFirst'))
    return
  }
  settleSheet.value.description = t('toast.confirmSettleBatch', { count: selectedIds.value.size })
  settleSheet.value.show = true
}

async function executeBatchSettle() {
  await Promise.all(
    [...selectedIds.value].map(id => liabilityStore.updateLiability(id, { is_active: false }))
  )
  showToast(t('toast.liabilitySettledBatch', { count: selectedIds.value.size }))
  exitSelectMode()
  settleSheet.value.show = false
  liabilityStore.fetchLiabilities({ is_active: true })
}

async function batchDelete() {
  if (selectedIds.value.size === 0) {
    showToast(t('toast.liabilitySelectFirst'))
    return
  }
  batchDeleteSheet.value.description = t('toast.confirmDeleteBatch', { count: selectedIds.value.size })
  batchDeleteSheet.value.show = true
}

async function executeBatchDelete() {
  await Promise.all([...selectedIds.value].map(id => liabilityStore.deleteLiability(id)))
  showToast(t('toast.liabilityDeleteBatch', { count: selectedIds.value.size }))
  exitSelectMode()
  batchDeleteSheet.value.show = false
}

liabilityStore.fetchLiabilities({ is_active: true })

// W5 (Plan B T8): handle the ?focus=liability_strategy deep link (spec §5.3: avoid
// 断链). Migrated from LiabilityListPage — FinanceHubPage now hosts this panel under
// /finance?tab=liabilities&focus=liability_strategy. Scroll to the L1 strategy card.
onMounted(() => {
  if (route.query.focus !== 'liability_strategy') return
  nextTick(() => {
    const el = document.querySelector('.liability-strategy-card')
    if (el) {
      el.scrollIntoView({ behavior: 'smooth' })
    } else {
      window.scrollTo({ top: 0, behavior: 'smooth' })
    }
  })
})

defineExpose({
  activeTab,
  filterCategory,
  sortOrder,
  strategySort,
  filteredLiabilities,
  totalAmount,
  totalMonthlyPayment,
  hasEstimatedItems,
  selectMode,
  selectedIds,
  onTabChange,
  toggleSort,
  onStrategyAdopt,
  onLongPress,
  toggleSelect,
  selectAll,
  exitSelectMode,
})
</script>

<style scoped>
/* Select-mode cancel bar (replaces the page-level PageHeader cancel slot) */
.panel-select-bar {
  display: flex;
  justify-content: flex-end;
  padding: 4px 12px;
}
.select-cancel {
  font-size: 14px;
  color: var(--van-primary-color);
  padding: 4px 8px;
}

/* Filter bar */
.filter-bar {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 12px;
  background: var(--bg-primary);
  border-bottom: 1px solid rgba(0, 0, 0, 0.06);
  overflow-x: auto;
  scrollbar-width: none;
}

.filter-bar::-webkit-scrollbar {
  display: none;
}

.filter-chips {
  display: flex;
  gap: 6px;
  flex: 1;
  overflow-x: auto;
  scrollbar-width: none;
}

.filter-chips::-webkit-scrollbar {
  display: none;
}

.chip {
  flex-shrink: 0;
  display: inline-flex;
  align-items: center;
  gap: 5px;
  padding: 4px 14px 4px 8px;
  border-radius: 30px;
  border: 1px solid rgba(0, 0, 0, 0.18);
  background: transparent;
  font-size: 13px;
  color: var(--text-secondary);
  cursor: pointer;
  transition: all 0.15s;
  white-space: nowrap;
}

.chip-icon {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 18px;
  height: 18px;
  border-radius: 50%;
  flex-shrink: 0;
}

.chip-svg {
  width: 11px;
  height: 11px;
  fill: white;
  color: white;
}

.chip.active {
  background: var(--van-primary-color);
  border-color: var(--van-primary-color);
  color: var(--color-on-primary);
}

[data-theme='dark'] .chip {
  border-color: rgba(255, 255, 255, 0.2);
}

[data-theme='dark'] .chip.active {
  background: var(--color-lavender);
  border-color: var(--color-lavender);
  color: #010120;
}

.sort-btn {
  flex-shrink: 0;
  display: flex;
  align-items: center;
  gap: 4px;
  padding: 4px 10px;
  border-radius: 20px;
  border: 1px solid rgba(0, 0, 0, 0.12);
  background: transparent;
  font-size: 13px;
  color: var(--text-secondary);
  cursor: pointer;
}

[data-theme='dark'] .sort-btn {
  border-color: rgba(255, 255, 255, 0.15);
}

/* Summary Banner */
.summary-banner {
  margin: 12px 12px 4px;
  background: linear-gradient(135deg, #991b1b 0%, #dc2626 60%, #ea580c 100%);
  border-radius: 16px;
  padding: 20px;
  color: #fff;
}

.monthly-payment-banner {
  margin: 8px 12px 4px;
  background: var(--bg-card, #fff);
  border: 1px solid var(--border-color, #e5e7eb);
  border-radius: 12px;
  padding: 12px 16px;
  display: flex;
  align-items: center;
  gap: 8px;
}

.monthly-payment-banner .mp-label {
  font-size: 13px;
  color: var(--text-secondary, #6b7280);
}

.monthly-payment-banner .mp-amount {
  font-family: 'Crimson Pro', Georgia, serif;
  font-size: 20px;
  font-weight: 600;
  color: var(--text-primary, #111827);
}

.monthly-payment-banner .mp-estimated {
  font-size: 11px;
  color: var(--color-warning, #d97706);
  border: 1px solid var(--color-warning, #d97706);
  border-radius: 4px;
  padding: 1px 5px;
  line-height: 1.4;
}

.summary-top {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  margin-bottom: 16px;
}

.summary-label {
  font-size: 13px;
  opacity: 0.8;
  margin-bottom: 6px;
  letter-spacing: 0.3px;
}

.summary-amount {
  font-family: 'Crimson Pro', Georgia, serif;
  font-size: 36px;
  font-weight: 600;
  line-height: 1.1;
  letter-spacing: -0.5px;
}

.summary-count {
  text-align: right;
  padding-top: 4px;
}

.count-num {
  font-family: 'IBM Plex Sans', -apple-system, sans-serif;
  font-size: 28px;
  font-weight: 600;
  line-height: 1;
}

.count-unit {
  font-size: 14px;
  opacity: 0.8;
  margin-left: 2px;
}

.summary-progress-bar {
  height: 6px;
  background: rgba(255, 255, 255, 0.25);
  border-radius: 3px;
  overflow: hidden;
  margin-bottom: 8px;
}

.summary-progress-fill {
  height: 100%;
  background: rgba(255, 255, 255, 0.9);
  border-radius: 3px;
  transition: width 0.6s cubic-bezier(0.4, 0, 0.2, 1);
}

.summary-progress-text {
  display: flex;
  justify-content: space-between;
  font-size: 12px;
  opacity: 0.85;
}

.summary-percent {
  font-weight: 600;
}

/* List */
.liability-list {
  padding: 8px 12px 0;
}

/* Batch bar */
.batch-bar {
  position: fixed;
  bottom: 0;
  left: 0;
  right: 0;
  background: var(--bg-primary);
  border-top: 1px solid rgba(0, 0, 0, 0.08);
  padding: 12px 16px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  z-index: 20;
  padding-bottom: calc(12px + env(safe-area-inset-bottom));
}

[data-theme='dark'] .batch-bar {
  border-color: rgba(255, 255, 255, 0.08);
}

.batch-count {
  font-size: 14px;
  color: var(--text-secondary);
}

.batch-actions {
  display: flex;
  gap: 8px;
}

.slide-up-enter-active,
.slide-up-leave-active {
  transition: transform 0.25s ease;
}

.slide-up-enter-from,
.slide-up-leave-to {
  transform: translateY(100%);
}

/* FAB */
.fab {
  position: fixed;
  right: 16px;
  bottom: 72px;
  width: 52px;
  height: 52px;
  border-radius: 50%;
  background: var(--van-primary-color);
  color: var(--color-on-primary);
  display: flex;
  align-items: center;
  justify-content: center;
  box-shadow: var(--shadow-elevated);
  z-index: 10;
  transition: transform 0.15s ease, box-shadow 0.15s ease;
  cursor: pointer;
  border: none;
}

.fab:active {
  transform: scale(0.93);
  box-shadow: 0 2px 8px rgba(1, 1, 32, 0.2);
}

[data-theme='dark'] .fab {
  background: var(--color-lavender);
  color: #010120;
  box-shadow: 0 4px 16px rgba(189, 187, 255, 0.3);
}

/* Payment dialog */
.pay-dialog-body {
  padding: 16px 16px 8px;
}

.pay-hint {
  text-align: center;
  font-size: 13px;
  color: var(--text-tertiary);
  margin-bottom: 12px;
}

.pay-quick-btns {
  display: flex;
  justify-content: center;
  gap: 8px;
  margin-top: 12px;
}

.quick-pct-btn {
  padding: 6px 16px;
  border-radius: 20px;
  border: 1px solid #059669;
  background: transparent;
  color: #059669;
  font-size: 13px;
  cursor: pointer;
}

.quick-pct-btn:active {
  background: #059669;
  color: #fff;
}

[data-theme='dark'] .quick-pct-btn {
  border-color: var(--color-lavender, #bdbbff);
  color: var(--color-lavender, #bdbbff);
}

[data-theme='dark'] .quick-pct-btn:active {
  background: var(--color-lavender, #bdbbff);
  color: #010120;
}
</style>
