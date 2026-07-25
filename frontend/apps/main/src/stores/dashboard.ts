import { defineStore } from 'pinia'
import { ref } from 'vue'
import { showToast, showFailToast } from 'vant'
import i18n from '@/i18n'
import type { DashboardOverview, AllocationItem, TrendPoint, DailyCostItem, InvestmentReturnItem, TopAssetItem, LowUsageItem, StatesSummaryResponse, Asset, NewAssetsResponse, EducationRewardSummary } from '@/types'
import * as dashboardApi from '@/api/dashboard'
import type { ActivityItem, ExpiringSoonItem } from '@/api/dashboard'

// Module-level dedup lock — plain variable, not a ref (Pinia warns on non-serializable state)
let _fetchPromise: Promise<void> | null = null

// Constants for pagination cache management
const KEEP_PAGES_BEFORE = 1  // 前一页
const KEEP_PAGES_AFTER = 2   // 后两页
const DEFAULT_PAGE_SIZE = 20

export const useDashboardStore = defineStore('dashboard', () => {
  const overview = ref<DashboardOverview | null>(null)
  const allocation = ref<AllocationItem[]>([])
  const allocationTotal = ref(0)
  const trend = ref<TrendPoint[]>([])
  const topAssets = ref<TopAssetItem[]>([])
  const dailyCostRanking = ref<DailyCostItem[]>([])
  const lowUsageAssets = ref<LowUsageItem[]>([])
  const expiringSoonAssets = ref<ExpiringSoonItem[]>([])
  const investmentReturns = ref<InvestmentReturnItem[]>([])
  const recentActivities = ref<ActivityItem[]>([])
  const statesSummary = ref<StatesSummaryResponse | null>(null)
  const newAssets = ref<NewAssetsResponse | null>(null)
  const educationRewardSummary = ref<EducationRewardSummary | null>(null)
  const homeAssets = ref<Record<string, Asset[]>>({})
  const loading = ref(false)

  // Pagination state for asset list
  const displayedAssets = ref<Asset[]>([])
  const assetPage = ref(1)
  const assetPageSize = DEFAULT_PAGE_SIZE
  const assetListFinished = ref(false)
  const assetListLoading = ref(false)

  // Pagination cache: status -> page -> assets
  const assetPagesCache = ref<Map<string, Map<number, Asset[]>>>(new Map())
  // Pagination info: status -> { total, has_next, current }
  const assetPageInfo = ref<Map<string, { total: number; total_pages: number; has_next: boolean; current: number }>>(new Map())
  // Current active status filter
  const activeAssetStatus = ref<string>('in_use')
  // Current active category filter (null = all categories)
  const activeAssetCategoryId = ref<string | null>(null)
  // Feature-parity filters (ported from AssetListPage): search/sort/asset_type
  const assetSearch = ref<string>('')
  const assetSortBy = ref<string>('current_value')
  const assetSortOrder = ref<'asc' | 'desc'>('desc')
  const activeAssetType = ref<'physical' | 'financial' | null>(null)
  // Category counts for nav (full counts from backend, not page-limited)
  const categoryCounts = ref<Array<{ id: string; name: string; icon: string; color: string; asset_type: 'physical' | 'financial'; count: number }>>([])

  async function fetchCategoryCounts(status: string) {
    try {
      const res = await dashboardApi.getHomeAssetsCategoryCounts(status)
      categoryCounts.value = res.data
    } catch {
      // non-critical
    }
  }

  async function fetchOverview() {
    const res = await dashboardApi.getOverview()
    overview.value = res.data
  }

  async function fetchAllocation() {
    const res = await dashboardApi.getAllocation()
    allocation.value = res.data.items
    allocationTotal.value = res.data.total
  }

  async function fetchTrend(period: 'month' | 'quarter' | 'year' = 'month') {
    const res = await dashboardApi.getTrend(period)
    trend.value = res.data.points
  }

  async function fetchTopAssets() {
    const res = await dashboardApi.getTopAssets()
    topAssets.value = res.data
  }

  async function fetchDailyCostRanking() {
    const res = await dashboardApi.getDailyCostRanking()
    dailyCostRanking.value = res.data
  }

  async function fetchLowUsageAssets() {
    const res = await dashboardApi.getLowUsageAssets()
    lowUsageAssets.value = res.data
  }

  async function fetchExpiringSoonAssets(daysThreshold = 90) {
    const res = await dashboardApi.getExpiringSoon(daysThreshold)
    expiringSoonAssets.value = res.data
  }

  async function fetchInvestmentReturns() {
    const res = await dashboardApi.getInvestmentReturns()
    investmentReturns.value = res.data
  }

  async function fetchEducationRewardSummary() {
    try {
      const res = await dashboardApi.getEducationRewardSummary()
      educationRewardSummary.value = res.data
    } catch {
      // non-critical
    }
  }

  async function fetchRecentActivities() {
    try {
      const res = await dashboardApi.getRecentActivities()
      recentActivities.value = res.data
    } catch {
      // non-critical
    }
  }

  async function fetchStatesSummary() {
    const res = await dashboardApi.getStatesSummary()
    statesSummary.value = res.data
  }

  async function fetchNewAssets(period: 'month' | 'quarter' | 'year' = 'month') {
    const res = await dashboardApi.getNewAssets(period)
    newAssets.value = res.data
  }

  async function fetchHomeAssets(limit = 5) {
    const res = await dashboardApi.getHomeAssets(limit)
    homeAssets.value = res.data
  }

  async function fetchAll(): Promise<void> {
    // Dedup: if a request is already in-flight, return the same Promise
    if (_fetchPromise !== null) {
      return _fetchPromise
    }

    loading.value = true
    _fetchPromise = (async () => {
      try {
        // Phase 1: critical data — blocks loading indicator
        await Promise.all([fetchOverview(), fetchStatesSummary()])
      } finally {
        loading.value = false
        _fetchPromise = null
      }

      // Phase 2: secondary data — fires in background, does not block
      Promise.all([
        fetchAllocation(),
        fetchTrend(),
        fetchLowUsageAssets(),
        fetchExpiringSoonAssets(),
        fetchHomeAssets(),
        fetchEducationRewardSummary(),
      ]).catch(() => {
        // Phase 2 failures are non-critical; individual fetch functions
        // do not throw by default, so this is a safety net only
      })
    })()

    return _fetchPromise
  }

  /**
   * Fetch a specific page of assets for a given status
   * Implements server-side pagination with client-side cache management
   */
  async function fetchAssetsPage(status: string, page: number = 1, pageSize: number = DEFAULT_PAGE_SIZE, categoryId?: string): Promise<void> {
    if (assetListLoading.value) return

    assetListLoading.value = true
    activeAssetStatus.value = status
    if (categoryId !== undefined) {
      activeAssetCategoryId.value = categoryId || null
    }

    try {
      const res = await dashboardApi.getHomeAssetsPaginated(status, page, pageSize, activeAssetCategoryId.value, {
        search: assetSearch.value || undefined,
        sortBy: assetSortBy.value || undefined,
        sortOrder: assetSortOrder.value,
        assetType: activeAssetType.value || undefined,
      })
      const data = res.data

      // Store page data in cache
      if (!assetPagesCache.value.has(status)) {
        assetPagesCache.value.set(status, new Map())
      }
      assetPagesCache.value.get(status)!.set(page, data.items)

      // Store pagination info
      assetPageInfo.value.set(status, {
        total: data.total,
        total_pages: data.total_pages,
        has_next: data.has_next,
        current: page,
      })

      // Prune cache to keep only MAX_CACHED_PAGES
      prunePageCache(status, page)

      // Merge all cached pages into displayedAssets
      mergeDisplayedAssets(status)

      // Update pagination state
      assetPage.value = page
      assetListFinished.value = !data.has_next
    } catch (error) {
      console.error('[fetchAssetsPage] Failed to load assets:', error)
      showFailToast(i18n.global.t('toast.assetLoadFailed'))
      // Prevent infinite retry on error
      assetListFinished.value = true
    } finally {
      assetListLoading.value = false
    }
  }

  /**
   * Prune page cache to keep only: currentPage-1, currentPage, currentPage+1, currentPage+2
   * This implements the "最多缓存4页" requirement (KEEP_PAGES_BEFORE + KEEP_PAGES_AFTER + current)
   * Uses explicit Map replacement to ensure Vue reactivity triggers correctly
   */
  function prunePageCache(status: string, currentPage: number) {
    const statusPages = assetPagesCache.value.get(status)
    if (!statusPages) return

    // Keep pages: currentPage-1, currentPage, currentPage+1, currentPage+2
    const keepPages = [
      currentPage - KEEP_PAGES_BEFORE,
      currentPage,
      currentPage + 1,
      currentPage + KEEP_PAGES_AFTER,
    ].filter(p => p >= 1)

    // Create a new Map to ensure Vue reactivity updates
    // Note: If none of the keepPages have data, newPages will be empty - this is expected
    // when cache was cleared (e.g., on status switch or refresh), not an error condition
    const newPages = new Map<number, Asset[]>()
    for (const page of keepPages) {
      const data = statusPages.get(page)
      if (data) {
        newPages.set(page, data)
      }
    }

    // Replace the entire Map to trigger Vue reactivity
    assetPagesCache.value.set(status, newPages)
  }

  /**
   * Merge all cached pages into displayedAssets in order
   */
  function mergeDisplayedAssets(status: string) {
    const statusPages = assetPagesCache.value.get(status)
    if (!statusPages) {
      displayedAssets.value = []
      return
    }

    // Sort pages and merge assets
    const allAssets: Asset[] = []
    const sortedPages = Array.from(statusPages.keys()).sort((a, b) => a - b)
    for (const page of sortedPages) {
      const pageAssets = statusPages.get(page)
      if (pageAssets) {
        allAssets.push(...pageAssets)
      }
    }

    displayedAssets.value = allAssets
  }

  /**
   * Load next page of assets (triggered by van-list @load event)
   */
  async function loadNextAssetsPage(): Promise<void> {
    const status = activeAssetStatus.value
    const info = assetPageInfo.value.get(status)

    if (!info || !info.has_next || assetListLoading.value) return

    const nextPage = info.current + 1
    await fetchAssetsPage(status, nextPage, assetPageSize, activeAssetCategoryId.value || undefined)
  }

  /**
   * Reset pagination for a specific status (or all statuses)
   */
  function resetAssetPagination(status?: string) {
    if (status) {
      assetPagesCache.value.delete(status)
      assetPageInfo.value.delete(status)
      if (activeAssetStatus.value === status) {
        displayedAssets.value = []
        assetPage.value = 1
        assetListFinished.value = false
      }
    } else {
      assetPagesCache.value.clear()
      assetPageInfo.value.clear()
      displayedAssets.value = []
      assetPage.value = 1
      assetListFinished.value = false
      activeAssetStatus.value = 'in_use'
      activeAssetCategoryId.value = null
    }
  }

  /**
   * Apply feature-parity filters (search/sort/asset_type) and refetch from page 1.
   * The page cache is keyed by status only, so any filter change invalidates it —
   * reset pagination for the active status before refetching.
   */
  async function applyAssetFilters(filters: {
    search?: string
    sortBy?: string
    sortOrder?: 'asc' | 'desc'
    assetType?: 'physical' | 'financial' | null
    resetCategory?: boolean
  }): Promise<void> {
    if (filters.search !== undefined) assetSearch.value = filters.search
    if (filters.sortBy !== undefined) assetSortBy.value = filters.sortBy
    if (filters.sortOrder !== undefined) assetSortOrder.value = filters.sortOrder
    if (filters.assetType !== undefined) activeAssetType.value = filters.assetType
    if (filters.resetCategory) activeAssetCategoryId.value = null
    const status = activeAssetStatus.value
    resetAssetPagination(status)
    await fetchAssetsPage(status, 1, assetPageSize, activeAssetCategoryId.value || undefined)
  }

  /**
   * Legacy function - kept for backward compatibility
   * Now uses server-side pagination
   */
  function loadMoreAssets(_allAssets: Asset[]) {
    // This function is deprecated - use loadNextAssetsPage instead
    loadNextAssetsPage()
  }

  function invalidateDashboard() {
    overview.value = null
    allocation.value = []
    allocationTotal.value = 0
    trend.value = []
    topAssets.value = []
    dailyCostRanking.value = []
    lowUsageAssets.value = []
    expiringSoonAssets.value = []
    investmentReturns.value = []
    recentActivities.value = []
    statesSummary.value = null
    newAssets.value = null
    educationRewardSummary.value = null
    homeAssets.value = {}
    resetAssetPagination()
  }

  return {
    overview, allocation, allocationTotal, trend, topAssets, dailyCostRanking,
    lowUsageAssets, expiringSoonAssets, investmentReturns, recentActivities, statesSummary, newAssets, homeAssets, loading,
    educationRewardSummary,
    displayedAssets, assetPage, assetPageSize, assetListFinished, assetListLoading,
    assetPagesCache, assetPageInfo, activeAssetStatus, activeAssetCategoryId, categoryCounts,
    assetSearch, assetSortBy, assetSortOrder, activeAssetType,
    fetchOverview, fetchAllocation, fetchTrend, fetchTopAssets,
    fetchDailyCostRanking, fetchLowUsageAssets, fetchExpiringSoonAssets, fetchInvestmentReturns,
    fetchRecentActivities, fetchStatesSummary, fetchNewAssets, fetchHomeAssets, fetchAll,
    fetchEducationRewardSummary,
    fetchAssetsPage, loadNextAssetsPage, resetAssetPagination, loadMoreAssets, applyAssetFilters,
    fetchCategoryCounts, invalidateDashboard,
  }
})
