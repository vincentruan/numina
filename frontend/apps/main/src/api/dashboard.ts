import http, { refreshTokenIfNeeded } from './index'
import { readSSEStream } from '@/utils/sseReader'
import type { DashboardOverview, AllocationResponse, TrendResponse, DailyCostItem, InvestmentReturnItem, TopAssetItem, LowUsageItem, StatesSummaryResponse, Asset, HomeAssetsPageResponse, NewAssetsResponse, EducationRewardSummary, LiabilityAllocationResponse } from '@/types'

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

export function getEducationRewardSummary() {
  return http.get<EducationRewardSummary>('/dashboard/education-reward-summary')
}

export function getLiabilityAllocation() {
  return http.get<LiabilityAllocationResponse>('/dashboard/liability-allocation')
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
  return http.get<Array<{ id: string; name: string; icon: string; color: string; asset_type: 'physical' | 'financial'; count: number }>>(
    `/dashboard/home-assets/${status}/categories`
  )
}

export function getHomeAssetsPaginated(
  status: string,
  page: number = 1,
  pageSize: number = 20,
  categoryId?: string | null,
  options?: {
    search?: string
    sortBy?: string
    sortOrder?: 'asc' | 'desc'
    assetType?: 'physical' | 'financial'
  }
) {
  return http.get<HomeAssetsPageResponse>(`/dashboard/home-assets/${status}`, {
    params: {
      page,
      page_size: pageSize,
      ...(categoryId ? { category_id: categoryId } : {}),
      ...(options?.search ? { search: options.search } : {}),
      ...(options?.sortBy ? { sort_by: options.sortBy } : {}),
      ...(options?.sortOrder ? { sort_order: options.sortOrder } : {}),
      ...(options?.assetType ? { asset_type: options.assetType } : {})
    }
  })
}

export function getNewAssets(period: 'month' | 'quarter' | 'year' = 'month') {
  return http.get<NewAssetsResponse>('/dashboard/new-assets', { params: { period } })
}

export function getInsights() {
  return http.get<InsightsResponse>('/dashboard/insights')
}

// ── Narrative (仪表盘叙事卡片) ──────────────────────────────────────────────
export interface NarrativeResponse {
  narrative: string | null
  first_sentence: string
  thinking: string
  generated_at: string | null
  /** Why generation was skipped (threshold gate). */
  reason?: 'insufficient_assets' | 'insufficient_history'
  /** Current asset count (when reason = insufficient_assets). */
  asset_count?: number
  /** Required minimum (when reason = insufficient_assets). */
  threshold?: number
}

export function getNarrative(force = false) {
  return http.get<NarrativeResponse>('/dashboard/narrative', {
    params: { force },
  })
}

// ── Narrative SSE streaming ─────────────────────────────────────────────────

export interface NarrativeBlockReason {
  reason: 'insufficient_assets' | 'insufficient_history'
  asset_count?: number
  threshold?: number
}

export interface NarrativeStreamCallbacks {
  onReasoningDelta: (content: string) => void
  onNarrativeDelta: (content: string) => void
  onDone: (result: { narrative: string; thinking: string }) => void
  onBlocked: (info: NarrativeBlockReason) => void
  onError: (message: string) => void
}

export interface NarrativeStreamHandle {
  abort: () => void
}

/**
 * Consume the narrative SSE stream.
 *
 * Returns JSON (cached / threshold-miss) or streams SSE events:
 * - custom { type: "reasoning_delta", content } → thinking chunk
 * - messages { type: "ai", content }             → narrative text chunk
 * - custom { type: "dashboard_narrative.result" }→ final result
 * - end                                          → stream complete
 * - error                                        → error
 */
export async function streamNarrative(
  callbacks: NarrativeStreamCallbacks,
): Promise<NarrativeStreamHandle> {
  const controller = new AbortController()

  // fire-and-forget: kick off the stream, return handle immediately
  void runNarrativeStream(controller, callbacks)

  return { abort: () => controller.abort() }
}

async function runNarrativeStream(
  controller: AbortController,
  callbacks: NarrativeStreamCallbacks,
): Promise<void> {
  const url = '/api/v1/dashboard/narrative'
  const headers: Record<string, string> = {
    Accept: 'text/event-stream',
  }

  let res: Response
  try {
    // SSE: axios lacks native EventSource/SSE support — bare fetch required.
    res = await fetch(url, {
      method: 'POST',
      headers,
      credentials: 'include',
      signal: controller.signal,
    })
    if (res.status === 401) {
      try {
        await refreshTokenIfNeeded()
      } catch {
        callbacks.onError('dashboard.narrative.error.auth_expired')
        return
      }
      // SSE: axios lacks native EventSource/SSE support — bare fetch required.
      res = await fetch(url, {
        method: 'POST',
        headers,
        credentials: 'include',
        signal: controller.signal,
      })
    }
  } catch (err) {
    if ((err as Error).name !== 'AbortError') {
      callbacks.onError('dashboard.narrative.error.connect_failed')
    }
    return
  }

  if (!res.ok) {
    callbacks.onError(`dashboard.narrative.error.request_failed:${res.status}`)
    return
  }

  // JSON response: cache hit or threshold miss
  const contentType = res.headers.get('Content-Type') || ''
  if (contentType.includes('application/json')) {
    try {
      const data = (await res.json()) as NarrativeResponse
      if (data.reason) {
        callbacks.onBlocked({
          reason: data.reason,
          asset_count: data.asset_count,
          threshold: data.threshold,
        })
      } else {
        callbacks.onDone({
          narrative: data.narrative || '',
          thinking: data.thinking || '',
        })
      }
    } catch {
      callbacks.onError('dashboard.narrative.error.parse_failed')
    }
    return
  }

  // SSE stream
  if (!res.body) {
    callbacks.onError('dashboard.narrative.error.stream_unavailable')
    return
  }

  let narrativeBuffer = ''
  let thinkingBuffer = ''
  let errored = false

  try {
    await readSSEStream(res, {
      onMessage: (event, data) => {
        if (errored) return
        if (event === 'messages' && data) {
          const msg = data as { type?: string; content?: string }
          if (msg.type === 'ai' && msg.content) {
            narrativeBuffer += msg.content
            callbacks.onNarrativeDelta(msg.content)
          }
        }
      },
      onCustom: (data) => {
        if (errored) return
        const custom = data as { type?: string; content?: string }
        if (custom.type === 'reasoning_delta' && custom.content) {
          thinkingBuffer += custom.content
          callbacks.onReasoningDelta(custom.content)
        } else if (custom.type === 'dashboard_narrative.result') {
          const payload = (data as { payload?: Record<string, unknown> }).payload || {}
          callbacks.onDone({
            narrative: String(payload.narrative || narrativeBuffer),
            thinking: String(payload.thinking || thinkingBuffer),
          })
        }
      },
      onError: (data) => {
        errored = true
        const errData = data as { error?: string; message?: string }
        callbacks.onError(errData.error || errData.message || 'dashboard.narrative.error.generation_failed')
      },
      onEnd: (data) => {
        if (errored) return
        const endData = data as { status?: string } | undefined
        if (endData?.status === 'error') {
          errored = true
          callbacks.onError('dashboard.narrative.error.generation_failed')
        } else if (endData?.status !== 'complete' && endData?.status !== 'completed') {
          // end frame with non-terminal status — use accumulated buffers.
          callbacks.onDone({
            narrative: narrativeBuffer,
            thinking: thinkingBuffer,
          })
        }
      },
    })
    // Stream ended naturally — deliver accumulated content if not yet done.
    if (!errored && (narrativeBuffer || thinkingBuffer)) {
      callbacks.onDone({
        narrative: narrativeBuffer,
        thinking: thinkingBuffer,
      })
    }
  } catch (err) {
    if ((err as Error).name !== 'AbortError') {
      callbacks.onError('dashboard.narrative.error.connection_interrupted')
    }
  }
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
