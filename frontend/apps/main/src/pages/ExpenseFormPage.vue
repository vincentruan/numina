<template>
  <div class="expense-form-page">
    <PageHeader :title="t('travel.addExpense')" />

    <van-form
      ref="formRef"
      :model="formData"
      :rules="formRules"
      @submit="onSubmit"
    >
      <van-cell-group inset>
        <van-field
          v-model="formData.amount"
          type="number"
          :label="t('travel.expenseAmount')"
          required
          :placeholder="t('travel.amountRequired')"
          :rules="[{ required: true, message: t('travel.amountRequired') }]"
        />

        <van-field
          :label="t('travel.currency')"
        >
          <template #input>
            <CurrencyButton v-model="formData.currency" />
          </template>
        </van-field>

        <!-- Split type selector (visible only when trip has active split group) -->
        <van-field
          v-if="hasSplitGroup"
          :label="t('travel.splitType')"
        >
          <template #input>
            <van-radio-group v-model="formData.split_type" direction="horizontal">
              <van-radio name="equal">{{ t('travel.splitTypeEqual') }}</van-radio>
              <van-radio name="per_person">{{ t('travel.splitTypePerPerson') }}</van-radio>
              <van-radio name="custom">{{ t('travel.splitTypeCustom') }}</van-radio>
            </van-radio-group>
          </template>
        </van-field>

        <van-field
          v-model="categoryName"
          is-link
          readonly
          :label="t('travel.expenseCategory')"
          :placeholder="t('travel.selectCategory')"
          @click="showCategoryPicker = true"
        />

        <van-field
          v-model="formData.expense_date"
          is-link
          readonly
          :label="t('travel.expenseDate')"
          :placeholder="t('travel.selectDate')"
          @click="showDatePicker = true"
        />

        <!-- Manual exchange rate (R3) -->
        <van-field
          v-if="showManualRate"
          v-model="formData.exchange_rate"
          type="number"
          :label="t('travel.manualRate')"
          :placeholder="t('travel.manualRateHint')"
        />
        <div v-if="showManualRateBadge" class="manual-rate-badge">
          <van-tag type="warning" plain>{{ t('travel.manualRateBadge') }}</van-tag>
        </div>

        <van-field
          v-model="formData.description"
          type="textarea"
          :label="t('travel.expenseDescription')"
          :placeholder="t('travel.expenseDescriptionPlaceholder')"
          rows="3"
          autosize
        />
      </van-cell-group>

      <div class="submit-button">
        <van-button type="primary" block round native-type="submit" :loading="submitting">
          {{ t('common.submit') }}
        </van-button>
      </div>
    </van-form>

    <!-- Category Picker -->
    <van-popup v-model:show="showCategoryPicker" position="bottom" round destroy-on-close>
      <van-picker
        :columns="categoryColumns"
        @confirm="onCategoryConfirm"
        @cancel="showCategoryPicker = false"
      />
    </van-popup>

    <!-- Date Picker -->
    <van-popup v-model:show="showDatePicker" position="bottom" round destroy-on-close>
      <van-date-picker
        v-model="currentDate"
        :title="t('travel.selectDate')"
        @confirm="onDateConfirm"
        @cancel="showDatePicker = false"
      />
    </van-popup>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { showSuccessToast, showFailToast } from 'vant'
import { useTravelStore } from '@/stores/travel'
import PageHeader from '@/components/common/PageHeader.vue'
import CurrencyButton from '@/components/common/CurrencyButton.vue'

const { t } = useI18n()
const route = useRoute()
const router = useRouter()
const store = useTravelStore()

const tripId = route.params.tripId as string
const trip = computed(() => store.currentTrip)

const formRef = ref()
const submitting = ref(false)

// Pre-fill from receipt AI extraction query params (U7)
const q = route.query
const formData = ref({
  amount: (q.receipt_amount as string) || '',
  currency: (q.receipt_currency as string) || '',
  category_id: null as string | null,
  expense_date: (q.receipt_date as string) || new Date().toISOString().split('T')[0],
  description: '',
  receipt_image_url: (q.receipt_image_url as string) || null,
  split_type: 'equal' as 'equal' | 'per_person' | 'custom',
  exchange_rate: undefined as string | undefined,
})

// Map extracted category to expense category_id (best-effort)
const receiptCategoryMap: Record<string, string> = {
  dining: '餐饮',
  transport: '交通',
  accommodation: '住宿',
  activities: '娱乐',
  shopping: '购物',
  misc: '其他',
}

const formRules = {
  amount: [{ required: true, message: t('travel.amountRequired') }],
}

const showCategoryPicker = ref(false)
const showDatePicker = ref(false)

const categoryName = computed(() => {
  if (!formData.value.category_id) return ''
  const cat = store.categories.find(c => c.id === formData.value.category_id)
  return cat?.name || ''
})

const categoryColumns = computed(() =>
  store.categories.map(cat => ({
    text: cat.name,
    value: cat.id,
  }))
)

const currentDate = ref(formData.value.expense_date.split('-'))

function onCategoryConfirm({ selectedOptions }: { selectedOptions: Array<{ value?: string }> }) {
  formData.value.category_id = selectedOptions[0]?.value || null
  showCategoryPicker.value = false
}

function onDateConfirm({ selectedValues }: { selectedValues: string[] }) {
  formData.value.expense_date = selectedValues.join('-')
  showDatePicker.value = false
}

// Whether the trip has an active split group (drives split type selector visibility)
const hasSplitGroup = computed(() => !!store.splitGroup?.is_active)

// Show manual rate input as optional field when expense currency differs from CNY (R3).
// The backend uses the user-provided rate only when ExchangeRateService has no auto-rate.
// The "手动汇率" badge appears when the user has actually entered a value.
const showManualRate = computed(() => {
  const curr = formData.value.currency || trip.value?.currency || 'CNY'
  return curr !== 'CNY'
})

// Show badge when user has entered a manual rate
const showManualRateBadge = computed(() => {
  return showManualRate.value && formData.value.exchange_rate && parseFloat(formData.value.exchange_rate) > 0
})

async function onSubmit() {
  submitting.value = true
  try {
    await store.createExpense(tripId, {
      amount: formData.value.amount,
      currency: formData.value.currency || trip.value?.currency || 'CNY',
      category_id: formData.value.category_id,
      expense_date: formData.value.expense_date,
      description: formData.value.description || null,
      receipt_image_url: formData.value.receipt_image_url,
      split_type: hasSplitGroup.value ? formData.value.split_type : null,
      exchange_rate: formData.value.exchange_rate ? parseFloat(formData.value.exchange_rate) || null : null,
    })
    showSuccessToast(t('common.success'))
    router.back()
  } catch {
    showFailToast(t('common.failed'))
  } finally {
    submitting.value = false
  }
}

onMounted(async () => {
  if (!trip.value) {
    await store.fetchTrip(tripId)
  }
  if (store.categories.length === 0) {
    await store.categories.length === 0 && await store.fetchCategories()
  }
  formData.value.currency = formData.value.currency || trip.value?.currency || 'CNY'

  // Map receipt AI-extracted category to local category_id
  const receiptCat = q.receipt_category as string
  if (receiptCat && !formData.value.category_id) {
    const label = receiptCategoryMap[receiptCat] || receiptCat
    const match = store.categories.find(c => c.name === label)
    if (match) formData.value.category_id = match.id
  }

  // Fetch split group to determine if split type selector should show
  if (!store.splitGroup) {
    store.fetchSplitGroup(tripId).catch(() => {})
  }
})
</script>

<style scoped>
.expense-form-page {
  min-height: 100vh;
  background: var(--bg-secondary);
  padding-bottom: calc(16px + env(safe-area-inset-bottom));
}
.submit-button {
  padding: 16px 12px;
}
.manual-rate-badge {
  padding: 0 16px 8px;
}
</style>
