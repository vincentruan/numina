import { mount, flushPromises } from '@vue/test-utils'
import { ref } from 'vue'
import { describe, it, expect, vi, beforeEach } from 'vitest'

// Mock vue-i18n (component uses useI18n; @/api/index → @/i18n calls createI18n at load).
vi.mock('vue-i18n', () => ({
  useI18n: () => ({
    t: (key: string, params?: Record<string, unknown>) => {
      if (!params) return key
      // Interpolate {name} style params for assertion readability.
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
  showFailToast: vi.fn(),
}))

// useCurrency → useAuthStore needs an active Pinia; stub to a plain formatter
// so FinanceHubPage's computed strings work without a Pinia plugin.
vi.mock('@/composables/useCurrency', () => ({
  useCurrency: () => ({
    format: (n: number) => `¥${n}`,
  }),
}))

// --- Store mocks (dashboard / liability / wish) + debt-warning threshold fetch ---
const fetchAllMock = vi.fn(() => Promise.resolve())
const fetchLiabilitiesMock = vi.fn(() => Promise.resolve())
const fetchWishesMock = vi.fn(() => Promise.resolve())

const overviewRef = ref<null | { net_worth: number; total_liabilities: number; total_assets: number; asset_count: number }>(null)
const liabilitiesRef = ref<Array<Record<string, unknown>>>([])
const wishesRef = ref<Array<Record<string, unknown>>>([])
const loadingRef = ref(false)
const educationRewardSummaryRef = ref<null | { total: number; month_total: number; count: number }>(null)

// Use getters so `store.liabilities` returns the unwrapped array (mimicking
// Pinia's automatic ref unwrapping when accessed off a store instance).
vi.mock('@/stores/dashboard', () => ({
  useDashboardStore: () => ({
    get overview() { return overviewRef.value },
    get loading() { return loadingRef.value },
    get educationRewardSummary() { return educationRewardSummaryRef.value },
    fetchAll: fetchAllMock,
    fetchEducationRewardSummary: vi.fn(),
    invalidateDashboard: vi.fn(),
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

// useDebtWarning fetches /family/debt-thresholds via @/api/index http.
// Stub it to a no-op composable driven by the store refs above so we exercise
// the real debtWishHint computed in FinanceHubPage.
vi.mock('@/composables/useDebtWarning', () => ({
  useDebtWarning: (liabs: { value: unknown[] }, _wishes: { value: unknown[] }) => {
    const highInterest = {
      get value() {
        return (liabs.value || [])
          .filter((l: Record<string, unknown>) => l.is_active && (l.interest_rate as number ?? 0) >= 12)
          .map((l: Record<string, unknown>) => ({
            ...l,
            monthly_interest: Math.round(
              (Number(l.remaining_amount) * ((l.interest_rate as number) / 100 / 12)) * 100,
            ) / 100,
          }))
      },
    }
    return { highInterestLiabilities: highInterest, loadThresholds: vi.fn(() => Promise.resolve()) }
  },
}))

import FinanceHubPage from '../FinanceHubPage.vue'

function resetState() {
  overviewRef.value = null
  liabilitiesRef.value = []
  wishesRef.value = []
  loadingRef.value = false
  educationRewardSummaryRef.value = null
  routeQuery.value = {}
  pushMock.mockReset()
  fetchAllMock.mockReset()
  fetchLiabilitiesMock.mockReset()
  fetchWishesMock.mockReset()
  fetchAllMock.mockResolvedValue(undefined)
  fetchLiabilitiesMock.mockResolvedValue(undefined)
  fetchWishesMock.mockResolvedValue(undefined)
}

describe('FinanceHubPage', () => {
  beforeEach(() => {
    resetState()
  })

  it('renders overview metrics (net worth / liabilities / monthly payment / wish progress)', async () => {
    overviewRef.value = { net_worth: 100000, total_liabilities: 30000, total_assets: 130000, asset_count: 5 }
    liabilitiesRef.value = [
      { id: '1', is_active: true, monthly_payment: '2000', remaining_amount: '10000', interest_rate: 5 },
    ]
    wishesRef.value = [
      { id: 'w1', expected_price: 10000, saved_amount: '2500', status: 'active' },
    ]

    const wrapper = mount(FinanceHubPage, {
      global: { stubs: ['van-pull-refresh', 'van-tabs', 'van-tab', 'van-button', 'van-icon', 'van-empty', 'DashboardSkeleton', 'MoneyDisplay'] },
    })
    await flushPromises()

    // Four overview rows present.
    const labels = wrapper.findAll('.ov-label').map((n) => n.text())
    expect(labels.some((l) => l.includes('financeHub.netWorth'))).toBe(true)
    expect(labels.some((l) => l.includes('financeHub.totalLiabilities'))).toBe(true)
    expect(labels.some((l) => l.includes('financeHub.monthlyPayment'))).toBe(true)
    expect(labels.some((l) => l.includes('financeHub.wishProgress'))).toBe(true)
  })

  it('shows estimate tag when an active liability lacks monthly_payment', async () => {
    overviewRef.value = { net_worth: 100000, total_liabilities: 0, total_assets: 100000, asset_count: 1 }
    liabilitiesRef.value = [
      { id: '1', is_active: true, monthly_payment: null, remaining_amount: '12000', interest_rate: 18 },
    ]
    wishesRef.value = []

    const wrapper = mount(FinanceHubPage, {
      global: { stubs: ['van-pull-refresh', 'van-tabs', 'van-tab', 'van-button', 'van-icon', 'van-empty', 'DashboardSkeleton', 'MoneyDisplay'] },
    })
    await flushPromises()

    expect(wrapper.find('.ov-estimate-tag').exists()).toBe(true)
  })

  it('hides debt-wish hint when no high-interest debt', async () => {
    overviewRef.value = { net_worth: 100000, total_liabilities: 0, total_assets: 100000, asset_count: 0 }
    liabilitiesRef.value = []
    wishesRef.value = [{ id: 'w1', name: '心愿A', monthly_saving: '500', target_date: '2026-12-01' }]

    const wrapper = mount(FinanceHubPage, {
      global: { stubs: ['van-pull-refresh', 'van-tabs', 'van-tab', 'van-button', 'van-icon', 'van-empty', 'DashboardSkeleton', 'MoneyDisplay'] },
    })
    await flushPromises()

    expect(wrapper.find('.debt-wish-hint').exists()).toBe(false)
  })

  it('shows debt-wish hint when high-interest debt + qualifying wish exist', async () => {
    overviewRef.value = { net_worth: 100000, total_liabilities: 12000, total_assets: 112000, asset_count: 0 }
    liabilitiesRef.value = [
      { id: '1', is_active: true, monthly_payment: null, remaining_amount: '12000', interest_rate: 18 },
    ]
    // monthly_interest = 12000 × 0.18/12 = 180; monthly_saving 60 → 3 months.
    wishesRef.value = [
      { id: 'w1', name: '心愿A', monthly_saving: '60', target_date: '2026-12-01', ignore_debt_warning: false },
    ]

    const wrapper = mount(FinanceHubPage, {
      global: { stubs: ['van-pull-refresh', 'van-tabs', 'van-tab', 'van-button', 'van-icon', 'van-empty', 'DashboardSkeleton', 'MoneyDisplay'] },
    })
    await flushPromises()

    const hint = wrapper.find('.debt-wish-hint')
    expect(hint.exists()).toBe(true)
    expect(hint.text()).toContain('financeHub.debtWishHint')
  })

  it('navigates to /assets when view-all clicked (sub-tab contract)', async () => {
    overviewRef.value = { net_worth: 0, total_liabilities: 0, total_assets: 0, asset_count: 0 }
    liabilitiesRef.value = []
    wishesRef.value = []

    const wrapper = mount(FinanceHubPage, {
      global: { stubs: ['van-pull-refresh', 'van-tabs', 'van-tab', 'van-button', 'van-icon', 'van-empty', 'DashboardSkeleton', 'MoneyDisplay'] },
    })
    await flushPromises()

    const assetBtn = wrapper.find('[data-test="view-all-assets"]')
    expect(assetBtn.exists()).toBe(true)
    await assetBtn.trigger('click')
    expect(pushMock).toHaveBeenCalledWith('/assets')
  })

  it('honors ?tab=liabilities query to preselect sub-tab', async () => {
    overviewRef.value = { net_worth: 0, total_liabilities: 0, total_assets: 0, asset_count: 0 }
    routeQuery.value = { tab: 'liabilities' }

    const wrapper = mount(FinanceHubPage, {
      global: { stubs: ['van-pull-refresh', 'van-tabs', 'van-tab', 'van-button', 'van-icon', 'van-empty', 'DashboardSkeleton', 'MoneyDisplay'] },
    })
    await flushPromises()

    // activeTab is reflected on the root element's data-active-tab attribute.
    expect(wrapper.find('.finance-hub-page').attributes('data-active-tab')).toBe('liabilities')
  })

  it('surfaces error state (not silent 0) when critical fetch rejects and overview absent', async () => {
    fetchAllMock.mockRejectedValueOnce(new Error('network'))
    overviewRef.value = null

    const wrapper = mount(FinanceHubPage, {
      global: { stubs: ['van-pull-refresh', 'van-tabs', 'van-tab', 'van-button', 'van-icon', 'van-empty', 'DashboardSkeleton', 'MoneyDisplay'] },
    })
    await flushPromises()

    expect(wrapper.find('.hub-error').exists()).toBe(true)
  })

  it('renders education reward card with total/month/count when data present', async () => {
    overviewRef.value = { net_worth: 100000, total_liabilities: 0, total_assets: 100000, asset_count: 1 }
    educationRewardSummaryRef.value = { total: 50, month_total: 20, count: 2 }

    const wrapper = mount(FinanceHubPage, {
      global: { stubs: ['van-pull-refresh', 'van-tabs', 'van-tab', 'van-button', 'van-icon', 'van-empty', 'DashboardSkeleton', 'MoneyDisplay'] },
    })
    await flushPromises()

    const card = wrapper.find('.education-reward-card')
    expect(card.exists()).toBe(true)
    // Title + total/month labels (i18n keys; MoneyDisplay stubbed so amounts not asserted as text).
    expect(card.text()).toContain('financeHub.educationReward')
    expect(card.text()).toContain('financeHub.educationRewardTotal')
    expect(card.text()).toContain('financeHub.educationRewardMonth')
    // Count cell renders the count i18n key (mock t() returns the key; the real
    // locale value "{count} 笔" is interpolated at runtime, not in this mock).
    expect(wrapper.find('.er-cell-count').text()).toContain('financeHub.educationRewardCount')
    // Non-empty state → no empty placeholder.
    expect(wrapper.find('.er-empty').exists()).toBe(false)
  })

  it('shows education reward empty text when count is 0', async () => {
    overviewRef.value = { net_worth: 100000, total_liabilities: 0, total_assets: 100000, asset_count: 1 }
    educationRewardSummaryRef.value = { total: 0, month_total: 0, count: 0 }

    const wrapper = mount(FinanceHubPage, {
      global: { stubs: ['van-pull-refresh', 'van-tabs', 'van-tab', 'van-button', 'van-icon', 'van-empty', 'DashboardSkeleton', 'MoneyDisplay'] },
    })
    await flushPromises()

    // Card still rendered (placeholder, no layout jump) but shows empty text.
    const card = wrapper.find('.education-reward-card')
    expect(card.exists()).toBe(true)
    expect(wrapper.find('.er-empty').exists()).toBe(true)
    expect(wrapper.find('.er-empty').text()).toContain('financeHub.educationRewardEmpty')
    expect(wrapper.find('.er-row').exists()).toBe(false)
  })

  it('shows education reward empty text when summary not yet loaded (null)', async () => {
    overviewRef.value = { net_worth: 100000, total_liabilities: 0, total_assets: 100000, asset_count: 1 }
    educationRewardSummaryRef.value = null

    const wrapper = mount(FinanceHubPage, {
      global: { stubs: ['van-pull-refresh', 'van-tabs', 'van-tab', 'van-button', 'van-icon', 'van-empty', 'DashboardSkeleton', 'MoneyDisplay'] },
    })
    await flushPromises()

    expect(wrapper.find('.er-empty').exists()).toBe(true)
  })
})
