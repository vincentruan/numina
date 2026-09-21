<template>
  <div class="travel-trip-panel">
    <van-pull-refresh v-model="refreshing" @refresh="onRefresh">
      <!-- Month summary card -->
      <div v-if="trips.length > 0" class="month-summary">
        <div class="summary-title">{{ t('travel.currentMonthSpend') }}</div>
        <div class="summary-amount">{{ formatAmount(currentMonthSpend) }}</div>
        <div class="summary-count">
          {{ activeTrips.length }} {{ t('travel.activeTrips') }}
        </div>
      </div>

      <!-- Trip list -->
      <div v-if="trips.length > 0" class="trip-list">
        <TravelTripCard
          v-for="trip in trips"
          :key="trip.id"
          :trip="trip"
          @click="navigateToTrip(trip.id)"
        />
      </div>

      <!-- Empty state -->
      <EmptyState
        v-else-if="!store.loading"
        :description="t('travel.noTrips')"
      >
        <van-button type="primary" size="small" @click="navigateToNew">
          {{ t('travel.createFirstTrip') }}
        </van-button>
      </EmptyState>
    </van-pull-refresh>

    <!-- FAB: create new trip -->
    <div
      v-if="trips.length > 0"
      class="fab"
      role="button"
      tabindex="0"
      @click="navigateToNew"
      @keydown.enter="navigateToNew"
      @keydown.space.prevent="navigateToNew"
    >
      <van-icon name="plus" size="22" />
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, ref, onMounted, onActivated } from 'vue'
import { useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { showFailToast } from 'vant'
import { useTravelStore } from '@/stores/travel'
import { useCurrency } from '@/composables/useCurrency'
import EmptyState from '@/components/common/EmptyState.vue'
import TravelTripCard from './TravelTripCard.vue'
import type { Trip } from '@/types/travel'

defineOptions({ name: 'TravelTripPanel' })

const { t, locale } = useI18n()
const router = useRouter()
const store = useTravelStore()
const { formatConverted } = useCurrency()

const refreshing = ref(false)

const trips = computed(() => store.trips)
const activeTrips = computed(() => store.upcomingTrips)

// Current month spend: sum actual_spend for trips active during the current month
const currentMonthSpend = computed(() => {
  const now = new Date()
  const monthStart = new Date(now.getFullYear(), now.getMonth(), 1)
  const monthEnd = new Date(now.getFullYear(), now.getMonth() + 1, 0, 23, 59, 59)
  let total = 0
  for (const trip of trips.value) {
    const depDate = new Date(trip.departure_date)
    const retDate = trip.return_date ? new Date(trip.return_date) : depDate
    // Include trips that overlap with the current month
    if (depDate <= monthEnd && retDate >= monthStart) {
      total += parseFloat(trip.actual_spend) || 0
    }
  }
  return total.toString()
})

function formatAmount(amount: string): string {
  const num = parseFloat(amount) || 0
  return formatConverted(num, 'CNY')
}

function navigateToTrip(id: string) {
  router.push(`/travel/${id}`)
}

function navigateToNew() {
  router.push('/travel/new')
}

async function loadTrips() {
  try {
    await store.fetchTrips()
  } catch {
    showFailToast(t('common.failed'))
  }
}

async function onRefresh() {
  refreshing.value = true
  try {
    await loadTrips()
  } finally {
    refreshing.value = false
  }
}

// Skip first onActivated — Vue 3 fires both onMounted and onActivated on first mount
let hasActivated = false
onMounted(loadTrips)
onActivated(() => {
  if (!hasActivated) { hasActivated = true; return }
  loadTrips()
})
</script>

<style scoped>
.travel-trip-panel {
  padding-bottom: 80px;
}
.month-summary {
  margin: 8px 12px;
  padding: 14px 16px;
  background: var(--card-bg);
  border-radius: 12px;
  box-shadow: 0 1px 4px rgba(0, 0, 0, 0.06);
}
[data-theme='dark'] .month-summary {
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.28);
}
.summary-title {
  font-size: 12px;
  color: var(--text-secondary);
  margin-bottom: 8px;
}
.summary-amount {
  font-size: 24px;
  font-weight: 700;
  color: var(--text-primary);
  margin-bottom: 4px;
}
.summary-count {
  font-size: 13px;
  color: var(--text-secondary);
}
.trip-list {
  padding: 8px 12px;
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.fab {
  position: fixed;
  right: 20px;
  bottom: calc(80px + env(safe-area-inset-bottom));
  width: 48px;
  height: 48px;
  border-radius: 50%;
  background: var(--van-button-primary-background, #1989fa);
  color: #fff;
  display: flex;
  align-items: center;
  justify-content: center;
  box-shadow: 0 4px 12px rgba(25, 137, 250, 0.4);
  cursor: pointer;
  z-index: 10;
}
</style>
