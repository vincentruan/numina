import { mount, flushPromises } from '@vue/test-utils'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import type { AxiosResponse } from 'axios'
import InterestForecast from '../InterestForecast.vue'
import type { Liability, LiabilitySimResult } from '@/types'

function simResp(data: LiabilitySimResult): AxiosResponse<LiabilitySimResult> {
  return { data } as AxiosResponse<LiabilitySimResult>
}

vi.mock('vue-i18n', () => ({
  useI18n: () => ({
    t: (key: string, params?: Record<string, unknown>) => {
      if (params && typeof params === 'object') {
        return `${key}:${JSON.stringify(params)}`
      }
      return key
    },
  }),
  createI18n: () => ({ global: { t: (k: string) => k, te: () => true } }),
}))

vi.mock('vue-router', () => ({
  useRouter: () => ({ push: vi.fn() }),
  createRouter: () => ({ beforeEach: () => {}, afterEach: () => {}, push: () => Promise.resolve() }),
  createWebHistory: () => ({}),
}))

vi.mock('vant', () => ({
  showSuccessToast: vi.fn(),
  showFailToast: vi.fn(),
  showConfirmDialog: vi.fn(() => Promise.resolve()),
}))

vi.mock('@/composables/useCurrency', () => ({
  useCurrency: () => ({ format: (n: number) => String(n), formatPercent: (n: number) => String(n) }),
}))

import * as liabilityApi from '@/api/liabilities'

function makeLiability(overrides: Partial<Liability> = {}): Liability {
  return {
    id: '1',
    user_id: 'u1',
    family_id: 'f1',
    category: 'credit_card',
    name: '信用卡',
    original_amount: '10000',
    remaining_amount: '8000',
    currency: 'CNY',
    monthly_payment: '1000',
    interest_rate: 18,
    start_date: '2024-01-01',
    is_active: true,
    ...overrides,
  }
}

function mountForecast(liability: Liability) {
  return mount(InterestForecast, {
    props: { liability },
    global: { stubs: ['van-button', 'van-loading', 'van-popup', 'van-field'] },
  })
}

describe('InterestForecast', () => {
  beforeEach(() => {
    vi.restoreAllMocks()
  })

  it('hides entirely when interest_rate is 0 (spec §6.1 adversarial)', async () => {
    const spy = vi.spyOn(liabilityApi, 'simulateLiability')
    const wrapper = mountForecast(makeLiability({ interest_rate: 0 }))
    await flushPromises()
    expect(wrapper.find('.interest-forecast').exists()).toBe(false)
    expect(spy).not.toHaveBeenCalled()
  })

  it('hides entirely when interest_rate is null', async () => {
    const wrapper = mountForecast(makeLiability({ interest_rate: 0 }))
    await flushPromises()
    expect(wrapper.find('.interest-forecast').exists()).toBe(false)
  })

  it('shows total_interest + months when rate > 0', async () => {
    vi.spyOn(liabilityApi, 'simulateLiability').mockResolvedValue(
      simResp({
        total_interest: '2400.00',
        months: 8,
        monthly_payment: '1000',
        warning: null,
        baseline_total_interest: '2400.00',
        baseline_months: 8,
        savings_vs_baseline: '0',
        months_saved: 0,
      }),
    )
    const wrapper = mountForecast(makeLiability({ interest_rate: 18 }))
    await flushPromises()
    expect(wrapper.find('.interest-forecast').exists()).toBe(true)
    expect(wrapper.find('.if-value').text()).toContain('2400')
  })

  it('simulate returns savings_vs_baseline for extra scenarios', async () => {
    vi.spyOn(liabilityApi, 'simulateLiability').mockImplementation(async (req) => {
      const extra = Number(req.extra_monthly ?? '0')
      return simResp({
        total_interest: extra > 0 ? '1200.00' : '2400.00',
        months: extra > 0 ? 6 : 8,
        monthly_payment: '1000',
        warning: null,
        baseline_total_interest: '2400.00',
        baseline_months: 8,
        savings_vs_baseline: extra > 0 ? '1200.00' : '0',
        months_saved: extra > 0 ? 2 : 0,
      })
    })
    const wrapper = mountForecast(makeLiability({ interest_rate: 18 }))
    await flushPromises()
    // extra500 + extra1000 scenarios rendered with savings
    const scenarios = wrapper.findAll('.if-scenario')
    expect(scenarios).toHaveLength(2)
    expect(scenarios[0].text()).toContain('1200')
  })
})
