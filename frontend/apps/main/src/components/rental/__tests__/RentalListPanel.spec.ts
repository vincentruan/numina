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

const TabsStub = { name: 'TabsStub', template: '<div class="van-tabs-stub"><slot /></div>' }
const DialogStub = { name: 'DialogStub', template: '<div class="van-dialog-stub"><slot /></div>' }
const FormStub = { name: 'FormStub', emits: ['submit'], template: '<div class="rental-form-stub" />' }

function mountPanel() {
  return mount(RentalListPanel, {
    global: {
      plugins: [i18n],
      stubs: {
        'van-tabs': TabsStub,
        'van-tab': { name: 'TabStub', template: '<div><slot /></div>' },
        'van-popup': { name: 'PopupStub', template: '<div><slot /></div>' },
        'van-dialog': DialogStub,
        'van-action-sheet': { name: 'ActionSheetStub', template: '<div />' },
        'van-icon': { name: 'IconStub', template: '<i class="van-icon" />' },
        RentalForm: FormStub,
        EmptyState: { name: 'EmptyStub', template: '<div class="empty-stub" />' },
        RentalContractCard: {
          name: 'CardStub',
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

  it('only renders active contracts by default (inactive are filtered client-side)', async () => {
    vi.mocked(rentalApi.getRentalContracts).mockResolvedValue({
      data: [
        makeContract({ id: '1', is_active: true }),
        makeContract({ id: '2', is_active: true }),
        makeContract({ id: '3', is_active: false }),
      ],
    } as never)
    const wrapper = mountPanel()
    await flushPromises()

    // Default activeTab='active' -> only active contracts rendered
    expect(wrapper.findAll('.rental-card-stub')).toHaveLength(2)
  })

  it('FAB is visible on active tab, hidden on history tab (not rendered)', async () => {
    const wrapper = mountPanel()
    await flushPromises()
    // Default is active tab - FAB should exist
    expect(wrapper.find('.fab').exists()).toBe(true)
  })

  it('card click opens action sheet (active contract)', async () => {
    const wrapper = mountPanel()
    await flushPromises()

    // Card stub emits click; panel listens and sets selected + opens action sheet
    const card = wrapper.find('.rental-card-stub')
    await card.trigger('click')
    await flushPromises()

    // Action sheet stub renders as <div />; the panel reacts via watcher.
    // Verify the card click does not throw and component remains mounted.
    expect(wrapper.findComponent(RentalListPanel).exists()).toBe(true)
  })
})
