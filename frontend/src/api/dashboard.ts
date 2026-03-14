import http from './index'
import type { DashboardOverview, AllocationItem, TrendPoint, DailyCostItem, InvestmentReturnItem, Asset } from '@/types'

export function getOverview() {
  return http.get<DashboardOverview>('/dashboard/overview')
}

export function getAllocation() {
  return http.get<AllocationItem[]>('/dashboard/allocation')
}

export function getTrend(period: 'month' | 'quarter' | 'year' = 'month') {
  return http.get<TrendPoint[]>('/dashboard/trend', { params: { period } })
}

export function getTopAssets(limit = 5) {
  return http.get<Asset[]>('/dashboard/top-assets', { params: { limit } })
}

export function getDailyCostRanking(limit = 10) {
  return http.get<DailyCostItem[]>('/dashboard/daily-cost-ranking', { params: { limit } })
}

export function getLowUsageAssets() {
  return http.get<Asset[]>('/dashboard/low-usage')
}

export function getInvestmentReturns(limit = 10) {
  return http.get<InvestmentReturnItem[]>('/dashboard/investment-returns', { params: { limit } })
}
