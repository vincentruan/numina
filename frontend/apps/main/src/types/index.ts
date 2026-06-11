export interface User {
  id: string
  family_id: string
  username: string | null  // 修复：允许 null（儿童账号可能为 null，迁移后必填）
  display_name: string
  avatar_color: string
  role: 'owner' | 'member' | 'child'
  is_active: boolean
  theme: string
  language: string
  default_currency: string
  view_mode: string
  created_at: string
  second_factor_enabled?: boolean
  second_factor_type?: string | null
  birthday?: string | null
  birthday_is_lunar?: boolean
}

export interface Family {
  id: string
  name: string
  custom_title?: string
  invite_code: string
  created_by: string
  members: User[]
}

export interface Category {
  id: string
  family_id: string | null
  name: string
  icon: string
  color: string
  asset_type: 'physical' | 'financial'
  sort_order: number
  is_system: boolean
}

export interface Asset {
  id: string
  user_id: string
  family_id: string
  category_id: string
  category?: Category
  name: string
  asset_type: 'physical' | 'financial'
  purchase_price: number
  current_value: number
  currency: string
  purchase_date: string
  status: 'in_use' | 'idle' | 'sold' | 'retired'
  location?: string
  institution?: string
  interest_rate?: number
  maturity_date?: string
  warranty_expiry_date?: string
  expected_lifespan_days?: number
  annual_maintenance_cost?: number
  usage_frequency?: 'daily' | 'weekly' | 'monthly' | 'rarely' | 'idle'
  properties?: string
  notes?: string
  sell_price?: number
  sell_date?: string
  sell_fee?: number
  sell_channel?: string
  retire_date?: string
  target_daily_cost?: number
  image_url?: string
  tags?: Tag[]
  daily_cost?: number
  return_rate?: number
  from_wish_id?: string
  created_at: string
  updated_at: string
}

export interface AssetSellRequest {
  sell_price: number
  sell_fee?: number
  sell_channel?: string
  notes?: string
}

export interface AssetSellResponse {
  asset_id: string
  name: string
  net_recovery: number
  total_profit_loss: number
  actual_daily_cost: number
  target_daily_cost: number | null
  days_held: number
  purchase_price: number | null
  sell_price: number
}

export interface AssetValuation {
  id: string
  asset_id: string
  value: number
  valued_at: string
  notes?: string
}

export interface Liability {
  id: string
  user_id: string
  family_id: string
  category: 'mortgage' | 'car_loan' | 'credit_card' | 'personal_loan' | 'other'
  name: string
  original_amount: number
  remaining_amount: number
  currency: string
  monthly_payment: number
  interest_rate: number
  start_date: string
  end_date?: string
  institution?: string
  linked_asset_id?: string
  notes?: string
  is_active: boolean
}

export interface Tag {
  id: string
  family_id: string
  name: string
  color: string
}

export interface DashboardOverview {
  total_assets: number
  total_liabilities: number
  net_worth: number
  asset_count: number
  month_over_month_change: number | null
  total_daily_cost: number
}

export interface AllocationItem {
  category_id: string
  category_name: string
  icon: string
  color: string
  amount: number
  percentage: number
}

export interface TrendPoint {
  date: string
  total_assets: number
  total_liabilities: number
  net_worth: number
}

export interface DailyCostItem {
  id: string
  name: string
  daily_cost: number
  icon: string
  category_name: string
  days_used: number
  total_cost: number
}

export interface InvestmentReturnItem {
  id: string
  name: string
  purchase_price: number
  current_value: number
  return_rate: number
  profit: number
  category_name: string
  icon: string
}

export interface TopAssetItem {
  id: string
  name: string
  category_name: string
  icon: string
  current_value: number
}

export interface AllocationResponse {
  items: AllocationItem[]
  total: number
}

export interface TrendResponse {
  points: TrendPoint[]
}

export interface LowUsageItem {
  id: string
  name: string
  category_name: string
  icon: string
  current_value: number
  usage_frequency: string
  purchase_date?: string
}

export interface StatusSummary {
  count: number
  total_value: number
}

export interface StatesSummaryResponse {
  states: Record<string, StatusSummary>
  total_count: number
  total_value: number
}

export interface NewAssetItem {
  id: string
  name: string
  icon: string
  category_name: string
  current_value: number
  currency: string
  created_at: string
}

export interface NewAssetsResponse {
  count: number
  period: string
  items: NewAssetItem[]
}

export interface LoginRequest {
  username: string
  password: string
  altcha?: string
}

export interface RegisterRequest {
  family_name: string
  username: string
  display_name: string
  password: string
  family_invitation_code: string
  altcha?: string
}

export interface JoinFamilyRequest {
  invite_code: string
  username: string
  display_name: string
  password: string
  altcha?: string
}

export interface AuthResponse {
  access_token: string
  refresh_token: string
  token_type: string
}

export interface AssetFilter {
  asset_type?: 'physical' | 'financial'
  category_id?: string
  status?: string
  tag_id?: string
  search?: string
  sort_by?: string
  sort_order?: 'asc' | 'desc'
}

export interface PaginatedResponse<T> {
  items: T[]
  total: number
  page: number
  page_size: number
  total_pages: number
  has_next: boolean
  has_prev: boolean
}

export interface HomeAssetsPageResponse {
  items: Asset[]
  total: number
  page: number
  page_size: number
  total_pages: number
  has_next: boolean
  has_prev: boolean
}

export interface Wish {
  id: string
  family_id: string
  user_id: string
  name: string
  description?: string
  expected_price?: number
  currency: string
  priority: string
  status: string
  category_id?: string
  category?: CategoryInfo
  converts_to_asset: boolean
  realized_asset_id?: string
  fulfilled_at?: string
  created_at: string
  updated_at: string
}

export interface CategoryInfo {
  id: string
  name: string
  icon: string
  asset_type: string
}

export interface WishRealizeRequest {
  purchase_price: number
  purchase_date: string
  category_id?: string
}

export interface PaymentRecord {
  id: string
  liability_id: string
  amount: number
  paid_at: string
  notes?: string
}

export interface Currency {
  code: string
  name_zh: string
  name_en: string
  symbol: string
  flag_emoji: string
  is_favorite: boolean
  sort_order: number
}

export interface RateResponse {
  rate: number
  fetched_at: string
}

export interface RatesResponse {
  [code: string]: RateResponse
}

// ── AI types ──────────────────────────────────────────────────────────────────

export interface AssetAlert {
  id: string
  asset_id: string
  asset_name: string
  alert_type: string
  severity: 'low' | 'medium' | 'high'
  suggestion: string | null
  remaining_life_days: number | null
  daily_cost: number | null
  created_at: string
}

export interface DisposalSuggestion {
  id: string
  asset_id: string
  asset_name: string
  category_name: string
  inefficiency_score: number | null
  suggested_channel: string | null
  estimated_resale_range: string | null
  suggestion: string | null
  daily_cost: number | null
  created_at: string
}

export interface LiabilityStrategy {
  strategy: string
  strategy_name: string
  priority_debt: string
  estimated_interest_saved: number
  order: Array<{ id: string; category: string; rate?: number }>
}

export interface LiabilityAdviceResponse {
  has_result: boolean
  has_liabilities: boolean
  total_remaining: number | null
  total_monthly_payment: number | null
  liability_count: number | null
  narrative: string | null
  recommended_strategy: string | null
  strategies: LiabilityStrategy[]
  generated_at: string
}

export interface AllocationDriftItem {
  category: string
  target_pct: number
  current_pct: number
  drift: number
  exceeds_threshold: boolean
}

export interface AllocationDriftResponse {
  has_result: boolean
  has_significant_drift: boolean
  narrative: string | null
  drifts: AllocationDriftItem[] | null
  generated_at: string
}

export interface AIReportSection {
  score?: number
  label?: string
  narrative?: string
  suggestions?: string[]
  data?: Record<string, unknown>
}

export interface AIReportIndicator {
  key: string
  label: string
  score: number  // 1-5 scale
  narrative: string
  suggestions: string[]
  data?: Record<string, unknown>
}

export interface AIReport {
  overall_score: number | null
  summary: string
  data_completeness_score: number
  // New flexible format with indicators array
  indicators?: AIReportIndicator[]
  markdown_file_path?: string  // Path to markdown report file for preview
  // New narrative format (LLM may output these)
  narrative?: string
  sections?: Record<string, string>
  // Legacy structured format (skill-defined schema)
  net_worth_health?: AIReportSection & {
    data?: { net_worth?: number; total_assets?: number; total_liabilities?: number; mom_change_pct?: number }
  }
  allocation_analysis?: AIReportSection & {
    data?: { items?: AllocationItem[] }
  }
  liability_pressure?: AIReportSection & {
    data?: { count?: number; total_liabilities?: number; total_assets?: number }
  }
  asset_efficiency?: AIReportSection & {
    data?: { low_usage_count?: number; total_daily_cost?: number }
  }
  suggestions?: string[]
  risk_flags?: string[]
}

export interface ChatMessage {
  id: string
  role: 'user' | 'assistant'
  content: string
  created_at: string
}

export interface ChildUser {
  id: string
  username: string | null  // 儿童用户名（迁移后必填，迁移前可能为 null）
  display_name: string
  avatar_color: string
  is_active: boolean
}

// ── Type guards for dynamic field access ──────────────────────────────────────

/**
 * Check if asset data represents a physical asset.
 * Use before accessing physical-only fields (location, expected_lifespan_days, etc.)
 */
export function isPhysicalAsset(data: Partial<Asset>): boolean {
  return data.asset_type === 'physical'
}

/**
 * Check if asset data represents a financial asset.
 * Use before accessing financial-only fields (institution, interest_rate, etc.)
 */
export function isFinancialAsset(data: Partial<Asset>): boolean {
  return data.asset_type === 'financial'
}

/**
 * Safely access a field from partial asset data.
 * Returns undefined if field doesn't exist or data is null.
 */
export function getAssetField<T>(data: Partial<Asset> | null | undefined, field: keyof Asset): T | undefined {
  if (!data) return undefined
  const value = data[field]
  return value !== undefined ? (value as T) : undefined
}

/**
 * Safely access a liability field from partial data.
 */
export function getLiabilityField<T>(data: Partial<Liability> | null | undefined, field: keyof Liability): T | undefined {
  if (!data) return undefined
  const value = data[field]
  return value !== undefined ? (value as T) : undefined
}
