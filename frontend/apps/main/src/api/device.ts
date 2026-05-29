import http from './index'

export interface DeviceCheckResponse {
  trusted: boolean
  temp_token?: string
  display_name?: string
  avatar_color?: string
  second_factor_type?: string
  user_id?: string
}

export function checkDevice(deviceId: string) {
  return http.post<DeviceCheckResponse>('/auth/device/check', { device_id: deviceId })
}

export interface DeviceTrustResponse {
  session_id: string
  device_id: string
  device_name: string
  expires_at: string
}

export interface DeviceSession {
  session_id: string
  device_id: string | null
  device_name: string
  created_at: string
  last_seen_at: string
  expires_at: string
  is_current: boolean
}

export function listDevices() {
  return http.get<DeviceSession[]>('/auth/devices')
}

export function revokeDevice(sessionId: string) {
  return http.delete(`/auth/devices/${sessionId}`)
}

export function revokeAllDevices() {
  return http.delete('/auth/devices')
}

export interface FamilyDevice {
  session_id: string
  device_id: string | null
  user_id: string
  display_name: string
  avatar_color: string
  device_name: string
  last_seen_at: string
  created_at: string
  is_current: boolean
}

export async function listFamilyDevices() {
  const { data } = await http.get<FamilyDevice[]>('/auth/devices/family')
  return data
}
