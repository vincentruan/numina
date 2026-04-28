export interface BlindBoxGift {
  id: number
  family_id: number
  name: string
  description: string | null
  emoji: string | null
  value_score: number
  source_wish_id: number | null
  is_active: boolean
  created_by: number
  created_at: string
  updated_at: string
  warning?: string | null
}

export interface BlindBoxGiftCreate {
  name: string
  description?: string | null
  emoji?: string | null
  value_score: number
  source_wish_id?: number | null
}

export interface BlindBoxGiftUpdate {
  name?: string
  description?: string | null
  emoji?: string | null
  value_score?: number
  is_active?: boolean
}

export interface BlindBoxDraw {
  id: number
  family_id: number
  child_user_id: number
  coins_spent: number
  gift_id: number
  gift_name: string
  gift_emoji: string | null
  is_surprise: boolean
  is_bonus: boolean
  status: 'pending_fulfillment' | 'fulfilled'
  draw_at: string
  fulfilled_at: string | null
}

export interface DrawRequest {
  chore_instance_ids: number[]
}

export interface BlindBoxConfig {
  id: number
  family_id: number
  enabled: boolean
  base_draw_prob: number
  special_day_prob: number
  weight_scale: number
  surprise_threshold_coins: number
  surprise_prob_normal: number
  surprise_prob_parent_bday: number
  surprise_prob_sibling_bday: number
}

export interface BlindBoxConfigUpdate {
  enabled?: boolean
  base_draw_prob?: number
  special_day_prob?: number
  weight_scale?: number
  surprise_threshold_coins?: number
  surprise_prob_normal?: number
  surprise_prob_parent_bday?: number
  surprise_prob_sibling_bday?: number
}

export interface BonusDraw {
  id: number
  family_id: number
  child_user_id: number
  source_wish_id: number | null
  status: 'available' | 'used' | 'expired'
  expires_at: string
  used_draw_id: number | null
  created_at: string
}
