export interface User {
  id: string
  family_id: string
  username: string
  display_name: string
  avatar_color: string
  role: 'owner' | 'member'
  is_active: boolean
  created_at: string
}

export interface Family {
  id: string
  name: string
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
  tags?: Tag[]
  daily_cost?: number
  return_rate?: number
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
  month_over_month_change: number
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

export interface LoginRequest {
  username: string
  password: string
}

export interface RegisterRequest {
  family_name: string
  username: string
  display_name: string
  password: string
}

export interface JoinFamilyRequest {
  invite_code: string
  username: string
  display_name: string
  password: string
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
}

export interface Wish {
  id: string
  family_id: string
  user_id: string
  name: string
  category_id?: string
  expected_price?: number
  target_date?: string
  priority: number
  notes?: string
  is_fulfilled: boolean
  fulfilled_asset_id?: string
  created_at: string
  updated_at: string
}

export interface PaymentRecord {
  id: string
  liability_id: string
  amount: number
  paid_at: string
  notes?: string
}
