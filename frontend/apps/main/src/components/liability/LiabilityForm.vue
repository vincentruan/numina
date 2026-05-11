<template>
  <van-form @submit="onSubmit">
    <van-cell-group inset>
      <van-field
        v-model="form.name"
        :label="t('liability.name')"
        :placeholder="t('liability.namePlaceholder')"
        :rules="[{ required: true, message: t('liability.nameRequired') }]"
      />

      <van-field
        v-model="categoryDisplay"
        is-link
        readonly
        :label="t('liability.category')"
        :placeholder="t('liability.selectCategory')"
        :rules="[{ required: true, message: t('liability.categoryRequired') }]"
        @click="showCategoryPicker = true"
      />
      <van-popup v-model:show="showCategoryPicker" position="bottom" round>
        <div class="category-popup">
          <div class="category-grid-popup">
            <div
              v-for="cat in categoryItems"
              :key="cat.value"
              class="category-item"
              :class="{ selected: form.category === cat.value }"
              @click="selectCategory(cat.value)"
            >
              <svg class="cat-icon" aria-hidden="true">
                <use :href="`#${cat.icon}`" />
              </svg>
              <span class="cat-name">{{ cat.text }}</span>
            </div>
          </div>
        </div>
      </van-popup>

      <van-field
        v-model="form.original_amount"
        type="number" inputmode="decimal"
        :label="t('liability.originalAmount')"
        :placeholder="t('liability.originalAmountPlaceholder')"
        :rules="[{ required: true, message: t('liability.amountRequired') }]"
      >
        <template #left-icon>
          <CurrencyButton v-model="form.currency" />
        </template>
      </van-field>

      <van-field
        v-model="form.remaining_amount"
        type="number" inputmode="decimal"
        :label="t('liability.remainingAmount')"
        :placeholder="t('liability.remainingAmountPlaceholder')"
        :rules="[{ required: true, message: t('liability.amountRequired') }]"
      >
        <template #left-icon>
          <span class="field-prefix">{{ currencySymbol }}</span>
        </template>
      </van-field>

      <van-field
        v-model="form.monthly_payment"
        type="number" inputmode="decimal"
        :label="t('liability.monthlyPayment')"
        :placeholder="t('liability.monthlyPaymentPlaceholder')"
        :rules="[{ required: true, message: t('liability.monthlyPaymentRequired') }]"
      >
        <template #left-icon><span class="field-prefix">{{ currencySymbol }}</span></template>
      </van-field>

      <van-field
        v-model="form.interest_rate"
        type="number" inputmode="decimal"
        :label="t('liability.interestRateLabel')"
        :placeholder="t('liability.interestRatePlaceholder')"
        :rules="[{ required: true, message: t('liability.interestRateRequired') }]"
      />

      <van-field
        v-model="form.start_date"
        is-link
        readonly
        :label="t('liability.startDate')"
        :placeholder="t('liability.selectStartDate')"
        @click="showStartPicker = true"
      />
      <van-popup v-model:show="showStartPicker" position="bottom" round>
        <van-date-picker
          v-model="startPickerValue"
          :title="t('liability.selectStartDate')"
          @confirm="onStartConfirm"
          @cancel="showStartPicker = false"
        />
      </van-popup>

      <van-field
        v-model="form.end_date"
        is-link
        readonly
        :label="t('liability.endDate')"
        :placeholder="t('liability.endDateOptional')"
        @click="showEndPicker = true"
      />
      <van-popup v-model:show="showEndPicker" position="bottom" round>
        <van-date-picker
          v-model="endPickerValue"
          :title="t('liability.selectEndDate')"
          @confirm="onEndConfirm"
          @cancel="showEndPicker = false"
        />
      </van-popup>

      <van-field v-model="form.institution" :label="t('liability.institution')" :placeholder="t('liability.institutionPlaceholder')" />

      <van-field v-model="form.notes" type="textarea" :label="t('liability.notes')" :placeholder="t('liability.notesPlaceholder')" rows="2" autosize />
    </van-cell-group>

    <div class="form-actions">
      <van-button round block type="primary" native-type="submit" :loading="loading">
        {{ isEdit ? t('liability.saveChanges') : t('liability.addLiability') }}
      </van-button>
    </div>
  </van-form>
</template>

<script setup lang="ts">
import { ref, computed, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import type { Liability } from '@/types'
import { getLiabilityField } from '@/types'
import CurrencyButton from '@/components/common/CurrencyButton.vue'

const { t } = useI18n()

const props = withDefaults(defineProps<{
  initialData?: Partial<Liability>
  isEdit?: boolean
  loading?: boolean
}>(), {
  initialData: undefined,
  isEdit: false,
  loading: false
})

const emit = defineEmits<{
  submit: [data: Partial<Liability>]
}>()

const form = ref<Record<string, string | number | boolean | null | undefined>>({
  name: '',
  category: 'mortgage',
  original_amount: '',
  remaining_amount: '',
  currency: 'CNY',
  monthly_payment: '',
  interest_rate: '',
  start_date: '',
  end_date: '',
  institution: '',
  notes: ''
})

// Currency symbol helper
const CURRENCY_SYMBOLS: Record<string, string> = {
  CNY: '¥',
  USD: '$',
  EUR: '€',
  GBP: '£',
  JPY: '¥',
  HKD: 'HK$',
}

const currencySymbol = computed(() => CURRENCY_SYMBOLS[form.value.currency] || form.value.currency)

watch(() => props.initialData, (data) => {
  if (data) {
    const keys: (keyof Liability)[] = [
      'name', 'category', 'original_amount', 'remaining_amount', 'currency',
      'monthly_payment', 'interest_rate', 'start_date', 'end_date', 'institution', 'notes'
    ]
    for (const key of keys) {
      const value = getLiabilityField<string | number>(data, key)
      if (value !== undefined) {
        form.value[key] = String(value ?? '')
      }
    }
  }
}, { immediate: true })

const showCategoryPicker = ref(false)
const showStartPicker = ref(false)
const showEndPicker = ref(false)

const now = new Date()
const startPickerValue = ref([
  String(now.getFullYear()),
  String(now.getMonth() + 1).padStart(2, '0'),
  String(now.getDate()).padStart(2, '0')
])
const endPickerValue = ref([...startPickerValue.value])

const categoryItems = computed(() => [
  { text: t('liability.mortgage'), value: 'mortgage', icon: 'icon-mortgage' },
  { text: t('liability.carLoan'), value: 'car_loan', icon: 'icon-car-loan' },
  { text: t('liability.creditCard'), value: 'credit_card', icon: 'icon-credit-card' },
  { text: t('liability.personalLoan'), value: 'personal_loan', icon: 'icon-personal-loan' },
  { text: t('liability.other'), value: 'other', icon: 'icon-other-liability' },
])

const categoryDisplay = computed(() => {
  const item = categoryItems.value.find(c => c.value === form.value.category)
  return item?.text ?? ''
})

function selectCategory(value: string) {
  form.value.category = value
  showCategoryPicker.value = false
}

function onStartConfirm({ selectedValues }: { selectedValues: string[] }) {
  form.value.start_date = selectedValues.join('-')
  showStartPicker.value = false
}

function onEndConfirm({ selectedValues }: { selectedValues: string[] }) {
  form.value.end_date = selectedValues.join('-')
  showEndPicker.value = false
}

function onSubmit() {
  const data: Partial<Liability> = {
    name: form.value.name,
    category: form.value.category,
    original_amount: Number(form.value.original_amount),
    remaining_amount: Number(form.value.remaining_amount),
    currency: form.value.currency,
    monthly_payment: Number(form.value.monthly_payment),
    interest_rate: Number(form.value.interest_rate),
    start_date: form.value.start_date || undefined,
    end_date: form.value.end_date || undefined,
    institution: form.value.institution || undefined,
    notes: form.value.notes || undefined
  }
  emit('submit', data)
}
</script>

<style scoped>
.field-prefix {
  color: var(--text-primary);
  margin-right: 4px;
}
.form-actions {
  padding: 16px;
}
.category-popup {
  padding: 16px;
}
.category-grid-popup {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 8px;
}
.category-item {
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 8px 4px;
  border-radius: 10px;
  background: var(--van-background-2);
  border: 1.5px solid transparent;
  cursor: pointer;
  transition: border-color 0.15s, background 0.15s, transform 0.15s;
}
.category-item:active {
  transform: scale(0.95);
}
.category-item.selected {
  border-color: var(--van-primary-color);
  background: color-mix(in srgb, var(--van-primary-color) 12%, transparent);
}
.cat-icon {
  width: 22px;
  height: 22px;
  fill: currentColor;
}
.cat-name {
  font-size: 10px;
  color: var(--van-text-color-2);
  margin-top: 4px;
  text-align: center;
  line-height: 1.2;
}
.category-item.selected .cat-name {
  color: var(--van-primary-color);
}
</style>
