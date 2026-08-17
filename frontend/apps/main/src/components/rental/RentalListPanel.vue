<template>
  <div class="rental-list-panel">
    <van-tabs v-model:active="activeTab">
      <van-tab :title="t('rental.activeTab')" name="active" />
      <van-tab :title="t('rental.historyTab')" name="inactive" />
    </van-tabs>

    <!-- Summary banner (active contracts only) -->
    <div v-if="activeTab === 'active' && summary" class="summary-banner">
      <div class="summary-row">
        <div class="summary-item income">
          <div class="summary-label">{{ t('rental.monthlyIncome') }}</div>
          <div class="summary-value">{{ formatConverted(summary.monthly_income, 'CNY') }}</div>
        </div>
        <div class="summary-item expense">
          <div class="summary-label">{{ t('rental.monthlyExpense') }}</div>
          <div class="summary-value">{{ formatConverted(summary.monthly_expense, 'CNY') }}</div>
        </div>
        <div class="summary-item net">
          <div class="summary-label">{{ t('rental.netCashFlow') }}</div>
          <div class="summary-value" :class="{ positive: netFlow > 0, negative: netFlow < 0 }">
            {{ formatConverted(summary.net_cash_flow, 'CNY') }}
          </div>
        </div>
      </div>
      <div v-if="Number(summary.total_deposit) > 0" class="deposit-row">
        <span>{{ t('rental.totalDeposit') }}</span>
        <span>{{ formatConverted(summary.total_deposit, 'CNY') }}</span>
      </div>
    </div>

    <!-- Contract list -->
    <div v-if="filteredContracts.length" class="rental-list">
      <RentalContractCard
        v-for="c in filteredContracts"
        :key="c.id"
        :contract="c"
        @click="selected = c"
      />
    </div>
    <EmptyState
      v-else
      :description="activeTab === 'active' ? t('rental.noContractDesc') : t('rental.noContractTitle')"
    />

    <!-- FAB: add contract -->
    <div v-if="activeTab === 'active'" class="fab" role="button" tabindex="0" @click="showForm = true" @keydown.enter="showForm = true" @keydown.space.prevent="showForm = true">
      <van-icon name="plus" size="22" />
    </div>

    <!-- Create dialog -->
    <van-popup v-model:show="showForm" position="bottom" round class="form-popup">
      <div class="popup-header">{{ t('rental.addContract') }}</div>
      <RentalForm @submit="onCreate" />
    </van-popup>

    <!-- Edit dialog -->
    <van-popup v-model:show="showEdit" position="bottom" round class="form-popup">
      <div class="popup-header">{{ t('rental.saveChanges') }}</div>
      <RentalForm v-if="selected" :initial-data="selected" is-edit @submit="onUpdate" />
    </van-popup>

    <!-- End-contract confirm -->
    <van-dialog
      v-model:show="showEndConfirm"
      :title="t('rental.deleteTitle')"
      show-cancel-button
      @confirm="onEndContract"
    >
      <div class="confirm-body">{{ t('rental.deleteConfirm') }}</div>
    </van-dialog>

    <!-- Detail actions -->
    <van-action-sheet
      v-model:show="showActions"
      :actions="actions"
      :cancel-text="t('common.cancel')"
      @select="onAction"
    />
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { showSuccessToast, showToast } from 'vant'
import type { RentalContract, RentalRequestPayload } from '@/types'
import { useRentalContractStore } from '@/stores/rentalContract'
import { useCurrency } from '@/composables/useCurrency'
import EmptyState from '@/components/common/EmptyState.vue'
import RentalContractCard from '@/components/rental/RentalContractCard.vue'
import RentalForm from '@/components/rental/RentalForm.vue'

const { t } = useI18n()
const store = useRentalContractStore()
const { formatConverted } = useCurrency()

const activeTab = ref<'active' | 'inactive'>('active')
const showForm = ref(false)
const showEdit = ref(false)
const showEndConfirm = ref(false)
const showActions = ref(false)
const selected = ref<RentalContract | null>(null)

const summary = computed(() => store.summary)
const filteredContracts = computed(() =>
  store.contracts.filter(c => c.is_active === (activeTab.value === 'active')),
)
const netFlow = computed(() =>
  summary.value ? Number(summary.value.net_cash_flow) : 0,
)

async function load() {
  try {
    await Promise.all([store.fetchContracts(), store.fetchSummary()])
  } catch {
    showToast(t('common.failed'))
  }
}

async function onCreate(data: RentalRequestPayload) {
  try {
    await store.createContract(data)
    showForm.value = false
    await store.fetchSummary()
    showSuccessToast(t('common.success'))
  } catch {
    showToast(t('common.failed'))
  }
}

async function onUpdate(data: RentalRequestPayload) {
  if (!selected.value) return
  try {
    await store.updateContract(selected.value.id, data)
    showEdit.value = false
    await store.fetchSummary()
    showSuccessToast(t('common.success'))
  } catch {
    showToast(t('common.failed'))
  }
}

async function onEndContract() {
  if (!selected.value) return
  try {
    await store.deactivateContract(selected.value.id)
    await store.fetchSummary()
    showSuccessToast(t('rental.deleteSuccess'))
  } catch {
    showToast(t('common.failed'))
  }
}

const actions = computed(() => [
  { name: t('rental.saveChanges'), value: 'edit' },
  { name: t('rental.deleteTitle'), value: 'end', color: '#ee0a24' },
])

function onAction(action: { value?: string }) {
  showActions.value = false
  if (action.value === 'edit') {
    showEdit.value = true
  } else if (action.value === 'end') {
    showEndConfirm.value = true
  }
}

// Card click -> open actions on active contracts
watch(selected, (v) => {
  if (v && v.is_active) showActions.value = true
})

onMounted(load)
</script>

<style scoped>
.rental-list-panel {
  padding-bottom: 80px;
}
.summary-banner {
  margin: 8px 12px;
  background: var(--card-bg);
  border-radius: 12px;
  padding: 14px 16px;
  box-shadow: 0 1px 4px rgba(0, 0, 0, 0.06);
}
[data-theme='dark'] .summary-banner {
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.28);
}
.summary-row {
  display: flex;
  gap: 8px;
}
.summary-item {
  flex: 1;
  text-align: center;
}
.summary-label {
  font-size: 11px;
  color: var(--text-secondary, #999);
}
.summary-value {
  font-size: 16px;
  font-weight: 600;
  margin-top: 4px;
}
.summary-item.income .summary-value {
  color: #059669;
}
.summary-item.expense .summary-value {
  color: #dc2626;
}
.summary-item.net .summary-value.positive {
  color: #059669;
}
.summary-item.net .summary-value.negative {
  color: #dc2626;
}
.deposit-row {
  display: flex;
  justify-content: space-between;
  margin-top: 10px;
  padding-top: 10px;
  border-top: 1px solid var(--separator, rgba(0, 0, 0, 0.06));
  font-size: 12px;
  color: var(--text-secondary, #999);
}
.rental-list {
  padding: 8px 12px;
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.fab {
  position: fixed;
  right: 20px;
  bottom: calc(80px + env(safe-area-inset-bottom));
  width: 48px;
  height: 48px;
  border-radius: 50%;
  background: var(--van-button-primary-background, #1989fa);
  color: #fff;
  display: flex;
  align-items: center;
  justify-content: center;
  box-shadow: 0 4px 12px rgba(25, 137, 250, 0.4);
  cursor: pointer;
  z-index: 10;
}
.form-popup {
  max-height: 85vh;
  overflow-y: auto;
  padding-bottom: 16px;
}
.popup-header {
  padding: 16px;
  font-size: 16px;
  font-weight: 600;
  text-align: center;
}
.confirm-body {
  padding: 24px 16px;
  text-align: center;
  font-size: 14px;
  color: var(--text-secondary, #666);
}
</style>
