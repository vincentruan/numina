import { mount, flushPromises } from '@vue/test-utils'
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
vi.mock('vue-router', () => ({
  useRouter: () => ({ push: pushMock }),
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

import LiabilityStrategyCard from '../LiabilityStrategyCard.vue'

const stubs = {
  'van-button': { template: '<button class="van-button" @click="$emit(\'click\')"><slot /></button>' },
  'van-icon': { template: '<i class="van-icon" />' },
}

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

describe('LiabilityStrategyCard', () => {
  beforeEach(() => {
    localStorage.clear()
    vi.clearAllMocks()
  })

  it('does not render with <2 active liabilities', () => {
    const wrapper = mount(LiabilityStrategyCard, {
      props: { liabilities: [makeLiability()] },
      global: { stubs },
    })
    expect(wrapper.find('.strategy-card').exists()).toBe(false)
  })

  it('renders with 2+ active liabilities', () => {
    const wrapper = mount(LiabilityStrategyCard, {
      props: {
        liabilities: [
          makeLiability({ id: '1', interest_rate: 18, remaining_amount: '5000' }),
          makeLiability({ id: '2', interest_rate: 12, remaining_amount: '3000' }),
        ],
      },
      global: { stubs },
    })
    expect(wrapper.find('.strategy-card').exists()).toBe(true)
  })

  it('shows recommended badge on avalanche method', () => {
    const wrapper = mount(LiabilityStrategyCard, {
      props: {
        liabilities: [
          makeLiability({ id: '1', interest_rate: 18, remaining_amount: '5000' }),
          makeLiability({ id: '2', interest_rate: 12, remaining_amount: '3000' }),
        ],
      },
      global: { stubs },
    })
    expect(wrapper.find('.strat-method--recommended').exists()).toBe(true)
    expect(wrapper.find('.strat-badge').text()).toBe('liability.strategy.recommended')
  })

  it('renders both strategy methods with interest estimates', () => {
    const wrapper = mount(LiabilityStrategyCard, {
      props: {
        liabilities: [
          makeLiability({ id: '1', interest_rate: 18, remaining_amount: '10000', monthly_payment: '1000' }),
          makeLiability({ id: '2', interest_rate: 5, remaining_amount: '1000', monthly_payment: '500' }),
        ],
      },
      global: { stubs },
    })
    // Both strategy method blocks are rendered
    const methods = wrapper.findAll('.strat-method')
    expect(methods.length).toBe(2)
    // Interest estimates are displayed
    const interests = wrapper.findAll('.strat-interest')
    expect(interests.length).toBe(2)
  })

  it('adopts avalanche strategy and emits event', async () => {
    const wrapper = mount(LiabilityStrategyCard, {
      props: {
        liabilities: [
          makeLiability({ id: '1', interest_rate: 18, remaining_amount: '5000' }),
          makeLiability({ id: '2', interest_rate: 12, remaining_amount: '3000' }),
        ],
      },
      global: { stubs },
    })
    const vm = wrapper.vm as unknown as { adoptStrategy: (s: 'avalanche' | 'snowball') => void }
    vm.adoptStrategy('avalanche')
    expect(wrapper.emitted('adopt')).toBeTruthy()
    expect(wrapper.emitted('adopt')![0]).toEqual(['avalanche'])
    expect(localStorage.getItem('liability_strategy_adopted')).toBe('avalanche')
  })

  it('adopts snowball strategy and emits event', async () => {
    const wrapper = mount(LiabilityStrategyCard, {
      props: {
        liabilities: [
          makeLiability({ id: '1', interest_rate: 18, remaining_amount: '5000' }),
          makeLiability({ id: '2', interest_rate: 12, remaining_amount: '3000' }),
        ],
      },
      global: { stubs },
    })
    const vm = wrapper.vm as unknown as { adoptStrategy: (s: 'avalanche' | 'snowball') => void }
    vm.adoptStrategy('snowball')
    expect(wrapper.emitted('adopt')).toBeTruthy()
    expect(wrapper.emitted('adopt')![0]).toEqual(['snowball'])
    expect(localStorage.getItem('liability_strategy_adopted')).toBe('snowball')
  })

  it('restores adopted state from localStorage on mount', async () => {
    localStorage.setItem('liability_strategy_adopted', 'snowball')
    const wrapper = mount(LiabilityStrategyCard, {
      props: {
        liabilities: [
          makeLiability({ id: '1', interest_rate: 18, remaining_amount: '5000' }),
          makeLiability({ id: '2', interest_rate: 12, remaining_amount: '3000' }),
        ],
      },
      global: { stubs },
    })
    await flushPromises()
    expect(wrapper.find('.strat-adopted').exists()).toBe(true)
    expect(wrapper.emitted('adopt')).toBeTruthy()
    expect(wrapper.emitted('adopt')![0]).toEqual(['snowball'])
  })

  it('resets strategy when change link clicked', async () => {
    localStorage.setItem('liability_strategy_adopted', 'avalanche')
    const wrapper = mount(LiabilityStrategyCard, {
      props: {
        liabilities: [
          makeLiability({ id: '1', interest_rate: 18, remaining_amount: '5000' }),
          makeLiability({ id: '2', interest_rate: 12, remaining_amount: '3000' }),
        ],
      },
      global: { stubs },
    })
    await flushPromises()
    const changeLink = wrapper.find('.strat-change-link')
    await changeLink.trigger('click')
    expect(localStorage.getItem('liability_strategy_adopted')).toBeNull()
    expect(wrapper.emitted('adopt')!.at(-1)).toEqual([null])
    expect(wrapper.find('.strat-adopted').exists()).toBe(false)
  })

  it('shows subtitle with active liability count', () => {
    const wrapper = mount(LiabilityStrategyCard, {
      props: {
        liabilities: [
          makeLiability({ id: '1', interest_rate: 18, remaining_amount: '5000' }),
          makeLiability({ id: '2', interest_rate: 12, remaining_amount: '3000' }),
          makeLiability({ id: '3', interest_rate: 8, remaining_amount: '2000', is_active: false }),
        ],
      },
      global: { stubs },
    })
    expect(wrapper.find('.strat-subtitle').text()).toBe('liability.strategy.subtitle')
  })
})
