import http from './index'
import type { ChildUser } from '@/types'

export async function childPinLogin(pin: string[], options?: { childId?: string; username?: string | null }): Promise<void> {
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

export async function listChildren(): Promise<ChildUser[]> {
  const res = await http.get('/family/children')
  return res.data
}

export interface CreateChildPayload {
  username: string
  display_name: string
  password: string
  pin: string[]
  avatar_color?: string
}

export async function createChild(payload: CreateChildPayload): Promise<ChildUser> {
  const res = await http.post('/family/children', payload)
  return res.data.data
}

export async function resetChildPin(childId: string, pin: string[]): Promise<void> {
  await http.patch(`/family/children/${childId}`, { pin })
}

export async function forceLogoutChild(childId: string): Promise<void> {
  await http.post(`/family/children/${childId}/force-logout`)
}

export async function unlockChildPin(childId: string): Promise<void> {
  await http.post(`/family/children/${childId}/unlock`)
}

