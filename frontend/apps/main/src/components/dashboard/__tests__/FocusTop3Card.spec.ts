import { mount, flushPromises } from '@vue/test-utils'
import { ref } from 'vue'
import { describe, it, expect, vi, beforeEach } from 'vitest'

// Mock vue-i18n (component uses useI18n; @/api/index → @/i18n calls createI18n at load).
vi.mock('vue-i18n', () => ({
  useI18n: () => ({
    t: (key: string, params?: Record<string, unknown>) => {
      if (!params) return key
      return key.replace(/\{(\w+)\}/g, (_m, p) => String(params[p] ?? ''))
    },
  }),
  createI18n: () => ({ global: { t: (k: string) => k, te: () => true } }),
}))

vi.mock('vue-router', () => ({
  useRouter: () => ({ push: vi.fn() }),
  useRoute: () => ({ query: {}, path: '/' }),
  createRouter: () => ({ beforeEach: () => {}, afterEach: () => {}, push: () => Promise.resolve() }),
  createWebHistory: () => ({}),
}))

// useCurrency → useAuthStore needs an active Pinia; stub to a plain formatter.
vi.mock('@/composables/useCurrency', () => ({
  useCurrency: () => ({ format: (n: number) => `¥${n}`, formatConverted: (n: number | string) => '¥' + n }),
}))

// --- Store mocks ---
const fetchLiabilitiesMock = vi.fn(() => Promise.resolve())
const fetchWishesMock = vi.fn(() => Promise.resolve())

const homeAssetsRef = ref<Record<string, Array<Record<string, unknown>>>>({})
const loadingRef = ref(false)
const liabilitiesRef = ref<Array<Record<string, unknown>>>([])
const wishesRef = ref<Array<Record<string, unknown>>>([])

vi.mock('@/stores/dashboard', () => ({
  useDashboardStore: () => ({
    get homeAssets() { return homeAssetsRef.value },
    get loading() { return loadingRef.value },
  }),
}))
vi.mock('@/stores/liability', () => ({
  useLiabilityStore: () => ({
    get liabilities() { return liabilitiesRef.value },
    fetchLiabilities: fetchLiabilitiesMock,
  }),
}))
vi.mock('@/stores/wish', () => ({
  useWishStore: () => ({
    get wishes() { return wishesRef.value },
    fetchWishes: fetchWishesMock,
  }),
}))

import FocusTop3Card from '../FocusTop3Card.vue'

// Stub AssetListItem to a simple span that exposes the asset name so ordering is assertable.
const AssetListItemStub = {
  name: 'AssetListItem',
  props: ['asset'],
  template: '<div class="asset-list-item-stub">{{ asset.name }}</div>',
}

// Render router-link as a real anchor so we can assert the 查看全部 href.
const RouterLinkStub = {
  name: 'RouterLink',
  props: ['to'],
  template: '<a :href="href"><slot /></a>',
  computed: {
    href(): string {
      const to = (this as { to?: unknown }).to
      if (typeof to === 'string') return to
      const t = to as { path?: string; query?: Record<string, unknown> }
      const qs = t?.query
        ? '?' + Object.entries(t.query).map(([k, v]) => `${k}=${v}`).join('&')
        : ''
      return `${t?.path ?? ''}${qs}`
    },
  },
}

const stubs = {
  'van-skeleton': true,
  'van-empty': true,
  MoneyDisplay: true,
  AssetListItem: AssetListItemStub,
  RouterLink: RouterLinkStub,
}

function resetState() {
  homeAssetsRef.value = {}
  loadingRef.value = false
  liabilitiesRef.value = []
  wishesRef.value = []
  fetchLiabilitiesMock.mockReset()
  fetchWishesMock.mockReset()
  fetchLiabilitiesMock.mockResolvedValue(undefined)
  fetchWishesMock.mockResolvedValue(undefined)
}

describe('FocusTop3Card', () => {
  beforeEach(() => {
    resetState()
  })

  it('shows top 3 assets by current value desc (AE5)', async () => {
    homeAssetsRef.value = {
      in_use: [
        { id: 'a1', name: 'Low', current_value: '100' },
        { id: 'a2', name: 'High', current_value: '9000' },
        { id: 'a3', name: 'Mid', current_value: '500' },
        { id: 'a4', name: 'Fourth', current_value: '50' },
      ],
    }

    const wrapper = mount(FocusTop3Card, { global: { stubs } })
    await flushPromises()

    const names = wrapper.findAll('.asset-list-item-stub').map((n) => n.text())
    expect(names).toEqual(['High', 'Mid', 'Low']) // top 3, Fourth excluded
  })

  it('shows top 3 active liabilities by interest rate desc (AE5)', async () => {
    liabilitiesRef.value = [
      { id: 'l1', name: 'LowRate', is_active: true, interest_rate: 3, remaining_amount: '1000' },
      { id: 'l2', name: 'HighRate', is_active: true, interest_rate: 24, remaining_amount: '1000' },
      { id: 'l3', name: 'MidRate', is_active: true, interest_rate: 12, remaining_amount: '1000' },
      { id: 'l4', name: 'Inactive', is_active: false, interest_rate: 99, remaining_amount: '1000' },
      { id: 'l5', name: 'Fourth', is_active: true, interest_rate: 1, remaining_amount: '1000' },
    ]

    const wrapper = mount(FocusTop3Card, { global: { stubs } })
    await flushPromises()

    const names = wrapper.findAll('.top3-liability-name').map((n) => n.text())
    expect(names).toEqual(['HighRate', 'MidRate', 'LowRate']) // active only, top 3, Inactive + Fourth excluded
  })

  it('sorts wishes by nearest target_date and EXCLUDES wishes with no target_date', async () => {
    wishesRef.value = [
      { id: 'w1', name: 'NoDate', target_date: null, expected_price: '100', saved_amount: '10' },
      { id: 'w2', name: 'Later', target_date: '2027-06-01', expected_price: '100', saved_amount: '10' },
      { id: 'w3', name: 'Sooner', target_date: '2026-08-01', expected_price: '100', saved_amount: '10' },
      { id: 'w4', name: 'Middle', target_date: '2026-12-01', expected_price: '100', saved_amount: '10' },
    ]

    const wrapper = mount(FocusTop3Card, { global: { stubs } })
    await flushPromises()

    const names = wrapper.findAll('.top3-wish-name').map((n) => n.text())
    expect(names).toEqual(['Sooner', 'Middle', 'Later']) // NoDate excluded, sorted asc by date
  })

  it('renders 查看全部 links for all three tabs → /finance?tab=X (R14)', async () => {
    const wrapper = mount(FocusTop3Card, { global: { stubs } })
    await flushPromises()

    expect(wrapper.find('[data-test="view-all-assets"]').attributes('href')).toContain('tab=assets')
    expect(wrapper.find('[data-test="view-all-liabilities"]').attributes('href')).toContain('tab=liabilities')
    expect(wrapper.find('[data-test="view-all-wishes"]').attributes('href')).toContain('tab=wishes')
  })

  it('shows all items when fewer than 3 (no padding/truncation)', async () => {
    homeAssetsRef.value = {
      in_use: [
        { id: 'a1', name: 'Only', current_value: '100' },
        { id: 'a2', name: 'Two', current_value: '50' },
      ],
    }

    const wrapper = mount(FocusTop3Card, { global: { stubs } })
    await flushPromises()

    expect(wrapper.findAll('.asset-list-item-stub').length).toBe(2)
  })

  it('shows empty state when a domain has 0 items', async () => {
    homeAssetsRef.value = {}
    liabilitiesRef.value = []
    wishesRef.value = []

    const wrapper = mount(FocusTop3Card, { global: { stubs } })
    await flushPromises()

    // van-empty is stubbed; assert three empty placeholders render (one per tab).
    expect(wrapper.findAll('van-empty-stub').length + wrapper.findAll('.van-empty').length).toBeGreaterThanOrEqual(3)
  })

  it('shows assets skeleton while dashboard asset list is loading', async () => {
    loadingRef.value = true

    const wrapper = mount(FocusTop3Card, { global: { stubs } })
    await flushPromises()

    expect(wrapper.find('[data-test="assets-skeleton"]').exists()).toBe(true)
  })

  it('degrades only the liabilities tab on fetch reject; inline retry refetches', async () => {
    fetchLiabilitiesMock.mockRejectedValueOnce(new Error('network'))

    const wrapper = mount(FocusTop3Card, { global: { stubs } })
    await flushPromises()

    expect(wrapper.find('[data-test="liabilities-retry"]').exists()).toBe(true)
    expect(wrapper.find('[data-test="wishes-retry"]').exists()).toBe(false)

    fetchLiabilitiesMock.mockResolvedValueOnce(undefined)
    await wrapper.find('[data-test="liabilities-retry"]').trigger('click')
    await flushPromises()
    expect(wrapper.find('[data-test="liabilities-retry"]').exists()).toBe(false)
    expect(fetchLiabilitiesMock).toHaveBeenCalledTimes(2)
  })

  it('degrades only the wishes tab on fetch reject; inline retry refetches', async () => {
    fetchWishesMock.mockRejectedValueOnce(new Error('network'))

    const wrapper = mount(FocusTop3Card, { global: { stubs } })
    await flushPromises()

    expect(wrapper.find('[data-test="wishes-retry"]').exists()).toBe(true)
    expect(wrapper.find('[data-test="liabilities-retry"]').exists()).toBe(false)

    fetchWishesMock.mockResolvedValueOnce(undefined)
    await wrapper.find('[data-test="wishes-retry"]').trigger('click')
    await flushPromises()
    expect(wrapper.find('[data-test="wishes-retry"]').exists()).toBe(false)
    expect(fetchWishesMock).toHaveBeenCalledTimes(2)
  })
})
