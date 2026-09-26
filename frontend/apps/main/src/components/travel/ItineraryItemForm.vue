<template>
  <van-popup
    v-model:show="visible"
    position="bottom"
    round
    :style="{ maxHeight: '85vh' }"
    teleport="body"
    @close="handleClose"
  >
    <div class="itinerary-form">
      <div class="form-header">
        <span class="form-title">{{ isEdit ? t('travel.itinerary.editItem') : t('travel.itinerary.addItem') }}</span>
        <van-icon name="cross" size="20" class="form-close" @click="handleClose" />
      </div>

      <div class="form-body">
        <!-- Type selector -->
        <van-cell-group inset>
          <van-field
            :model-value="selectedTypeName"
            :label="t('travel.itinerary.form.type')"
            readonly
            is-link
            @click="showTypePicker = true"
          />
        </van-cell-group>

        <!-- Date picker -->
        <van-cell-group inset>
          <van-field
            :model-value="form.date"
            :label="t('travel.itinerary.form.date')"
            readonly
            is-link
            @click="showDatePicker = true"
          />
        </van-cell-group>

        <!-- Cross-day toggle -->
        <van-cell-group inset>
          <van-cell :title="t('travel.itinerary.crossDay')" center>
            <template #right-icon>
              <van-switch v-model="showCrossDay" size="20" @change="onCrossDayChange" />
            </template>
          </van-cell>
          <van-field
            v-if="showCrossDay"
            :model-value="form.end_date || ''"
            :label="t('travel.itinerary.endDate')"
            readonly
            is-link
            @click="showEndDatePicker = true"
          />
        </van-cell-group>

        <!-- Time fields -->
        <van-cell-group inset>
          <van-field
            v-model="form.start_time"
            :label="t('travel.itinerary.form.startTime')"
            type="time"
            clearable
            placeholder="--:--"
          />
          <van-field
            v-model="form.end_time"
            :label="t('travel.itinerary.form.endTime')"
            type="time"
            clearable
            placeholder="--:--"
          />
        </van-cell-group>

        <!-- Type-specific fields -->
        <van-cell-group v-if="form.type === 'accommodation'" inset>
          <van-field
            v-model="typeMeta.check_in_time"
            :label="t('travel.itinerary.form.checkInTime')"
            type="time"
            clearable
            placeholder="--:--"
          />
          <van-field
            v-model="typeMeta.check_out_time"
            :label="t('travel.itinerary.form.checkOutTime')"
            type="time"
            clearable
            placeholder="--:--"
          />
          <div v-if="showCrossDay" class="accommodation-date-hint">
            {{ t('travel.itinerary.accommodationDateHint') }}
          </div>
        </van-cell-group>

        <van-cell-group v-if="form.type === 'dining'" inset>
          <van-field
            v-model="typeMeta.diners"
            :label="t('travel.itinerary.form.diners')"
            type="digit"
            clearable
            :placeholder="t('travel.itinerary.form.diners')"
          />
        </van-cell-group>

        <van-cell-group v-if="form.type === 'transport'" inset>
          <van-field
            v-model="typeMeta.origin"
            :label="t('travel.itinerary.form.origin')"
            clearable
            :placeholder="t('travel.itinerary.form.origin')"
          />
          <van-field
            v-model="typeMeta.destination"
            :label="t('travel.itinerary.form.destination')"
            clearable
            :placeholder="t('travel.itinerary.form.destination')"
          />
        </van-cell-group>

        <van-cell-group v-if="form.type === 'activity'" inset>
          <van-field
            v-model="typeMeta.ticket_price"
            :label="t('travel.itinerary.form.ticketPrice')"
            type="number"
            clearable
            placeholder="0.00"
          />
        </van-cell-group>

        <!-- Location & Description -->
        <van-cell-group inset>
          <van-field
            v-model="form.location"
            :label="t('travel.itinerary.form.location')"
            clearable
            :placeholder="t('travel.itinerary.form.location')"
          />
          <van-field
            v-model="form.description"
            :label="t('travel.itinerary.form.description')"
            type="textarea"
            autosize
            :placeholder="t('travel.itinerary.form.description')"
          />
        </van-cell-group>

        <!-- Cost section -->
        <van-cell-group inset>
          <van-field
            v-model="form.cost_amount"
            :label="t('travel.itinerary.form.costAmount')"
            type="number"
            clearable
            placeholder="0.00"
          />
          <van-field
            v-model="form.cost_currency"
            :label="t('travel.itinerary.form.costCurrency')"
            clearable
            placeholder="CNY"
          />
          <van-field
            v-if="form.cost_amount"
            :model-value="form.purchase_date || form.date"
            :label="t('travel.itinerary.purchaseDate')"
            readonly
            is-link
            @click="showPurchaseDatePicker = true"
          />
        </van-cell-group>

        <!-- Custom type creation -->
        <van-cell-group v-if="showCustomTypeForm" inset class="custom-type-form">
          <van-field
            v-model="newCustomTypeName"
            :label="t('travel.itinerary.form.customTypeName')"
            clearable
            :placeholder="t('travel.itinerary.form.customTypeName')"
          />
          <div class="custom-type-actions">
            <van-button size="small" type="primary" :loading="creatingType" @click="createCustomType">
              {{ t('common.confirm') }}
            </van-button>
            <van-button size="small" plain @click="showCustomTypeForm = false">
              {{ t('common.cancel') }}
            </van-button>
          </div>
        </van-cell-group>
      </div>

      <!-- Submit button -->
      <div class="form-footer">
        <van-button
          type="primary"
          block
          round
          :loading="submitting"
          :disabled="!canSubmit"
          @click="handleSubmit"
        >
          {{ isEdit ? t('common.save') : t('common.confirm') }}
        </van-button>
      </div>
    </div>

    <!-- Type picker popup -->
    <van-popup v-model:show="showTypePicker" position="bottom" round teleport="body">
      <van-picker
        :columns="typeColumns"
        :model-value="[form.type]"
        @confirm="onTypeConfirm"
        @cancel="showTypePicker = false"
      />
    </van-popup>

    <!-- Date picker popup -->
    <van-popup v-model:show="showDatePicker" position="bottom" round teleport="body">
      <van-date-picker
        v-model="pickerDate"
        :min-date="minDate"
        :max-date="maxDate"
        @confirm="onDateConfirm"
        @cancel="showDatePicker = false"
      />
    </van-popup>

    <!-- End date picker popup -->
    <van-popup v-model:show="showEndDatePicker" position="bottom" round teleport="body">
      <van-date-picker
        v-model="endDatePickerDate"
        :min-date="startDateAsDate"
        :max-date="maxDate"
        @confirm="onEndDateConfirm"
        @cancel="showEndDatePicker = false"
      />
    </van-popup>

    <!-- Purchase date picker popup -->
    <van-popup v-model:show="showPurchaseDatePicker" position="bottom" round teleport="body">
      <van-date-picker
        v-model="purchaseDatePickerDate"
        :min-date="minDate"
        :max-date="maxDate"
        @confirm="onPurchaseDateConfirm"
        @cancel="showPurchaseDatePicker = false"
      />
    </van-popup>
  </van-popup>
</template>

<script setup lang="ts">
import { ref, computed, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { showSuccessToast, showFailToast } from 'vant'
import { useTravelStore } from '@/stores/travel'
import { createItineraryType } from '@/api/travel'
import type { ItineraryItem, ItineraryItemCreate, ItineraryItemType } from '@/types/travel'

const props = defineProps<{
  modelValue: boolean
  tripId: string
  editItem?: ItineraryItem | null
  initialDate?: string
}>()

const emit = defineEmits<{
  'update:modelValue': [value: boolean]
  saved: []
}>()

const { t } = useI18n()
const store = useTravelStore()

const visible = computed({
  get: () => props.modelValue,
  set: (v) => emit('update:modelValue', v),
})

const isEdit = computed(() => !!props.editItem)

const form = ref({
  date: '',
  end_date: '' as string | null,
  type: 'activity' as ItineraryItemType,
  start_time: '' as string,
  end_time: '' as string,
  location: '',
  description: '',
  cost_amount: '',
  cost_currency: 'CNY',
  purchase_date: '' as string | null,
  custom_type_id: null as string | null,
})

const typeMeta = ref<Record<string, string>>({})

const showTypePicker = ref(false)
const showDatePicker = ref(false)
const showEndDatePicker = ref(false)
const showPurchaseDatePicker = ref(false)
const showCrossDay = ref(false)
const showCustomTypeForm = ref(false)
const newCustomTypeName = ref('')
const creatingType = ref(false)
const submitting = ref(false)

const today = new Date()
const pickerDate = ref([
  String(today.getFullYear()),
  String(today.getMonth() + 1).padStart(2, '0'),
  String(today.getDate()).padStart(2, '0'),
])
const endDatePickerDate = ref([...pickerDate.value])
const purchaseDatePickerDate = ref([...pickerDate.value])
const minDate = new Date(2020, 0, 1)
const maxDate = new Date(2030, 11, 31)

const startDateAsDate = computed(() => {
  if (!form.value.date) return minDate
  const parts = form.value.date.split('-')
  return new Date(Number(parts[0]), Number(parts[1]) - 1, Number(parts[2]))
})

const CORE_TYPES: ItineraryItemType[] = ['accommodation', 'dining', 'transport', 'activity']

const typeColumns = computed(() => {
  const core = CORE_TYPES.map(type => ({
    text: t(`travel.itinerary.types.${type}`),
    value: type,
  }))
  const custom = store.itineraryTypes.map(ct => ({
    text: ct.name,
    value: `custom:${ct.id}`,
  }))
  return [
    ...core,
    ...custom,
    { text: `+ ${t('travel.itinerary.form.addCustomType')}`, value: '__add_custom__' },
  ]
})

const selectedTypeName = computed(() => {
  if (form.value.type === 'custom' && form.value.custom_type_id) {
    const ct = store.itineraryTypes.find(c => c.id === form.value.custom_type_id)
    if (ct) return ct.name
  }
  return t(`travel.itinerary.types.${form.value.type}`)
})

const canSubmit = computed(() => {
  return form.value.date && form.value.type
})

// Helper to parse date string for picker
function parseDateParts(dateStr: string): string[] {
  const parts = dateStr.split('-')
  return parts.length === 3 ? parts : []
}

// Watch for edit item changes
watch(() => props.editItem, (item) => {
  if (item) {
    form.value = {
      date: item.date,
      end_date: item.end_date || null,
      type: item.type,
      start_time: item.start_time || '',
      end_time: item.end_time || '',
      location: item.location || '',
      description: item.description || '',
      cost_amount: item.cost_amount || '',
      cost_currency: item.cost_currency || 'CNY',
      purchase_date: item.purchase_date || null,
      custom_type_id: item.custom_type_id,
    }
    // Sync date picker with edit item's date
    if (item.date) pickerDate.value = parseDateParts(item.date)
    // Hydrate cross-day toggle
    showCrossDay.value = !!(item.end_date && item.end_date !== item.date)
    if (item.end_date) endDatePickerDate.value = parseDateParts(item.end_date)
    if (item.purchase_date) purchaseDatePickerDate.value = parseDateParts(item.purchase_date)
    else if (item.date) purchaseDatePickerDate.value = parseDateParts(item.date)
    // Restore type_metadata from the item
    const meta = item.type_metadata as Record<string, unknown> | null
    typeMeta.value = meta
      ? Object.fromEntries(Object.entries(meta).map(([k, v]) => [k, String(v ?? '')]))
      : {}
  } else {
    resetForm()
  }
}, { immediate: true })

// Watch for initialDate prop (when opening form from timeline "+")
watch(() => props.initialDate, (d) => {
  if (d && !props.editItem) {
    form.value.date = d
    pickerDate.value = parseDateParts(d)
  }
}, { immediate: true })

// Sync picker when popup opens
watch(showDatePicker, (open) => {
  if (open && form.value.date) {
    pickerDate.value = parseDateParts(form.value.date)
  }
})

function resetForm() {
  form.value = {
    date: props.initialDate || '',
    end_date: null,
    type: 'activity',
    start_time: '',
    end_time: '',
    location: '',
    description: '',
    cost_amount: '',
    cost_currency: 'CNY',
    purchase_date: null,
    custom_type_id: null,
  }
  typeMeta.value = {}
  showCrossDay.value = false
}

function onTypeConfirm({ selectedOptions }: { selectedOptions: Array<{ value?: string | number }> }) {
  const value = selectedOptions[0]?.value
  showTypePicker.value = false

  if (value === '__add_custom__') {
    showCustomTypeForm.value = true
    newCustomTypeName.value = ''
    return
  }

  if (typeof value === 'string' && value.startsWith('custom:')) {
    const typeId = value.split(':')[1]
    form.value.type = 'custom'
    form.value.custom_type_id = typeId
  } else {
    form.value.type = value as ItineraryItemType
    form.value.custom_type_id = null
  }
  // Clear type-specific fields when switching type
  typeMeta.value = {}
}

function onDateConfirm({ selectedValues }: { selectedValues: string[] }) {
  form.value.date = selectedValues.join('-')
  showDatePicker.value = false
  // Sync end date picker min-date and purchase date picker
  endDatePickerDate.value = parseDateParts(form.value.date)
  if (!form.value.purchase_date) {
    purchaseDatePickerDate.value = parseDateParts(form.value.date)
  }
}

function onEndDateConfirm({ selectedValues }: { selectedValues: string[] }) {
  form.value.end_date = selectedValues.join('-')
  showEndDatePicker.value = false
}

function onPurchaseDateConfirm({ selectedValues }: { selectedValues: string[] }) {
  form.value.purchase_date = selectedValues.join('-')
  showPurchaseDatePicker.value = false
}

function onCrossDayChange(checked: boolean) {
  if (!checked) {
    form.value.end_date = null
  }
}

async function createCustomType() {
  if (!newCustomTypeName.value.trim()) return
  creatingType.value = true
  try {
    const res = await createItineraryType({ name: newCustomTypeName.value.trim() })
    await store.fetchItineraryTypes()
    form.value.type = 'custom'
    form.value.custom_type_id = res.data.id
    showCustomTypeForm.value = false
    showSuccessToast(t('common.success'))
  } catch {
    showFailToast(t('common.error'))
  } finally {
    creatingType.value = false
  }
}

async function handleSubmit() {
  submitting.value = true
  try {
    // Build type_metadata from type-specific fields (only non-empty values)
    const meta: Record<string, string> = {}
    for (const [k, v] of Object.entries(typeMeta.value)) {
      if (v !== '' && v !== null && v !== undefined) meta[k] = v
    }
    const hasMeta = Object.keys(meta).length > 0

    const data: ItineraryItemCreate = {
      date: form.value.date,
      end_date: showCrossDay.value ? form.value.end_date : null,
      type: form.value.type,
      start_time: form.value.start_time || null,
      end_time: form.value.end_time || null,
      location: form.value.location || null,
      description: form.value.description || null,
      cost_amount: form.value.cost_amount || null,
      cost_currency: form.value.cost_amount ? (form.value.cost_currency || 'CNY') : null,
      purchase_date: form.value.cost_amount ? (form.value.purchase_date || form.value.date) : null,
      custom_type_id: form.value.custom_type_id,
      type_metadata: hasMeta ? meta : null,
    }

    if (isEdit.value && props.editItem) {
      await store.updateItineraryItem(props.tripId, props.editItem.id, data)
    } else {
      await store.createItineraryItem(props.tripId, data)
    }

    showSuccessToast(t('common.success'))
    visible.value = false
    emit('saved')
  } catch {
    showFailToast(t('common.error'))
  } finally {
    submitting.value = false
  }
}

function handleClose() {
  visible.value = false
}
</script>

<style scoped>
.itinerary-form {
  padding-bottom: env(safe-area-inset-bottom);
}

.form-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 16px;
  border-bottom: 1px solid var(--border-color, #eee);
}

.form-title {
  font-size: 16px;
  font-weight: 600;
  color: var(--text-primary);
}

.form-close {
  padding: 8px;
  color: var(--text-secondary);
  cursor: pointer;
  min-width: 44px;
  min-height: 44px;
  display: flex;
  align-items: center;
  justify-content: center;
}

.form-body {
  padding: 12px 0;
  max-height: 50vh;
  overflow-y: auto;
}

.form-body :deep(.van-cell-group--inset) {
  margin: 8px 12px;
}

.custom-type-form {
  padding: 8px 0;
}

.custom-type-actions {
  display: flex;
  gap: 8px;
  padding: 8px 16px;
  justify-content: flex-end;
}

.accommodation-date-hint {
  font-size: 12px;
  color: var(--text-tertiary, #c8c9cc);
  padding: 4px 16px 8px;
}

.form-footer {
  padding: 12px 16px;
}
</style>
