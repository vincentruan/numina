<template>
  <van-cell
    class="trip-card"
    :border="false"
    @click="$emit('click')"
  >
    <template #title>
      <div class="trip-header">
        <span class="trip-name">{{ trip.name }}</span>
        <van-tag :type="statusTagType" size="medium">{{ statusLabel }}</van-tag>
      </div>
    </template>
    <template #label>
      <div class="trip-body">
        <div class="trip-destination">
          <van-icon name="location-o" />
          <span>{{ trip.destination }}</span>
        </div>
        <div class="trip-dates">
          <van-icon name="clock-o" />
          <span>{{ formatDate(trip.departure_date) }} - {{ trip.return_date ? formatDate(trip.return_date) : t('travel.openEnded') }}</span>
        </div>
        <div v-if="budgetPercentage > 0" class="trip-budget">
          <div class="budget-info">
            <span class="budget-spent">{{ formatAmount(trip.actual_spend) }}</span>
            <span class="budget-separator">/</span>
            <span class="budget-total">{{ formatAmount(trip.planned_budget) }}</span>
          </div>
          <van-progress
            :percentage="Math.min(budgetPercentage, 100)"
            :color="budgetPercentage > 100 ? '#ee0a24' : '#1989fa'"
            :stroke-width="6"
            :show-pivot="false"
          />
        </div>
      </div>
    </template>
  </van-cell>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import type { Trip } from '@/types/travel'

const props = defineProps<{
  trip: Trip
}>()

defineEmits<{
  click: []
}>()

const { t, locale } = useI18n()

const statusLabel = computed(() => {
  const map: Record<string, string> = {
    planning: t('travel.status.planning'),
    active: t('travel.status.active'),
    settled: t('travel.status.settled'),
    archived: t('travel.status.archived'),
    cancelled: t('travel.status.cancelled'),
  }
  return map[props.trip.status] || props.trip.status
})

const statusTagType = computed((): 'primary' | 'success' | 'warning' | 'default' | 'danger' => {
  const map: Record<string, 'primary' | 'success' | 'warning' | 'default' | 'danger'> = {
    planning: 'primary',
    active: 'success',
    settled: 'warning',
    archived: 'default',
    cancelled: 'danger',
  }
  return map[props.trip.status] || 'default'
})

function formatDate(dateStr: string): string {
  const date = new Date(dateStr)
  return date.toLocaleDateString(locale.value, { month: 'short', day: 'numeric' })
}

function formatAmount(amount: string | null): string {
  if (!amount) return '¥0'
  const num = parseFloat(amount)
  return `¥${num.toLocaleString(locale.value, { minimumFractionDigits: 0, maximumFractionDigits: 0 })}`
}

const budgetPercentage = computed(() => {
  if (!props.trip.planned_budget) return 0
  const spend = parseFloat(props.trip.actual_spend) || 0
  const budget = parseFloat(props.trip.planned_budget) || 0
  if (budget === 0) return 0
  return Math.round((spend / budget) * 100)
})
</script>

<style scoped>
.trip-card {
  margin-bottom: 8px;
  background: var(--card-bg);
  border-radius: 12px;
  box-shadow: 0 1px 4px rgba(0, 0, 0, 0.06);
  cursor: pointer;
}
[data-theme='dark'] .trip-card {
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.28);
}
.trip-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
}
.trip-name {
  font-size: 16px;
  font-weight: 600;
  color: var(--text-primary);
  flex: 1;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.trip-body {
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.trip-destination,
.trip-dates {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 13px;
  color: var(--text-secondary);
}
.trip-destination .van-icon,
.trip-dates .van-icon {
  font-size: 14px;
  flex-shrink: 0;
}
.trip-budget {
  margin-top: 4px;
}
.budget-info {
  display: flex;
  align-items: center;
  gap: 4px;
  margin-bottom: 6px;
  font-size: 12px;
}
.budget-spent {
  font-weight: 600;
  color: var(--text-primary);
}
.budget-separator {
  color: var(--text-secondary);
}
.budget-total {
  color: var(--text-secondary);
}
</style>
