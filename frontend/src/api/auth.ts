import http from './index'
import type { LoginRequest, RegisterRequest, JoinFamilyRequest, AuthResponse, User } from '@/types'

export function login(data: LoginRequest) {
  return http.post<AuthResponse>('/auth/login', data)
}

export function register(data: RegisterRequest) {
  return http.post<AuthResponse>('/auth/register', data)
}

export function joinFamily(data: JoinFamilyRequest) {
  return http.post<AuthResponse>('/auth/family/join', data)
}

export function getMe() {
  return http.get<User>('/auth/me')
}

export function refreshToken(refreshToken: string) {
  return http.post<AuthResponse>('/auth/refresh', { refresh_token: refreshToken })
}

interface UpdateSettingsRequest {
  theme?: string
  language?: string
  default_currency?: string
  view_mode?: string
}

export function updateSettings(data: UpdateSettingsRequest) {
  return http.put<User>('/auth/me/settings', data)
}
