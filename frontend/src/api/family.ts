import http from './index'
import type { Family, User } from '@/types'

export interface FamilySettings {
  auto_approve_hours: number
  ai_enabled: boolean
  coin_copper_to_silver: number
  coin_silver_to_gold: number
}

export function getFamily() {
  return http.get<Family>('/family')
}

export function getMembers() {
  return http.get<User[]>('/family/members')
}

export function regenerateInviteCode() {
  return http.post<{ invite_code: string }>('/family/invite-code')
}

export function updateMemberRole(userId: string, role: 'owner' | 'member') {
  return http.patch(`/family/members/${userId}/role`, { role })
}

export function removeMember(userId: string) {
  return http.delete(`/family/members/${userId}`)
}

export function updateFamilyTitle(custom_title: string | null) {
  return http.patch<Family>('/family/title', { custom_title })
}

export function getFamilySettings() {
  return http.get<FamilySettings>('/family/settings')
}

export function updateFamilySettings(settings: {
  autoApproveHours?: number
  aiEnabled?: boolean
  coinCopperToSilver?: number
  coinSilverToGold?: number
}) {
  const body: Record<string, unknown> = {}
  if (settings.autoApproveHours !== undefined) body.auto_approve_hours = settings.autoApproveHours
  if (settings.aiEnabled !== undefined) body.ai_enabled = settings.aiEnabled
  if (settings.coinCopperToSilver !== undefined) body.coin_copper_to_silver = settings.coinCopperToSilver
  if (settings.coinSilverToGold !== undefined) body.coin_silver_to_gold = settings.coinSilverToGold
  return http.patch<FamilySettings>('/family/settings', body)
}

export function getChildBalance(childId: string) {
  return http.get<{ balance: number }>(`/family/children/${childId}/balance`)
}

/** Batch fetch all child balances in one request. Returns {child_user_id: balance}. */
export function getAllChildBalances() {
  return http.get<Record<string, number>>('/family/children/balances')
}

export interface ChoreStats {
  completed_this_week: number
  total_this_week: number
}

/** Fetch weekly chore completion stats for all children. Returns {child_user_id: ChoreStats}. */
export function getChildrenChoreStats() {
  return http.get<Record<string, ChoreStats>>('/family/children/chore-stats')
}
