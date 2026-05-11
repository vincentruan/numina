<template>
  <div class="liability-list-page">
    <PageHeader title="负债" :show-back="false">
      <template v-if="selectMode" #right>
        <span class="select-cancel" @click="exitSelectMode">取消</span>
      </template>
    </PageHeader>

    <van-tabs v-model:active="activeTab" sticky @change="onTabChange">
      <van-tab title="还款中" name="active" />
      <van-tab title="已结清" name="inactive" />
    </van-tabs>

    <!-- Filter / Sort bar -->
    <div class="filter-bar">
      <div class="filter-chips">
        <button
          class="chip"
          :class="{ active: filterCategory === '' }"
          @click="filterCategory = ''"
        >全部</button>
        <button
          v-for="cat in categories"
          :key="cat.value"
          class="chip"
          :class="{ active: filterCategory === cat.value }"
          @click="filterCategory = cat.value"
        >{{ cat.label }}</button>
      </div>
      <button class="sort-btn" @click="toggleSort">
        <van-icon name="sort" size="16" />
        <span>{{ sortLabel }}</span>
      </button>
    </div>

    <van-pull-refresh v-model="refreshing" @refresh="onRefresh">
      <!-- Summary Banner -->
      <div v-if="liabilityStore.liabilities.length" class="summary-banner">
        <div class="summary-top">
          <div class="summary-main">
            <div class="summary-label">{{ activeTab === 'active' ? '待还总额' : '已结清总额' }}</div>
            <div class="summary-amount">{{ formatAmountDisplay(totalAmount) }}</div>
          </div>
          <div class="summary-count">
            <span class="count-num">{{ filteredLiabilities.length }}</span>
            <span class="count-unit">笔</span>
          </div>
        </div>
        <template v-if="activeTab === 'active' && totalOriginal > 0">
          <div class="summary-progress-bar">
            <div class="summary-progress-fill" :style="{ width: repaidPercent + '%' }" />
          </div>
          <div class="summary-progress-text">
            <span>总还款进度</span>
            <span class="summary-percent">{{ repaidPercent }}%</span>
          </div>
        </template>
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
      <EmptyState v-else description="暂无负债记录">
        <van-button size="small" type="primary" @click="$router.push('/liabilities/new')">
          添加负债
        </van-button>
      </EmptyState>
    </van-pull-refresh>

    <!-- Batch action bar -->
    <Transition name="slide-up">
      <div v-if="selectMode" class="batch-bar">
        <span class="batch-count">已选 {{ selectedIds.size }} 笔</span>
        <div class="batch-actions">
          <van-button size="small" plain @click="selectAll">全选</van-button>
          <van-button
            v-if="activeTab === 'active'"
            size="small"
            type="success"
            :disabled="selectedIds.size === 0"
            @click="batchSettle"
          >标记结清</van-button>
          <van-button
            size="small"
            type="danger"
            :disabled="selectedIds.size === 0"
            @click="batchDelete"
          >批量删除</van-button>
        </div>
      </div>
    </Transition>

    <!-- FAB (hidden in select mode) -->
    <div v-if="!selectMode" class="fab" @click="$router.push('/liabilities/new')">
      <van-icon name="plus" size="22" />
    </div>

    <!-- Quick payment dialog -->
    <van-dialog
      v-model:show="payDialogVisible"
      :title="`还款 · ${payTarget?.name ?? ''}`"
      show-cancel-button
      confirm-button-text="确认还款"
      confirm-button-color="#059669"
      @confirm="submitPayment"
    >
      <div class="pay-dialog-body">
        <div class="pay-hint">剩余本金：{{ payTarget ? formatAmountDisplay(payTarget.remaining_amount) : '' }}</div>
        <van-field
          v-model="payAmount"
          type="number"
          placeholder="请输入还款金额"
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
          >{{ pct === 100 ? '全额' : pct + '%' }}</button>
        </div>
      </div>
    </van-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import { useRouter } from 'vue-router'
import { showToast, showConfirmDialog } from 'vant'
import { useI18n } from 'vue-i18n'
import { useLiabilityStore } from '@/stores/liability'
import type { Liability } from '@/types'
import PageHeader from '@/components/common/PageHeader.vue'
import EmptyState from '@/components/common/EmptyState.vue'
import LiabilityCard from '@/components/liability/LiabilityCard.vue'

const { t } = useI18n()
const router = useRouter()
const liabilityStore = useLiabilityStore()

const refreshing = ref(false)
const activeTab = ref('active')

// --- Filter / Sort ---
const filterCategory = ref('')
const sortOrder = ref<'default' | 'asc' | 'desc'>('default')

const categories = [
  { value: 'mortgage', label: '房贷' },
  { value: 'car_loan', label: '车贷' },
  { value: 'credit_card', label: '信用卡' },
  { value: 'personal_loan', label: '个人贷款' },
  { value: 'other', label: '其他' },
]

const sortLabel = computed(() => {
  if (sortOrder.value === 'asc') return '金额↑'
  if (sortOrder.value === 'desc') return '金额↓'
  return '排序'
})

function toggleSort() {
  if (sortOrder.value === 'default') sortOrder.value = 'desc'
  else if (sortOrder.value === 'desc') sortOrder.value = 'asc'
  else sortOrder.value = 'default'
}

const filteredLiabilities = computed(() => {
  let list = liabilityStore.liabilities
  if (filterCategory.value) {
    list = list.filter(l => l.category === filterCategory.value)
  }
  if (sortOrder.value === 'desc') {
    list = [...list].sort((a, b) => b.remaining_amount - a.remaining_amount)
  } else if (sortOrder.value === 'asc') {
    list = [...list].sort((a, b) => a.remaining_amount - b.remaining_amount)
  }
  return list
})

// --- Summary ---
const totalAmount = computed(() =>
  liabilityStore.liabilities.reduce((sum, l) => sum + l.remaining_amount, 0)
)
const totalOriginal = computed(() =>
  liabilityStore.liabilities.reduce((sum, l) => sum + (l.original_amount ?? l.remaining_amount), 0)
)
const repaidPercent = computed(() => {
  if (totalOriginal.value <= 0) return 0
  return Math.round(((totalOriginal.value - totalAmount.value) / totalOriginal.value) * 100)
})

function formatAmountDisplay(amount: number): string {
  if (amount >= 100000000) return (amount / 100000000).toFixed(2) + '亿'
  if (amount >= 10000) return (amount / 10000).toFixed(1) + '万'
  if (amount >= 1000) return (amount / 1000).toFixed(1) + 'k'
  return amount.toLocaleString('zh-CN')
}

// --- Tab / Refresh ---
function onTabChange() {
  exitSelectMode()
  filterCategory.value = ''
  sortOrder.value = 'default'
  liabilityStore.fetchLiabilities({ is_active: activeTab.value === 'active' })
}

async function onRefresh() {
  await liabilityStore.fetchLiabilities({ is_active: activeTab.value === 'active' })
  refreshing.value = false
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

async function confirmDelete(item: Liability) {
  await showConfirmDialog({
    message: t('toast.confirmDelete', { name: item.name }),
    confirmButtonColor: '#dc2626',
  })
  await liabilityStore.deleteLiability(item.id)
  showToast(t('toast.deleteSuccess'))
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
  const val = (payTarget.value.remaining_amount * pct) / 100
  payAmount.value = val.toFixed(2)
}

async function submitPayment() {
  const amount = parseFloat(payAmount.value)
  if (!amount || amount <= 0) {
    showToast(t('toast.paymentAmountRequired'))
    return
  }
  if (payTarget.value && amount > payTarget.value.remaining_amount) {
    showToast(t('toast.paymentExceedsBalance'))
    return
  }
  await liabilityStore.recordPayment(payTarget.value!.id, amount)
  showToast(t('toast.paymentSuccess'))
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
  await showConfirmDialog({
    message: t('toast.confirmSettleBatch', { count: selectedIds.value.size }),
    confirmButtonColor: '#059669',
  })
  await Promise.all(
    [...selectedIds.value].map(id => liabilityStore.updateLiability(id, { is_active: false }))
  )
  showToast(t('toast.liabilitySettledBatch', { count: selectedIds.value.size }))
  exitSelectMode()
  liabilityStore.fetchLiabilities({ is_active: true })
}

async function batchDelete() {
  if (selectedIds.value.size === 0) {
    showToast(t('toast.liabilitySelectFirst'))
    return
  }
  await showConfirmDialog({
    message: t('toast.confirmDeleteBatch', { count: selectedIds.value.size }),
    confirmButtonColor: '#dc2626',
  })
  await Promise.all([...selectedIds.value].map(id => liabilityStore.deleteLiability(id)))
  showToast(t('toast.liabilityDeleteBatch', { count: selectedIds.value.size }))
  exitSelectMode()
}

liabilityStore.fetchLiabilities({ is_active: true })
</script>

<style scoped>
@import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Sans:wght@400;500;600&family=Crimson+Pro:wght@600&display=swap');

.liability-list-page {
  background: var(--bg-secondary);
  min-height: 100vh;
  padding-bottom: 80px;
}

/* Select mode cancel button */
.select-cancel {
  font-size: 14px;
  color: var(--color-primary);
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
  padding: 4px 14px;
  border-radius: 30px;
  border: 1px solid rgba(0, 0, 0, 0.18);
  background: transparent;
  font-size: 13px;
  color: var(--text-secondary);
  cursor: pointer;
  transition: all 0.15s;
  white-space: nowrap;
}

.chip.active {
  background: var(--color-primary);
  border-color: var(--color-primary);
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
  background: var(--color-primary);
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
</style>
