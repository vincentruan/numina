import type { User as _AuthUser } from '@numina/auth'
export type { User } from '@numina/auth'

export interface Family {
  id: string
  name: string
  custom_title?: string
  invite_code: string
  creator_code?: string
  created_by: string
  members: _AuthUser[]
  share_link_enabled?: boolean
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
  // Money fields are str on the wire (money-as-str: Decimal in compute, str on
  // the wire; JS double loses precision >2^53). Backend migrated Float→Numeric(18,2).
  purchase_price: string | null
  current_value: string | null
  currency: string
  purchase_date: string
  status: 'in_use' | 'idle' | 'sold' | 'retired'
  location?: string
  institution?: string
  interest_rate?: number
  maturity_date?: string
  warranty_expiry_date?: string
  expected_lifespan_days?: number
  annual_maintenance_cost?: string | null
  usage_frequency?: 'daily' | 'weekly' | 'monthly' | 'rarely' | 'idle'
  properties?: string
  notes?: string
  sell_price?: string | null
  sell_date?: string
  sell_fee?: string | null
  sell_channel?: string
  retire_date?: string
  target_daily_cost?: string | null
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
  net_recovery: string
  total_profit_loss: string
  actual_daily_cost: string
  target_daily_cost: string | null
  days_held: number
  purchase_price: string | null
  sell_price: string
}

export interface AssetValuation {
  id: string
  asset_id: string
  value: string
  valued_at: string
  notes?: string
}

export interface Liability {
  id: string
  user_id: string
  family_id: string
  category: 'mortgage' | 'car_loan' | 'credit_card' | 'personal_loan' | 'other'
  name: string
  // Money fields are str on the wire (SnowflakeBase money-as-str). Was number
  // pre-T8b; backend migrated Float→Numeric(18,2)+str serialization.
  original_amount: string
  remaining_amount: string
  currency: string
  monthly_payment: string | null
  interest_rate: number | null
  start_date: string
  end_date?: string
  institution?: string
  linked_asset_id?: string
  // L7 (KTD-2): populated only on the detail endpoint — {name, current_value(str)}.
  // Absent on list/create/update responses.
  linked_asset?: { name: string; current_value: string | null }
  notes?: string
  is_active: boolean
}

// The Asset money fields, single source of truth. Money is `string` on the response
// (money-as-str) but `number` on the request (backend coerces). Both AssetRequestPayload
// (below) and the asset store's optimistic update derive from this list, so adding or
// renaming a money field is a one-line change here instead of editing three places.
export const ASSET_MONEY_FIELDS = [
  'purchase_price',
  'current_value',
  'annual_maintenance_cost',
  'sell_price',
  'sell_fee',
  'target_daily_cost',
] as const
export type AssetMoneyField = (typeof ASSET_MONEY_FIELDS)[number]

// Request payloads for create/update. The response types above carry money as
// `string` (money-as-str on the wire OUT), but the backend's create/update schemas
// declare these fields `float`/`Decimal` and Pydantic coerces numeric input — so the
// forms send numbers. These payload types make that direction honest instead of
// reusing the response shape (which mistypes the money fields as string).
export type AssetRequestPayload = Omit<Partial<Asset>, AssetMoneyField> & {
  purchase_price?: number | null
  current_value?: number | null
  annual_maintenance_cost?: number | null
  sell_price?: number | null
  sell_fee?: number | null
  target_daily_cost?: number | null
  tag_ids?: string[]
}

export type LiabilityRequestPayload = Omit<Partial<Liability>, 'original_amount' | 'remaining_amount' | 'monthly_payment' | 'linked_asset_id'> & {
  original_amount?: number
  remaining_amount?: number
  monthly_payment?: number | null
  // null = explicitly unlink (backend update uses exclude_unset, so null clears the
  // link while omitting the key preserves it). Distinct from undefined.
  linked_asset_id?: string | null
}

// Rental contracts - money fields are str on the wire (money-as-str), matching
// Liability above.
export interface RentalContract {
  id: string
  user_id: string
  family_id: string
  role: 'landlord' | 'tenant'
  monthly_rent: string
  deposit: string
  start_date: string
  end_date?: string | null // null = 不定期租约
  linked_asset_id?: string | null // landlord-only
  counterparty?: string | null
  notes?: string | null
  currency: string
  is_active: boolean
  created_at?: string
  updated_at?: string
}

export type RentalRequestPayload = Omit<Partial<RentalContract>, 'monthly_rent' | 'deposit' | 'linked_asset_id'> & {
  monthly_rent?: number
  deposit?: number
  linked_asset_id?: string | null
}

export interface RentalSummary {
  monthly_income: string
  monthly_expense: string
  net_cash_flow: string
  total_deposit: string
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
  month_over_month_change_amount: number | null
  total_daily_cost: number
  rental_net_cash_flow: number | null
  rental_monthly_income: number | null
  rental_monthly_expense: number | null
  rental_total_deposit: number | null
}

export interface AllocationItem {
  category_id: string
  category_name: string
  icon: string
  color: string
  amount: number
  percentage: number
  asset_type?: 'physical' | 'financial'
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
  physical_items: AllocationItem[]
  financial_items: AllocationItem[]
  total: number
}

export interface LiabilityAllocationItem {
  category_name: string
  amount: number
  percentage: number
  color: string
}

export interface LiabilityAllocationResponse {
  items: LiabilityAllocationItem[]
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

export interface EducationRewardSummary {
  total: number
  month_total: number
  count: number
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
  // Serialized as str from the backend (SnowflakeBase money-as-str), like
  // saved_amount/monthly_saving below. WishResponse.expected_price is str | None.
  expected_price?: string
  currency: string
  priority: string
  status: string
  category_id?: string
  category?: CategoryInfo
  converts_to_asset: boolean
  realized_asset_id?: string
  fulfilled_at?: string
  // W1 savings fields (Plan B T1-T3). Serialized as str from the backend
  // (SnowflakeBase money-as-str); typed loosely here as the existing fields.
  saved_amount?: string
  monthly_saving?: string
  target_date?: string
  savings_count?: number
  ignore_debt_warning?: boolean
  created_at: string
  updated_at: string
}

export interface CategoryInfo {
  id: string
  name: string
  icon: string
  asset_type: string
}

// Wish create/update payload. The form sends expected_price/monthly_saving as numbers
// (parseFloat of the text input); the redistribution path sends monthly_saving as a
// numeric string. Backend declares these Decimal and coerces either, so accept both.
export type WishRequestPayload = Omit<Partial<Wish>, 'expected_price' | 'monthly_saving'> & {
  expected_price?: number
  monthly_saving?: number | string
}

// W4 wish-priority advice (Plan B T7). Independent of finance_coach's suggestions[].
export interface WishRedistribution {
  wish_id: string
  suggested_amount: string
  note: string
}
export interface WishAdvice {
  primary_wish_id: string
  reason: string
  suggested_monthly: string
  redistribution: WishRedistribution[]
}

// W1 savings log (Plan B T9 frontend). T3 added the backend route + schema.
export interface SavingsLog {
  id: string
  wish_id: string
  amount: string
  log_date: string
  note: string | null
  created_at: string
}

// L2 /liabilities/simulate result (Plan B T9 frontend). T4 added the endpoint.
export interface LiabilitySimResult {
  total_interest: string
  months: number
  monthly_payment: string | null
  warning: string | null
  baseline_total_interest?: string
  baseline_months?: number
  savings_vs_baseline?: string
  months_saved?: number
}

export interface WishRealizeRequest {
  purchase_price: number
  purchase_date: string
  category_id?: string
}

export interface PaymentRecord {
  id: string
  liability_id: string
  amount: string
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
  data?: Record<string, unknown> & {
    // New bilingual items format (SKILL.md v2): items with zh/en labels
    items?: Array<{ key: string; zh: string; en: string; value: number }>
  }
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

// D2/A1a: finance_coach proactive suggestions (Plan B T5). The backend
// /ai/finance-coach/generate endpoint returns cached JSON or streams a
// finance_coach.result frame; both carry the same report shape.
export type SuggestionSeverity = 'high' | 'medium' | 'low'
export interface FinanceSuggestion {
  id: string
  severity: SuggestionSeverity
  title: string
  action: string
  target_type: 'liability' | 'asset' | 'wish'
  target_id: string
  cta_label: string
}
export interface FinanceCoachResponse {
  status: 'cached' | 'streaming'
  generated_at?: string
  report: { suggestions: FinanceSuggestion[] }
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
