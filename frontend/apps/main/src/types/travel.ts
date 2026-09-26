// Travel module types — Snowflake IDs are `string` per project convention.

export interface Trip {
  id: string
  family_id: string
  user_id: string
  name: string
  description: string | null
  destination: string
  departure_date: string
  return_date: string | null
  status: 'planning' | 'active' | 'settled' | 'archived' | 'cancelled'
  planned_budget: string | null
  initial_funding: string | null
  actual_spend: string
  currency: string
  wish_id: string | null
  is_active: boolean
  created_at: string
  updated_at: string
}

export interface TripCreate {
  name: string
  destination: string
  departure_date: string
  return_date?: string | null
  planned_budget?: string | null
  currency?: string
  wish_id?: string | null
  description?: string | null
}

export interface TripUpdate {
  name?: string
  description?: string | null
  destination?: string
  departure_date?: string
  return_date?: string | null
  status?: string
  planned_budget?: string | null
  currency?: string
}

export interface ExpenseEntry {
  id: string
  family_id: string
  transfer_id: string
  leg_type: 'debit' | 'credit'
  ref_id: string | null
  ref_type: string | null
  category_id: string | null
  amount: string
  currency: string
  amount_cny: string
  exchange_rate: number | null
  expense_date: string
  description: string | null
  receipt_image_url: string | null
  user_id: string
  itinerary_item_id: string | null
  created_at: string
  updated_at: string
}

export interface ExpenseEntryCreate {
  amount: string
  currency: string
  expense_date: string
  category_id?: string | null
  description?: string | null
  receipt_image_url?: string | null
  split_type?: 'equal' | 'per_person' | 'custom' | null
  exchange_rate?: number | null
}

export interface ExpenseCategory {
  id: string
  family_id: string | null
  name: string
  icon: string
  sort_order: number
  is_system: boolean
}

export interface SplitGroup {
  id: string
  trip_id: string
  invite_code: string
  created_by_user_id: string
  is_active: boolean
  expires_at: string | null
  participants: SplitParticipant[]
}

export interface SplitParticipant {
  id: string
  group_id: string
  name: string
  family_id: string | null
  joined_at: string
}

export interface SplitSettlement {
  id: string
  trip_id: string
  from_participant_name: string
  to_participant_name: string
  amount: string
  currency: string
  is_complete: boolean
  settled_at: string | null
  settled_by_user_id: string | null
}

export interface SharedExpense {
  trip_name: string
  destination: string
  departure_date: string
  return_date: string | null
  trip_status: string
  expenses: SharedExpenseItem[]
  participants: SplitParticipant[]
}

export interface SharedExpenseItem {
  id: string
  amount: string
  currency: string
  amount_cny: string
  expense_date: string
  category_name: string | null
  payer_name: string
}

export type ItineraryItemType = 'accommodation' | 'dining' | 'transport' | 'activity' | 'custom'

export interface ItineraryItemTypeDef {
  id: string
  family_id: string | null
  name: string
  icon: string
  sort_order: number
}

export interface ItineraryItem {
  id: string
  trip_id: string
  family_id: string
  date: string
  type: ItineraryItemType
  sort_order: number
  start_time: string | null
  end_time: string | null
  location: string | null
  description: string | null
  cost_amount: string | null
  cost_currency: string | null
  custom_type_id: string | null
  type_metadata: Record<string, unknown> | null
  created_at: string
  updated_at: string
}

export interface ItineraryItemCreate {
  date: string
  type: ItineraryItemType
  sort_order?: number
  start_time?: string | null
  end_time?: string | null
  location?: string | null
  description?: string | null
  cost_amount?: string | null
  cost_currency?: string | null
  custom_type_id?: string | null
  type_metadata?: Record<string, unknown> | null
}

export interface ItineraryItemUpdate {
  date?: string
  type?: ItineraryItemType
  sort_order?: number
  start_time?: string | null
  end_time?: string | null
  location?: string | null
  description?: string | null
  cost_amount?: string | null
  cost_currency?: string | null
  custom_type_id?: string | null
  type_metadata?: Record<string, unknown> | null
}
