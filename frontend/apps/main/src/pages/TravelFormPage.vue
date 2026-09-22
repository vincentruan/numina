<template>
  <div class="travel-form-page">
    <PageHeader :title="isEdit ? t('travel.editTrip') : t('travel.newTrip')" />

    <van-form
      ref="formRef"
      :model="formData"
      :rules="formRules"
      @submit="onSubmit"
    >
      <van-cell-group inset>
        <van-field
          v-model="formData.name"
          :label="t('travel.tripName')"
          :placeholder="t('travel.tripNamePlaceholder')"
          required
          :rules="[{ required: true, message: t('travel.tripNameRequired') }]"
        />
        <van-field
          v-model="formData.description"
          :label="t('travel.description')"
          type="textarea"
          rows="2"
          autosize
          :placeholder="t('travel.descriptionPlaceholder')"
        />
        <van-field
          v-model="formData.destination"
          :label="t('travel.destination')"
          :placeholder="t('travel.destinationPlaceholder')"
          required
          :rules="[{ required: true, message: t('travel.destinationRequired') }]"
        />
        <van-field
          v-model="formData.departure_date"
          is-link
          readonly
          :label="t('travel.departureDate')"
          :placeholder="t('travel.selectDate')"
          required
          :rules="[{ required: true, message: t('travel.departureDateRequired') }]"
          @click="showDeparturePicker = true"
        />
        <van-field
          v-model="formData.return_date"
          is-link
          readonly
          :label="t('travel.returnDate')"
          :placeholder="t('travel.returnDateOptional')"
          @click="showReturnPicker = true"
        />
        <van-field
          v-model="formData.planned_budget"
          :label="t('travel.plannedBudget')"
          type="number"
          :placeholder="t('travel.budgetPlaceholder')"
        />
        <van-field
          :label="t('travel.currency')"
        >
          <template #input>
            <CurrencyButton v-model="formData.currency" />
          </template>
        </van-field>
        <van-field
          v-model="formData.timezone"
          :label="t('travel.timezone')"
          :placeholder="t('travel.timezonePlaceholder')"
        />
      </van-cell-group>

      <div class="form-actions">
        <van-button type="primary" block round native-type="submit" :loading="submitting">
          {{ isEdit ? t('common.save') : t('travel.createTrip') }}
        </van-button>
      </div>
    </van-form>

    <!-- Departure date picker -->
    <van-popup v-model:show="showDeparturePicker" position="bottom" round>
      <van-date-picker
        v-model="departureDateValue"
        :title="t('travel.selectDepartureDate')"
        :min-date="minDate"
        :max-date="maxDate"
        @confirm="onDepartureConfirm"
        @cancel="showDeparturePicker = false"
      />
    </van-popup>

    <!-- Return date picker -->
    <van-popup v-model:show="showReturnPicker" position="bottom" round>
      <van-date-picker
        v-model="returnDateValue"
        :title="t('travel.selectReturnDate')"
        :min-date="minDate"
        :max-date="maxDate"
        @confirm="onReturnConfirm"
        @cancel="showReturnPicker = false"
      />
    </van-popup>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { showSuccessToast, showFailToast } from 'vant'
import { useTravelStore } from '@/stores/travel'
import PageHeader from '@/components/common/PageHeader.vue'
import CurrencyButton from '@/components/common/CurrencyButton.vue'
import type { TripCreate, TripUpdate } from '@/types/travel'

const { t } = useI18n()
const route = useRoute()
const router = useRouter()
const store = useTravelStore()

const isEdit = ref(false)
const tripId = ref<string | null>(null)
const submitting = ref(false)

const formData = reactive({
  name: '',
  description: '',
  destination: '',
  departure_date: '',
  return_date: '',
  planned_budget: '',
  currency: 'CNY',
  timezone: '',
})

const formRules = {
  name: [{ required: true, message: t('travel.tripNameRequired') }],
  destination: [{ required: true, message: t('travel.destinationRequired') }],
  departure_date: [{ required: true, message: t('travel.departureDateRequired') }],
}

// Date picker state
const showDeparturePicker = ref(false)
const showReturnPicker = ref(false)
const now = new Date()
const minDate = new Date(now.getFullYear() - 1, 0, 1)
const maxDate = new Date(now.getFullYear() + 5, 11, 31)

const departureDateValue = ref<string[]>([])
const returnDateValue = ref<string[]>([])

function formatDateStr(values: string[]): string {
  return `${values[0]}-${values[1]}-${values[2]}`
}

function parseDateStr(dateStr: string): string[] {
  if (!dateStr) return []
  const parts = dateStr.split('-')
  return parts.length === 3 ? parts : []
}

function onDepartureConfirm({ selectedValues }: { selectedValues: string[] }) {
  formData.departure_date = formatDateStr(selectedValues)
  showDeparturePicker.value = false
}

function onReturnConfirm({ selectedValues }: { selectedValues: string[] }) {
  formData.return_date = formatDateStr(selectedValues)
  showReturnPicker.value = false
}

async function onSubmit() {
  submitting.value = true
  try {
    const data: TripCreate = {
      name: formData.name,
      description: formData.description || undefined,
      destination: formData.destination,
      departure_date: formData.departure_date,
      return_date: formData.return_date || undefined,
      planned_budget: formData.planned_budget || undefined,
      currency: formData.currency || 'CNY',
      timezone: formData.timezone || undefined,
    }

    if (isEdit.value && tripId.value) {
      const updateData: TripUpdate = {
        name: data.name,
        description: data.description,
        destination: data.destination,
        departure_date: data.departure_date,
        return_date: data.return_date,
        planned_budget: data.planned_budget,
        currency: data.currency,
        timezone: data.timezone,
      }
      // Use API directly for update
      const { updateTrip } = await import('@/api/travel')
      await updateTrip(tripId.value, updateData)
      await store.fetchTrip(tripId.value)
      showSuccessToast(t('common.success'))
      router.push(`/travel/${tripId.value}`)
    } else {
      const newTrip = await store.createTrip(data)
      showSuccessToast(t('common.success'))
      router.push(`/travel/${newTrip.id}`)
    }
  } catch {
    showFailToast(t('common.failed'))
  } finally {
    submitting.value = false
  }
}

// Load trip data if editing
onMounted(async () => {
  const id = route.params.id as string
  if (id) {
    isEdit.value = true
    tripId.value = id
    try {
      await store.fetchTrip(id)
      const trip = store.currentTrip
      if (trip) {
        formData.name = trip.name
        formData.description = trip.description ?? ''
        formData.destination = trip.destination
        formData.departure_date = trip.departure_date
        formData.return_date = trip.return_date || ''
        formData.planned_budget = trip.planned_budget || ''
        formData.currency = trip.currency
        formData.timezone = trip.timezone || ''
        departureDateValue.value = parseDateStr(trip.departure_date)
        if (trip.return_date) {
          returnDateValue.value = parseDateStr(trip.return_date)
        }
      }
    } catch {
      showFailToast(t('common.failed'))
      router.back()
    }
  }
})
</script>

<style scoped>
.travel-form-page {
  min-height: 100vh;
  background: var(--bg-secondary);
  padding-bottom: calc(16px + env(safe-area-inset-bottom));
}
.form-actions {
  padding: 16px 12px;
}
</style>
