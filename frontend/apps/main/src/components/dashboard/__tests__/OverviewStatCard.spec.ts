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

// router-link renders as an anchor; we assert on its `to` via the stub.
vi.mock('vue-router', () => ({
  useRouter: () => ({ push: vi.fn() }),
  useRoute: () => ({ query: {}, path: '/' }),
  createRouter: () => ({ beforeEach: () => {}, afterEach: () => {}, push: () => Promise.resolve() }),
  createWebHistory: () => ({}),
}))

// useCurrency → useAuthStore needs an active Pinia; stub to a plain formatter.
vi.mock('@/composables/useCurrency', () => ({
  useCurrency: () => ({ format: (n: number) => `¥${n}` }),
}))

// --- Store mocks ---
const fetchLiabilitiesMock = vi.fn(() => Promise.resolve())
const fetchWishesMock = vi.fn(() => Promise.resolve())

const overviewRef = ref<null | Record<string, unknown>>(null)
const liabilitiesRef = ref<Array<Record<string, unknown>>>([])
const wishesRef = ref<Array<Record<string, unknown>>>([])

vi.mock('@/stores/dashboard', () => ({
  useDashboardStore: () => ({
    get overview() { return overviewRef.value },
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

import OverviewStatCard from '../OverviewStatCard.vue'

// Render router-link as a real anchor so we can assert the drill-down href.
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
  MoneyDisplay: true,
  'van-skeleton': true,
  RouterLink: RouterLinkStub,
}

function resetState() {
  overviewRef.value = null
  liabilitiesRef.value = []
  wishesRef.value = []
  fetchLiabilitiesMock.mockReset()
  fetchWishesMock.mockReset()
  fetchLiabilitiesMock.mockResolvedValue(undefined)
  fetchWishesMock.mockResolvedValue(undefined)
}

describe('OverviewStatCard', () => {
  beforeEach(() => {
    resetState()
  })

  it('renders net-worth hero and all four drill-down sub-stats linking to /finance tabs (AE1)', async () => {
    overviewRef.value = { net_worth: 100000, total_assets: 130000, total_liabilities: 30000, asset_count: 5 }

    const wrapper = mount(OverviewStatCard, { global: { stubs } })
    await flushPromises()

    expect(wrapper.find('.osc-main').exists()).toBe(true)

    const links = wrapper.findAll('a.osc-item')
    const byTest = (name: string) => wrapper.find(`[data-test="${name}"]`)
    expect(byTest('stat-assets').exists()).toBe(true)
    expect(byTest('stat-liabilities').exists()).toBe(true)
    expect(byTest('stat-monthly').exists()).toBe(true)
    expect(byTest('stat-wishes').exists()).toBe(true)
    expect(links.length).toBe(4)

    // Drill-down targets.
    expect(byTest('stat-assets').attributes('href')).toContain('/finance')
    expect(byTest('stat-assets').attributes('href')).toContain('tab=assets')
    expect(byTest('stat-liabilities').attributes('href')).toContain('tab=liabilities')
    expect(byTest('stat-monthly').attributes('href')).toContain('tab=liabilities')
    expect(byTest('stat-wishes').attributes('href')).toContain('tab=wishes')
  })

  it('shows estimate tag when any active liability lacks monthly_payment (AE4)', async () => {
    overviewRef.value = { net_worth: 0, total_assets: 0, total_liabilities: 0, asset_count: 0 }
    liabilitiesRef.value = [
      { id: '1', is_active: true, monthly_payment: null, remaining_amount: '12000', interest_rate: 18 },
    ]

    const wrapper = mount(OverviewStatCard, { global: { stubs } })
    await flushPromises()

    expect(wrapper.find('[data-test="monthly-estimate"]').exists()).toBe(true)
  })

  it('hides estimate tag when every active liability has an explicit monthly_payment', async () => {
    overviewRef.value = { net_worth: 0, total_assets: 0, total_liabilities: 0, asset_count: 0 }
    liabilitiesRef.value = [
      { id: '1', is_active: true, monthly_payment: '500', remaining_amount: '12000', interest_rate: 18 },
    ]

    const wrapper = mount(OverviewStatCard, { global: { stubs } })
    await flushPromises()

    expect(wrapper.find('[data-test="monthly-estimate"]').exists()).toBe(false)
  })

  it('caps wish progress at 100 when saved exceeds expected', async () => {
    overviewRef.value = { net_worth: 0, total_assets: 0, total_liabilities: 0, asset_count: 0 }
    wishesRef.value = [
      { id: 'w1', expected_price: '100', saved_amount: '250' },
    ]

    const wrapper = mount(OverviewStatCard, { global: { stubs } })
    await flushPromises()

    const fill = wrapper.find('.wish-progress-fill')
    expect(fill.exists()).toBe(true)
    expect(fill.attributes('style')).toContain('width: 100%')
  })

  it('returns 0 wish progress when total expected is 0 (avoids divide-by-zero)', async () => {
    overviewRef.value = { net_worth: 0, total_assets: 0, total_liabilities: 0, asset_count: 0 }
    wishesRef.value = [
      { id: 'w1', expected_price: '0', saved_amount: '50' },
    ]

    const wrapper = mount(OverviewStatCard, { global: { stubs } })
    await flushPromises()

    const fill = wrapper.find('.wish-progress-fill')
    expect(fill.attributes('style')).toContain('width: 0%')
  })

  it('shows monthly skeleton while liabilities load, then value after resolve', async () => {
    overviewRef.value = { net_worth: 0, total_assets: 0, total_liabilities: 0, asset_count: 0 }
    let resolveFetch!: () => void
    fetchLiabilitiesMock.mockReturnValueOnce(new Promise<void>((res) => { resolveFetch = res }))

    const wrapper = mount(OverviewStatCard, { global: { stubs } })
    // Skeleton visible during pending fetch (wait a tick for onMounted's loading=true to render).
    await wrapper.vm.$nextTick()
    expect(wrapper.find('[data-test="monthly-skeleton"]').exists()).toBe(true)

    resolveFetch()
    await flushPromises()
    expect(wrapper.find('[data-test="monthly-skeleton"]').exists()).toBe(false)
  })

  it('degrades only the monthly stat when liability fetch rejects; retry refetches (per-domain error)', async () => {
    overviewRef.value = { net_worth: 0, total_assets: 0, total_liabilities: 0, asset_count: 0 }
    fetchLiabilitiesMock.mockRejectedValueOnce(new Error('network'))

    const wrapper = mount(OverviewStatCard, { global: { stubs } })
    await flushPromises()

    // Monthly stat shows retry; wish stat is unaffected (renders its progress bar).
    expect(wrapper.find('[data-test="monthly-retry"]').exists()).toBe(true)
    expect(wrapper.find('[data-test="wish-retry"]').exists()).toBe(false)
    expect(wrapper.find('.wish-progress-bar').exists()).toBe(true)

    // Retry recovers.
    fetchLiabilitiesMock.mockResolvedValueOnce(undefined)
    await wrapper.find('[data-test="monthly-retry"]').trigger('click')
    await flushPromises()
    expect(wrapper.find('[data-test="monthly-retry"]').exists()).toBe(false)
    expect(fetchLiabilitiesMock).toHaveBeenCalledTimes(2)
  })

  it('degrades only the wish stat when wish fetch rejects; retry refetches', async () => {
    overviewRef.value = { net_worth: 0, total_assets: 0, total_liabilities: 0, asset_count: 0 }
    fetchWishesMock.mockRejectedValueOnce(new Error('network'))

    const wrapper = mount(OverviewStatCard, { global: { stubs } })
    await flushPromises()

    expect(wrapper.find('[data-test="wish-retry"]').exists()).toBe(true)
    expect(wrapper.find('[data-test="monthly-retry"]').exists()).toBe(false)

    fetchWishesMock.mockResolvedValueOnce(undefined)
    await wrapper.find('[data-test="wish-retry"]').trigger('click')
    await flushPromises()
    expect(wrapper.find('[data-test="wish-retry"]').exists()).toBe(false)
    expect(fetchWishesMock).toHaveBeenCalledTimes(2)
  })
})
