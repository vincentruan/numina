import { mount, flushPromises } from '@vue/test-utils'
import { ref } from 'vue'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import type { Liability } from '@/types'

vi.mock('vue-i18n', () => ({
  useI18n: () => ({
    t: (key: string, params?: Record<string, unknown>) => {
      if (!params) return key
      return key.replace(/\{(\w+)\}/g, (_m, p) => String(params[p] ?? ''))
    },
  }),
  createI18n: () => ({ global: { t: (k: string) => k, te: () => true } }),
}))

const pushMock = vi.fn()
const routeQuery = { value: {} as Record<string, unknown> }
vi.mock('vue-router', () => ({
  useRouter: () => ({ push: pushMock }),
  useRoute: () => ({ query: routeQuery.value, path: '/finance' }),
  createRouter: () => ({ beforeEach: () => {}, afterEach: () => {}, push: () => Promise.resolve() }),
  createWebHistory: () => ({}),
}))

vi.mock('vant', () => ({
  showToast: vi.fn(),
  showSuccessToast: vi.fn(),
  showFailToast: vi.fn(),
  showConfirmDialog: vi.fn(() => Promise.resolve()),
}))

vi.mock('@/composables/useCurrency', () => ({
  useCurrency: () => ({ format: (n: number) => `¥${n}` }),
}))

// --- Liability store mock ---
const fetchLiabilitiesMock = vi.fn(() => Promise.resolve())
const liabilitiesRef = ref<Liability[]>([])
const loadingRef = ref(false)

vi.mock('@/stores/liability', () => ({
  useLiabilityStore: () => ({
    get liabilities() { return liabilitiesRef.value },
    get loading() { return loadingRef.value },
    fetchLiabilities: fetchLiabilitiesMock,
    deleteLiability: vi.fn(() => Promise.resolve()),
    updateLiability: vi.fn(() => Promise.resolve()),
    recordPayment: vi.fn(() => Promise.resolve()),
  }),
}))

import LiabilityListPanel from '../LiabilityListPanel.vue'

// Stub children to keep the render shallow and assertable.
const LiabilityCardStub = {
  name: 'LiabilityCard',
  props: ['liability', 'selectMode', 'selected'],
  template: '<div class="liability-card-stub" :data-selected="selected">{{ liability.name }}</div>',
}
const stubs = {
  LiabilityCard: LiabilityCardStub,
  LiabilityStrategyCard: true,
  LiabilityListSkeleton: true,
  EmptyState: true,
  'van-tabs': true,
  'van-tab': true,
  'van-icon': true,
  'van-button': true,
  'van-dialog': true,
  'van-field': true,
  Transition: true,
}

function makeLiability(overrides: Partial<Liability> = {}): Liability {
  return {
    id: '1',
    user_id: 'u1',
    family_id: 'f1',
    category: 'credit_card',
    name: '信用卡',
    original_amount: 10000,
    remaining_amount: 8000,
    currency: 'CNY',
    monthly_payment: 1000,
    interest_rate: 18,
    start_date: '2024-01-01',
    is_active: true,
    ...overrides,
  } as Liability
}

function resetState() {
  liabilitiesRef.value = []
  loadingRef.value = false
  routeQuery.value = {}
  pushMock.mockReset()
  fetchLiabilitiesMock.mockReset()
  fetchLiabilitiesMock.mockResolvedValue(undefined)
}

describe('LiabilityListPanel', () => {
  beforeEach(() => {
    resetState()
  })

  it('renders active/inactive inner tabs and fetches active liabilities on mount (AE6)', async () => {
    const wrapper = mount(LiabilityListPanel, { global: { stubs } })
    await flushPromises()

    expect(fetchLiabilitiesMock).toHaveBeenCalledWith({ is_active: true })
    expect(wrapper.findComponent({ name: 'VanTabs' }).exists() || wrapper.html().includes('van-tabs')).toBe(true)
  })

  it('tab change refetches with the corresponding is_active and resets filters', async () => {
    const wrapper = mount(LiabilityListPanel, { global: { stubs } })
    await flushPromises()
    fetchLiabilitiesMock.mockClear()

    const vm = wrapper.vm as unknown as {
      activeTab: string
      filterCategory: string
      sortOrder: string
      onTabChange: () => void
    }
    vm.filterCategory = 'mortgage'
    vm.sortOrder = 'desc'
    vm.activeTab = 'inactive'
    vm.onTabChange()
    await flushPromises()

    expect(fetchLiabilitiesMock).toHaveBeenCalledWith({ is_active: false })
    expect(vm.filterCategory).toBe('')
    expect(vm.sortOrder).toBe('default')
  })

  it('filters by category and sorts by remaining_amount desc/asc', async () => {
    liabilitiesRef.value = [
      makeLiability({ id: 'a', name: 'Mortgage', category: 'mortgage', remaining_amount: '5000' }),
      makeLiability({ id: 'b', name: 'CardLow', category: 'credit_card', remaining_amount: '100' }),
      makeLiability({ id: 'c', name: 'CardHigh', category: 'credit_card', remaining_amount: '900' }),
    ]
    const wrapper = mount(LiabilityListPanel, { global: { stubs } })
    await flushPromises()

    const vm = wrapper.vm as unknown as {
      filterCategory: string
      sortOrder: string
      filteredLiabilities: Liability[]
    }

    // Category filter.
    vm.filterCategory = 'credit_card'
    await wrapper.vm.$nextTick()
    expect(vm.filteredLiabilities.map((l) => l.name)).toEqual(['CardLow', 'CardHigh'])

    // Sort desc within the filter.
    vm.sortOrder = 'desc'
    await wrapper.vm.$nextTick()
    expect(vm.filteredLiabilities.map((l) => l.name)).toEqual(['CardHigh', 'CardLow'])

    // Sort asc.
    vm.sortOrder = 'asc'
    await wrapper.vm.$nextTick()
    expect(vm.filteredLiabilities.map((l) => l.name)).toEqual(['CardLow', 'CardHigh'])
  })

  it('computes monthly payment total with interest-only estimate tag for null monthly_payment (L3)', async () => {
    liabilitiesRef.value = [
      makeLiability({ id: 'a', monthly_payment: '500', remaining_amount: '10000', interest_rate: 12, is_active: true }),
      // Null monthly_payment → estimate = remaining × rate/12 = 12000 × 0.01 = 120.
      makeLiability({ id: 'b', monthly_payment: null, remaining_amount: '12000', interest_rate: 12, is_active: true }),
      // Inactive items must not count.
      makeLiability({ id: 'c', monthly_payment: '9999', remaining_amount: '1', interest_rate: 99, is_active: false }),
    ]
    const wrapper = mount(LiabilityListPanel, { global: { stubs } })
    await flushPromises()

    const vm = wrapper.vm as unknown as { totalMonthlyPayment: number; hasEstimatedItems: boolean }
    expect(vm.totalMonthlyPayment).toBeCloseTo(500 + 120, 5)
    expect(vm.hasEstimatedItems).toBe(true)
  })

  it('enters select mode on long-press and maintains selectedIds through toggle/selectAll/exit', async () => {
    liabilitiesRef.value = [
      makeLiability({ id: 'a', name: 'A' }),
      makeLiability({ id: 'b', name: 'B' }),
    ]
    const wrapper = mount(LiabilityListPanel, { global: { stubs } })
    await flushPromises()

    const vm = wrapper.vm as unknown as {
      selectMode: boolean
      selectedIds: Set<string>
      onLongPress: (l: Liability) => void
      toggleSelect: (id: string) => void
      selectAll: () => void
      exitSelectMode: () => void
    }

    vm.onLongPress(liabilitiesRef.value[0])
    expect(vm.selectMode).toBe(true)
    expect([...vm.selectedIds]).toEqual(['a'])

    vm.toggleSelect('b')
    expect([...vm.selectedIds].sort()).toEqual(['a', 'b'])
    vm.toggleSelect('a')
    expect([...vm.selectedIds]).toEqual(['b'])

    vm.selectAll()
    expect([...vm.selectedIds].sort()).toEqual(['a', 'b'])

    vm.exitSelectMode()
    expect(vm.selectMode).toBe(false)
    expect(vm.selectedIds.size).toBe(0)
  })

  it('shows empty state when no liabilities and not loading', async () => {
    liabilitiesRef.value = []
    loadingRef.value = false
    const wrapper = mount(LiabilityListPanel, { global: { stubs } })
    await flushPromises()

    expect(wrapper.findComponent({ name: 'EmptyState' }).exists() || wrapper.html().includes('empty-state')).toBe(true)
  })

  it('shows skeleton while loading with empty list', async () => {
    liabilitiesRef.value = []
    loadingRef.value = true
    const wrapper = mount(LiabilityListPanel, { global: { stubs } })
    await flushPromises()

    expect(wrapper.html()).toContain('liability-list-skeleton')
  })

  it('scrolls to strategy card when ?focus=liability_strategy (W5 deep link)', async () => {
    routeQuery.value = { tab: 'liabilities', focus: 'liability_strategy' }
    const scrollSpy = vi.fn()
    // jsdom lacks scrollIntoView; stub it on the prototype.
    window.HTMLElement.prototype.scrollIntoView = scrollSpy

    // Render a strategy card element so querySelector finds it.
    const el = document.createElement('div')
    el.className = 'liability-strategy-card'
    document.body.appendChild(el)

    mount(LiabilityListPanel, { global: { stubs } })
    await flushPromises()
    await new Promise((r) => setTimeout(r, 0))

    expect(scrollSpy).toHaveBeenCalled()
    document.body.removeChild(el)
  })
})
