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

// ═══════════════════════════════════════
// Insights Types
// ═══════════════════════════════════════

export interface SmartDiscoveryResponse {
  purchase_yoy: number | null
  highest_daily_cost: { name: string; cost: number; icon: string } | null
  lowest_daily_cost: { name: string; cost: number; icon: string } | null
  longest_held: { name: string; days: number; icon: string } | null
  top_category: { name: string; percentage: number; icon: string; color: string } | null
}

export interface GoalProgressItem {
  id: string
  name: string
  category_color: string
  status: 'on-track' | 'near-end' | 'overdue'
  progress_pct: number
  days_held: number
  expected_days: number
  expected_years: number
}

export interface GoalProgressSummary {
  healthy: number
  near_end: number
  overdue: number
}

export interface GoalProgressResponse {
  summary: GoalProgressSummary
  items: GoalProgressItem[]
}

export interface TypeDistributionItem {
  category_id: string
  name: string
  color: string
  percentage: number
  amount: number
  count: number
}

export interface TypeDistributionResponse {
  total_value: number
  total_count: number
  categories: TypeDistributionItem[]
}

export interface DurationBucket {
  label_key: string
  count: number
  percentage: number
}

export interface DurationDistributionResponse {
  avg_days: number
  max_days: number
  buckets: DurationBucket[]
}

export interface RetentionItem {
  id: string
  name: string
  icon: string
  service_days: number
  bought_amount: number
  current_amount: number
  retention_rate: number
  profit_loss: number
  rank: number
}

export interface RetentionRateResponse {
  total_bought: number
  total_sold: number
  avg_rate: number
  total_profit_loss: number
  top_items: RetentionItem[]
}

export interface InvestmentReturnSummary {
  annualized_rate: number | null
  asset_count: number
  description: string
}

export interface InsightsResponse {
  smart_discovery: SmartDiscoveryResponse
  daily_cost_ranking: DailyCostItem[]
  goal_progress: GoalProgressResponse
  type_distribution: TypeDistributionResponse
  duration_distribution: DurationDistributionResponse
  retention_rate: RetentionRateResponse
  investment_returns: InvestmentReturnSummary | null
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

export function getInsights() {
  return http.get<InsightsResponse>('/dashboard/insights')
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

export interface UpcomingPaymentItem {
  liability_id: string
  name: string
  amount: number | null
  due_date: string
}

export interface UpcomingPaymentsResponse {
  items: UpcomingPaymentItem[]
  total_amount: number
}

export function getUpcomingPayments() {
  return http.get<UpcomingPaymentsResponse>('/dashboard/upcoming-payments')
}
