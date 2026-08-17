<template>
  <van-form @submit="onSubmit">
    <van-cell-group inset>
      <!-- Role: landlord / tenant -->
      <van-field
        :model-value="roleDisplay"
        is-link
        readonly
        :label="t('rental.role')"
        :placeholder="t('rental.role')"
        @click="showRolePicker = true"
      />
      <van-popup v-model:show="showRolePicker" position="bottom" round>
        <van-picker
          v-model="rolePickerValue"
          :columns="roleColumns"
          :title="t('rental.role')"
          @confirm="onRoleConfirm"
          @cancel="showRolePicker = false"
        />
      </van-popup>

      <van-field
        v-model="form.monthly_rent"
        type="number" inputmode="decimal"
        :label="t('rental.monthlyRent')"
        :placeholder="t('rental.monthlyRentPlaceholder')"
        :rules="[{ required: true, message: t('rental.amountRequired') }]"
      >
        <template #left-icon>
          <CurrencyButton v-model="form.currency" />
        </template>
      </van-field>

      <van-field
        v-model="form.deposit"
        type="number" inputmode="decimal"
        :label="t('rental.deposit')"
        :placeholder="t('rental.deposit')"
      />

      <van-field
        v-model="form.start_date"
        is-link
        readonly
        :label="t('rental.startDate')"
        :placeholder="t('rental.startDate')"
        :rules="[{ required: true, message: t('rental.dateRequired') }]"
        @click="showStartPicker = true"
      />
      <van-popup v-model:show="showStartPicker" position="bottom" round>
        <van-date-picker
          v-model="startPickerValue"
          :title="t('rental.startDate')"
          @confirm="onStartConfirm"
          @cancel="showStartPicker = false"
        />
      </van-popup>

      <van-field
        v-model="endDisplay"
        is-link
        readonly
        :label="t('rental.endDate')"
        :placeholder="t('rental.openEnded')"
        @click="showEndPicker = true"
      />
      <van-popup v-model:show="showEndPicker" position="bottom" round>
        <van-picker
          v-model="endPickerValue"
          :columns="endColumns"
          :title="t('rental.endDate')"
          @confirm="onEndConfirm"
          @cancel="showEndPicker = false"
        />
      </van-popup>

      <!-- Landlord-only: link to an owned property asset -->
      <van-field
        v-if="form.role === 'landlord'"
        v-model="linkedAssetDisplay"
        is-link
        readonly
        :label="t('rental.linkedAsset')"
        :placeholder="t('rental.selectLinkedAsset')"
        @click="showAssetPicker = true"
      />
      <van-popup v-model:show="showAssetPicker" position="bottom" round>
        <van-picker
          v-model="assetPickerValue"
          :columns="assetPickerColumns"
          :title="t('rental.linkedAsset')"
          @confirm="onAssetConfirm"
          @cancel="showAssetPicker = false"
        />
      </van-popup>

      <van-field v-model="form.counterparty" :label="t('rental.counterparty')" :placeholder="t('rental.counterpartyPlaceholder')" />
      <van-field v-model="form.notes" type="textarea" :label="t('rental.notes')" :placeholder="t('rental.notesPlaceholder')" rows="2" autosize />
    </van-cell-group>

    <div class="form-actions">
      <van-button round block type="primary" native-type="submit" :loading="loading">
        {{ isEdit ? t('rental.saveChanges') : t('rental.addContract') }}
      </van-button>
    </div>
  </van-form>
</template>

<script setup lang="ts">
import { ref, computed, watch, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import type { Asset, RentalContract, RentalRequestPayload } from '@/types'
import { useAuthStore } from '@/stores/auth'
import { getAssets } from '@/api/assets'
import CurrencyButton from '@/components/common/CurrencyButton.vue'

const { t } = useI18n()
const authStore = useAuthStore()

const props = withDefaults(defineProps<{
  initialData?: Partial<RentalContract>
  isEdit?: boolean
  loading?: boolean
}>(), {
  initialData: undefined,
  isEdit: false,
  loading: false,
})

const emit = defineEmits<{
  submit: [data: RentalRequestPayload]
}>()

interface FormState {
  role: 'landlord' | 'tenant'
  monthly_rent: string
  deposit: string
  currency: string
  start_date: string
  end_date: string | null
  linked_asset_id: string | null
  counterparty: string
  notes: string
}

const form = ref<FormState>({
  role: 'landlord',
  monthly_rent: '',
  deposit: '',
  currency: authStore.user?.default_currency || 'CNY',
  start_date: '',
  end_date: null,
  linked_asset_id: null,
  counterparty: '',
  notes: '',
})

watch(() => props.initialData, (data) => {
  if (data) {
    if (data.role !== undefined) form.value.role = data.role
    if (data.monthly_rent !== undefined) form.value.monthly_rent = String(data.monthly_rent ?? '')
    if (data.deposit !== undefined) form.value.deposit = String(data.deposit ?? '')
    if (data.currency !== undefined) form.value.currency = String(data.currency ?? 'CNY')
    if (data.start_date !== undefined) form.value.start_date = String(data.start_date ?? '')
    if (data.end_date !== undefined) form.value.end_date = data.end_date ? String(data.end_date) : null
    if (data.linked_asset_id !== undefined) form.value.linked_asset_id = data.linked_asset_id ? String(data.linked_asset_id) : null
    if (data.counterparty !== undefined) form.value.counterparty = String(data.counterparty ?? '')
    if (data.notes !== undefined) form.value.notes = String(data.notes ?? '')
  }
}, { immediate: true })

// --- Role picker ---
const showRolePicker = ref(false)
const rolePickerValue = ref<string[]>(['landlord'])
const roleColumns = computed(() => [
  { text: t('rental.roleLandlord'), value: 'landlord' },
  { text: t('rental.roleTenant'), value: 'tenant' },
])
const roleDisplay = computed(() =>
  roleColumns.value.find(c => c.value === form.value.role)?.text ?? '',
)
function onRoleConfirm({ selectedValues }: { selectedValues: string[] }) {
  const v = selectedValues[0] ?? 'landlord'
  form.value.role = v as 'landlord' | 'tenant'
  if (v === 'tenant') form.value.linked_asset_id = null
  showRolePicker.value = false
}

// --- Date pickers ---
const showStartPicker = ref(false)
const showEndPicker = ref(false)
const now = new Date()
const startPickerValue = ref([
  String(now.getFullYear()),
  String(now.getMonth() + 1).padStart(2, '0'),
  String(now.getDate()).padStart(2, '0'),
])
const endPickerValue = ref<string[]>([])

const NONE_END_VALUE = '__open__'
const endColumns = computed(() => [
  { text: t('rental.openEnded'), value: NONE_END_VALUE },
  ...(form.value.end_date ? [{ text: form.value.end_date, value: form.value.end_date }] : []),
])
const endDisplay = computed(() => form.value.end_date ?? '')

function onStartConfirm({ selectedValues }: { selectedValues: string[] }) {
  form.value.start_date = selectedValues.join('-')
  showStartPicker.value = false
}
function onEndConfirm({ selectedValues }: { selectedValues: string[] }) {
  const v = selectedValues[0] ?? NONE_END_VALUE
  form.value.end_date = v === NONE_END_VALUE ? null : v
  showEndPicker.value = false
}

// --- Asset picker (landlord only) ---
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
    assets.value = []
  }
})

function onSubmit() {
  const data: RentalRequestPayload = {
    role: form.value.role,
    monthly_rent: Number(form.value.monthly_rent),
    deposit: Number(form.value.deposit || 0),
    currency: form.value.currency,
    start_date: form.value.start_date || undefined,
    end_date: form.value.end_date ?? null,
    linked_asset_id: form.value.role === 'landlord' ? (form.value.linked_asset_id ?? null) : null,
    counterparty: form.value.counterparty || undefined,
    notes: form.value.notes || undefined,
  }
  emit('submit', data)
}
</script>

<style scoped>
.form-actions {
  padding: 16px;
}
</style>
