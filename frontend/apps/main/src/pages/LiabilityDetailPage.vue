<template>
  <div class="liability-detail-page">
    <PageHeader :title="t('liability.liabilityDetail')" />

    <template v-if="liability">
      <!-- Value Card -->
      <div class="value-card">
        <div class="value-label">{{ t('liability.detailRemainingPrincipal') }}</div>
        <MoneyDisplay :amount="liability.remaining_amount" size="large" />
        <div class="progress-info">
          {{ t('liability.detailPaidAmount') }} ¥{{ paidAmount.toLocaleString() }} / {{ t('liability.detailTotalAmount') }} ¥{{ liability.original_amount.toLocaleString() }}
        </div>
        <van-progress
          :percentage="paidPercent"
          :stroke-width="8"
          color="#07c160"
          track-color="rgba(255,255,255,0.3)"
          :show-pivot="false"
          class="progress-bar"
        />
      </div>

      <!-- L2 (Plan B T9): interest forecast + simulate dialog. -->
      <InterestForecast :liability="liability" />

      <!-- Payment Countdown -->
      <div class="countdown-wrapper">
        <PaymentCountdown
          :start-date="liability.start_date ?? null"
          :end-date="liability.end_date ?? null"
          :is-active="liability.is_active"
        />
      </div>

      <!-- Basic Info -->
      <van-cell-group inset :title="t('liability.detailSectionBasicInfo')">
        <van-cell :title="t('liability.detailFieldName')" :value="liability.name" />
        <van-cell :title="t('liability.detailFieldType')">
          <template #value>
            <span>{{ categoryText }}</span>
          </template>
          <template #icon>
            <svg class="type-icon-svg" aria-hidden="true">
              <use :href="`#${categoryIcon}`" />
            </svg>
          </template>
        </van-cell>
        <van-cell :title="t('liability.detailFieldStatus')">
          <template #value>
            <van-tag :type="liability.is_active ? 'primary' : 'success'" size="medium">
              {{ liability.is_active ? t('liability.active') : t('liability.inactive') }}
            </van-tag>
          </template>
        </van-cell>
        <van-cell :title="t('liability.detailFieldOriginalAmount')">
          <template #value><MoneyDisplay :amount="liability.original_amount" /></template>
        </van-cell>
        <van-cell v-if="liability.monthly_payment" :title="t('liability.detailFieldMonthlyPayment')">
          <template #value><MoneyDisplay :amount="liability.monthly_payment" /></template>
        </van-cell>
        <van-cell v-if="liability.interest_rate" :title="t('liability.detailFieldAnnualRate')" :value="`${liability.interest_rate}%`" />
      </van-cell-group>

      <!-- Detail Info -->
      <van-cell-group inset :title="t('liability.detailSectionDetailInfo')">
        <van-cell v-if="liability.institution" :title="t('liability.detailFieldInstitution')" :value="liability.institution" />
        <van-cell v-if="liability.start_date" :title="t('liability.detailFieldStartDate')" :value="liability.start_date" />
        <van-cell v-if="liability.end_date" :title="t('liability.detailFieldEndDate')" :value="liability.end_date" />
        <van-cell v-if="liability.linked_asset_id" :title="t('liability.detailFieldLinkedAsset')" :value="t('liability.detailLinkedAssetHint')" is-link @click="goToAsset" />
      </van-cell-group>

      <!-- Notes -->
      <van-cell-group v-if="liability.notes" inset :title="t('liability.detailSectionNotes')">
        <van-cell :title="liability.notes" />
      </van-cell-group>

      <!-- Actions -->
      <div class="actions">
        <van-button v-if="liability.is_active" block type="success" @click="showPayment = true">
          {{ t('liability.detailBtnRecordPayment') }}
        </van-button>
        <!-- A1b (Plan B T6/T9): passive '问 AI 优化还款' button → /ai/chat?source=liability_detail&id= -->
        <van-button block type="default" plain @click="router.push({ name: 'AIChat', query: { source: 'liability_detail', id: liability.id } })">
          {{ t('liability.interest.askAi') }}
        </van-button>
        <van-button block type="primary" plain @click="$router.push(`/liabilities/${liability.id}/edit`)">
          {{ t('liability.detailBtnEdit') }}
        </van-button>
        <van-button block type="danger" plain :loading="deleting" @click="onDelete">
          {{ t('liability.detailBtnDelete') }}
        </van-button>
      </div>
    </template>

    <!-- Payment Dialog -->
    <van-dialog
      v-model:show="showPayment"
      :title="t('liability.detailPaymentDialogTitle')"
      show-cancel-button
      :confirm-button-text="t('liability.detailPaymentConfirmBtn')"
      :before-close="onPaymentConfirm"
    >
      <div class="payment-dialog">
        <div class="payment-hint">{{ t('liability.detailPaymentRemainingHint', { amount: liability?.remaining_amount.toLocaleString() }) }}</div>
        <van-field
          v-model="paymentAmount"
          type="number"
          :label="t('liability.detailPaymentAmountLabel')"
          :placeholder="t('liability.detailPaymentAmountPlaceholder')"
          input-align="right"
        >
          <template #button>{{ t('liability.detailPaymentUnit') }}</template>
        </van-field>
      </div>
    </van-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { showConfirmDialog, showToast, showSuccessToast } from 'vant'
import { useI18n } from 'vue-i18n'
import { useLiabilityStore } from '@/stores/liability'
import PageHeader from '@/components/common/PageHeader.vue'
import MoneyDisplay from '@/components/common/MoneyDisplay.vue'
import PaymentCountdown from '@/components/liability/PaymentCountdown.vue'
import InterestForecast from '@/components/liability/InterestForecast.vue'
import { usePageLoading } from '@/composables/usePageLoading'

const { t } = useI18n()

const route = useRoute()
const router = useRouter()
const liabilityStore = useLiabilityStore()
const deleting = ref(false)
const showPayment = ref(false)
const paymentAmount = ref('')
const { increment, decrement } = usePageLoading()

const liability = computed(() => liabilityStore.currentLiability)

const categoryMap: Record<string, { text: string; icon: string }> = {
  mortgage: { text: t('liability.mortgage'), icon: 'icon-mortgage' },
  car_loan: { text: t('liability.carLoan'), icon: 'icon-car-loan' },
  credit_card: { text: t('liability.creditCard'), icon: 'icon-credit-card' },
  consumer_loan: { text: t('liability.consumerLoan'), icon: 'icon-personal-loan' },
  personal_loan: { text: t('liability.personalLoan'), icon: 'icon-personal-loan' },
  other: { text: t('liability.other'), icon: 'icon-other-liability' }
}

const categoryText = computed(() => categoryMap[liability.value?.category || '']?.text || '')
const categoryIcon = computed(() => categoryMap[liability.value?.category || '']?.icon || 'icon-other-liability')

const paidAmount = computed(() => {
  if (!liability.value) return 0
  return liability.value.original_amount - liability.value.remaining_amount
})

const paidPercent = computed(() => {
  if (!liability.value || liability.value.original_amount === 0) return 0
  return Math.round((paidAmount.value / liability.value.original_amount) * 100)
})

function goToAsset() {
  if (liability.value?.linked_asset_id) {
    router.push(`/assets/${liability.value.linked_asset_id}`)
  }
}

async function onPaymentConfirm(action: string) {
  if (action === 'confirm') {
    const amount = parseFloat(paymentAmount.value)
    if (isNaN(amount) || amount <= 0) {
      showToast(t('toast.paymentAmountRequired'))
      return false
    }
    if (amount > (liability.value?.remaining_amount || 0)) {
      showToast(t('toast.paymentExceedsBalance'))
      return false
    }
    try {
      await liabilityStore.recordPayment(liability.value!.id, amount)
      showSuccessToast(t('toast.paymentSuccess'))
      paymentAmount.value = ''
      return true
    } catch {
      return false
    }
  }
  paymentAmount.value = ''
  return true
}

async function onDelete() {
  try {
    await showConfirmDialog({ title: t('common.confirm'), message: t('toast.confirmDelete', { name: liability.value?.name }) })
    deleting.value = true
    await liabilityStore.deleteLiability(liability.value!.id)
    showSuccessToast(t('toast.deleteSuccess'))
    router.back()
  } catch {
    // cancelled
  } finally {
    deleting.value = false
  }
}

onMounted(async () => {
  increment()
  try {
    const id = route.params.id as string
    await liabilityStore.fetchLiability(id)
  } finally {
    decrement()
  }
})
</script>

<style scoped>
.liability-detail-page {
  background: var(--bg-secondary);
  min-height: 100vh;
  padding-bottom: 20px;
}
.value-card {
  background: linear-gradient(135deg, #ee0a24 0%, #ff6034 100%);
  padding: 20px 16px;
  color: #fff;
  text-align: center;
}
.value-label {
  font-size: 13px;
  opacity: 0.8;
}
.value-card :deep(.money-display) {
  color: #fff;
}
.progress-info {
  font-size: 12px;
  opacity: 0.8;
  margin-top: 8px;
}
.progress-bar {
  margin-top: 8px;
}
.actions {
  padding: 16px;
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.payment-dialog {
  padding: 16px;
}
.payment-hint {
  font-size: 13px;
  color: var(--text-tertiary);
  margin-bottom: 12px;
  text-align: center;
}
.type-icon-svg {
  width: 18px;
  height: 18px;
  margin-right: 4px;
  fill: currentColor;
}
.countdown-wrapper {
  padding: 8px 16px 0;
}
</style>
