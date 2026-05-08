import http from './index'
import type { ChildUser } from '@/types'

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

export async function resetChildPassword(childId: string, newPassword: string): Promise<void> {
  await http.post(`/auth/child/${childId}/password`, { new_password: newPassword })
}
