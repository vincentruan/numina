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
          v-model="formData.currency"
          is-link
          readonly
          :label="t('travel.currency')"
          :placeholder="trip?.currency || 'CNY'"
          @click="showCurrencyPicker = true"
        />

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
          placeholder="选择日期"
          @click="showDatePicker = true"
        />

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

    <!-- Currency Picker -->
    <van-popup v-model:show="showCurrencyPicker" position="bottom" round destroy-on-close>
      <van-picker
        :columns="currencyColumns"
        @confirm="onCurrencyConfirm"
        @cancel="showCurrencyPicker = false"
      />
    </van-popup>

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
        title="选择日期"
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

const { t } = useI18n()
const route = useRoute()
const router = useRouter()
const store = useTravelStore()

const tripId = route.params.tripId as string
const trip = computed(() => store.currentTrip)

const formRef = ref()
const submitting = ref(false)

const formData = ref({
  amount: '',
  currency: '',
  category_id: null as string | null,
  expense_date: new Date().toISOString().split('T')[0],
  description: '',
  receipt_image_url: route.query.receipt_image_url as string | null || null,
})

const formRules = {
  amount: [{ required: true, message: t('travel.amountRequired') }],
}

const showCurrencyPicker = ref(false)
const showCategoryPicker = ref(false)
const showDatePicker = ref(false)

const currencyColumns = [
  { text: '人民币 (CNY)', value: 'CNY' },
  { text: '美元 (USD)', value: 'USD' },
  { text: '欧元 (EUR)', value: 'EUR' },
  { text: '日元 (JPY)', value: 'JPY' },
  { text: '港币 (HKD)', value: 'HKD' },
]

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

function onCurrencyConfirm({ selectedOptions }: any) {
  formData.value.currency = selectedOptions[0]?.value || 'CNY'
  showCurrencyPicker.value = false
}

function onCategoryConfirm({ selectedOptions }: any) {
  formData.value.category_id = selectedOptions[0]?.value || null
  showCategoryPicker.value = false
}

function onDateConfirm({ selectedValues }: any) {
  formData.value.expense_date = selectedValues.join('-')
  showDatePicker.value = false
}

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
    await store.fetchCategories()
  }
  formData.value.currency = trip.value?.currency || 'CNY'
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
</style>
