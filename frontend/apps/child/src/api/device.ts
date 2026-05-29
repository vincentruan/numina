import http from './index'

export interface DeviceCheckResponse {
  trusted: boolean
  temp_token?: string
  display_name?: string
  avatar_color?: string
  second_factor_type?: 'emoji_pin' | 'webauthn'
  user_id?: string
}

export async function checkDevice(deviceId: string): Promise<DeviceCheckResponse> {
  const { data } = await http.post<DeviceCheckResponse>('/auth/device/check', { device_id: deviceId })
  return data
}
