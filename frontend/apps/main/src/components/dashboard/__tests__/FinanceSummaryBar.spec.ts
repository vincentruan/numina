import { mount, flushPromises } from '@vue/test-utils'
import { ref, computed } from 'vue'
import { describe, it, expect, vi, beforeEach } from 'vitest'

// Mock vue-i18n
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
  useCurrency: () => ({ format: (n: number) => `¥${n}` }),
}))

// --- Store mocks ---
const overviewRef = ref<Record<string, unknown> | null>(null)
const liabilitiesRef = ref<Array<Record<string, unknown>>>([])

vi.mock('@/stores/dashboard', () => ({
  useDashboardStore: () => ({
    get overview() { return overviewRef.value },
  }),
}))
vi.mock('@/stores/liability', () => ({
  useLiabilityStore: () => ({
    get liabilities() { return liabilitiesRef.value },
  }),
}))

import FinanceSummaryBar from '../FinanceSummaryBar.vue'

// Stub MoneyDisplay to render amount as text
const MoneyDisplayStub = {
  name: 'MoneyDisplay',
  props: ['amount'],
  template: '<span class="money-display">{{ amount }}</span>',
}

describe('FinanceSummaryBar', () => {
  beforeEach(() => {
    overviewRef.value = null
    liabilitiesRef.value = []
  })

  it('does not render when overview is null', () => {
    const wrapper = mount(FinanceSummaryBar, {
      global: {
        stubs: { MoneyDisplay: MoneyDisplayStub },
      },
    })
    expect(wrapper.find('.finance-summary-bar').exists()).toBe(false)
  })

  it('renders three summary items when overview is loaded', async () => {
    overviewRef.value = {
      total_assets: 100000,
      total_liabilities: 30000,
      net_worth: 70000,
      asset_count: 5,
      month_over_month_change: 2.5,
      month_over_month_change_amount: 1750,
      total_daily_cost: 100,
    }

    const wrapper = mount(FinanceSummaryBar, {
      global: {
        stubs: { MoneyDisplay: MoneyDisplayStub },
      },
    })

    await flushPromises()

    expect(wrapper.find('[data-test="summary-net-worth"]').exists()).toBe(true)
    expect(wrapper.find('[data-test="summary-liability-ratio"]').exists()).toBe(true)
    expect(wrapper.find('[data-test="summary-monthly-payment"]').exists()).toBe(true)
  })

  it('calculates liability ratio correctly', async () => {
    overviewRef.value = {
      total_assets: 100000,
      total_liabilities: 30000,
      net_worth: 70000,
      asset_count: 5,
      month_over_month_change: 2.5,
      month_over_month_change_amount: 1750,
      total_daily_cost: 100,
    }

    const wrapper = mount(FinanceSummaryBar, {
      global: {
        stubs: { MoneyDisplay: MoneyDisplayStub },
      },
    })

    await flushPromises()

    const ratioItem = wrapper.find('[data-test="summary-liability-ratio"]')
    const valueSpan = ratioItem.find('.summary-value')
    expect(valueSpan.text()).toBe('30.0%')
  })

  it('shows "-" when total_assets is 0 (zero-division protection)', async () => {
    overviewRef.value = {
      total_assets: 0,
      total_liabilities: 30000,
      net_worth: -30000,
      asset_count: 0,
      month_over_month_change: null,
      month_over_month_change_amount: null,
      total_daily_cost: 0,
    }

    const wrapper = mount(FinanceSummaryBar, {
      global: {
        stubs: { MoneyDisplay: MoneyDisplayStub },
      },
    })

    await flushPromises()

    const ratioItem = wrapper.find('[data-test="summary-liability-ratio"]')
    const valueSpan = ratioItem.find('.summary-value')
    expect(valueSpan.text()).toBe('-')
  })

  it('emits navigate event with "assets" when net worth is clicked', async () => {
    overviewRef.value = {
      total_assets: 100000,
      total_liabilities: 30000,
      net_worth: 70000,
      asset_count: 5,
      month_over_month_change: 2.5,
      month_over_month_change_amount: 1750,
      total_daily_cost: 100,
    }

    const wrapper = mount(FinanceSummaryBar, {
      global: {
        stubs: { MoneyDisplay: MoneyDisplayStub },
      },
    })

    await flushPromises()

    const netWorthItem = wrapper.find('[data-test="summary-net-worth"]')
    await netWorthItem.trigger('click')

    expect(wrapper.emitted('navigate')).toBeTruthy()
    expect(wrapper.emitted('navigate')![0]).toEqual(['assets'])
  })

  it('emits navigate event with "liabilities" when liability ratio is clicked', async () => {
    overviewRef.value = {
      total_assets: 100000,
      total_liabilities: 30000,
      net_worth: 70000,
      asset_count: 5,
      month_over_month_change: 2.5,
      month_over_month_change_amount: 1750,
      total_daily_cost: 100,
    }

    const wrapper = mount(FinanceSummaryBar, {
      global: {
        stubs: { MoneyDisplay: MoneyDisplayStub },
      },
    })

    await flushPromises()

    const ratioItem = wrapper.find('[data-test="summary-liability-ratio"]')
    await ratioItem.trigger('click')

    expect(wrapper.emitted('navigate')).toBeTruthy()
    expect(wrapper.emitted('navigate')![0]).toEqual(['liabilities'])
  })

  it('emits navigate event with "liabilities" when monthly payment is clicked', async () => {
    overviewRef.value = {
      total_assets: 100000,
      total_liabilities: 30000,
      net_worth: 70000,
      asset_count: 5,
      month_over_month_change: 2.5,
      month_over_month_change_amount: 1750,
      total_daily_cost: 100,
    }

    liabilitiesRef.value = [
      {
        id: '1',
        name: 'Mortgage',
        is_active: true,
        monthly_payment: 5000,
        remaining_amount: 500000,
        interest_rate: 4.5,
      },
      {
        id: '2',
        name: 'Credit Card',
        is_active: true,
        monthly_payment: 1000,
        remaining_amount: 10000,
        interest_rate: 18,
      },
    ]

    const wrapper = mount(FinanceSummaryBar, {
      global: {
        stubs: { MoneyDisplay: MoneyDisplayStub },
      },
    })

    await flushPromises()

    const monthlyItem = wrapper.find('[data-test="summary-monthly-payment"]')
    await monthlyItem.trigger('click')

    expect(wrapper.emitted('navigate')).toBeTruthy()
    expect(wrapper.emitted('navigate')![0]).toEqual(['liabilities'])
  })

  it('calculates monthly payment total from active liabilities', async () => {
    overviewRef.value = {
      total_assets: 100000,
      total_liabilities: 30000,
      net_worth: 70000,
      asset_count: 5,
      month_over_month_change: 2.5,
      month_over_month_change_amount: 1750,
      total_daily_cost: 100,
    }

    liabilitiesRef.value = [
      {
        id: '1',
        name: 'Mortgage',
        is_active: true,
        monthly_payment: 5000,
        remaining_amount: 500000,
        interest_rate: 4.5,
      },
      {
        id: '2',
        name: 'Credit Card',
        is_active: true,
        monthly_payment: 1000,
        remaining_amount: 10000,
        interest_rate: 18,
      },
      {
        id: '3',
        name: 'Paid Loan',
        is_active: false,
        monthly_payment: 2000,
        remaining_amount: 0,
        interest_rate: 5,
      },
    ]

    const wrapper = mount(FinanceSummaryBar, {
      global: {
        stubs: { MoneyDisplay: MoneyDisplayStub },
      },
    })

    await flushPromises()

    const monthlyItem = wrapper.find('[data-test="summary-monthly-payment"]')
    const moneyDisplay = monthlyItem.find('.money-display')
    // 5000 + 1000 = 6000 (inactive liability excluded)
    expect(moneyDisplay.text()).toBe('6000')
  })

  it('has correct accessibility attributes', async () => {
    overviewRef.value = {
      total_assets: 100000,
      total_liabilities: 30000,
      net_worth: 70000,
      asset_count: 5,
      month_over_month_change: 2.5,
      month_over_month_change_amount: 1750,
      total_daily_cost: 100,
    }

    const wrapper = mount(FinanceSummaryBar, {
      global: {
        stubs: { MoneyDisplay: MoneyDisplayStub },
      },
    })

    await flushPromises()

    const items = wrapper.findAll('.summary-item')
    expect(items.length).toBe(3)

    items.forEach((item) => {
      expect(item.attributes('role')).toBe('button')
      expect(item.attributes('tabindex')).toBe('0')
      expect(item.attributes('aria-label')).toBeTruthy()
    })
  })

  it('responds to Enter key press', async () => {
    overviewRef.value = {
      total_assets: 100000,
      total_liabilities: 30000,
      net_worth: 70000,
      asset_count: 5,
      month_over_month_change: 2.5,
      month_over_month_change_amount: 1750,
      total_daily_cost: 100,
    }

    const wrapper = mount(FinanceSummaryBar, {
      global: {
        stubs: { MoneyDisplay: MoneyDisplayStub },
      },
    })

    await flushPromises()

    const netWorthItem = wrapper.find('[data-test="summary-net-worth"]')
    await netWorthItem.trigger('keydown.enter')

    expect(wrapper.emitted('navigate')).toBeTruthy()
    expect(wrapper.emitted('navigate')![0]).toEqual(['assets'])
  })

  it('responds to Space key press', async () => {
    overviewRef.value = {
      total_assets: 100000,
      total_liabilities: 30000,
      net_worth: 70000,
      asset_count: 5,
      month_over_month_change: 2.5,
      month_over_month_change_amount: 1750,
      total_daily_cost: 100,
    }

    const wrapper = mount(FinanceSummaryBar, {
      global: {
        stubs: { MoneyDisplay: MoneyDisplayStub },
      },
    })

    await flushPromises()

    const ratioItem = wrapper.find('[data-test="summary-liability-ratio"]')
    await ratioItem.trigger('keydown.space')

    expect(wrapper.emitted('navigate')).toBeTruthy()
    expect(wrapper.emitted('navigate')![0]).toEqual(['liabilities'])
  })
})
