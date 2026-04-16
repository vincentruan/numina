import http from './index'
import type { Family, User } from '@/types'

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

export function updateFamilySettings(settings: { autoApproveHours?: number; aiEnabled?: boolean }) {
  const body: Record<string, unknown> = {}
  if (settings.autoApproveHours !== undefined) body.auto_approve_hours = settings.autoApproveHours
  if (settings.aiEnabled !== undefined) body.ai_enabled = settings.aiEnabled
  return http.patch<{ auto_approve_hours: number; ai_enabled: boolean }>('/family/settings', body)
}
