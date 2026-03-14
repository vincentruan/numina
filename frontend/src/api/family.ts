import http from './index'
import type { Family, User } from '@/types'

export function getFamily() {
  return http.get<Family>('/family')
}

export function getMembers() {
  return http.get<User[]>('/family/members')
}

export function regenerateInviteCode() {
  return http.post<{ invite_code: string }>('/family/regenerate-invite-code')
}

export function updateMemberRole(userId: string, role: 'owner' | 'member') {
  return http.patch(`/family/members/${userId}/role`, { role })
}

export function removeMember(userId: string) {
  return http.delete(`/family/members/${userId}`)
}
