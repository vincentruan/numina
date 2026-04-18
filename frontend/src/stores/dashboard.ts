import { defineStore } from 'pinia'
import { ref } from 'vue'
import type { DashboardOverview, AllocationItem, TrendPoint, DailyCostItem, InvestmentReturnItem, TopAssetItem, LowUsageItem, StatesSummaryResponse, Asset } from '@/types'
import * as dashboardApi from '@/api/dashboard'
import type { ActivityItem, ExpiringSoonItem } from '@/api/dashboard'

// Module-level dedup lock — plain variable, not a ref (Pinia warns on non-serializable state)
let _fetchPromise: Promise<void> | null = null
const DASHBOARD_TTL_MS = 2 * 60 * 1000

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
  const homeAssets = ref<Record<string, Asset[]>>({})
  const loading = ref(false)
  const lastFetchedAt = ref<number | null>(null)
  // True when the last fetchAll() call was served from the staleness cache (no network request)
  const servedFromCache = ref(false)

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

  async function fetchHomeAssets(limit = 5) {
    const res = await dashboardApi.getHomeAssets(limit)
    homeAssets.value = res.data
  }

  async function fetchAll(force = false): Promise<void> {
    // 1. Dedup: if a request is already in-flight, return the same Promise
    if (_fetchPromise !== null) {
      return _fetchPromise
    }
    // 2. Staleness guard: skip if data is fresh and caller didn't force
    if (!force && lastFetchedAt.value !== null && Date.now() - lastFetchedAt.value < DASHBOARD_TTL_MS) {
      servedFromCache.value = true
      return Promise.resolve()
    }
    // 3. Issue new request
    servedFromCache.value = false
    loading.value = true
    _fetchPromise = (async () => {
      try {
        const res = await dashboardApi.getDashboardBundle()
        const data = res.data
        overview.value = data.overview
        statesSummary.value = data.statesSummary
        homeAssets.value = data.homeAssets
        allocation.value = data.allocation.items
        allocationTotal.value = data.allocation.total
        trend.value = data.trend.points
        lowUsageAssets.value = data.lowUsageAssets
        expiringSoonAssets.value = data.expiringSoon
        lastFetchedAt.value = Date.now()
      } finally {
        loading.value = false
        _fetchPromise = null
      }
    })()
    return _fetchPromise
  }

  function invalidateDashboard() {
    lastFetchedAt.value = null
    servedFromCache.value = false
  }

  return {
    overview, allocation, allocationTotal, trend, topAssets, dailyCostRanking,
    lowUsageAssets, expiringSoonAssets, investmentReturns, recentActivities, statesSummary, homeAssets, loading,
    lastFetchedAt, servedFromCache, invalidateDashboard,
    fetchOverview, fetchAllocation, fetchTrend, fetchTopAssets,
    fetchDailyCostRanking, fetchLowUsageAssets, fetchExpiringSoonAssets, fetchInvestmentReturns,
    fetchRecentActivities, fetchStatesSummary, fetchHomeAssets, fetchAll,
  }
})
