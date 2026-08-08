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
  useCurrency: () => ({
    format: (n: number) => `¥${n}`,
    formatConverted: (n: number | string) => '¥' + n,
  }),
}))

// useAffordBar → returns a stable state object per wish. `accelerate` is controllable
// so the truthy/falsy render branches of the `.accelerate` span can both be asserted.
const accelerateRef = ref<null | { requiredMonthly: number; daysLeft: number }>(null)
vi.mock('@/composables/useAffordBar', () => ({
  useAffordBar: () => ({
    state: computed(() => ({ kind: 'progress', months: 3 })),
    accelerate: computed(() => accelerateRef.value),
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
  accelerateRef.value = null
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

  it('renders the .accelerate span when affordAccelerate(wish) is truthy (ComputedRef unwrap)', async () => {
    // Companion to the falsy-branch test above: when accelerate.value carries a real
    // {requiredMonthly, daysLeft} nudge, the .accelerate span MUST render and carry the
    // needAccelerate i18n key. Pins the truthy half of the affordAccelerate .value unwrap.
    accelerateRef.value = { requiredMonthly: 1500, daysLeft: 90 }
    wishesRef.value = [makeWish({ id: 'w-acc', name: 'Accelerate', status: 'pending', expected_price: '1000' })]
    const wrapper = mount(WishListPanel, { global: { stubs } })
    await flushPromises()

    const bar = wrapper.find('.afford-bar')
    expect(bar.exists()).toBe(true)
    const span = bar.find('.accelerate')
    expect(span.exists()).toBe(true)
    expect(span.text()).toContain('wish.afford.needAccelerate')
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

  describe('U3: Progress bar', () => {
    it('does not render progress bar for realized wishes', async () => {
      wishesRef.value = [makeWish({ id: 'r', name: 'Realized', status: 'realized', saved_amount: '500', expected_price: '1000' })]
      const wrapper = mount(WishListPanel, { global: { stubs } })
      await flushPromises()

      expect(wrapper.find('.wish-progress').exists()).toBe(false)
    })

    it('does not render progress bar for cancelled wishes', async () => {
      wishesRef.value = [makeWish({ id: 'c', name: 'Cancelled', status: 'cancelled', saved_amount: '500', expected_price: '1000' })]
      const wrapper = mount(WishListPanel, { global: { stubs } })
      await flushPromises()

      expect(wrapper.find('.wish-progress').exists()).toBe(false)
    })

    it('does not render progress bar when expected_price is missing', async () => {
      wishesRef.value = [makeWish({ id: 'no-price', name: 'No Price', status: 'pending', expected_price: undefined, saved_amount: '500' })]
      const wrapper = mount(WishListPanel, { global: { stubs } })
      await flushPromises()

      expect(wrapper.find('.wish-progress').exists()).toBe(false)
    })

    it('renders dashed border when progress is 0% and monthly_saving is not set', async () => {
      wishesRef.value = [makeWish({ id: 'empty', name: 'Empty', status: 'pending', saved_amount: '0', monthly_saving: '0', expected_price: '1000' })]
      const wrapper = mount(WishListPanel, { global: { stubs } })
      await flushPromises()

      const bar = wrapper.find('.wish-progress-bar')
      expect(bar.exists()).toBe(true)
      expect(bar.classes()).toContain('wish-progress-empty')
    })

    it('renders 2% minimum width when progress is 0% but monthly_saving is set', async () => {
      wishesRef.value = [makeWish({ id: 'started', name: 'Started', status: 'pending', saved_amount: '0', monthly_saving: '100', expected_price: '1000' })]
      const wrapper = mount(WishListPanel, { global: { stubs } })
      await flushPromises()

      const bar = wrapper.find('.wish-progress-bar')
      expect(bar.exists()).toBe(true)
      expect(bar.classes()).toContain('wish-progress-empty-dot')
      const fill = wrapper.find('.wish-progress-fill')
      expect(fill.attributes('style')).toContain('width: 2%')
    })

    it('renders 50% width when progress is 50%', async () => {
      wishesRef.value = [makeWish({ id: 'half', name: 'Half', status: 'pending', saved_amount: '500', monthly_saving: '100', expected_price: '1000' })]
      const wrapper = mount(WishListPanel, { global: { stubs } })
      await flushPromises()

      const fill = wrapper.find('.wish-progress-fill')
      expect(fill.attributes('style')).toContain('width: 50%')
    })

    it('renders 100% width when progress is 100%', async () => {
      wishesRef.value = [makeWish({ id: 'full', name: 'Full', status: 'pending', saved_amount: '1000', monthly_saving: '100', expected_price: '1000' })]
      const wrapper = mount(WishListPanel, { global: { stubs } })
      await flushPromises()

      const fill = wrapper.find('.wish-progress-fill')
      expect(fill.attributes('style')).toContain('width: 100%')
    })

    it('applies priority-high class for high priority wishes', async () => {
      wishesRef.value = [makeWish({ id: 'high', name: 'High', status: 'pending', priority: 'high', saved_amount: '500', expected_price: '1000' })]
      const wrapper = mount(WishListPanel, { global: { stubs } })
      await flushPromises()

      const fill = wrapper.find('.wish-progress-fill')
      expect(fill.classes()).toContain('priority-high')
    })

    it('applies priority-medium class for medium priority wishes', async () => {
      wishesRef.value = [makeWish({ id: 'med', name: 'Med', status: 'pending', priority: 'medium', saved_amount: '500', expected_price: '1000' })]
      const wrapper = mount(WishListPanel, { global: { stubs } })
      await flushPromises()

      const fill = wrapper.find('.wish-progress-fill')
      expect(fill.classes()).toContain('priority-medium')
    })

    it('applies priority-low class for low priority wishes', async () => {
      wishesRef.value = [makeWish({ id: 'low', name: 'Low', status: 'pending', priority: 'low', saved_amount: '500', expected_price: '1000' })]
      const wrapper = mount(WishListPanel, { global: { stubs } })
      await flushPromises()

      const fill = wrapper.find('.wish-progress-fill')
      expect(fill.classes()).toContain('priority-low')
    })

    it('shows "almost reached" badge when progress >= 80%', async () => {
      wishesRef.value = [makeWish({ id: 'almost', name: 'Almost', status: 'pending', saved_amount: '800', expected_price: '1000' })]
      const wrapper = mount(WishListPanel, { global: { stubs } })
      await flushPromises()

      const badge = wrapper.find('.almost-badge')
      expect(badge.exists()).toBe(true)
      expect(badge.text()).toContain('wish.almostReached')
    })

    it('applies almost-reached class when progress >= 80%', async () => {
      wishesRef.value = [makeWish({ id: 'almost', name: 'Almost', status: 'pending', saved_amount: '800', expected_price: '1000' })]
      const wrapper = mount(WishListPanel, { global: { stubs } })
      await flushPromises()

      const fill = wrapper.find('.wish-progress-fill')
      expect(fill.classes()).toContain('almost-reached')
    })

    it('does not show "almost reached" badge when progress < 80%', async () => {
      wishesRef.value = [makeWish({ id: 'not-almost', name: 'Not Almost', status: 'pending', saved_amount: '700', expected_price: '1000' })]
      const wrapper = mount(WishListPanel, { global: { stubs } })
      await flushPromises()

      const badge = wrapper.find('.almost-badge')
      expect(badge.exists()).toBe(false)
    })

    it('wishProgress calculation is correct', async () => {
      wishesRef.value = [makeWish({ id: 'calc', name: 'Calc', status: 'pending', saved_amount: '333', expected_price: '1000' })]
      const wrapper = mount(WishListPanel, { global: { stubs } })
      await flushPromises()

      const vm = wrapper.vm as unknown as { wishProgress: (w: Wish) => number }
      expect(vm.wishProgress(wishesRef.value[0])).toBe(33)
    })

    it('wishProgress returns 0 when expected_price is missing', async () => {
      wishesRef.value = [makeWish({ id: 'no-price', name: 'No Price', status: 'pending', expected_price: undefined })]
      const wrapper = mount(WishListPanel, { global: { stubs } })
      await flushPromises()

      const vm = wrapper.vm as unknown as { wishProgress: (w: Wish) => number }
      expect(vm.wishProgress(wishesRef.value[0])).toBe(0)
    })

    it('wishProgress returns 0 when expected_price is 0', async () => {
      wishesRef.value = [makeWish({ id: 'zero-price', name: 'Zero Price', status: 'pending', expected_price: '0', saved_amount: '500' })]
      const wrapper = mount(WishListPanel, { global: { stubs } })
      await flushPromises()

      const vm = wrapper.vm as unknown as { wishProgress: (w: Wish) => number }
      expect(vm.wishProgress(wishesRef.value[0])).toBe(0)
    })

    it('wishProgress clamps to 100 when saved > target', async () => {
      wishesRef.value = [makeWish({ id: 'over', name: 'Over', status: 'pending', saved_amount: '1500', expected_price: '1000' })]
      const wrapper = mount(WishListPanel, { global: { stubs } })
      await flushPromises()

      const vm = wrapper.vm as unknown as { wishProgress: (w: Wish) => number }
      expect(vm.wishProgress(wishesRef.value[0])).toBe(100)
    })

    it('progress bar has correct aria attributes', async () => {
      wishesRef.value = [makeWish({ id: 'aria', name: 'Aria', status: 'pending', saved_amount: '500', expected_price: '1000' })]
      const wrapper = mount(WishListPanel, { global: { stubs } })
      await flushPromises()

      const progress = wrapper.find('.wish-progress')
      expect(progress.attributes('role')).toBe('progressbar')
      expect(progress.attributes('aria-valuenow')).toBe('50')
      expect(progress.attributes('aria-valuemin')).toBe('0')
      expect(progress.attributes('aria-valuemax')).toBe('100')
      // After i18n refactor, aria-label uses t('wish.progressAria', { name })
      expect(progress.attributes('aria-label')).toBe('wish.progressAria')
    })
  })
})
