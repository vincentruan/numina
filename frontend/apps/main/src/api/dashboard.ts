import http from './index'
import type { DashboardOverview, AllocationResponse, TrendResponse, DailyCostItem, InvestmentReturnItem, TopAssetItem, LowUsageItem, StatesSummaryResponse, Asset, HomeAssetsPageResponse, NewAssetsResponse } from '@/types'

export interface ExpiringSoonItem {
  id: string
  name: string
  category_name: string
  icon: string
  asset_type: 'physical' | 'financial'
  purchase_date: string | null
  expected_lifespan_days: number | null
  remaining_days: number | null
  current_value: number
  currency: string
  original_value: number
}

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

export function getExpiringSoon(daysThreshold = 90) {
  return http.get<ExpiringSoonItem[]>('/dashboard/expiring-soon', { params: { days_threshold: daysThreshold } })
}

export function getInvestmentReturns(limit = 10) {
  return http.get<InvestmentReturnItem[]>('/dashboard/investment-returns', { params: { limit } })
}

export function getRecentActivities(limit = 20) {
  return http.get<ActivityItem[]>('/activities/recent', { params: { limit } })
}

export function getStatesSummary() {
  return http.get<StatesSummaryResponse>('/dashboard/states-summary')
}

export function getHomeAssets(limit = 5) {
  return http.get<Record<string, Asset[]>>('/dashboard/home-assets', { params: { limit } })
}

export function getHomeAssetsCategoryCounts(status: string) {
  return http.get<Array<{ id: string; name: string; icon: string; color: string; count: number }>>(
    `/dashboard/home-assets/${status}/categories`
  )
}

export function getHomeAssetsPaginated(
  status: string,
  page: number = 1,
  pageSize: number = 20,
  categoryId?: string | null
) {
  return http.get<HomeAssetsPageResponse>(`/dashboard/home-assets/${status}`, {
    params: { page, page_size: pageSize, ...(categoryId ? { category_id: categoryId } : {}) }
  })
}

export function getNewAssets(period: 'month' | 'quarter' | 'year' = 'month') {
  return http.get<NewAssetsResponse>('/dashboard/new-assets', { params: { period } })
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
