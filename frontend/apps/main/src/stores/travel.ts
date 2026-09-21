import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import type { Trip, ExpenseEntry, ExpenseCategory, SplitGroup, SplitSettlement } from '@/types/travel'
import * as travelApi from '@/api/travel'
import { enqueue, listPending } from '@/utils/offlineQueue'

export const useTravelStore = defineStore('travel', () => {
  // State
  const trips = ref<Trip[]>([])
  const currentTrip = ref<Trip | null>(null)
  const expenses = ref<ExpenseEntry[]>([])
  const categories = ref<ExpenseCategory[]>([])
  const splitGroup = ref<SplitGroup | null>(null)
  const settlements = ref<SplitSettlement[]>([])
  const loading = ref(false)
  const pendingSyncCount = ref(0)

  // Getters
  const upcomingTrips = computed(() =>
    trips.value.filter(t => t.status === 'planning' || t.status === 'active'),
  )

  const activeTrip = computed(() =>
    trips.value.find(t => t.status === 'active'),
  )

  // Actions
  async function fetchTrips(params?: { status?: string }) {
    loading.value = true
    try {
      const res = await travelApi.getTrips(params)
      trips.value = res.data
    } finally {
      loading.value = false
    }
  }

  async function fetchTrip(id: string) {
    const res = await travelApi.getTrip(id)
    currentTrip.value = res.data
  }

  async function createTrip(data: Parameters<typeof travelApi.createTrip>[0]) {
    const res = await travelApi.createTrip(data)
    trips.value.unshift(res.data)
    return res.data
  }

  async function fetchExpenses(tripId: string) {
    const res = await travelApi.getExpenses(tripId)
    expenses.value = res.data
  }

  /**
   * Create expense with offline support (R2).
   * When online: direct API call.
   * When offline: enqueue to IndexedDB for later sync.
   */
  async function createExpense(tripId: string, data: Parameters<typeof travelApi.createExpense>[1]) {
    if (navigator.onLine) {
      const res = await travelApi.createExpense(tripId, data)
      expenses.value.unshift(res.data)
      return res.data
    }

    // Offline: enqueue mutation for later sync
    await enqueue({
      method: 'POST',
      url: `/api/v1/trips/${tripId}/expenses`,
      body: data,
      idempotencyKey: `expense-${Date.now()}-${Math.random().toString(36).slice(2)}`,
    })
    await refreshPendingCount()
    return null
  }

  async function fetchCategories() {
    const res = await travelApi.getExpenseCategories()
    categories.value = res.data
  }

  async function fetchSplitGroup(tripId: string) {
    const res = await travelApi.getSplitGroup(tripId)
    splitGroup.value = res.data
  }

  async function fetchSettlements(tripId: string) {
    const res = await travelApi.getSettlements(tripId)
    settlements.value = res.data
  }

  async function refreshPendingCount() {
    const pending = await listPending()
    pendingSyncCount.value = pending.length
  }

  function $reset() {
    trips.value = []
    currentTrip.value = null
    expenses.value = []
    categories.value = []
    splitGroup.value = null
    settlements.value = []
    loading.value = false
    pendingSyncCount.value = 0
  }

  return {
    trips,
    currentTrip,
    expenses,
    categories,
    splitGroup,
    settlements,
    loading,
    pendingSyncCount,
    upcomingTrips,
    activeTrip,
    fetchTrips,
    fetchTrip,
    createTrip,
    fetchExpenses,
    createExpense,
    fetchCategories,
    fetchSplitGroup,
    fetchSettlements,
    refreshPendingCount,
    $reset,
  }
})
