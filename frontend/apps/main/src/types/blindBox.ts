export interface BlindBoxGift {
  id: string
  family_id: string
  name: string
  description: string | null
  emoji: string | null
  value_score: number
  source_wish_id: string | null
  is_active: boolean
  created_by: string
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
  id: string
  family_id: string
  child_user_id: string
  coins_spent: number
  gift_id: string
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
  id: string
  family_id: string
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
  id: string
  family_id: string
  child_user_id: string
  source_wish_id: string | null
  status: 'available' | 'used' | 'expired'
  expires_at: string
  used_draw_id: string | null
  created_at: string
}
