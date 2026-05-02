import http from './index'

export interface DeviceCheckResponse {
  trusted: boolean
  temp_token?: string
  display_name?: string
  avatar_color?: string
  second_factor_type?: string
  user_id?: number
}

export function checkDevice(fingerprint: string) {
  return http.post<DeviceCheckResponse>('/auth/device/check', { fingerprint })
}

export interface DeviceTrustResponse {
  device_id: string
  device_name: string
  expires_at: string
}

export interface DeviceSession {
  id: string
  device_name: string
  created_at: string
  last_seen_at: string
  expires_at: string
  is_current: boolean
}

export function trustDevice() {
  return http.post<DeviceTrustResponse>('/auth/device/trust')
}

export function listDevices() {
  return http.get<DeviceSession[]>('/auth/devices')
}

export function revokeDevice(deviceId: string) {
  return http.delete(`/auth/devices/${deviceId}`)
}

export function revokeAllDevices() {
  return http.delete('/auth/devices')
}

export interface FamilyDevice {
  id: number
  user_id: number
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
