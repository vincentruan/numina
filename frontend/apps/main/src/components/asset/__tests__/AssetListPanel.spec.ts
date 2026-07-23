import { mount, flushPromises } from '@vue/test-utils'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { ref } from 'vue'
import AssetListPanel from '../AssetListPanel.vue'

// Mock vue-i18n: component uses useI18n for all labels.
vi.mock('vue-i18n', () => ({
  useI18n: () => ({ t: (key: string) => key }),
  createI18n: () => ({ global: { t: (k: string) => k, te: () => true } }),
}))

// Mock vue-router: component uses useRouter for FAB / asset-detail navigation.
const pushMock = vi.fn()
vi.mock('vue-router', () => ({
  useRouter: () => ({ push: pushMock }),
  createRouter: () => ({ beforeEach: () => {}, afterEach: () => {}, push: () => Promise.resolve() }),
  createWebHistory: () => ({}),
}))

// Mock vant imperatives so they don't touch the DOM.
vi.mock('vant', () => ({
  showToast: vi.fn(),
  showFailToast: vi.fn(),
  showConfirmDialog: vi.fn(() => Promise.resolve()),
}))

// Mock the batch APIs the panel imports directly.
vi.mock('@/api/assets', () => ({
  batchArchiveAssets: vi.fn(),
  batchUpdateStatus: vi.fn(),
  batchExportAssets: vi.fn(),
}))
vi.mock('@/api/auth', () => ({
  updateSettings: vi.fn(),
}))

// Mock the dashboard store. The panel reads filter state + pagination and calls
// applyAssetFilters / fetchAssetsPage / resetAssetPagination / fetchCategoryCounts.
const applyAssetFiltersMock = vi.fn()
const fetchAssetsPageMock = vi.fn()
const resetAssetPaginationMock = vi.fn()
const fetchCategoryCountsMock = vi.fn()
const loadNextAssetsPageMock = vi.fn()
const fetchAllMock = vi.fn()

const displayedAssets = ref<Array<Record<string, unknown>>>([])
const assetListFinished = ref(true)
const assetListLoading = ref(false)
const statesSummary = ref<Record<string, unknown> | null>(null)
const categoryCounts = ref<Array<Record<string, unknown>>>([])
const assetPageInfo = ref(new Map())

vi.mock('@/stores/dashboard', () => ({
  useDashboardStore: () => ({
    get statesSummary() { return statesSummary.value },
    get displayedAssets() { return displayedAssets.value },
    get assetListFinished() { return assetListFinished.value },
    get assetListLoading() { return assetListLoading.value },
    get categoryCounts() { return categoryCounts.value },
    get assetPageInfo() { return assetPageInfo.value },
    applyAssetFilters: applyAssetFiltersMock,
    fetchAssetsPage: fetchAssetsPageMock,
    resetAssetPagination: resetAssetPaginationMock,
    fetchCategoryCounts: fetchCategoryCountsMock,
    loadNextAssetsPage: loadNextAssetsPageMock,
    fetchAll: fetchAllMock,
  }),
}))

// Mock the auth store: viewMode drives card/list rendering.
const viewMode = ref<'card' | 'list'>('card')
vi.mock('@/stores/auth', () => ({
  useAuthStore: () => ({
    get user() { return { view_mode: viewMode.value, role: 'owner' } },
    fetchMe: vi.fn(),
  }),
}))

// Mock usePageLoading (selection-mode batch ops call increment/decrement).
vi.mock('@/composables/usePageLoading', () => ({
  usePageLoading: () => ({ increment: vi.fn(), decrement: vi.fn() }),
}))

const sampleAsset = (id: string, name: string) => ({
  id,
  name,
  asset_type: 'physical',
  current_value: '100.00',
  status: 'in_use',
})

function mountPanel() {
  return mount(AssetListPanel, {
    global: {
      stubs: {
        // Stub heavy children; we only assert on panel wiring.
        StatusSummaryGrid: {
          template: '<div class="status-summary-grid"><slot name="toolbar" /></div>',
          props: ['summary', 'activeStatus'],
        },
        AssetCard: { template: '<div class="asset-card" />', props: ['asset', 'selectable', 'selected'] },
        AssetListItem: { template: '<div class="asset-list-item" />', props: ['asset', 'selectable', 'selected'] },
        SvgIcon: { template: '<span class="svg-icon" />', props: ['name'] },
        'van-icon': true,
        'van-tabs': { template: '<div class="van-tabs"><slot /></div>', props: ['active'] },
        'van-tab': { template: '<div class="van-tab" />', props: ['title', 'name'] },
        'van-search': {
          template: '<input class="van-search" />',
          props: ['modelValue'],
        },
        'van-dropdown-menu': { template: '<div class="van-dropdown-menu"><slot /></div>' },
        'van-dropdown-item': { template: '<div class="van-dropdown-item" />', props: ['modelValue', 'options'] },
        'van-list': { template: '<div class="van-list"><slot /></div>', props: ['loading', 'finished'] },
        'van-empty': { template: '<div class="van-empty" />', props: ['description'] },
        'van-checkbox': { template: '<div class="van-checkbox"><slot /></div>', props: ['modelValue'] },
        'van-button': { template: '<button class="van-button"><slot /></button>' },
        'van-action-sheet': { template: '<div class="van-action-sheet" />', props: ['show', 'actions'] },
      },
    },
  })
}

describe('AssetListPanel', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    displayedAssets.value = []
    assetListFinished.value = true
    assetListLoading.value = false
    statesSummary.value = null
    categoryCounts.value = []
    assetPageInfo.value = new Map()
    viewMode.value = 'card'
  })

  it('renders asset cards from displayedAssets (card view)', () => {
    displayedAssets.value = [sampleAsset('1', '房产'), sampleAsset('2', '基金')]
    const wrapper = mountPanel()
    expect(wrapper.findAll('.asset-card')).toHaveLength(2)
  })

  it('renders list items instead of cards when viewMode is list', () => {
    viewMode.value = 'list'
    displayedAssets.value = [sampleAsset('1', '房产')]
    const wrapper = mountPanel()
    expect(wrapper.findAll('.asset-list-item')).toHaveLength(1)
    expect(wrapper.findAll('.asset-card')).toHaveLength(0)
  })

  it('gates the empty state on assetListLoading (no flash during pagination)', () => {
    displayedAssets.value = []
    assetListLoading.value = true
    const loadingWrapper = mountPanel()
    expect(loadingWrapper.find('.van-empty').exists()).toBe(false)

    assetListLoading.value = false
    const idleWrapper = mountPanel()
    expect(idleWrapper.find('.van-empty').exists()).toBe(true)
  })

  it('applies search + sort via applyAssetFilters on search', async () => {
    const wrapper = mountPanel()
    const vm = wrapper.vm as unknown as { onSearch: () => void; searchText: string; sortBy: string }
    vm.searchText = '基金'
    vm.sortBy = 'purchase_date'
    vm.onSearch()
    await flushPromises()
    expect(applyAssetFiltersMock).toHaveBeenCalledWith({ search: '基金', sortBy: 'purchase_date' })
  })

  it('maps type tab to asset_type filter (physical)', async () => {
    const wrapper = mountPanel()
    const vm = wrapper.vm as unknown as { onTypeTabChange: (n: string | number) => void }
    vm.onTypeTabChange('physical')
    await flushPromises()
    expect(applyAssetFiltersMock).toHaveBeenCalledWith({ assetType: 'physical' })
  })

  it('maps "all" type tab to null asset_type', async () => {
    const wrapper = mountPanel()
    const vm = wrapper.vm as unknown as { onTypeTabChange: (n: string | number) => void }
    vm.onTypeTabChange('all')
    await flushPromises()
    expect(applyAssetFiltersMock).toHaveBeenCalledWith({ assetType: null })
  })

  it('resets pagination and refetches page 1 on status select', async () => {
    const wrapper = mountPanel()
    const vm = wrapper.vm as unknown as { onStatusSelect: (s: string | null) => void }
    vm.onStatusSelect('idle')
    await flushPromises()
    expect(resetAssetPaginationMock).toHaveBeenCalledWith('idle')
    expect(fetchAssetsPageMock).toHaveBeenCalledWith('idle', 1, 20, '')
    expect(fetchCategoryCountsMock).toHaveBeenCalledWith('idle')
  })

  it('resets pagination and refetches with category id on category change', async () => {
    categoryCounts.value = [{ id: 'cat-1', name: '电子产品', icon: '', color: '', count: 3 }]
    const wrapper = mountPanel()
    const vm = wrapper.vm as unknown as { onCategoryChange: (i: number) => void }
    vm.onCategoryChange(1) // first real category (index 0 = 全部)
    await flushPromises()
    expect(resetAssetPaginationMock).toHaveBeenCalledWith('in_use')
    expect(fetchAssetsPageMock).toHaveBeenCalledWith('in_use', 1, 20, 'cat-1')
  })

  it('loads next page via loadNextAssetsPage when not finished', async () => {
    assetListFinished.value = false
    const wrapper = mountPanel()
    const vm = wrapper.vm as unknown as { onLoadMore: () => Promise<void> }
    await vm.onLoadMore()
    expect(loadNextAssetsPageMock).toHaveBeenCalled()
  })

  it('does not load more when already finished', async () => {
    assetListFinished.value = true
    const wrapper = mountPanel()
    const vm = wrapper.vm as unknown as { onLoadMore: () => Promise<void> }
    await vm.onLoadMore()
    expect(loadNextAssetsPageMock).not.toHaveBeenCalled()
  })

  it('enters selection mode and toggles selection', async () => {
    displayedAssets.value = [sampleAsset('1', '房产'), sampleAsset('2', '基金')]
    const wrapper = mountPanel()
    const vm = wrapper.vm as unknown as {
      enterSelectionMode: () => void
      toggleSelection: (id: string) => void
      selectionMode: boolean
      selectedIds: string[]
    }
    vm.enterSelectionMode()
    expect(vm.selectionMode).toBe(true)
    vm.toggleSelection('1')
    expect(vm.selectedIds).toContain('1')
    vm.toggleSelection('1')
    expect(vm.selectedIds).not.toContain('1')
  })
})
