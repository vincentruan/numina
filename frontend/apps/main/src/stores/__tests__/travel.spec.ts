import { describe, it, expect, vi, beforeEach } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
import { useTravelStore } from '@/stores/travel'
import type { Trip, ExpenseEntry, ExpenseCategory, SplitGroup, SplitSettlement } from '@/types/travel'

vi.mock('@/api/travel', () => ({
  getTrips: vi.fn(),
  getTrip: vi.fn(),
  createTrip: vi.fn(),
  updateTrip: vi.fn(),
  deleteTrip: vi.fn(),
  getExpenses: vi.fn(),
  createExpense: vi.fn(),
  getExpenseCategories: vi.fn(),
  getSplitGroup: vi.fn(),
  getSettlements: vi.fn(),
}))

import * as travelApi from '@/api/travel'

function makeTrip(overrides: Partial<Trip> = {}): Trip {
  return {
    id: '1',
    family_id: '1',
    user_id: '1',
    name: '东京之旅',
    destination: '东京',
    departure_date: '2026-10-01',
    return_date: '2026-10-07',
    status: 'planning',
    planned_budget: '15000.00',
    initial_funding: null,
    actual_spend: '5000.00',
    currency: 'CNY',
    wish_id: null,
    timezone: null,
    is_active: true,
    created_at: '2026-09-01T00:00:00',
    updated_at: '2026-09-01T00:00:00',
    ...overrides,
  }
}

function makeExpense(overrides: Partial<ExpenseEntry> = {}): ExpenseEntry {
  return {
    id: '1',
    family_id: '1',
    transfer_id: '100',
    leg_type: 'debit',
    ref_id: '1',
    ref_type: 'trip',
    category_id: null,
    amount: '500.00',
    currency: 'CNY',
    amount_cny: '500.00',
    exchange_rate: null,
    expense_date: '2026-10-01',
    description: '酒店',
    receipt_image_url: null,
    user_id: '1',
    created_at: '2026-09-01T00:00:00',
    updated_at: '2026-09-01T00:00:00',
    ...overrides,
  }
}

describe('useTravelStore', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
  })

  // -------------------------------------------------------------------------
  // Initial state
  // -------------------------------------------------------------------------

  it('starts with empty state', () => {
    const store = useTravelStore()
    expect(store.trips).toEqual([])
    expect(store.currentTrip).toBeNull()
    expect(store.expenses).toEqual([])
    expect(store.categories).toEqual([])
    expect(store.splitGroup).toBeNull()
    expect(store.settlements).toEqual([])
    expect(store.loading).toBe(false)
  })

  // -------------------------------------------------------------------------
  // Actions
  // -------------------------------------------------------------------------

  it('fetchTrips populates trips array', async () => {
    const trips = [makeTrip(), makeTrip({ id: '2', name: '上海出差' })]
    vi.mocked(travelApi.getTrips).mockResolvedValue({ data: trips } as never)

    const store = useTravelStore()
    await store.fetchTrips()

    expect(store.trips).toHaveLength(2)
    expect(store.trips[0].name).toBe('东京之旅')
    expect(travelApi.getTrips).toHaveBeenCalled()
  })

  it('fetchTrips sets loading flag', async () => {
    vi.mocked(travelApi.getTrips).mockResolvedValue({ data: [] } as never)

    const store = useTravelStore()
    const promise = store.fetchTrips()
    expect(store.loading).toBe(true)
    await promise
    expect(store.loading).toBe(false)
  })

  it('fetchTrips passes status filter', async () => {
    vi.mocked(travelApi.getTrips).mockResolvedValue({ data: [] } as never)

    const store = useTravelStore()
    await store.fetchTrips({ status: 'active' })

    expect(travelApi.getTrips).toHaveBeenCalledWith({ status: 'active' })
  })

  it('fetchTrip sets currentTrip', async () => {
    const trip = makeTrip({ id: '42' })
    vi.mocked(travelApi.getTrip).mockResolvedValue({ data: trip } as never)

    const store = useTravelStore()
    await store.fetchTrip('42')

    expect(store.currentTrip).not.toBeNull()
    expect(store.currentTrip!.id).toBe('42')
  })

  it('createTrip prepends to trips array', async () => {
    const newTrip = makeTrip({ id: '99', name: '新旅行' })
    vi.mocked(travelApi.createTrip).mockResolvedValue({ data: newTrip } as never)

    const store = useTravelStore()
    store.trips = [makeTrip()]
    await store.createTrip({ name: '新旅行', destination: '北京', departure_date: '2026-11-01' })

    expect(store.trips).toHaveLength(2)
    expect(store.trips[0].name).toBe('新旅行')
  })

  it('fetchExpenses populates expenses array', async () => {
    const expenses = [makeExpense(), makeExpense({ id: '2', amount: '200.00' })]
    vi.mocked(travelApi.getExpenses).mockResolvedValue({ data: expenses } as never)

    const store = useTravelStore()
    await store.fetchExpenses('1')

    expect(store.expenses).toHaveLength(2)
  })

  it('createExpense prepends to expenses array', async () => {
    const newExpense = makeExpense({ id: '99', amount: '999.00' })
    vi.mocked(travelApi.createExpense).mockResolvedValue({ data: newExpense } as never)

    const store = useTravelStore()
    store.expenses = [makeExpense()]
    await store.createExpense('1', { amount: '999.00', currency: 'CNY', expense_date: '2026-10-01' })

    expect(store.expenses).toHaveLength(2)
    expect(store.expenses[0].amount).toBe('999.00')
  })

  it('fetchCategories populates categories', async () => {
    const categories = [
      { id: '1', family_id: null, name: '餐饮', icon: 'food', sort_order: 0, is_system: true },
    ]
    vi.mocked(travelApi.getExpenseCategories).mockResolvedValue({ data: categories } as never)

    const store = useTravelStore()
    await store.fetchCategories()

    expect(store.categories).toHaveLength(1)
    expect(store.categories[0].name).toBe('餐饮')
  })

  it('fetchSplitGroup populates splitGroup', async () => {
    const group: SplitGroup = {
      id: '1',
      trip_id: '1',
      invite_code: 'ABC123',
      created_by_user_id: '1',
      is_active: true,
      participants: [],
    }
    vi.mocked(travelApi.getSplitGroup).mockResolvedValue({ data: group } as never)

    const store = useTravelStore()
    await store.fetchSplitGroup('1')

    expect(store.splitGroup).not.toBeNull()
    expect(store.splitGroup!.invite_code).toBe('ABC123')
  })

  it('fetchSettlements populates settlements', async () => {
    const settlements: SplitSettlement[] = [
      {
        id: '1',
        trip_id: '1',
        from_participant_name: 'Alice',
        to_participant_name: 'Bob',
        amount: '150.00',
        currency: 'CNY',
        is_complete: false,
        settled_at: null,
        settled_by_user_id: null,
      },
    ]
    vi.mocked(travelApi.getSettlements).mockResolvedValue({ data: settlements } as never)

    const store = useTravelStore()
    await store.fetchSettlements('1')

    expect(store.settlements).toHaveLength(1)
    expect(store.settlements[0].from_participant_name).toBe('Alice')
  })

  // -------------------------------------------------------------------------
  // Getters
  // -------------------------------------------------------------------------

  it('upcomingTrips returns planning and active trips', () => {
    const store = useTravelStore()
    store.trips = [
      makeTrip({ id: '1', status: 'planning' }),
      makeTrip({ id: '2', status: 'active' }),
      makeTrip({ id: '3', status: 'settled' }),
      makeTrip({ id: '4', status: 'archived' }),
      makeTrip({ id: '5', status: 'cancelled' }),
    ]

    expect(store.upcomingTrips).toHaveLength(2)
    expect(store.upcomingTrips.map(t => t.status)).toEqual(['planning', 'active'])
  })

  it('activeTrip returns the first active trip', () => {
    const store = useTravelStore()
    store.trips = [
      makeTrip({ id: '1', status: 'planning' }),
      makeTrip({ id: '2', status: 'active', name: '进行中' }),
    ]

    expect(store.activeTrip).toBeDefined()
    expect(store.activeTrip!.name).toBe('进行中')
  })

  it('activeTrip returns undefined when no active trip', () => {
    const store = useTravelStore()
    store.trips = [
      makeTrip({ id: '1', status: 'planning' }),
      makeTrip({ id: '2', status: 'settled' }),
    ]

    expect(store.activeTrip).toBeUndefined()
  })

  // -------------------------------------------------------------------------
  // $reset
  // -------------------------------------------------------------------------

  it('$reset clears all state', async () => {
    vi.mocked(travelApi.getTrips).mockResolvedValue({
      data: [makeTrip()],
    } as never)

    const store = useTravelStore()
    await store.fetchTrips()
    expect(store.trips).toHaveLength(1)

    store.$reset()
    expect(store.trips).toEqual([])
    expect(store.currentTrip).toBeNull()
    expect(store.expenses).toEqual([])
    expect(store.loading).toBe(false)
  })
})
