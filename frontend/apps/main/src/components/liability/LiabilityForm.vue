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

      <!-- L7 (KTD-3): optional collateral asset picker. -->
      <van-field
        v-model="linkedAssetDisplay"
        is-link
        readonly
        :label="t('liability.linkedAssetPicker')"
        :placeholder="t('liability.linkedAssetPickerPlaceholder')"
        @click="showAssetPicker = true"
      />
      <van-popup v-model:show="showAssetPicker" position="bottom" round>
        <van-picker
          v-model="assetPickerValue"
          :columns="assetPickerColumns"
          :title="t('liability.linkedAssetPicker')"
          @confirm="onAssetConfirm"
          @cancel="showAssetPicker = false"
        />
      </van-popup>

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
import { ref, computed, watch, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import type { Asset, Liability, LiabilityRequestPayload } from '@/types'
import { useAuthStore } from '@/stores/auth'
import { getLiabilityField } from '@/types'
import { getAssets } from '@/api/assets'
import CurrencyButton from '@/components/common/CurrencyButton.vue'

const { t } = useI18n()
const authStore = useAuthStore()

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
  submit: [data: LiabilityRequestPayload]
}>()

interface FormState {
  name: string
  category: 'mortgage' | 'car_loan' | 'credit_card' | 'personal_loan' | 'other'
  original_amount: string
  remaining_amount: string
  currency: string
  monthly_payment: string
  interest_rate: string
  start_date: string
  end_date: string
  institution: string
  linked_asset_id: string | null
  notes: string
}

const form = ref<FormState>({
  name: '',
  category: 'mortgage',
  original_amount: '',
  remaining_amount: '',
  currency: authStore.user?.default_currency || 'CNY',
  monthly_payment: '',
  interest_rate: '',
  start_date: '',
  end_date: '',
  institution: '',
  linked_asset_id: null,
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
    if (data.name !== undefined) form.value.name = String(data.name ?? '')
    if (data.category !== undefined) form.value.category = data.category
    if (data.original_amount !== undefined) form.value.original_amount = String(data.original_amount ?? '')
    if (data.remaining_amount !== undefined) form.value.remaining_amount = String(data.remaining_amount ?? '')
    if (data.currency !== undefined) form.value.currency = String(data.currency ?? '')
    if (data.monthly_payment !== undefined) form.value.monthly_payment = String(data.monthly_payment ?? '')
    if (data.interest_rate !== undefined) form.value.interest_rate = String(data.interest_rate ?? '')
    if (data.start_date !== undefined) form.value.start_date = String(data.start_date ?? '')
    if (data.end_date !== undefined) form.value.end_date = String(data.end_date ?? '')
    if (data.institution !== undefined) form.value.institution = String(data.institution ?? '')
    if (data.linked_asset_id !== undefined) form.value.linked_asset_id = data.linked_asset_id ? String(data.linked_asset_id) : null
    if (data.notes !== undefined) form.value.notes = String(data.notes ?? '')
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
  form.value.category = value as 'mortgage' | 'car_loan' | 'credit_card' | 'personal_loan' | 'other'
  showCategoryPicker.value = false
}

// L7 (KTD-3): collateral asset picker. Fetches family assets once on mount;
// a leading "无" option (value '') unsets the link. Value is the asset id.
const showAssetPicker = ref(false)
const assets = ref<Asset[]>([])
const NONE_ASSET_VALUE = ''
const assetPickerValue = ref<string[]>([])

const assetPickerColumns = computed(() => [
  { text: t('liability.noLinkedAsset'), value: NONE_ASSET_VALUE },
  ...assets.value.map(a => ({ text: a.name, value: a.id })),
])

const linkedAssetDisplay = computed(() => {
  if (!form.value.linked_asset_id) return ''
  const a = assets.value.find(x => x.id === form.value.linked_asset_id)
  return a?.name ?? ''
})

function onAssetConfirm({ selectedValues }: { selectedValues: string[] }) {
  const v = selectedValues[0] ?? NONE_ASSET_VALUE
  form.value.linked_asset_id = v === NONE_ASSET_VALUE ? null : v
  showAssetPicker.value = false
}

// Keep the picker's cursor in sync with the current selection when opened.
watch(showAssetPicker, (open) => {
  if (open) {
    assetPickerValue.value = [form.value.linked_asset_id ?? NONE_ASSET_VALUE]
  }
})

onMounted(async () => {
  try {
    const res = await getAssets()
    assets.value = res.data
  } catch {
    // Non-fatal: picker just shows the "无" option if assets fail to load.
    assets.value = []
  }
})

function onStartConfirm({ selectedValues }: { selectedValues: string[] }) {
  form.value.start_date = selectedValues.join('-')
  showStartPicker.value = false
}

function onEndConfirm({ selectedValues }: { selectedValues: string[] }) {
  form.value.end_date = selectedValues.join('-')
  showEndPicker.value = false
}

function onSubmit() {
  const data: LiabilityRequestPayload = {
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
    linked_asset_id: form.value.linked_asset_id ?? null,
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
