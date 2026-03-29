<template>
  <van-form @submit="onSubmit">

    <!-- P1: Image upload — top independent section -->
    <div class="image-upload-section">
      <van-uploader
        v-model="fileList"
        :max-count="1"
        :max-size="5 * 1024 * 1024"
        :after-read="afterRead"
        @delete="onDelete"
      >
        <template #default>
          <div v-if="!fileList.length" class="image-placeholder">
            <van-icon name="photograph" size="28" color="var(--van-text-color-3)" />
            <span class="image-hint">添加图片</span>
          </div>
        </template>
      </van-uploader>
    </div>

    <!-- P1: Asset type — SegmentedControl -->
    <div class="type-segmented">
      <div
        class="type-option"
        :class="{ active: form.asset_type === 'physical' }"
        @click="onTypeChange('physical')"
      >实物资产</div>
      <div
        class="type-option"
        :class="{ active: form.asset_type === 'financial' }"
        @click="onTypeChange('financial')"
      >金融资产</div>
    </div>

    <!-- Basic info -->
    <van-cell-group inset title="基本信息">
      <van-field
        v-model="form.name"
        label="名称"
        placeholder="请输入资产名称"
        :rules="[{ required: true, message: '请输入名称' }]"
      />

      <!-- P0: Category — inline icon grid -->
      <van-cell title="分类" />
      <CategoryGrid
        v-model="form.category_id"
        :categories="categories"
        :asset-type="form.asset_type"
      />

      <van-field
        v-model="form.purchase_price"
        type="number"
        label="购入价格"
        placeholder="请输入购入价格"
        :rules="[{ required: true, message: '请输入购入价格' }]"
      >
        <template #left-icon>
          <CurrencyButton v-model="form.currency" />
        </template>
      </van-field>

      <!-- P0: current_value — with "同购入价" button -->
      <van-field
        v-model="form.current_value"
        type="number"
        label="当前价值"
        placeholder="请输入当前价值"
        :rules="[{ required: true, message: '请输入当前价值' }]"
      >
        <template #left-icon>
          <span class="field-prefix">{{ currencySymbol }}</span>
        </template>
        <template #right-icon>
          <van-button
            size="mini"
            plain
            type="primary"
            :disabled="!form.purchase_price"
            class="same-price-btn"
            @click.stop="syncPurchasePrice"
          >同购入价</van-button>
        </template>
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

      <!-- P0: Status — only show in edit mode -->
      <template v-if="isEdit">
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
      </template>
    </van-cell-group>

    <!-- Physical asset fields — reordered: freq → lifespan → location → maintenance -->
    <van-cell-group v-if="form.asset_type === 'physical'" inset title="实物资产信息">

      <!-- P1: Usage frequency — icon button group -->
      <van-cell title="使用频率" />
      <UsageFreqSelector v-model="form.usage_frequency" />

      <!-- P0: Expected lifespan — unit years + "不限" -->
      <van-field
        v-model="expectedLifeYears"
        type="digit"
        label="预期寿命"
        placeholder="请输入年限"
      >
        <template #extra>
          <span class="unit-label">年</span>
        </template>
        <template #right-icon>
          <van-button
            size="mini"
            plain
            class="same-price-btn"
            @click.stop="expectedLifeYears = ''"
          >不限</van-button>
        </template>
      </van-field>

      <van-field v-model="form.location" label="存放位置" placeholder="可选" />

      <van-field v-model="form.annual_maintenance_cost" type="number" label="年维护费" placeholder="可选">
        <template #left-icon><span class="field-prefix">{{ currencySymbol }}</span></template>
      </van-field>
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

    <!-- P1: Tags + notes -->
    <van-cell-group inset title="标签与备注">
      <van-cell title="标签">
        <template #value>
          <TagSelector
            v-model="selectedTagIds"
            :tags="availableTags"
            @tag-created="onTagCreated"
          />
        </template>
      </van-cell>
      <van-field v-model="form.notes" type="textarea" label="备注" placeholder="可选" rows="2" autosize />
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
import type { Asset, Category, Tag } from '@/types'
import { uploadImage } from '@/api/upload'
import { getTags, createTag as apiCreateTag } from '@/api/tags'
import CurrencyButton from '@/components/common/CurrencyButton.vue'
import CategoryGrid from './CategoryGrid.vue'
import UsageFreqSelector from './UsageFreqSelector.vue'
import TagSelector from './TagSelector.vue'

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
  currency: 'CNY',
  purchase_date: '',
  status: 'in_use',
  location: '',
  institution: '',
  interest_rate: '',
  maturity_date: '',
  annual_maintenance_cost: '',
  usage_frequency: 'daily',
  notes: '',
  image_url: ''
})

// P0: Lifespan in years (display) — submitted as days
// Use string for van-field v-model compatibility; empty string = "不限" (null days)
const expectedLifeYears = ref<string>('')

watch(expectedLifeYears, (val) => {
  const num = val !== '' ? parseInt(val, 10) : null
  form.value.expected_lifespan_days = num !== null && !isNaN(num) ? Math.round(num * 365) : null
})

// P0: Sync current_value = purchase_price
function syncPurchasePrice() {
  if (form.value.purchase_price) {
    form.value.current_value = form.value.purchase_price
  }
}

// P1: Type change — clear type-specific fields
function onTypeChange(type: 'physical' | 'financial') {
  if (form.value.asset_type === type) return
  form.value.asset_type = type
  if (type === 'financial') {
    form.value.location = ''
    form.value.expected_lifespan_days = null
    form.value.annual_maintenance_cost = ''
    form.value.usage_frequency = ''
    expectedLifeYears.value = ''
  } else {
    form.value.institution = ''
    form.value.interest_rate = ''
    form.value.maturity_date = ''
    form.value.usage_frequency = 'daily'
  }
}

// Currency symbol helper
const CURRENCY_SYMBOLS: Record<string, string> = {
  CNY: '¥', USD: '$', EUR: '€', GBP: '£', JPY: '¥', HKD: 'HK$',
}
const currencySymbol = computed(() => CURRENCY_SYMBOLS[form.value.currency] || form.value.currency)

// Image upload state
const fileList = ref<{ url: string; status?: 'uploading' | 'done' | 'failed'; message?: string }[]>([])

// Tags state
const availableTags = ref<Tag[]>([])
const selectedTagIds = ref<string[]>([])

async function fetchTags() {
  try {
    const res = await getTags()
    availableTags.value = res.data
  } catch {
    // non-critical
  }
}

function onTagCreated(tag: Tag) {
  availableTags.value.push(tag)
}

// Populate form from initialData (edit mode)
watch(() => props.initialData, (data) => {
  if (data) {
    Object.keys(form.value).forEach(key => {
      if ((data as any)[key] !== undefined) {
        form.value[key] = String((data as any)[key] ?? '')
      }
    })
    // P0: reverse-convert lifespan days → years
    expectedLifeYears.value = (data as any).expected_lifespan_days
      ? String(Math.round(Number((data as any).expected_lifespan_days) / 365))
      : ''
    // Tags
    selectedTagIds.value = (data as any).tags?.map((t: Tag) => t.id) ?? []
    // Image preview
    if (data.image_url) {
      const imageUrl = data.image_url.startsWith('/') ? `/api/v1${data.image_url}` : data.image_url
      fileList.value = [{ url: imageUrl }]
    }
  }
}, { immediate: true })

// Fetch tags on mount
fetchTags()

// Pickers state
const showDatePicker = ref(false)
const showStatusPicker = ref(false)
const showMaturityPicker = ref(false)

const now = new Date()
const datePickerValue = ref([
  String(now.getFullYear()),
  String(now.getMonth() + 1).padStart(2, '0'),
  String(now.getDate()).padStart(2, '0')
])
const maturityPickerValue = ref([...datePickerValue.value])

const statusColumns = [
  { text: '服役中', value: 'in_use' },
  { text: '闲置', value: 'idle' },
  { text: '已出售', value: 'sold' },
  { text: '已退役', value: 'retired' }
]
const statusDisplayMap: Record<string, string> = {
  in_use: '服役中', idle: '闲置', sold: '已出售', retired: '已退役'
}
const statusDisplay = computed(() => statusDisplayMap[form.value.status] || '')

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

// Image upload handlers
async function afterRead(file: any) {
  file.status = 'uploading'
  try {
    const res = await uploadImage(file.file)
    file.status = 'done'
    file.url = `/api/v1${res.data.url}`
    form.value.image_url = res.data.url
  } catch {
    file.status = 'failed'
    file.message = '上传失败'
  }
}

function onDelete() {
  form.value.image_url = ''
}

function onSubmit() {
  const data: Partial<Asset> = {
    name: form.value.name,
    asset_type: form.value.asset_type,
    category_id: form.value.category_id || undefined,
    purchase_price: Number(form.value.purchase_price),
    current_value: Number(form.value.current_value),
    currency: form.value.currency,
    purchase_date: form.value.purchase_date || undefined,
    status: form.value.status,
    notes: form.value.notes || undefined,
    image_url: form.value.image_url || undefined,
    tag_ids: selectedTagIds.value.length ? selectedTagIds.value : undefined,
  } as any

  if (form.value.asset_type === 'physical') {
    ;(data as any).location = form.value.location || undefined
    ;(data as any).expected_lifespan_days = form.value.expected_lifespan_days ?? undefined
    ;(data as any).annual_maintenance_cost = form.value.annual_maintenance_cost ? Number(form.value.annual_maintenance_cost) : undefined
    ;(data as any).usage_frequency = form.value.usage_frequency || undefined
  } else {
    ;(data as any).institution = form.value.institution || undefined
    ;(data as any).interest_rate = form.value.interest_rate ? Number(form.value.interest_rate) : undefined
    ;(data as any).maturity_date = form.value.maturity_date || undefined
  }

  emit('submit', data)
}
</script>

<style scoped>
/* P1: Image upload section */
.image-upload-section {
  display: flex;
  justify-content: center;
  padding: 20px 16px 12px;
  background: var(--van-background);
}
.image-placeholder {
  width: 76px;
  height: 76px;
  border-radius: 14px;
  border: 2px dashed var(--van-border-color);
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 4px;
}
.image-hint {
  font-size: 10px;
  color: var(--van-text-color-3);
}
:deep(.van-uploader__preview-image) {
  width: 76px;
  height: 76px;
  border-radius: 14px;
}

/* P1: Type segmented control */
.type-segmented {
  display: flex;
  margin: 8px 16px 4px;
  background: var(--van-background-2);
  border-radius: 10px;
  padding: 3px;
}
.type-option {
  flex: 1;
  text-align: center;
  padding: 8px;
  border-radius: 8px;
  font-size: 13px;
  color: var(--van-text-color-2);
  cursor: pointer;
  transition: background 0.15s, color 0.15s;
}
.type-option.active {
  background: var(--van-primary-color);
  color: #fff;
  font-weight: 600;
}

/* Shared */
.field-prefix {
  color: var(--text-primary);
  margin-right: 4px;
}
.unit-label {
  font-size: 12px;
  color: var(--van-text-color-2);
  margin-left: 4px;
}
.same-price-btn {
  height: 24px;
  padding: 0 8px;
  font-size: 11px;
}
.form-actions {
  padding: 16px;
}
:deep(.van-cell-group__title) {
  font-size: 13px;
  color: var(--text-tertiary);
}
</style>
