<template>
  <div class="itinerary-timeline" role="list">
    <!-- Trip-level empty state -->
    <template v-if="totalItems === 0 && standaloneExpenses.length === 0">
      <div class="trip-empty-state">
        <EmptyState
          :description="t('travel.itinerary.emptyState')"
          image="search"
        >
          <van-button
            type="primary"
            size="small"
            round
            icon="plus"
            @click="$emit('add')"
          >
            {{ t('travel.itinerary.addItem') }}
          </van-button>
        </EmptyState>
      </div>
    </template>

    <!-- Day sections -->
    <template v-if="totalItems > 0 || standaloneExpenses.length > 0">
      <template v-for="day in days" :key="day.date">
        <div class="day-section" :class="{ 'day--oor': day.outOfRange }">
          <div class="day-header" role="heading" :aria-label="formatDate(day.date)">
            <span class="day-date">{{ formatDate(day.date) }}</span>
            <span class="day-weekday">{{ formatWeekday(day.date) }}</span>
            <van-tag v-if="day.outOfRange" type="warning" size="medium" class="day-oor-tag">
              {{ t('travel.itinerary.outOfRange') }}
            </van-tag>
            <van-button
              v-if="!day.outOfRange"
              size="mini"
              round
              plain
              icon="plus"
              class="day-add-btn"
              @click="$emit('add', day.date)"
            />
          </div>

          <!-- Items for this day -->
          <ItineraryItemCard
            v-for="bucketItem in day.items"
            :key="bucketItem.item.id"
            :item="bucketItem.item"
            :custom-types="store.itineraryTypes"
            :out-of-range="day.outOfRange"
            @edit="$emit('edit', $event)"
            @delete="$emit('delete', $event)"
          />

          <!-- Standalone expenses for this day -->
          <ExpenseTimelineEntry
            v-for="expense in day.expenses"
            :key="expense.id"
            :expense="expense"
          />

          <!-- Empty day state (when there are items on other days) -->
          <div v-if="day.items.length === 0 && day.expenses.length === 0 && totalItems > 0" class="day-empty">
            <span class="day-empty-text">{{ t('travel.itinerary.emptyDay') }}</span>
            <van-button
              v-if="!day.outOfRange"
              size="mini"
              round
              plain
              icon="plus"
              @click="$emit('add', day.date)"
            />
          </div>
        </div>
      </template>
    </template>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { useTravelStore } from '@/stores/travel'
import ItineraryItemCard from './ItineraryItemCard.vue'
import ExpenseTimelineEntry from './ExpenseTimelineEntry.vue'
import EmptyState from '@/components/common/EmptyState.vue'
import type { ItineraryItem, ExpenseEntry } from '@/types/travel'

const props = defineProps<{
  tripId: string
  departureDate: string
  returnDate: string | null
  expenses?: ExpenseEntry[]
}>()

defineEmits<{
  add: [date?: string]
  edit: [item: ItineraryItem]
  delete: [item: ItineraryItem]
}>()

const { t, locale } = useI18n()
const store = useTravelStore()

const totalItems = computed(() => store.itineraryItems.length)

const standaloneExpenses = computed(() => {
  // Expenses not linked to any itinerary item
  return (props.expenses || []).filter(e =>
    e.leg_type === 'debit' &&
    !e.itinerary_item_id
  )
})

interface DayBucketItem {
  item: ItineraryItem
}

interface DayBucket {
  date: string
  items: DayBucketItem[]
  expenses: ExpenseEntry[]
  outOfRange: boolean
}

const days = computed<DayBucket[]>(() => {
  const depDate = new Date(props.departureDate)
  let endDate: Date

  if (props.returnDate) {
    endDate = new Date(props.returnDate)
  } else {
    // Default: 7 days from departure (KTD5: departure_date through departure_date + 7 days)
    endDate = new Date(depDate)
    endDate.setDate(endDate.getDate() + 7)
  }

  const depStr = depDate.toISOString().split('T')[0]
  const endStr = endDate.toISOString().split('T')[0]
  const dayMap = new Map<string, DayBucket>()

  // Main range: departureDate → returnDate
  const current = new Date(depDate)
  while (current <= endDate) {
    const dateStr = current.toISOString().split('T')[0]
    const bucketItems: DayBucketItem[] = []

    for (const i of store.itineraryItems) {
      // Only show item on its start date (no continuation hints for multi-day items)
      if (i.date === dateStr) {
        bucketItems.push({ item: i })
      }
    }

    bucketItems.sort((a, b) => {
      const ai = a.item, bi = b.item
      if (ai.sort_order !== bi.sort_order) return ai.sort_order - bi.sort_order
      if (ai.start_time && bi.start_time) return ai.start_time.localeCompare(bi.start_time)
      return (ai.created_at || '').localeCompare(bi.created_at || '')
    })

    const expenses = standaloneExpenses.value.filter(e => e.expense_date === dateStr)

    dayMap.set(dateStr, { date: dateStr, items: bucketItems, expenses, outOfRange: false })
    current.setDate(current.getDate() + 1)
  }

  // Out-of-range items: only show on their start date, no gap filling
  for (const item of store.itineraryItems) {
    const isBefore = item.date < depStr
    const isAfter = props.returnDate != null && item.date > props.returnDate
    if (!isBefore && !isAfter) continue
    // Already covered by main range (e.g. multi-day item spanning into range)
    if (dayMap.has(item.date)) continue

    const bucket: DayBucket = {
      date: item.date,
      items: [{ item }],
      expenses: standaloneExpenses.value.filter(e => e.expense_date === item.date),
      outOfRange: true,
    }
    dayMap.set(item.date, bucket)
  }

  // Sort all days chronologically
  return [...dayMap.values()].sort((a, b) => a.date.localeCompare(b.date))
})

function formatDate(dateStr: string): string {
  const date = new Date(dateStr + 'T00:00:00')
  return date.toLocaleDateString(locale.value, { month: 'long', day: 'numeric' })
}

function formatWeekday(dateStr: string): string {
  const date = new Date(dateStr + 'T00:00:00')
  return date.toLocaleDateString(locale.value, { weekday: 'short' })
}
</script>

<style scoped>
.itinerary-timeline {
  padding: 8px 0;
}

.trip-empty-state {
  padding: 40px 16px;
}

.day-section {
  margin-bottom: 8px;
}

.day-header {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 16px;
  position: sticky;
  top: 0;
  z-index: 1;
  background: var(--bg-secondary);
}

.day-date {
  font-size: 15px;
  font-weight: 600;
  color: var(--text-primary);
}

.day-weekday {
  font-size: 13px;
  color: var(--text-secondary);
}

.day-add-btn {
  margin-left: auto;
}

.day-empty {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  padding: 16px;
  opacity: 0.6;
}

.day-empty-text {
  font-size: 13px;
  color: var(--text-secondary);
}

.day--oor .day-header {
  opacity: 0.75;
}

.day-oor-tag {
  margin-left: auto;
}
</style>
