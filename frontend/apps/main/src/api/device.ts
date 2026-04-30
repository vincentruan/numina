import http from './index'

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
