import { mount, flushPromises } from '@vue/test-utils'
import { ref, computed } from 'vue'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import type { Wish } from '@/types'

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
vi.mock('vue-router', () => ({
  useRouter: () => ({ push: pushMock }),
  useRoute: () => ({ query: {}, path: '/finance' }),
  createRouter: () => ({ beforeEach: () => {}, afterEach: () => {}, push: () => Promise.resolve() }),
  createWebHistory: () => ({}),
}))

vi.mock('vant', () => ({
  showToast: vi.fn(),
  showSuccessToast: vi.fn(),
  showFailToast: vi.fn(),
}))

vi.mock('@/composables/useCurrency', () => ({
  useCurrency: () => ({ format: (n: number) => `¥${n}` }),
}))

// useAffordBar → returns a stable state object per wish.
vi.mock('@/composables/useAffordBar', () => ({
  useAffordBar: () => ({
    state: computed(() => ({ kind: 'progress', months: 3 })),
    accelerate: computed(() => false),
  }),
}))

// useDebtWarning → controllable hasHighInterestDebt.
const hasHighInterestDebtRef = ref(false)
const highInterestLiabilitiesRef = ref<Array<Record<string, unknown>>>([])
vi.mock('@/composables/useDebtWarning', () => ({
  useDebtWarning: () => ({
    hasHighInterestDebt: computed(() => hasHighInterestDebtRef.value),
    highInterestLiabilities: computed(() => highInterestLiabilitiesRef.value),
    loadThresholds: vi.fn(() => Promise.resolve()),
  }),
}))

// --- Store mocks ---
const fetchWishesMock = vi.fn(() => Promise.resolve())
const fetchLiabilitiesMock = vi.fn(() => Promise.resolve())
const wishesRef = ref<Wish[]>([])
const wishLoadingRef = ref(false)
const liabilitiesRef = ref<Array<Record<string, unknown>>>([])
const overviewRef = ref<null | { net_worth: number }>({ net_worth: 100000 })

vi.mock('@/stores/wish', () => ({
  useWishStore: () => ({
    get wishes() { return wishesRef.value },
    get loading() { return wishLoadingRef.value },
    fetchWishes: fetchWishesMock,
  }),
}))
vi.mock('@/stores/liability', () => ({
  useLiabilityStore: () => ({
    get liabilities() { return liabilitiesRef.value },
    fetchLiabilities: fetchLiabilitiesMock,
  }),
}))
vi.mock('@/stores/dashboard', () => ({
  useDashboardStore: () => ({
    get overview() { return overviewRef.value },
    fetchOverview: vi.fn(() => Promise.resolve()),
  }),
}))

import WishListPanel from '../WishListPanel.vue'

const stubs = {
  WishAdviceCard: true,
  WishListSkeleton: true,
  ShimmerText: true,
  SvgIcon: true,
  'van-tabs': true,
  'van-tab': true,
  'van-icon': true,
  'van-button': true,
}

function makeWish(overrides: Partial<Wish> = {}): Wish {
  return {
    id: 'w1',
    user_id: 'u1',
    family_id: 'f1',
    name: '心愿',
    status: 'pending',
    priority: 'medium',
    expected_price: '1000',
    saved_amount: '0',
    monthly_saving: '100',
    ...overrides,
  } as Wish
}

function resetState() {
  wishesRef.value = []
  wishLoadingRef.value = false
  liabilitiesRef.value = []
  hasHighInterestDebtRef.value = false
  highInterestLiabilitiesRef.value = []
  overviewRef.value = { net_worth: 100000 }
  pushMock.mockReset()
  fetchWishesMock.mockReset()
  fetchLiabilitiesMock.mockReset()
  fetchWishesMock.mockResolvedValue(undefined)
  fetchLiabilitiesMock.mockResolvedValue(undefined)
}

describe('WishListPanel', () => {
  beforeEach(() => {
    resetState()
  })

  it('renders pending/realized/cancelled inner tabs and fetches wishes on mount (AE6)', async () => {
    const wrapper = mount(WishListPanel, { global: { stubs } })
    await flushPromises()

    expect(fetchWishesMock).toHaveBeenCalled()
    expect(wrapper.html()).toContain('van-tabs')
  })

  it('filters wishes by active tab status', async () => {
    wishesRef.value = [
      makeWish({ id: 'p', name: 'Pending', status: 'pending' }),
      makeWish({ id: 'r', name: 'Realized', status: 'realized' }),
      makeWish({ id: 'c', name: 'Cancelled', status: 'cancelled' }),
    ]
    const wrapper = mount(WishListPanel, { global: { stubs } })
    await flushPromises()

    const vm = wrapper.vm as unknown as {
      activeTab: 'pending' | 'realized' | 'cancelled'
      filteredWishes: Wish[]
    }

    expect(vm.activeTab).toBe('pending')
    expect(vm.filteredWishes.map((w) => w.name)).toEqual(['Pending'])

    vm.activeTab = 'realized'
    await wrapper.vm.$nextTick()
    expect(vm.filteredWishes.map((w) => w.name)).toEqual(['Realized'])

    vm.activeTab = 'cancelled'
    await wrapper.vm.$nextTick()
    expect(vm.filteredWishes.map((w) => w.name)).toEqual(['Cancelled'])
  })

  it('renders the afford-bar state text via .state.value.kind (ComputedRef unwrap)', async () => {
    // Regression for the .state.kind -> .state.value.kind fix: pre-fix, .kind on a
    // ComputedRef was undefined, so no v-if/v-else-if branch matched and the afford-bar
    // rendered empty. The useAffordBar mock returns kind 'progress' with months 3.
    wishesRef.value = [makeWish({ id: 'w-afford', name: 'Afford', status: 'pending', expected_price: '1000' })]
    const wrapper = mount(WishListPanel, { global: { stubs } })
    await flushPromises()

    const bar = wrapper.find('.afford-bar')
    expect(bar.exists()).toBe(true)
    expect(bar.classes()).toContain('afford-progress')
    // i18n mock returns the key; the progress branch renders the etaMonths key.
    expect(bar.text()).toContain('wish.afford.etaMonths')
    // The mock's accelerate is computed(() => false): the accelerate span must NOT render.
    // Pre-fix, v-if bound the bare ComputedRef object (always truthy), so the span rendered
    // even when accelerate.value was falsy — this assertion pins the .value unwrap.
    expect(bar.find('.accelerate').exists()).toBe(false)
  })

  it('sorts by priority (high→low desc default), then toggles direction', async () => {
    wishesRef.value = [
      makeWish({ id: 'low', name: 'Low', status: 'pending', priority: 'low' }),
      makeWish({ id: 'high', name: 'High', status: 'pending', priority: 'high' }),
      makeWish({ id: 'med', name: 'Med', status: 'pending', priority: 'medium' }),
    ]
    const wrapper = mount(WishListPanel, { global: { stubs } })
    await flushPromises()

    const vm = wrapper.vm as unknown as {
      sortBy: 'priority' | 'price' | 'name'
      sortDir: 'asc' | 'desc'
      sortedWishes: Wish[]
      toggleSort: (v: 'priority' | 'price' | 'name') => void
    }

    // Default: priority desc → high, medium, low.
    expect(vm.sortedWishes.map((w) => w.name)).toEqual(['High', 'Med', 'Low'])

    // Toggle same key flips direction → asc.
    vm.toggleSort('priority')
    await wrapper.vm.$nextTick()
    expect(vm.sortedWishes.map((w) => w.name)).toEqual(['Low', 'Med', 'High'])
  })

  it('sorts by price', async () => {
    wishesRef.value = [
      makeWish({ id: 'a', name: 'Cheap', status: 'pending', expected_price: '100' }),
      makeWish({ id: 'b', name: 'Pricey', status: 'pending', expected_price: '900' }),
    ]
    const wrapper = mount(WishListPanel, { global: { stubs } })
    await flushPromises()

    const vm = wrapper.vm as unknown as {
      sortedWishes: Wish[]
      toggleSort: (v: 'priority' | 'price' | 'name') => void
    }
    vm.toggleSort('price') // sets sortBy=price, dir=desc
    await wrapper.vm.$nextTick()
    expect(vm.sortedWishes.map((w) => w.name)).toEqual(['Pricey', 'Cheap'])
  })

  it('shows W5 debt-warning bar when high-interest debt and wishes exist', async () => {
    wishesRef.value = [makeWish({ id: 'p', name: 'Pending', status: 'pending' })]
    hasHighInterestDebtRef.value = true
    highInterestLiabilitiesRef.value = [{ remaining_amount: '12000', interest_rate: 18 }]

    const wrapper = mount(WishListPanel, { global: { stubs } })
    await flushPromises()

    expect(wrapper.find('.debt-warning-bar').exists()).toBe(true)
  })

  it('hides W5 debt-warning bar when no high-interest debt', async () => {
    wishesRef.value = [makeWish({ id: 'p', name: 'Pending', status: 'pending' })]
    hasHighInterestDebtRef.value = false

    const wrapper = mount(WishListPanel, { global: { stubs } })
    await flushPromises()

    expect(wrapper.find('.debt-warning-bar').exists()).toBe(false)
  })

  it('W5 view-strategy deep-links to /finance?tab=liabilities&focus=liability_strategy', async () => {
    wishesRef.value = [makeWish({ id: 'p', name: 'Pending', status: 'pending' })]
    const wrapper = mount(WishListPanel, { global: { stubs } })
    await flushPromises()

    const vm = wrapper.vm as unknown as { goToLiabilityStrategy: () => void }
    vm.goToLiabilityStrategy()
    expect(pushMock).toHaveBeenCalledWith({
      path: '/finance',
      query: { tab: 'liabilities', focus: 'liability_strategy' },
    })
  })

  it('shows empty state when no wishes in the active tab', async () => {
    wishesRef.value = []
    const wrapper = mount(WishListPanel, { global: { stubs } })
    await flushPromises()

    expect(wrapper.find('.empty-state').exists()).toBe(true)
  })
})
