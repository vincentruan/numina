import { beforeEach, describe, expect, it, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { nextTick } from 'vue'

import AssetListPanel from '../../src/components/asset/AssetListPanel.vue'
import { useDashboardStore } from '../../src/stores/dashboard'

// Shape of the mocked dashboard store used by these tests. Loosely typed on
// purpose — the panel only touches a subset of the real store.
type DashboardStoreMock = ReturnType<typeof defaultStore>

vi.mock('vue-router', () => ({
  useRouter: () => ({ push: vi.fn() }),
  createRouter: vi.fn(() => ({
    push: vi.fn(),
    replace: vi.fn(),
    go: vi.fn(),
    back: vi.fn(),
    forward: vi.fn(),
    beforeEach: vi.fn(),
    afterEach: vi.fn(),
    currentRoute: { value: { path: '/', params: {}, query: {} } },
  })),
  createWebHistory: vi.fn(),
}))

vi.mock('vue-i18n', () => ({
  useI18n: () => ({ t: (key: string) => key }),
  createI18n: vi.fn(() => ({
    global: { t: (key: string) => key },
  })),
}))

vi.mock('../../src/api/assets', () => ({
  batchArchiveAssets: vi.fn(),
  batchUpdateStatus: vi.fn(),
  batchExportAssets: vi.fn(),
}))

vi.mock('../../src/api/auth', () => ({
  updateSettings: vi.fn(),
}))

const defaultStore = () => ({
  loading: false,
  overview: {
    asset_count: 10,
    net_worth: 100000,
    total_assets: 150000,
    total_liabilities: 50000,
    total_daily_cost: 50,
    month_over_month_change: 5.2,
  },
  statesSummary: {
    total_count: 10,
    states: {
      in_use: { count: 6 },
      idle: { count: 2 },
      sold: { count: 1 },
      retired: { count: 1 },
    },
  },
  categoryCounts: [
    { id: 'cat1', name: 'Electronics', icon: '📱', count: 4 },
    { id: 'cat2', name: 'Furniture', icon: '🪑', count: 3 },
  ],
  displayedAssets: [],
  allocation: [],
  trend: [],
  assetListFinished: false,
  assetListLoading: false,
  assetPageInfo: new Map(),
  fetchAll: vi.fn(() => Promise.resolve()),
  fetchAssetsPage: vi.fn(() => Promise.resolve()),
  fetchAllAssetsPage: vi.fn(() => Promise.resolve()),
  fetchCategoryCounts: vi.fn(() => Promise.resolve()),
  fetchTrend: vi.fn(() => Promise.resolve()),
  loadNextAssetsPage: vi.fn(() => Promise.resolve()),
  resetAssetPagination: vi.fn(),
  applyAssetFilters: vi.fn(() => Promise.resolve()),
  lowUsageAssets: [],
  expiringSoonAssets: [],
})

vi.mock('../../src/stores/dashboard', () => ({
  useDashboardStore: vi.fn(() => defaultStore()),
}))

vi.mock('../../src/stores/auth', () => ({
  useAuthStore: vi.fn(() => ({
    user: { role: 'member', view_mode: 'card' },
  })),
}))

const stubs = {
  StatusSummaryGrid: {
    name: 'StatusSummaryGrid',
    props: ['summary', 'activeStatus'],
    emits: ['select'],
    template: '<div class="status-grid-mock"><slot name="toolbar"></slot></div>',
  },
  VanCollapse: { template: '<div><slot></slot></div>' },
  VanCollapseItem: { template: '<div><slot></slot></div>' },
  VanCellGroup: { template: '<div><slot></slot></div>' },
  VanTabs: { props: ['active'], template: '<div class="tabs-mock"><slot></slot></div>' },
  VanTab: { props: ['title'], template: '<div></div>' },
  VanList: { template: '<div><slot></slot></div>' },
  VanEmpty: { props: ['description', 'imageSize'], template: '<div></div>' },
  VanPullRefresh: { template: '<div><slot></slot></div>' },
  VanCheckbox: { template: '<div></div>' },
  VanButton: { template: '<button></button>' },
  VanIcon: { props: ['name', 'size'], template: '<i></i>' },
  VanActionSheet: { template: '<div></div>' },
  VanSearch: { props: ['modelValue'], template: '<input />' },
  VanDropdownMenu: { template: '<div><slot></slot></div>' },
  VanDropdownItem: { props: ['modelValue', 'options'], template: '<div></div>' },
  AssetCard: { template: '<div></div>' },
  AssetListItem: { template: '<div></div>' },
  SvgIcon: { props: ['name'], template: '<span></span>' },
}

describe('AssetListPanel filter bar behavior', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.mocked(useDashboardStore).mockImplementation(
      () => defaultStore() as unknown as ReturnType<typeof useDashboardStore>,
    )
  })

  describe('filter bar sticky positioning', () => {
    it('renders filter bar container with sticky CSS class', async () => {
      const wrapper = mount(AssetListPanel, { global: { stubs } })
      await nextTick()

      const filterBar = wrapper.find('.filter-bar-sticky')
      expect(filterBar.exists()).toBe(true)
    })

    it('filter bar contains StatusSummaryGrid and category nav container', async () => {
      const wrapper = mount(AssetListPanel, { global: { stubs } })
      await nextTick()

      const filterBar = wrapper.find('.filter-bar-sticky')
      expect(filterBar.find('.status-grid-mock').exists()).toBe(true)
      expect(filterBar.find('.category-nav-container').exists()).toBe(true)
    })

    it('category nav is NOT rendered when no categories exist', async () => {
      vi.mocked(useDashboardStore).mockReturnValueOnce({
        ...defaultStore(),
        categoryCounts: [],
      } as unknown as ReturnType<typeof useDashboardStore>)

      const wrapper = mount(AssetListPanel, { global: { stubs } })
      await nextTick()

      expect(wrapper.find('.category-nav-container').exists()).toBe(false)
    })
  })

  describe('filter interactions', () => {
    it('status select triggers fetchAssetsPage and fetchCategoryCounts', async () => {
      const store: DashboardStoreMock = defaultStore()
      vi.mocked(useDashboardStore).mockReturnValueOnce(
        store as unknown as ReturnType<typeof useDashboardStore>,
      )

      const wrapper = mount(AssetListPanel, { global: { stubs } })
      await nextTick()

      // Emit select event from StatusSummaryGrid stub
      await wrapper.findComponent({ name: 'StatusSummaryGrid' }).vm.$emit('select', 'idle')
      await nextTick()

      expect(store.fetchAssetsPage).toHaveBeenCalledWith('idle', 1, 20, '')
      expect(store.fetchCategoryCounts).toHaveBeenCalledWith('idle')
    })
  })
})
