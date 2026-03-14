import { defineStore } from 'pinia'
import { ref } from 'vue'
import type { DashboardOverview, AllocationItem, TrendPoint, DailyCostItem, InvestmentReturnItem, Asset } from '@/types'
import * as dashboardApi from '@/api/dashboard'

export const useDashboardStore = defineStore('dashboard', () => {
  const overview = ref<DashboardOverview | null>(null)
  const allocation = ref<AllocationItem[]>([])
  const trend = ref<TrendPoint[]>([])
  const topAssets = ref<Asset[]>([])
  const dailyCostRanking = ref<DailyCostItem[]>([])
  const lowUsageAssets = ref<Asset[]>([])
  const investmentReturns = ref<InvestmentReturnItem[]>([])
  const loading = ref(false)

  async function fetchOverview() {
    const res = await dashboardApi.getOverview()
    overview.value = res.data
  }

  async function fetchAllocation() {
    const res = await dashboardApi.getAllocation()
    allocation.value = res.data
  }

  async function fetchTrend(period: 'month' | 'quarter' | 'year' = 'month') {
    const res = await dashboardApi.getTrend(period)
    trend.value = res.data
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
        fetchInvestmentReturns()
      ])
    } finally {
      loading.value = false
    }
  }

  return {
    overview, allocation, trend, topAssets, dailyCostRanking,
    lowUsageAssets, investmentReturns, loading,
    fetchOverview, fetchAllocation, fetchTrend, fetchTopAssets,
    fetchDailyCostRanking, fetchLowUsageAssets, fetchInvestmentReturns, fetchAll
  }
})
