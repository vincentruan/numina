import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import type { Trip, ExpenseEntry, ExpenseCategory, SplitGroup, SplitSettlement, ItineraryItem, ItineraryItemTypeDef } from '@/types/travel'
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
  const itineraryItems = ref<ItineraryItem[]>([])
  const itineraryTypes = ref<ItineraryItemTypeDef[]>([])
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

  async function fetchItinerary(tripId: string) {
    const res = await travelApi.getItineraryItems(tripId)
    itineraryItems.value = res.data
  }

  async function fetchItineraryTypes() {
    const res = await travelApi.getItineraryTypes()
    itineraryTypes.value = res.data
  }

  async function createItineraryItem(tripId: string, data: Parameters<typeof travelApi.createItineraryItem>[1]) {
    const res = await travelApi.createItineraryItem(tripId, data)
    itineraryItems.value.push(res.data)
    return res.data
  }

  async function updateItineraryItem(tripId: string, itemId: string, data: Parameters<typeof travelApi.updateItineraryItem>[2]) {
    const res = await travelApi.updateItineraryItem(tripId, itemId, data)
    const idx = itineraryItems.value.findIndex(i => i.id === itemId)
    if (idx !== -1) itineraryItems.value[idx] = res.data
    return res.data
  }

  async function deleteItineraryItem(tripId: string, itemId: string, mode: 'cascade' | 'unlink') {
    await travelApi.deleteItineraryItem(tripId, itemId, mode)
    itineraryItems.value = itineraryItems.value.filter(i => i.id !== itemId)
  }

  function $reset() {
    trips.value = []
    currentTrip.value = null
    expenses.value = []
    categories.value = []
    splitGroup.value = null
    settlements.value = []
    itineraryItems.value = []
    itineraryTypes.value = []
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
    itineraryItems,
    itineraryTypes,
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
    fetchItinerary,
    fetchItineraryTypes,
    createItineraryItem,
    updateItineraryItem,
    deleteItineraryItem,
    fetchSplitGroup,
    fetchSettlements,
    refreshPendingCount,
    $reset,
  }
})
