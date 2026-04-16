import http from './index'
import type { ChildUser, ChildBindInfo } from '@/types'

export async function childPinLogin(childId: string, pin: string[]): Promise<void> {
  await http.post('/auth/child/login', { child_id: childId, pin_sequence: pin })
}

export async function verifyParentPassword(password: string): Promise<void> {
  await http.post('/auth/child/verify-parent', { password })
}

export async function childLogout(): Promise<void> {
  await http.post('/auth/child/logout')
}

export async function getChildBindInfo(token: string): Promise<ChildBindInfo> {
  const res = await http.get(`/auth/child/bind?token=${token}`)
  return res.data
}

export async function getFamilyChildren(familyId: string): Promise<ChildUser[]> {
  const res = await http.get(`/auth/child/family/${familyId}/children`)
  return res.data
}

export async function listChildren(): Promise<ChildUser[]> {
  const res = await http.get('/family/children')
  return res.data
}
