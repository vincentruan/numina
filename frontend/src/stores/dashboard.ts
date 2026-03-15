import { defineStore } from 'pinia'
import { ref } from 'vue'
import type { DashboardOverview, AllocationItem, TrendPoint, DailyCostItem, InvestmentReturnItem, TopAssetItem, LowUsageItem } from '@/types'
import * as dashboardApi from '@/api/dashboard'
import type { ActivityItem } from '@/api/dashboard'

export const useDashboardStore = defineStore('dashboard', () => {
  const overview = ref<DashboardOverview | null>(null)
  const allocation = ref<AllocationItem[]>([])
  const allocationTotal = ref(0)
  const trend = ref<TrendPoint[]>([])
  const topAssets = ref<TopAssetItem[]>([])
  const dailyCostRanking = ref<DailyCostItem[]>([])
  const lowUsageAssets = ref<LowUsageItem[]>([])
  const investmentReturns = ref<InvestmentReturnItem[]>([])
  const recentActivities = ref<ActivityItem[]>([])
  const loading = ref(false)

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

  async function fetchAll() {
    loading.value = true
    try {
      await Promise.all([
        fetchOverview(),
        fetchAllocation(),
        fetchTrend(),
        fetchTopAssets(),
        fetchDailyCostRanking(),
        fetchLowUsageAssets(),
        fetchInvestmentReturns(),
        fetchRecentActivities(),
      ])
    } finally {
      loading.value = false
    }
  }

  return {
    overview, allocation, allocationTotal, trend, topAssets, dailyCostRanking,
    lowUsageAssets, investmentReturns, recentActivities, loading,
    fetchOverview, fetchAllocation, fetchTrend, fetchTopAssets,
    fetchDailyCostRanking, fetchLowUsageAssets, fetchInvestmentReturns,
    fetchRecentActivities, fetchAll
  }
})
