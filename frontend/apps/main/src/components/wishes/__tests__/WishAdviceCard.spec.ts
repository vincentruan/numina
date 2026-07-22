import { mount, flushPromises } from '@vue/test-utils'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import WishAdviceCard from '../WishAdviceCard.vue'

vi.mock('vue-i18n', () => ({
  useI18n: () => ({
    t: (key: string, params?: Record<string, unknown>) => {
      if (params && typeof params === 'object' && 'name' in params) {
        return `${key}:${String(params.name)}:${String(params.amount ?? '')}`
      }
      if (params && typeof params === 'object' && 'total' in params) {
        return `${key}:${String(params.total)}`
      }
      if (params && typeof params === 'object' && 'ok' in params) {
        return `${key}:${String(params.ok)}/${String(params.total)}`
      }
      return key
    },
  }),
  // @/api/index → @/i18n calls createI18n at module load; stub it.
  createI18n: () => ({ global: { t: (k: string) => k, te: () => true } }),
}))

const pushMock = vi.fn()
vi.mock('vue-router', () => ({
  useRouter: () => ({ push: pushMock }),
  // @/api/index → @/router calls createRouter/createWebHistory at module load.
  createRouter: () => ({ beforeEach: () => {}, afterEach: () => {}, push: () => Promise.resolve() }),
  createWebHistory: () => ({}),
}))

vi.mock('vant', () => ({
  showSuccessToast: vi.fn(),
  showFailToast: vi.fn(),
  showDialog: vi.fn(() => Promise.resolve()),
}))

const fetchWishesMock = vi.fn(() => Promise.resolve())
vi.mock('@/stores/wish', () => ({
  useWishStore: () => ({ fetchWishes: fetchWishesMock }),
}))

// useCurrency → useAuthStore needs an active Pinia; stub to a plain formatter
// so the component's confirmation-dialog strings work without a Pinia plugin.
vi.mock('@/composables/useCurrency', () => ({
  useCurrency: () => ({
    format: (n: number) => `¥${n}`,
  }),
}))

import * as wishApi from '@/api/wishes'
import type { AxiosResponse } from 'axios'
import type { WishAdvice } from '@/types'

const mockAdvice: WishAdvice = {
  primary_wish_id: '1',
  reason: '距目标近',
  suggested_monthly: '2000',
  redistribution: [
    { wish_id: '1', suggested_amount: '2000', note: '本月优先' },
  ],
}

type AdviceResp = AxiosResponse<{ status: string; generated_at?: string; report: WishAdvice | null }>

function adviceResp(status: string, report: WishAdvice | null): AdviceResp {
  return { data: { status, report } } as AdviceResp
}

const sampleWishes = [
  { id: '1', name: '心愿A', monthly_saving: '500' },
  { id: '2', name: '心愿B', monthly_saving: '300' },
]

function mountCard(wishes = sampleWishes) {
  return mount(WishAdviceCard, {
    props: { wishes },
    global: { stubs: ['van-button', 'van-icon'] },
  })
}

describe('WishAdviceCard', () => {
  beforeEach(() => {
    vi.restoreAllMocks()
    pushMock.mockReset()
    fetchWishesMock.mockReset()
    localStorage.clear()
  })

  it('renders when valid advice is returned', async () => {
    vi.spyOn(wishApi, 'getWishAdvice').mockResolvedValue(adviceResp('cached', mockAdvice))
    const wrapper = mountCard()
    await flushPromises()
    expect(wrapper.find('[data-test="wish-advice-card"]').exists()).toBe(true)
  })

  it('hides when advice is empty', async () => {
    vi.spyOn(wishApi, 'getWishAdvice').mockResolvedValue(adviceResp('empty', null))
    const wrapper = mountCard()
    await flushPromises()
    expect(wrapper.find('[data-test="wish-advice-card"]').exists()).toBe(false)
  })

  it('hides after close (8h localStorage suppression)', async () => {
    vi.spyOn(wishApi, 'getWishAdvice').mockResolvedValue(adviceResp('cached', mockAdvice))
    const wrapper = mountCard()
    await flushPromises()
    expect(wrapper.find('[data-test="wish-advice-card"]').exists()).toBe(true)
    await wrapper.find('[data-test="wa-close"]').trigger('click')
    expect(wrapper.find('[data-test="wish-advice-card"]').exists()).toBe(false)
    // Re-mount: suppressed.
    const wrapper2 = mountCard()
    await flushPromises()
    expect(wrapper2.find('[data-test="wish-advice-card"]').exists()).toBe(false)
  })

  it('adopts by calling adoptWishAdvice (batch PATCH) per redistribution item', async () => {
    const adoptSpy = vi
      .spyOn(wishApi, 'adoptWishAdvice')
      .mockResolvedValue([{ status: 'fulfilled', value: {} }])
    vi.spyOn(wishApi, 'getWishAdvice').mockResolvedValue(adviceResp('cached', mockAdvice))
    const wrapper = mountCard()
    await flushPromises()
    await wrapper.find('[data-test="wa-adopt"]').trigger('click')
    await flushPromises()
    expect(adoptSpy).toHaveBeenCalledTimes(1)
    expect(adoptSpy).toHaveBeenCalledWith(mockAdvice.redistribution)
    expect(fetchWishesMock).toHaveBeenCalled()
  })
})
