/**
 * Authentication API endpoints.
 *
 * Cookie-based auth:
 * - login/register/joinFamily: Server sets httpOnly Cookie
 * - logout: Clears server Cookie
 * - No manual token handling needed
 */

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

export function logout() {
  return http.post('/auth/logout')
}

export function getMe() {
  return http.get<User>('/auth/me')
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

export function adminSwitchToChild(childId: string) {
  return http.post<AuthResponse>('/auth/admin/switch-child/' + childId)
}