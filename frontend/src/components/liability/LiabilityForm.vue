<template>
  <van-form @submit="onSubmit">
    <van-cell-group inset>
      <van-field
        v-model="form.name"
        label="名称"
        placeholder="请输入负债名称"
        :rules="[{ required: true, message: '请输入名称' }]"
      />

      <van-field
        v-model="categoryDisplay"
        is-link
        readonly
        label="类别"
        placeholder="选择负债类别"
        @click="showCategoryPicker = true"
        :rules="[{ required: true, message: '请选择类别' }]"
      />
      <van-popup v-model:show="showCategoryPicker" position="bottom" round>
        <van-picker
          :columns="categoryColumns"
          @confirm="onCategoryConfirm"
          @cancel="showCategoryPicker = false"
        />
      </van-popup>

      <van-field
        v-model="form.original_amount"
        type="number"
        label="原始金额"
        placeholder="请输入原始金额"
        :rules="[{ required: true, message: '请输入原始金额' }]"
      >
        <template #left-icon>
          <CurrencyButton v-model="form.currency" />
        </template>
      </van-field>

      <van-field
        v-model="form.remaining_amount"
        type="number"
        label="剩余金额"
        placeholder="请输入剩余金额"
        :rules="[{ required: true, message: '请输入剩余金额' }]"
      >
        <template #left-icon>
          <span class="field-prefix">{{ currencySymbol }}</span>
        </template>
      </van-field>

      <van-field
        v-model="form.monthly_payment"
        type="number"
        label="月供"
        placeholder="请输入月供金额"
        :rules="[{ required: true, message: '请输入月供' }]"
      >
        <template #left-icon><span class="field-prefix">{{ currencySymbol }}</span></template>
      </van-field>

      <van-field
        v-model="form.interest_rate"
        type="number"
        label="利率(%)"
        placeholder="请输入年利率"
        :rules="[{ required: true, message: '请输入利率' }]"
      />

      <van-field
        v-model="form.start_date"
        is-link
        readonly
        label="开始日期"
        placeholder="选择开始日期"
        @click="showStartPicker = true"
      />
      <van-popup v-model:show="showStartPicker" position="bottom" round>
        <van-date-picker
          v-model="startPickerValue"
          title="选择开始日期"
          @confirm="onStartConfirm"
          @cancel="showStartPicker = false"
        />
      </van-popup>

      <van-field
        v-model="form.end_date"
        is-link
        readonly
        label="结束日期"
        placeholder="选择结束日期(可选)"
        @click="showEndPicker = true"
      />
      <van-popup v-model:show="showEndPicker" position="bottom" round>
        <van-date-picker
          v-model="endPickerValue"
          title="选择结束日期"
          @confirm="onEndConfirm"
          @cancel="showEndPicker = false"
        />
      </van-popup>

      <van-field v-model="form.institution" label="金融机构" placeholder="请输入金融机构(可选)" />

      <van-field v-model="form.notes" type="textarea" label="备注" placeholder="请输入备注(可选)" rows="2" autosize />
    </van-cell-group>

    <div class="form-actions">
      <van-button round block type="primary" native-type="submit" :loading="loading">
        {{ isEdit ? '保存修改' : '添加负债' }}
      </van-button>
    </div>
  </van-form>
</template>

<script setup lang="ts">
import { ref, computed, watch } from 'vue'
import type { Liability } from '@/types'
import CurrencyButton from '@/components/common/CurrencyButton.vue'

const props = withDefaults(defineProps<{
  initialData?: Partial<Liability>
  isEdit?: boolean
  loading?: boolean
}>(), {
  isEdit: false,
  loading: false
})

const emit = defineEmits<{
  submit: [data: Partial<Liability>]
}>()

const form = ref<Record<string, any>>({
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
    Object.keys(form.value).forEach(key => {
      if ((data as any)[key] !== undefined) {
        form.value[key] = String((data as any)[key] ?? '')
      }
    })
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

const categoryColumns = [
  { text: '🏠 房贷', value: 'mortgage' },
  { text: '🚗 车贷', value: 'car_loan' },
  { text: '💳 信用卡', value: 'credit_card' },
  { text: '💰 个人贷款', value: 'personal_loan' },
  { text: '📋 其他', value: 'other' }
]

const categoryDisplayMap: Record<string, string> = {
  mortgage: '🏠 房贷',
  car_loan: '🚗 车贷',
  credit_card: '💳 信用卡',
  personal_loan: '💰 个人贷款',
  other: '📋 其他'
}

const categoryDisplay = computed(() => categoryDisplayMap[form.value.category] || '')

function onCategoryConfirm({ selectedOptions }: any) {
  form.value.category = selectedOptions[0].value
  showCategoryPicker.value = false
}

function onStartConfirm({ selectedValues }: any) {
  form.value.start_date = selectedValues.join('-')
  showStartPicker.value = false
}

function onEndConfirm({ selectedValues }: any) {
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
  color: #323233;
  margin-right: 4px;
}
.form-actions {
  padding: 16px;
}
</style>
