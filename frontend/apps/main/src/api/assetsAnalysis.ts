import http from './index'

export interface BuyVsRentParams {
  purchase_price: number
  monthly_rent: number
  usage_months: number
  annual_maintenance_cost?: number
  depreciation_years?: number
  residual_value_rate?: number
}

export interface BuyVsRentResult {
  buy_total: number
  rent_total: number
  breakeven_months: number | null
  recommendation: string
  buy_advantage_pct: number
}

export interface CostEquivalenceResult {
  asset_id: string
  asset_name: string
  held_days: number | null
  total_held_cost: number | null
  daily_cost: number | null
  time_cost_hours: number | null
  opportunity_cost: number | null
}

export const calculateBuyVsRent = (params: BuyVsRentParams): Promise<BuyVsRentResult> =>
  http.post('/assets/buy-vs-rent', params)

export const getCostEquivalence = (
  assetId: string,
  params?: { hourly_wage?: number; yield_rate?: number; years?: number },
): Promise<CostEquivalenceResult> =>
  http.get(`/assets/${assetId}/cost-equivalence`, { params })
