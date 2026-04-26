import request from '@/utils/request'

export interface WhatIfAction {
  action_type: 'sell' | 'buy' | 'invest' | 'stop_expense'
  asset_id?: number
  amount?: number
  annual_return_rate?: number
  annual_cost?: number
  liquidation_rate?: number
}

export interface WhatIfRequest {
  actions: WhatIfAction[]
  projection_years?: number
  inflation_rate?: number
}

export interface WhatIfYearPoint {
  year: number
  baseline_net_worth: number
  scenario_net_worth: number
  difference: number
}

export interface WhatIfResponse {
  projection: WhatIfYearPoint[]
  total_difference: number
  breakeven_year: number | null
  summary: string | null
}

export interface ProjectionRequest {
  projection_years?: number
  inflation_rate?: number
  custom_overrides?: Record<number, number>
}

export interface ProjectionYearPoint {
  year: number
  total_assets: number
  total_liabilities: number
  net_worth: number
  real_net_worth: number
}

export interface ProjectionResponse {
  history: ProjectionYearPoint[]
  forecast: ProjectionYearPoint[]
  assumptions: Record<string, unknown>
  summary: string | null
}

export interface PurchasingPowerResponse {
  original_amount: number
  adjusted_amount: number
  from_year: number
  to_year: number
  cumulative_inflation: number
  annual_avg_inflation: number
  explanation: string
}

export function postWhatIf(data: WhatIfRequest) {
  return request.post<WhatIfResponse>('/ai/whatif', data)
}

export function postProjection(data: ProjectionRequest) {
  return request.post<ProjectionResponse>('/ai/projection', data)
}

export function getPurchasingPower(params: {
  amount: number
  from_year: number
  to_year: number
  custom_inflation_rate?: number
}) {
  return request.get<PurchasingPowerResponse>('/ai/purchasing-power', { params })
}

export function getAssetPurchasingPower(assetId: number) {
  return request.get<PurchasingPowerResponse>(`/assets/${assetId}/purchasing-power`)
}
