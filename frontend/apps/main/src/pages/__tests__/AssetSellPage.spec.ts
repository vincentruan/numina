import { mount, flushPromises } from '@vue/test-utils'
import { describe, it, expect, vi, beforeEach } from 'vitest'

vi.mock('vue-i18n', () => ({
  useI18n: () => ({ t: (key: string) => key }),
  createI18n: () => ({ global: { t: (k: string) => k, te: () => true } }),
}))

const pushMock = vi.fn()
vi.mock('vue-router', () => ({
  useRouter: () => ({ push: pushMock }),
  useRoute: () => ({ params: { id: 'a1' }, query: {}, path: '/assets/a1/sell' }),
  createRouter: () => ({ beforeEach: () => {}, afterEach: () => {}, push: () => Promise.resolve() }),
  createWebHistory: () => ({}),
}))

vi.mock('vant', () => ({
  showToast: vi.fn(),
  showFailToast: vi.fn(),
  showConfirmDialog: vi.fn(() => Promise.resolve()),
}))

vi.mock('@/composables/useCurrency', () => ({
  useCurrency: () => ({ format: (n: number) => `¥${n}`, formatConverted: (n: number | string) => '¥' + n }),
}))
vi.mock('@/composables/usePageLoading', () => ({
  usePageLoading: () => ({ increment: vi.fn(), decrement: vi.fn() }),
}))

vi.mock('@/stores/asset', () => ({
  useAssetStore: () => ({
    currentAsset: { id: 'a1', name: '资产', current_value: '1000' },
    fetchAsset: vi.fn(() => Promise.resolve()),
    sellAsset: vi.fn(() => Promise.resolve({})),
  }),
}))
vi.mock('@/stores/dashboard', () => ({
  useDashboardStore: () => ({ fetchAll: vi.fn() }),
}))

import AssetSellPage from '../AssetSellPage.vue'

const stubs = ['PageHeader', 'van-field', 'van-button', 'van-dialog', 'van-radio-group', 'van-radio', 'MoneyDisplay']

describe('AssetSellPage (U6 redirect)', () => {
  beforeEach(() => {
    pushMock.mockReset()
  })

  it('onResultClose("confirm") redirects to /finance?tab=assets', async () => {
    const wrapper = mount(AssetSellPage, { global: { stubs } })
    await flushPromises()

    const vm = wrapper.vm as unknown as { onResultClose: (action: string) => boolean }
    const ret = vm.onResultClose('confirm')
    expect(ret).toBe(true)
    expect(pushMock).toHaveBeenCalledWith({ path: '/finance', query: { tab: 'assets' } })
  })

  it('onResultClose with a non-confirm action does NOT navigate', async () => {
    const wrapper = mount(AssetSellPage, { global: { stubs } })
    await flushPromises()

    const vm = wrapper.vm as unknown as { onResultClose: (action: string) => boolean }
    vm.onResultClose('cancel')
    expect(pushMock).not.toHaveBeenCalled()
  })
})
