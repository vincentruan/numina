<template>
  <van-form ref="formRef" @submit="onSubmit" @failed="onValidationFailed">
    <div ref="formContainerRef">

    <!-- P1: Image upload — top independent section -->
    <div class="image-upload-section">
      <div class="avatar-area">
        <!-- Current icon / placeholder -->
        <div v-if="form.image_url" class="asset-preview" @click="showIconPicker = true">
          <img :src="form.image_url" />
        </div>
        <div v-else class="image-placeholder" @click="showIconPicker = true">
          <van-icon name="photograph" size="32" color="var(--van-text-color-3)" />
          <span class="image-hint">{{ t('assetForm.imageUploadHint') }}</span>
        </div>
        <!-- Change icon button -->
        <van-button
          size="small"
          icon="exchange"
          class="change-icon-btn"
          @click="showIconPicker = true"
        >{{ t('iconPicker.changeIcon') }}</van-button>
      </div>
      <!-- Hidden file inputs for gallery/camera selection (triggered by IconPicker) -->
      <input
        ref="galleryFileInput"
        type="file"
        accept="image/jpeg,image/png,image/webp"
        hidden
        @change="onFileSelected"
      />
      <input
        ref="cameraFileInput"
        type="file"
        accept="image/jpeg,image/png,image/webp"
        capture="environment"
        hidden
        @change="onFileSelected"
      />
    </div>

    <!-- P1: Asset type — SegmentedControl -->
    <div class="type-segmented">
      <div
        class="type-option"
        :class="{ active: form.asset_type === 'physical' }"
        @click="onTypeChange('physical')"
      >{{ t('assetForm.typePhysical') }}</div>
      <div
        class="type-option"
        :class="{ active: form.asset_type === 'financial' }"
        @click="onTypeChange('financial')"
      >{{ t('assetForm.typeFinancial') }}</div>
    </div>

    <!-- Basic info — always expanded (not collapsible) -->
    <van-cell-group inset :title="t('assetForm.sectionBasicInfo')">
      <van-field
        v-model="form.name"
        required
        name="name"
        :label="t('assetForm.nameLabel')"
        :placeholder="t('assetForm.namePlaceholder')"
        :rules="[{ required: true, message: t('assetForm.nameRequired') }]"
        @blur="onNameBlur"
      >
        <template v-if="aiSuggesting" #right-icon>
          <van-loading size="16" />
        </template>
      </van-field>

      <!-- P0: Category — tap-to-open popup picker -->
      <van-field
        :model-value="selectedCategoryName"
        required
        name="category_id"
        is-link
        readonly
        :label="t('assetForm.categoryLabel')"
        :placeholder="t('assetForm.categoryPlaceholder')"
        :rules="[{ required: true, message: t('assetForm.categoryRequired') }]"
        @click="showCategoryPicker = true"
      />
      <van-popup v-model:show="showCategoryPicker" position="bottom" round>
        <div class="category-popup">
          <div v-if="filteredCategories.length === 0" class="category-empty">{{ t('assetForm.categoryEmpty') }}</div>
          <div v-else class="category-grid-popup">
            <div
              v-for="cat in filteredCategories"
              :key="cat.id"
              class="category-item"
              :class="{ selected: form.category_id === cat.id }"
              @click="selectCategory(cat.id)"
            >
              <SvgIcon :name="getIconId(cat.icon)" class="cat-icon" />
              <span class="cat-name">{{ cat.name }}</span>
            </div>
          </div>
        </div>
      </van-popup>

      <van-field
        v-model="form.purchase_price"
        required
        name="purchase_price"
        type="number" inputmode="decimal"
        :label="t('assetForm.purchasePriceLabel')"
        :placeholder="t('assetForm.purchasePricePlaceholder')"
        :rules="[{ required: true, message: t('assetForm.purchasePriceRequired') }]"
      >
        <template #left-icon>
          <CurrencyButton v-model="form.currency" />
        </template>
      </van-field>

      <!-- P0: current_value — with "同购入价" button -->
      <van-field
        v-model="form.current_value"
        required
        name="current_value"
        type="number" inputmode="decimal"
        :label="t('assetForm.currentValueLabel')"
        :placeholder="t('assetForm.currentValuePlaceholder')"
        :rules="[{ required: true, message: t('assetForm.currentValueRequired') }]"
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
          >{{ t('assetForm.samePriceBtn') }}</van-button>
        </template>
      </van-field>

      <van-field
        v-model="form.purchase_date"
        required
        name="purchase_date"
        is-link
        readonly
        :label="t('assetForm.purchaseDateLabel')"
        :placeholder="t('assetForm.purchaseDatePlaceholder')"
        :rules="[{ required: true, message: t('assetForm.purchaseDateRequired') }]"
        @click="showDatePicker = true"
      />
      <van-popup v-model:show="showDatePicker" position="bottom" round>
        <van-date-picker
          v-model="datePickerValue"
          :title="t('assetForm.datePickerTitle')"
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
          :label="t('assetForm.statusLabel')"
          :placeholder="t('assetForm.statusPlaceholder')"
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

    <!-- Physical asset fields — collapsible, auto-expand when asset_type=physical -->
    <van-collapse
      v-if="form.asset_type === 'physical'"
      v-model="expandedSections"
      class="form-collapse"
    >
      <van-collapse-item :title="t('assetForm.sectionPhysicalInfo')" name="physical">
        <!-- P1: Usage frequency — icon button group -->
        <van-cell :title="t('assetForm.usageFreqLabel')" />
        <UsageFreqSelector v-model="form.usage_frequency" />

        <!-- P0: Expected lifespan — unit years + "不限" -->
        <van-field
          v-model="expectedLifeYears"
          name="expected_lifespan_years"
          type="digit"
          :label="t('assetForm.lifespanLabel')"
          :placeholder="t('assetForm.lifespanPlaceholder')"
          :class="{ 'ai-fill': aiFilledFields.has('expected_lifespan_years') }"
        >
          <template #extra>
            <span class="unit-label">{{ t('assetForm.lifespanUnitYears') }}</span>
          </template>
          <template #right-icon>
            <van-button
              size="mini"
              plain
              class="same-price-btn"
              @click.stop="expectedLifeYears = ''"
            >{{ t('assetForm.lifespanUnlimited') }}</van-button>
          </template>
        </van-field>

        <van-field v-model="form.location" name="location" :label="t('assetForm.locationLabel')" :placeholder="t('assetForm.locationPlaceholder')" />

        <van-field v-model="form.annual_maintenance_cost" name="annual_maintenance_cost" type="number" inputmode="decimal" :label="t('assetForm.maintenanceLabel')" :placeholder="t('assetForm.maintenancePlaceholder')">
          <template #left-icon><span class="field-prefix">{{ currencySymbol }}</span></template>
        </van-field>
      </van-collapse-item>
    </van-collapse>

    <!-- Financial asset fields — collapsible -->
    <van-collapse
      v-if="form.asset_type === 'financial'"
      v-model="expandedSections"
      class="form-collapse"
    >
      <van-collapse-item :title="t('assetForm.sectionFinancialInfo')" name="financial">
        <van-field v-model="form.institution" name="institution" :label="t('assetForm.institutionLabel')" :placeholder="t('assetForm.institutionPlaceholder')" />
        <van-field v-model="form.interest_rate" name="interest_rate" type="number" inputmode="decimal" :label="t('assetForm.interestRateLabel')" :placeholder="t('assetForm.interestRatePlaceholder')" />
        <van-field
          v-model="form.maturity_date"
          name="maturity_date"
          is-link
          readonly
          :label="t('assetForm.maturityDateLabel')"
          :placeholder="t('assetForm.maturityDatePlaceholder')"
          @click="showMaturityPicker = true"
        />
        <van-popup v-model:show="showMaturityPicker" position="bottom" round>
          <van-date-picker
            v-model="maturityPickerValue"
            :title="t('assetForm.maturityPickerTitle')"
            @confirm="onMaturityConfirm"
            @cancel="showMaturityPicker = false"
          />
        </van-popup>
      </van-collapse-item>
    </van-collapse>

    <!-- Physical asset: warranty expiry date — collapsible -->
    <van-collapse
      v-if="form.asset_type === 'physical'"
      v-model="expandedSections"
      class="form-collapse"
    >
      <van-collapse-item :title="t('assetForm.sectionWarrantyInfo')" name="warranty">
        <van-field
          v-model="form.warranty_expiry_date"
          name="warranty_expiry_date"
          is-link
          readonly
          :label="t('assetForm.warrantyExpiryLabel')"
          :placeholder="t('assetForm.warrantyExpiryPlaceholder')"
          @click="showWarrantyPicker = true"
        />
        <van-popup v-model:show="showWarrantyPicker" position="bottom" round>
          <van-date-picker
            v-model="warrantyPickerValue"
            :title="t('assetForm.warrantyPickerTitle')"
            @confirm="onWarrantyConfirm"
            @cancel="showWarrantyPicker = false"
          />
        </van-popup>
      </van-collapse-item>
    </van-collapse>

    <!-- P1: Tags + notes — collapsible -->
    <van-collapse v-model="expandedSections" class="form-collapse">
      <van-collapse-item :title="t('assetForm.sectionTagsNotes')" name="tagsNotes">
        <van-cell :title="t('assetForm.tagsLabel')">
          <template #value>
            <TagSelector
              v-model="selectedTagIds"
              :tags="availableTags"
              @tag-created="onTagCreated"
            />
          </template>
        </van-cell>
        <van-field v-model="form.notes" name="notes" type="textarea" :label="t('assetForm.notesLabel')" :placeholder="t('assetForm.notesPlaceholder')" rows="2" autosize :class="{ 'ai-fill': aiFilledFields.has('notes') }" />
      </van-collapse-item>
    </van-collapse>

    <div class="form-actions">
      <van-button round block type="primary" native-type="submit" :loading="loading">
        {{ isEdit ? t('asset.editAsset') : t('asset.addAsset') }}
      </van-button>
    </div>
    </div>
  </van-form>

  <!-- Logo cropper popup -->
  <LogoCropper
    v-model:show="showCropper"
    :source="cropperSource"
    @confirm="onCropperConfirm"
  />

  <!-- Icon picker popup (gallery + 3D icons) -->
  <IconPicker
    v-model:show="showIconPicker"
    :current-image-url="form.image_url"
    @select-image="onIconPickerSelectImage"
    @request-gallery="onIconPickerRequestGallery"
    @request-camera="onIconPickerRequestCamera"
    @delete="onIconPickerDelete"
  />
</template>

<script setup lang="ts">
import { ref, computed, watch, nextTick } from 'vue'
import { useI18n } from 'vue-i18n'
import type { FormInstance } from 'vant'
import { showLoadingToast, showSuccessToast, showFailToast, showToast } from 'vant'
import type { Asset, AssetRequestPayload, Category, Tag } from '@/types'
import { uploadImage } from '@/api/upload'
import { getTags } from '@/api/tags'
import { suggestAssetFields } from '@/api/ai'
import { useFamilyStore } from '@/stores/family'
import { useAuthStore } from '@/stores/auth'
import CurrencyButton from '@/components/common/CurrencyButton.vue'
import UsageFreqSelector from './UsageFreqSelector.vue'
import TagSelector from './TagSelector.vue'
import LogoCropper from './LogoCropper.vue'
import IconPicker from './IconPicker.vue'
import { useWatermark } from '@/composables/useWatermark'
import { getIconId } from '@/utils/icon'

const { t } = useI18n()

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

const familyStore = useFamilyStore()
const authStore = useAuthStore()

// Form ref for validation
const formRef = ref<FormInstance>()
const formContainerRef = ref<HTMLFormElement>()

// Collapsible sections state — shared array of expanded section names
// Basic info is always expanded (not collapsible). Others default collapsed.
const expandedSections = ref<string[]>([])

function expandSection(name: string) {
  if (!expandedSections.value.includes(name)) {
    expandedSections.value.push(name)
  }
}

const emit = defineEmits<{
  submit: [data: AssetRequestPayload]
}>()

interface FormState {
  name: string
  asset_type: 'physical' | 'financial'
  category_id: string
  purchase_price: string
  current_value: string
  currency: string
  purchase_date: string
  status: 'in_use' | 'idle' | 'sold' | 'retired'
  location: string
  institution: string
  interest_rate: string
  maturity_date: string
  warranty_expiry_date: string
  annual_maintenance_cost: string
  usage_frequency: 'daily' | 'weekly' | 'monthly' | 'rarely' | 'idle' | ''
  notes: string
  image_url: string
  expected_lifespan_days: number | null
}

const form = ref<FormState>({
  name: '',
  asset_type: 'physical',
  category_id: '',
  purchase_price: '',
  current_value: '',
  currency: authStore.user?.default_currency || 'CNY',
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
  image_url: '',
  expected_lifespan_days: null
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

// P1: Type change — clear type-specific fields + auto-expand physical section
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
    // Auto-expand physical section when switching to physical
    expandSection('physical')
  }
}

// Auto-expand physical section when asset_type changes to physical (e.g. via initialData)
watch(() => form.value.asset_type, (type) => {
  if (type === 'physical') {
    expandSection('physical')
  }
})

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

// Image upload state - tracks current image URL for preview
const fileList = ref<{ url: string; content?: string; status?: 'uploading' | 'done' | 'failed'; message?: string }[]>([])

// Logo cropper state
const { applyWatermark, canvasToBlob } = useWatermark()
const showCropper = ref(false)
const cropperSource = ref<File | string | null>(null)

// IconPicker state
const showIconPicker = ref(false)
const galleryFileInput = ref<HTMLInputElement>()
const cameraFileInput = ref<HTMLInputElement>()

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
  const name = form.value.name.trim()
  if (!name || name.length < 2) return
  if (!familyStore.aiEnabled) return

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
        form.value.usage_frequency = s.usage_frequency as 'daily' | 'weekly' | 'monthly' | 'rarely' | 'idle' | ''
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
    if (data.name !== undefined) form.value.name = String(data.name ?? '')
    if (data.asset_type !== undefined) form.value.asset_type = data.asset_type
    if (data.category_id !== undefined) form.value.category_id = String(data.category_id ?? '')
    if (data.purchase_price !== undefined) form.value.purchase_price = String(data.purchase_price ?? '')
    if (data.current_value !== undefined) form.value.current_value = String(data.current_value ?? '')
    if (data.currency !== undefined) form.value.currency = String(data.currency ?? '')
    if (data.purchase_date !== undefined) form.value.purchase_date = String(data.purchase_date ?? '')
    if (data.status !== undefined) form.value.status = data.status
    if (data.notes !== undefined) form.value.notes = String(data.notes ?? '')
    if (data.image_url !== undefined) form.value.image_url = String(data.image_url ?? '')

    // Copy physical fields
    if (data.location !== undefined) form.value.location = String(data.location ?? '')
    if (data.annual_maintenance_cost !== undefined) form.value.annual_maintenance_cost = String(data.annual_maintenance_cost ?? '')
    if (data.usage_frequency !== undefined) form.value.usage_frequency = data.usage_frequency ?? ''
    if (data.warranty_expiry_date !== undefined) form.value.warranty_expiry_date = String(data.warranty_expiry_date ?? '')

    // Copy financial fields
    if (data.institution !== undefined) form.value.institution = String(data.institution ?? '')
    if (data.interest_rate !== undefined) form.value.interest_rate = String(data.interest_rate ?? '')
    if (data.maturity_date !== undefined) form.value.maturity_date = String(data.maturity_date ?? '')

    // P0: reverse-convert lifespan days → years
    const lifespanDays = data.expected_lifespan_days
    expectedLifeYears.value = lifespanDays
      ? String(Math.round(lifespanDays / 365))
      : ''

    // Tags
    const tags = data.tags
    selectedTagIds.value = tags?.map((t: Tag) => t.id) ?? []

    // Image preview
    const imageUrl = data.image_url
    if (imageUrl) {
      fileList.value = [{ url: imageUrl, content: imageUrl, status: 'done' }]
    }

    // Edit mode: auto-expand sections that have data
    if (data.asset_type === 'physical') {
      expandSection('physical')
      // Expand warranty if warranty date is set
      if (data.warranty_expiry_date) {
        expandSection('warranty')
      }
    }
    if (data.asset_type === 'financial') {
      expandSection('financial')
    }
    // Expand tags/notes if tags or notes exist
    if ((tags && tags.length > 0) || data.notes) {
      expandSection('tagsNotes')
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

const statusColumns = computed(() => [
  { text: t('asset.inUse'), value: 'in_use' },
  { text: t('asset.idle'), value: 'idle' },
  { text: t('asset.sold'), value: 'sold' },
  { text: t('asset.retired'), value: 'retired' }
])
const statusDisplayMap: Record<string, string> = {
  in_use: t('asset.inUse'), idle: t('asset.idle'), sold: t('asset.sold'), retired: t('asset.retired')
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
  form.value.status = selectedOptions[0].value as 'in_use' | 'idle' | 'sold' | 'retired'
  showStatusPicker.value = false
}

// Image upload handlers
// Flow: IconPicker -> gallery/camera file input -> cropper -> watermark -> upload
//   or: IconPicker -> 3D icon select -> direct image_url set (no watermark)

// File size check (5MB max, matching previous van-uploader constraint)
const MAX_FILE_SIZE = 5 * 1024 * 1024

// Called when cropper confirms - applies watermark then uploads
async function onCropperConfirm(canvas: HTMLCanvasElement) {
  showCropper.value = false
  try {
    // Apply watermark
    const userName = authStore.user?.display_name || ''
    await applyWatermark(canvas, userName)

    // Convert to Blob
    const blob = await canvasToBlob(canvas, 'image/jpeg', 0.92)

    // Upload via existing API
    showLoadingToast({ message: t('common.loading'), forbidClick: true, duration: 0 })
    const res = await uploadImage(new File([blob], 'logo.jpg', { type: 'image/jpeg' }))

    // Update form and file list
    form.value.image_url = res.data.url
    fileList.value = [{ url: res.data.url, content: res.data.url, status: 'done' }]
    showSuccessToast(t('assetForm.uploadSuccess'))
  } catch {
    showFailToast(t('assetForm.watermarkFailed'))
  } finally {
    cropperSource.value = null
  }
}

// IconPicker event handlers
function onIconPickerSelectImage(url: string) {
  form.value.image_url = url
  fileList.value = [{ url, content: url, status: 'done' }]
  showIconPicker.value = false
}

function onIconPickerRequestGallery() {
  showIconPicker.value = false
  galleryFileInput.value?.click()
}

function onIconPickerRequestCamera() {
  showIconPicker.value = false
  cameraFileInput.value?.click()
}

function onIconPickerDelete() {
  form.value.image_url = ''
  fileList.value = []
  showIconPicker.value = false
}

// Gallery/camera file selected -> check size -> cropper flow
function onFileSelected(event: Event) {
  const input = event.target as HTMLInputElement
  const file = input.files?.[0]
  if (!file) return
  // Reset input so same file can be selected again
  input.value = ''

  // Size check (replaces @oversize handler)
  if (file.size > MAX_FILE_SIZE) {
    showToast({ message: t('assetForm.fileTooLarge'), icon: 'warning-o' })
    return
  }

  // Open cropper with the selected file
  cropperSource.value = file
  showCropper.value = true
}

// Map field names to their collapsible section
function findFieldSection(fieldName: string): string | null {
  const physicalFields = ['location', 'expected_lifespan_years', 'annual_maintenance_cost', 'usage_frequency']
  const financialFields = ['institution', 'interest_rate', 'maturity_date']
  const warrantyFields = ['warranty_expiry_date']
  const tagsNotesFields = ['notes', 'tags']

  if (physicalFields.includes(fieldName)) return 'physical'
  if (financialFields.includes(fieldName)) return 'financial'
  if (warrantyFields.includes(fieldName)) return 'warranty'
  if (tagsNotesFields.includes(fieldName)) return 'tagsNotes'
  return null
}

// Validation failure: auto-expand section containing first invalid field, scroll and focus it
async function onValidationFailed({ errors }: { errors: Array<{ name?: string; message: string }> }) {
  if (!errors?.length) return

  const firstError = errors[0]
  const fieldName = firstError.name
  if (!fieldName) return

  const section = findFieldSection(fieldName)

  // Auto-expand section if collapsed
  if (section) {
    expandSection(section)
    await nextTick()
  }

  // Find the field element within form container and scroll/focus it
  const fieldEl = formContainerRef.value?.querySelector(`[name="${fieldName}"]`) as HTMLInputElement | null
  if (fieldEl) {
    fieldEl.scrollIntoView({ behavior: 'smooth', block: 'center' })
    fieldEl.focus()
  }
}

function onSubmit() {
  // Build base payload with common fields
  const data: AssetRequestPayload = {
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
  flex-direction: column;
  align-items: center;
  padding: 24px 16px 16px;
  background: var(--van-background);
  gap: 12px;
}
.avatar-area {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 12px;
}
.asset-preview {
  width: 120px;
  height: 120px;
  border-radius: 16px;
  overflow: hidden;
  background: var(--van-background-2);
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
}
.asset-preview img {
  width: 100%;
  height: 100%;
  object-fit: contain;
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
  cursor: pointer;
}
.image-hint {
  font-size: 12px;
  color: var(--van-text-color-3);
}
.change-icon-btn {
  height: 30px;
  padding: 0 14px;
  font-size: 13px;
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

/* Collapsible sections */
.form-collapse {
  margin: 8px 0;
}

.form-collapse :deep(.van-collapse-item__title) {
  padding: 12px 16px;
  background: transparent;
}

.form-collapse :deep(.van-collapse-item__title .van-cell__title) {
  font-size: 13px;
  color: var(--text-tertiary);
  font-weight: 500;
}

.form-collapse :deep(.van-collapse-item__content) {
  padding: 0;
}

.form-collapse :deep(.van-cell-group--inset) {
  margin: 0;
  background: var(--van-background-2);
}

/* Reduced motion */
@media (prefers-reduced-motion: reduce) {
  .form-collapse :deep(.van-collapse-item__wrapper) {
    transition: none;
  }
}
</style>
