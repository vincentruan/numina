import http from './index'

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export interface ChildWish {
  id: string
  family_id: string
  child_user_id: string
  name: string
  description: string | null
  emoji: string | null
  priority: 'high' | 'medium' | 'low'
  status: 'pending_review' | 'active' | 'rejected' | 'redemption_requested' | 'realized'
  has_cost_set: boolean
  progress: number | null
  rejection_reason: string | null
  realized_asset_id: string | null
  fulfilled_at: string | null
  created_at: string
  updated_at: string
}

export interface ChildWishList {
  pending_review: ChildWish[]
  active: ChildWish[]
  redemption_requested: ChildWish[]
  realized: ChildWish[]
  rejected: ChildWish[]
}

export interface ChildWishStats {
  balance: number
  active_wish_count: number
  realized_wish_count: number
  priority_simulation: {
    wish_id: string
    name: string
    priority: string
    star_coin_cost: number
    progress: number
    covered: boolean
  }[]
  shortfall_for_high_priority: number
}

export interface ParentWish {
  id: string
  family_id: string
  child_user_id: string
  child_display_name: string
  name: string
  description: string | null
  emoji: string | null
  priority: 'high' | 'medium' | 'low'
  status: string
  star_coin_cost: number | null
  star_coin_cost_history: { old: number; new: number; changed_at: string }[] | null
  rejection_reason: string | null
  realized_asset_id: string | null
  fulfilled_at: string | null
  created_at: string
  updated_at: string
}

// ---------------------------------------------------------------------------
// Child API
// ---------------------------------------------------------------------------

export async function createChildWish(data: {
  name: string
  description?: string
  emoji?: string
  priority: 'high' | 'medium' | 'low'
}): Promise<ChildWish> {
  const res = await http.post('/child/wishes', data)
  return res.data
}

export async function listChildWishes(): Promise<ChildWishList> {
  const res = await http.get('/child/wishes')
  return res.data
}

export async function getChildWishStats(): Promise<ChildWishStats> {
  const res = await http.get('/child/wishes/stats')
  return res.data
}

export async function requestRedemption(wishId: string): Promise<ChildWish> {
  const res = await http.post(`/child/wishes/${wishId}/request-redemption`)
  return res.data
}

// ---------------------------------------------------------------------------
// Parent API
// ---------------------------------------------------------------------------

export async function listParentChildWishes(): Promise<ParentWish[]> {
  const res = await http.get('/family/child-wishes')
  return res.data
}

export async function approveChildWish(wishId: string, starCoinCost: number): Promise<ParentWish> {
  const res = await http.post(`/family/child-wishes/${wishId}/approve`, { star_coin_cost: starCoinCost })
  return res.data
}

export async function rejectChildWish(wishId: string, rejectionReason?: string): Promise<ParentWish> {
  const res = await http.post(`/family/child-wishes/${wishId}/reject`, { rejection_reason: rejectionReason })
  return res.data
}

export async function updateChildWishCost(wishId: string, starCoinCost: number): Promise<ParentWish> {
  const res = await http.patch(`/family/child-wishes/${wishId}/cost`, { star_coin_cost: starCoinCost })
  return res.data
}

export async function realizeChildWish(wishId: string, categoryId?: string): Promise<ParentWish> {
  const res = await http.post(`/family/child-wishes/${wishId}/realize`, { category_id: categoryId })
  return res.data
}

export async function deferChildWish(wishId: string): Promise<ParentWish> {
  const res = await http.post(`/family/child-wishes/${wishId}/defer`)
  return res.data
}
