<template>
  <div class="itinerary-timeline" role="list">
    <!-- Trip-level empty state -->
    <template v-if="totalItems === 0 && standaloneExpenses.length === 0">
      <div class="trip-empty-state">
        <van-empty
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
        </van-empty>
      </div>
    </template>

    <!-- Day sections -->
    <template v-for="day in days" :key="day.date">
      <div class="day-section">
        <div class="day-header" role="heading" :aria-label="formatDate(day.date)">
          <span class="day-date">{{ formatDate(day.date) }}</span>
          <span class="day-weekday">{{ formatWeekday(day.date) }}</span>
          <van-button
            v-if="day.items.length === 0"
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
          v-for="item in day.items"
          :key="item.id"
          :item="item"
          :custom-types="store.itineraryTypes"
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
            size="mini"
            round
            plain
            icon="plus"
            @click="$emit('add', day.date)"
          />
        </div>
      </div>
    </template>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { useTravelStore } from '@/stores/travel'
import ItineraryItemCard from './ItineraryItemCard.vue'
import ExpenseTimelineEntry from './ExpenseTimelineEntry.vue'
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
  const linkedItemIds = new Set(store.itineraryItems.map(i => i.id))
  return (props.expenses || []).filter(e =>
    e.leg_type === 'debit' &&
    (!e as any).itinerary_item_id
  )
})

interface DayBucket {
  date: string
  items: ItineraryItem[]
  expenses: ExpenseEntry[]
}

const days = computed<DayBucket[]>(() => {
  const depDate = new Date(props.departureDate)
  let endDate: Date

  if (props.returnDate) {
    endDate = new Date(props.returnDate)
  } else {
    // Default: 7 days from departure (KTD5)
    endDate = new Date(depDate)
    endDate.setDate(endDate.getDate() + 6)
  }

  const result: DayBucket[] = []
  const current = new Date(depDate)

  while (current <= endDate) {
    const dateStr = current.toISOString().split('T')[0]
    const items = store.itineraryItems
      .filter(i => i.date === dateStr)
      .sort((a, b) => {
        if (a.sort_order !== b.sort_order) return a.sort_order - b.sort_order
        if (a.start_time && b.start_time) return a.start_time.localeCompare(b.start_time)
        return (a.created_at || '').localeCompare(b.created_at || '')
      })

    const expenses = standaloneExpenses.value.filter(e => e.expense_date === dateStr)

    result.push({ date: dateStr, items, expenses })
    current.setDate(current.getDate() + 1)
  }

  return result
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
</style>
