<template>
  <van-form @submit="onSubmit">
    <van-cell-group inset>
      <van-field
        v-model="form.name"
        label="名称"
        placeholder="请输入资产名称"
        :rules="[{ required: true, message: '请输入名称' }]"
      />

      <van-field
        v-model="form.asset_type"
        is-link
        readonly
        label="类型"
        placeholder="选择资产类型"
        @click="showTypePicker = true"
        :rules="[{ required: true, message: '请选择类型' }]"
      />
      <van-popup v-model:show="showTypePicker" position="bottom" round>
        <van-picker
          :columns="typeColumns"
          @confirm="onTypeConfirm"
          @cancel="showTypePicker = false"
        />
      </van-popup>

      <van-field
        v-model="categoryDisplay"
        is-link
        readonly
        label="分类"
        placeholder="选择分类"
        @click="showCategoryPicker = true"
      />
      <van-popup v-model:show="showCategoryPicker" position="bottom" round>
        <van-picker
          :columns="categoryColumns"
          @confirm="onCategoryConfirm"
          @cancel="showCategoryPicker = false"
        />
      </van-popup>

      <van-field
        v-model="form.purchase_price"
        type="number"
        label="购入价格"
        placeholder="请输入购入价格"
        :rules="[{ required: true, message: '请输入购入价格' }]"
      >
        <template #left-icon><span class="field-prefix">¥</span></template>
      </van-field>

      <van-field
        v-model="form.current_value"
        type="number"
        label="当前价值"
        placeholder="请输入当前价值"
        :rules="[{ required: true, message: '请输入当前价值' }]"
      >
        <template #left-icon><span class="field-prefix">¥</span></template>
      </van-field>

      <van-field
        v-model="form.purchase_date"
        is-link
        readonly
        label="购入日期"
        placeholder="选择日期"
        @click="showDatePicker = true"
      />
      <van-popup v-model:show="showDatePicker" position="bottom" round>
        <van-date-picker
          v-model="datePickerValue"
          title="选择日期"
          @confirm="onDateConfirm"
          @cancel="showDatePicker = false"
        />
      </van-popup>

      <van-field
        v-model="statusDisplay"
        is-link
        readonly
        label="状态"
        placeholder="选择状态"
        @click="showStatusPicker = true"
      />
      <van-popup v-model:show="showStatusPicker" position="bottom" round>
        <van-picker
          :columns="statusColumns"
          @confirm="onStatusConfirm"
          @cancel="showStatusPicker = false"
        />
      </van-popup>
    </van-cell-group>

    <!-- Physical asset fields -->
    <van-cell-group v-if="form.asset_type === 'physical'" inset title="实物资产信息">
      <van-field v-model="form.location" label="存放位置" placeholder="请输入存放位置" />
      <van-field v-model="form.expected_lifespan_days" type="digit" label="预期寿命(天)" placeholder="请输入" />
      <van-field v-model="form.annual_maintenance_cost" type="number" label="年维护费" placeholder="请输入">
        <template #left-icon><span class="field-prefix">¥</span></template>
      </van-field>
      <van-field
        v-model="usageDisplay"
        is-link
        readonly
        label="使用频率"
        placeholder="选择使用频率"
        @click="showUsagePicker = true"
      />
      <van-popup v-model:show="showUsagePicker" position="bottom" round>
        <van-picker
          :columns="usageColumns"
          @confirm="onUsageConfirm"
          @cancel="showUsagePicker = false"
        />
      </van-popup>
    </van-cell-group>

    <!-- Financial asset fields -->
    <van-cell-group v-if="form.asset_type === 'financial'" inset title="金融资产信息">
      <van-field v-model="form.institution" label="金融机构" placeholder="请输入金融机构" />
      <van-field v-model="form.interest_rate" type="number" label="利率(%)" placeholder="请输入利率" />
      <van-field
        v-model="form.maturity_date"
        is-link
        readonly
        label="到期日期"
        placeholder="选择到期日期"
        @click="showMaturityPicker = true"
      />
      <van-popup v-model:show="showMaturityPicker" position="bottom" round>
        <van-date-picker
          v-model="maturityPickerValue"
          title="选择到期日期"
          @confirm="onMaturityConfirm"
          @cancel="showMaturityPicker = false"
        />
      </van-popup>
    </van-cell-group>

    <van-cell-group inset title="其他">
      <van-field v-model="form.notes" type="textarea" label="备注" placeholder="请输入备注" rows="2" autosize />
    </van-cell-group>

    <div class="form-actions">
      <van-button round block type="primary" native-type="submit" :loading="loading">
        {{ isEdit ? '保存修改' : '添加资产' }}
      </van-button>
    </div>
  </van-form>
</template>

<script setup lang="ts">
import { ref, computed, watch } from 'vue'
import type { Asset, Category } from '@/types'

const props = withDefaults(defineProps<{
  initialData?: Partial<Asset>
  categories?: Category[]
  isEdit?: boolean
  loading?: boolean
}>(), {
  isEdit: false,
  loading: false,
  categories: () => []
})

const emit = defineEmits<{
  submit: [data: Partial<Asset>]
}>()

const form = ref<Record<string, any>>({
  name: '',
  asset_type: 'physical',
  category_id: '',
  purchase_price: '',
  current_value: '',
  purchase_date: '',
  status: 'in_use',
  location: '',
  institution: '',
  interest_rate: '',
  maturity_date: '',
  expected_lifespan_days: '',
  annual_maintenance_cost: '',
  usage_frequency: '',
  notes: ''
})

watch(() => props.initialData, (data) => {
  if (data) {
    Object.keys(form.value).forEach(key => {
      if ((data as any)[key] !== undefined) {
        form.value[key] = String((data as any)[key] ?? '')
      }
    })
  }
}, { immediate: true })

const showTypePicker = ref(false)
const showCategoryPicker = ref(false)
const showDatePicker = ref(false)
const showStatusPicker = ref(false)
const showUsagePicker = ref(false)
const showMaturityPicker = ref(false)

const now = new Date()
const datePickerValue = ref([
  String(now.getFullYear()),
  String(now.getMonth() + 1).padStart(2, '0'),
  String(now.getDate()).padStart(2, '0')
])
const maturityPickerValue = ref([...datePickerValue.value])

const typeColumns = [
  { text: '实物资产', value: 'physical' },
  { text: '金融资产', value: 'financial' }
]

const typeDisplayMap: Record<string, string> = { physical: '实物资产', financial: '金融资产' }

const statusColumns = [
  { text: '使用中', value: 'in_use' },
  { text: '闲置', value: 'idle' },
  { text: '已出售', value: 'sold' },
  { text: '已报废', value: 'retired' }
]

const statusDisplayMap: Record<string, string> = {
  in_use: '使用中', idle: '闲置', sold: '已出售', retired: '已报废'
}

const usageColumns = [
  { text: '每天', value: 'daily' },
  { text: '每周', value: 'weekly' },
  { text: '每月', value: 'monthly' },
  { text: '很少', value: 'rarely' },
  { text: '闲置', value: 'idle' }
]

const usageDisplayMap: Record<string, string> = {
  daily: '每天', weekly: '每周', monthly: '每月', rarely: '很少', idle: '闲置'
}

const categoryColumns = computed(() =>
  props.categories
    .filter(c => !form.value.asset_type || c.asset_type === form.value.asset_type)
    .map(c => ({ text: `${c.icon} ${c.name}`, value: c.id }))
)

const categoryDisplay = computed(() => {
  const cat = props.categories.find(c => c.id === form.value.category_id)
  return cat ? `${cat.icon} ${cat.name}` : ''
})

const statusDisplay = computed(() => statusDisplayMap[form.value.status] || '')
const usageDisplay = computed(() => usageDisplayMap[form.value.usage_frequency] || '')

function onTypeConfirm({ selectedOptions }: any) {
  form.value.asset_type = selectedOptions[0].value
  showTypePicker.value = false
}

function onCategoryConfirm({ selectedOptions }: any) {
  form.value.category_id = selectedOptions[0].value
  showCategoryPicker.value = false
}

function onDateConfirm({ selectedValues }: any) {
  form.value.purchase_date = selectedValues.join('-')
  showDatePicker.value = false
}

function onMaturityConfirm({ selectedValues }: any) {
  form.value.maturity_date = selectedValues.join('-')
  showMaturityPicker.value = false
}

function onStatusConfirm({ selectedOptions }: any) {
  form.value.status = selectedOptions[0].value
  showStatusPicker.value = false
}

function onUsageConfirm({ selectedOptions }: any) {
  form.value.usage_frequency = selectedOptions[0].value
  showUsagePicker.value = false
}

function onSubmit() {
  const data: Partial<Asset> = {
    name: form.value.name,
    asset_type: form.value.asset_type,
    category_id: form.value.category_id || undefined,
    purchase_price: Number(form.value.purchase_price),
    current_value: Number(form.value.current_value),
    purchase_date: form.value.purchase_date || undefined,
    status: form.value.status,
    notes: form.value.notes || undefined
  }

  if (form.value.asset_type === 'physical') {
    data.location = form.value.location || undefined
    data.expected_lifespan_days = form.value.expected_lifespan_days ? Number(form.value.expected_lifespan_days) : undefined
    data.annual_maintenance_cost = form.value.annual_maintenance_cost ? Number(form.value.annual_maintenance_cost) : undefined
    data.usage_frequency = form.value.usage_frequency || undefined
  } else {
    data.institution = form.value.institution || undefined
    data.interest_rate = form.value.interest_rate ? Number(form.value.interest_rate) : undefined
    data.maturity_date = form.value.maturity_date || undefined
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
:deep(.van-cell-group__title) {
  font-size: 13px;
  color: #969799;
}
</style>
