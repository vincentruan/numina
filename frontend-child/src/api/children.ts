import http from './index'
import type { ChildUser, ChildBindInfo } from '@/types'

export async function childPinLogin(pin: string[], options?: { childId?: string; username?: string | null }): Promise<void> {
  // 支持 username 方式登录（主推），child_id 方式作为备选
  const payload: { child_id?: string; username?: string; pin_sequence: string[] } = {
    pin_sequence: pin,
  }
  if (options?.username) {
    payload.username = options.username
  } else if (options?.childId) {
    payload.child_id = options.childId
  }
  await http.post('/auth/child/login', payload)
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
