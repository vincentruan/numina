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
            <van-icon name="photograph" size="32" color="var(--van-text-color-3)" />
            <span class="image-hint">点击添加图片</span>
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
        @blur="onNameBlur"
      >
        <template v-if="aiSuggesting" #right-icon>
          <van-loading size="16" />
        </template>
      </van-field>

      <!-- P0: Category — tap-to-open popup picker -->
      <van-field
        :model-value="selectedCategoryName"
        is-link
        readonly
        label="分类"
        placeholder="请选择分类"
        :rules="[{ required: true, message: '请选择分类' }]"
        @click="showCategoryPicker = true"
      />
      <van-popup v-model:show="showCategoryPicker" position="bottom" round>
        <div class="category-popup">
          <div v-if="filteredCategories.length === 0" class="category-empty">暂无分类</div>
          <div v-else class="category-grid-popup">
            <div
              v-for="cat in filteredCategories"
              :key="cat.id"
              class="category-item"
              :class="{ selected: form.category_id === cat.id }"
              @click="selectCategory(cat.id)"
            >
              <svg class="cat-icon" aria-hidden="true">
                <use :href="`#${getIconId(cat.icon)}`" />
              </svg>
              <span class="cat-name">{{ cat.name }}</span>
            </div>
          </div>
        </div>
      </van-popup>

      <van-field
        v-model="form.purchase_price"
        type="number" inputmode="decimal"
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
        type="number" inputmode="decimal"
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
        :rules="[{ required: true, message: '请选择购入日期' }]"
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
        :class="{ 'ai-fill': aiFilledFields.has('expected_lifespan_years') }"
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

      <van-field v-model="form.location" label="存放位置" placeholder="可选，如：书房" />

      <van-field v-model="form.annual_maintenance_cost" type="number" inputmode="decimal" label="年维护费" placeholder="可选，单位：元">
        <template #left-icon><span class="field-prefix">{{ currencySymbol }}</span></template>
      </van-field>
    </van-cell-group>

    <!-- Financial asset fields -->
    <van-cell-group v-if="form.asset_type === 'financial'" inset title="金融资产信息">
      <van-field v-model="form.institution" label="金融机构" placeholder="请输入金融机构" />
      <van-field v-model="form.interest_rate" type="number" inputmode="decimal" label="利率(%)" placeholder="请输入利率" />
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

    <!-- Physical asset: warranty expiry date -->
    <van-cell-group v-if="form.asset_type === 'physical'" inset title="保修信息">
      <van-field
        v-model="form.warranty_expiry_date"
        is-link
        readonly
        label="保修到期日"
        placeholder="选择保修到期日"
        @click="showWarrantyPicker = true"
      />
      <van-popup v-model:show="showWarrantyPicker" position="bottom" round>
        <van-date-picker
          v-model="warrantyPickerValue"
          title="保修到期日"
          @confirm="onWarrantyConfirm"
          @cancel="showWarrantyPicker = false"
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
      <van-field v-model="form.notes" type="textarea" label="备注" placeholder="可选" rows="2" autosize :class="{ 'ai-fill': aiFilledFields.has('notes') }" />
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
import { getAssetField } from '@/types'
import { uploadImage } from '@/api/upload'
import { getTags } from '@/api/tags'
import { suggestAssetFields } from '@/api/ai'
import { useAIStore } from '@/stores/ai'
import CurrencyButton from '@/components/common/CurrencyButton.vue'
import UsageFreqSelector from './UsageFreqSelector.vue'
import TagSelector from './TagSelector.vue'
import { getIconId } from '@/utils/icon'

const props = withDefaults(defineProps<{
  initialData?: Partial<Asset>
  categories?: Category[]
  isEdit?: boolean
  loading?: boolean
}>(), {
  initialData: undefined,
  isEdit: false,
  loading: false,
  categories: () => []
})

const aiStore = useAIStore()

const emit = defineEmits<{
  submit: [data: Partial<Asset>]
}>()

const form = ref<Record<string, string | number | boolean | null | undefined>>({
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
  warranty_expiry_date: '',
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
  form.value.category_id = ''
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

// Category picker
const showCategoryPicker = ref(false)
const filteredCategories = computed(() =>
  props.categories.filter(c => c.asset_type === form.value.asset_type)
)
const selectedCategoryName = computed(() => {
  const cat = props.categories.find(c => c.id === form.value.category_id)
  return cat?.name ?? ''
})

function selectCategory(id: string) {
  form.value.category_id = id
  showCategoryPicker.value = false
}

// Image upload state
const fileList = ref<{ url: string; content?: string; status?: 'uploading' | 'done' | 'failed'; message?: string }[]>([])

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

// AI suggest
const aiSuggesting = ref(false)
const aiFilledFields = ref<Set<string>>(new Set())

async function onNameBlur() {
  if (props.isEdit) return
  const name = form.value.name?.trim()
  if (!name || name.length < 2) return
  if (!aiStore.aiEnabled) return

  const categoryName = props.categories.find(c => c.id === form.value.category_id)?.name ?? ''

  aiSuggesting.value = true
  try {
    const res = await suggestAssetFields({
      name,
      category: categoryName,
      asset_type: form.value.asset_type,
    })
    const s = res.data
    const filled = new Set<string>()

    if (form.value.asset_type === 'physical') {
      if (s.expected_lifespan_years != null && !expectedLifeYears.value) {
        expectedLifeYears.value = String(s.expected_lifespan_years)
        filled.add('expected_lifespan_years')
      }
      if (s.usage_frequency && form.value.usage_frequency === 'daily') {
        form.value.usage_frequency = s.usage_frequency
        filled.add('usage_frequency')
      }
    }
    if (s.notes_hint && !form.value.notes) {
      form.value.notes = s.notes_hint
      filled.add('notes')
    }
    if (s.suggested_tags?.length && !selectedTagIds.value.length) {
      // Match suggested tag names to existing tags
      const matched = availableTags.value
        .filter(t => s.suggested_tags.includes(t.name))
        .map(t => t.id)
      if (matched.length) {
        selectedTagIds.value = matched
        filled.add('tags')
      }
    }
    aiFilledFields.value = filled
  } catch {
    // silent — AI suggest is non-critical
  } finally {
    aiSuggesting.value = false
  }
}

// Populate form from initialData (edit mode)
watch(() => props.initialData, (data) => {
  if (data) {
    // Copy common fields
    const commonKeys: (keyof Asset)[] = [
      'name', 'asset_type', 'category_id', 'purchase_price', 'current_value',
      'currency', 'purchase_date', 'status', 'notes', 'image_url'
    ]
    for (const key of commonKeys) {
      const value = getAssetField<string | number>(data, key)
      if (value !== undefined) {
        form.value[key] = String(value ?? '')
      }
    }
    // Copy physical fields
    const physicalKeys: (keyof Asset)[] = ['location', 'annual_maintenance_cost', 'usage_frequency', 'warranty_expiry_date']
    for (const key of physicalKeys) {
      const value = getAssetField<string | number>(data, key)
      if (value !== undefined) {
        form.value[key] = String(value ?? '')
      }
    }
    // Copy financial fields
    const financialKeys: (keyof Asset)[] = ['institution', 'interest_rate', 'maturity_date']
    for (const key of financialKeys) {
      const value = getAssetField<string | number>(data, key)
      if (value !== undefined) {
        form.value[key] = String(value ?? '')
      }
    }
    // P0: reverse-convert lifespan days → years
    const lifespanDays = getAssetField<number>(data, 'expected_lifespan_days')
    expectedLifeYears.value = lifespanDays
      ? String(Math.round(lifespanDays / 365))
      : ''
    // Tags
    const tags = getAssetField<Tag[]>(data, 'tags')
    selectedTagIds.value = tags?.map((t: Tag) => t.id) ?? []
    // Image preview
    const imageUrl = getAssetField<string>(data, 'image_url')
    if (imageUrl) {
      const fullUrl = imageUrl.startsWith('/api/v1') ? imageUrl : `/api/v1${imageUrl}`
      fileList.value = [{ url: fullUrl, content: fullUrl, status: 'done' }]
    }
  }
}, { immediate: true })

// Fetch tags on mount
fetchTags()

// Pickers state
const showDatePicker = ref(false)
const showStatusPicker = ref(false)
const showMaturityPicker = ref(false)
const showWarrantyPicker = ref(false)

const now = new Date()
const datePickerValue = ref([
  String(now.getFullYear()),
  String(now.getMonth() + 1).padStart(2, '0'),
  String(now.getDate()).padStart(2, '0')
])
const maturityPickerValue = ref([...datePickerValue.value])
const warrantyPickerValue = ref([...datePickerValue.value])

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

function onDateConfirm({ selectedValues }: { selectedValues: string[] }) {
  form.value.purchase_date = selectedValues.join('-')
  showDatePicker.value = false
}

function onMaturityConfirm({ selectedValues }: { selectedValues: string[] }) {
  form.value.maturity_date = selectedValues.join('-')
  showMaturityPicker.value = false
}

function onWarrantyConfirm({ selectedValues }: { selectedValues: string[] }) {
  form.value.warranty_expiry_date = selectedValues.join('-')
  showWarrantyPicker.value = false
}

function onStatusConfirm({ selectedOptions }: { selectedOptions: { value: string }[] }) {
  form.value.status = selectedOptions[0].value
  showStatusPicker.value = false
}

// Image upload handlers
async function afterRead(file: { file: File; url?: string; content?: string; status: string; message?: string }) {
  file.status = 'uploading'
  try {
    const res = await uploadImage(file.file)
    file.status = 'done'
    const fullUrl = `/api/v1${res.data.url}`
    file.url = fullUrl
    file.content = fullUrl
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
  // Build base payload with common fields
  const data: Partial<Asset> & { tag_ids?: string[] } = {
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
  }

  // Add type-specific fields based on asset_type
  if (form.value.asset_type === 'physical') {
    data.location = form.value.location || undefined
    data.expected_lifespan_days = form.value.expected_lifespan_days ?? undefined
    data.annual_maintenance_cost = form.value.annual_maintenance_cost ? Number(form.value.annual_maintenance_cost) : undefined
    data.usage_frequency = form.value.usage_frequency || undefined
    data.warranty_expiry_date = form.value.warranty_expiry_date || undefined
  } else {
    data.institution = form.value.institution || undefined
    data.interest_rate = form.value.interest_rate ? Number(form.value.interest_rate) : undefined
    data.maturity_date = form.value.maturity_date || undefined
  }

  emit('submit', data)
}
</script>

<style scoped>
/* P1: Image upload section */
.image-upload-section {
  display: flex;
  justify-content: center;
  padding: 24px 16px 16px;
  background: var(--van-background);
}
.image-placeholder {
  width: 120px;
  height: 120px;
  border-radius: 16px;
  border: 2px dashed var(--van-border-color);
  background: var(--van-background-2);
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 6px;
}
.image-hint {
  font-size: 12px;
  color: var(--van-text-color-3);
}
:deep(.van-uploader__preview-image) {
  width: 120px;
  height: 120px;
  border-radius: 16px;
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
[data-theme='dark'] .type-option.active {
  background: var(--color-lavender, #bdbbff);
  color: #010120;
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
  height: 26px;
  line-height: 24px;
  padding: 0 10px;
  font-size: 12px;
  white-space: nowrap;
  vertical-align: middle;
}
:deep(.van-field__right-icon) {
  display: flex;
  align-items: center;
}
.form-actions {
  padding: 16px;
}
/* AI-filled field highlight */
:deep(.ai-fill .van-field__control) {
  background: color-mix(in srgb, var(--van-primary-color) 8%, transparent);
  border-radius: 4px;
  transition: background 0.3s;
}
[data-theme='dark'] :deep(.ai-fill .van-field__control) {
  background: color-mix(in srgb, var(--van-primary-color) 15%, transparent);
}
:deep(.van-cell-group__title) {
  font-size: 13px;
  color: var(--text-tertiary);
}

/* Category popup */
.category-popup {
  padding: 16px;
  max-height: 60vh;
  overflow-y: auto;
}
.category-empty {
  text-align: center;
  padding: 24px 0;
  font-size: 14px;
  color: var(--van-text-color-3);
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
  font-size: 12px;
  color: var(--van-text-color-2);
  margin-top: 4px;
  text-align: center;
  line-height: 1.2;
}
.category-item.selected .cat-name {
  color: var(--van-primary-color);
}
</style>
