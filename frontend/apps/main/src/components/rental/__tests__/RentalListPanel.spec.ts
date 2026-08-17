import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { createI18n } from 'vue-i18n'
import { createPinia, setActivePinia } from 'pinia'
import RentalListPanel from '../RentalListPanel.vue'
import { useRentalContractStore } from '@/stores/rentalContract'
import type { RentalContract, RentalSummary } from '@/types'

vi.mock('@/api/rentalContracts', () => ({
  getRentalContracts: vi.fn(),
  getRentalContract: vi.fn(),
  createRentalContract: vi.fn(),
  updateRentalContract: vi.fn(),
  deleteRentalContract: vi.fn(),
  getRentalSummary: vi.fn(),
}))

const i18n = createI18n({
  legacy: false,
  locale: 'zh-CN',
  messages: { 'zh-CN': {} },
})

function makeContract(overrides: Partial<RentalContract> = {}): RentalContract {
  return {
    id: '1',
    user_id: '1',
    family_id: '1',
    role: 'landlord',
    monthly_rent: '3000.00',
    deposit: '6000.00',
    start_date: '2026-01-01',
    currency: 'CNY',
    is_active: true,
    ...overrides,
  }
}

const mockSummary: RentalSummary = {
  monthly_income: '3000.00',
  monthly_expense: '1500.00',
  net_cash_flow: '1500.00',
  total_deposit: '8000.00',
}

import * as rentalApi from '@/api/rentalContracts'

function mountPanel() {
  return mount(RentalListPanel, {
    global: {
      plugins: [i18n],
      stubs: {
        'van-tabs': { template: '<div><slot /></div>' },
        'van-tab': { template: '<div><slot /></div>' },
        'van-popup': { template: '<div><slot /></div>' },
        'van-dialog': { template: '<div><slot /></div>' },
        'van-action-sheet': { template: '<div />' },
        'van-icon': { template: '<i class="van-icon" />' },
        RentalForm: { template: '<div class="rental-form-stub" />' },
        EmptyState: { template: '<div class="empty-stub" />' },
        RentalContractCard: {
          props: ['contract'],
          template: '<div class="rental-card-stub" @click="$emit(\'click\')" />',
        },
      },
    },
  })
}

describe('RentalListPanel', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
    vi.mocked(rentalApi.getRentalContracts).mockResolvedValue({
      data: [
        makeContract(),
        makeContract({ id: '2', role: 'tenant', is_active: false }),
      ],
    } as never)
    vi.mocked(rentalApi.getRentalSummary).mockResolvedValue({
      data: mockSummary,
    } as never)
  })

  it('renders summary with income/expense/net on active tab', async () => {
    const wrapper = mountPanel()
    await flushPromises()

    const banner = wrapper.find('.summary-banner')
    expect(banner.exists()).toBe(true)
    expect(wrapper.findAll('.summary-item')).toHaveLength(3)
    expect(wrapper.find('.deposit-row').exists()).toBe(true)
  })

  it('renders only active contracts on the active tab', async () => {
    const wrapper = mountPanel()
    await flushPromises()

    // 2 contracts fetched; 1 is_active=true
    expect(wrapper.findAll('.rental-card-stub')).toHaveLength(1)
  })

  it('shows empty state when no active contracts', async () => {
    vi.mocked(rentalApi.getRentalContracts).mockResolvedValue({
      data: [makeContract({ id: '2', is_active: false })],
    } as never)
    const wrapper = mountPanel()
    await flushPromises()

    expect(wrapper.find('.empty-stub').exists()).toBe(true)
    expect(wrapper.findAll('.rental-card-stub')).toHaveLength(0)
  })

  it('hides deposit row when total deposit is 0', async () => {
    vi.mocked(rentalApi.getRentalSummary).mockResolvedValue({
      data: { ...mockSummary, total_deposit: '0.00' },
    } as never)
    const wrapper = mountPanel()
    await flushPromises()

    expect(wrapper.find('.deposit-row').exists()).toBe(false)
  })

  it('populates the pinia store on load', async () => {
    mountPanel()
    await flushPromises()

    const store = useRentalContractStore()
    expect(store.contracts).toHaveLength(2)
    expect(store.summary?.net_cash_flow).toBe('1500.00')
  })
})
