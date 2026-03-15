import http from './index'
import type { DashboardOverview, AllocationResponse, TrendResponse, DailyCostItem, InvestmentReturnItem, TopAssetItem, LowUsageItem } from '@/types'

export function getOverview() {
  return http.get<DashboardOverview>('/dashboard/overview')
}

export function getAllocation() {
  return http.get<AllocationResponse>('/dashboard/allocation')
}

export function getTrend(period: 'month' | 'quarter' | 'year' = 'month') {
  return http.get<TrendResponse>('/dashboard/trend', { params: { period } })
}

export function getTopAssets(limit = 5) {
  return http.get<TopAssetItem[]>('/dashboard/top-assets', { params: { limit } })
}

export function getDailyCostRanking(limit = 10) {
  return http.get<DailyCostItem[]>('/dashboard/daily-cost-ranking', { params: { limit } })
}

export function getLowUsageAssets() {
  return http.get<LowUsageItem[]>('/dashboard/low-usage-assets')
}

export function getInvestmentReturns(limit = 10) {
  return http.get<InvestmentReturnItem[]>('/dashboard/investment-returns', { params: { limit } })
}

export function getRecentActivities(limit = 20) {
  return http.get<ActivityItem[]>('/activities/recent', { params: { limit } })
}

export interface ActivityItem {
  id: string
  type: string
  entity_type: string
  entity_id: string
  title: string
  amount: number | null
  created_at: string
}
