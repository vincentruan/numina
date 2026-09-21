import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { createI18n } from 'vue-i18n'
import { createPinia, setActivePinia } from 'pinia'
import TravelTripPanel from '../TravelTripPanel.vue'
import { useTravelStore } from '@/stores/travel'
import type { Trip } from '@/types/travel'

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

vi.mock('vue-i18n', async () => {
  const actual = await vi.importActual('vue-i18n')
  return {
    ...actual,
    useI18n: () => ({
      t: (key: string) => key,
      locale: { value: 'zh-CN' },
    }),
  }
})

vi.mock('vue-router', async () => {
  const actual = await vi.importActual('vue-router')
  return {
    ...actual,
    useRouter: () => ({
      push: vi.fn(),
    }),
    useRoute: () => ({
      path: '/finance',
    }),
  }
})

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

const i18n = createI18n({
  legacy: false,
  locale: 'zh-CN',
  messages: { 'zh-CN': {} },
})

function mountPanel() {
  return mount(TravelTripPanel, {
    global: {
      plugins: [i18n],
      stubs: {
        VanPullRefresh: { template: '<div class="van-pull-refresh-stub"><slot /></div>' },
        VanCell: { template: '<div class="van-cell-stub"><slot name="title" /><slot name="label" /><slot /></div>' },
        VanTag: { props: ['type'], template: '<span class="van-tag-stub"><slot /></span>' },
        VanIcon: { template: '<i class="van-icon-stub" />' },
        VanProgress: { template: '<div class="van-progress-stub" />' },
        VanEmpty: { template: '<div class="van-empty-stub" />' },
        VanFloatingBubble: { template: '<div class="fab-stub" />' },
        TravelTripCard: { props: ['trip'], template: '<div class="trip-card-stub" />' },
        TravelListSkeleton: { template: '<div class="skeleton-stub" />' },
      },
    },
  })
}

describe('TravelTripPanel', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
  })

  it('fetches trips on mount', async () => {
    vi.mocked(travelApi.getTrips).mockResolvedValue({
      data: [makeTrip()],
    } as never)

    mountPanel()
    await flushPromises()

    expect(travelApi.getTrips).toHaveBeenCalled()
  })

  it('shows empty state when no trips', async () => {
    vi.mocked(travelApi.getTrips).mockResolvedValue({
      data: [],
    } as never)

    const wrapper = mountPanel()
    await flushPromises()

    expect(wrapper.find('.van-empty-stub').exists()).toBe(true)
  })

  it('renders trip cards when trips exist', async () => {
    vi.mocked(travelApi.getTrips).mockResolvedValue({
      data: [makeTrip(), makeTrip({ id: '2', name: '上海出差' })],
    } as never)

    const wrapper = mountPanel()
    await flushPromises()

    expect(wrapper.findAll('.trip-card-stub')).toHaveLength(2)
  })

  it('populates the pinia store on load', async () => {
    vi.mocked(travelApi.getTrips).mockResolvedValue({
      data: [makeTrip(), makeTrip({ id: '2', status: 'active' })],
    } as never)

    mountPanel()
    await flushPromises()

    const store = useTravelStore()
    expect(store.trips).toHaveLength(2)
  })

  it('upcomingTrips getter filters planning and active', async () => {
    vi.mocked(travelApi.getTrips).mockResolvedValue({
      data: [
        makeTrip({ id: '1', status: 'planning' }),
        makeTrip({ id: '2', status: 'active' }),
        makeTrip({ id: '3', status: 'settled' }),
      ],
    } as never)

    mountPanel()
    await flushPromises()

    const store = useTravelStore()
    expect(store.upcomingTrips).toHaveLength(2)
  })

  it('activeTrip getter returns the active trip', async () => {
    vi.mocked(travelApi.getTrips).mockResolvedValue({
      data: [
        makeTrip({ id: '1', status: 'planning' }),
        makeTrip({ id: '2', status: 'active', name: '正在旅行' }),
      ],
    } as never)

    mountPanel()
    await flushPromises()

    const store = useTravelStore()
    expect(store.activeTrip?.name).toBe('正在旅行')
  })

  it('sets loading to false after fetch completes', async () => {
    vi.mocked(travelApi.getTrips).mockResolvedValue({
      data: [makeTrip()],
    } as never)

    mountPanel()
    await flushPromises()

    const store = useTravelStore()
    expect(store.loading).toBe(false)
  })
})
