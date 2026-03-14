import http from './index'
import type { LoginRequest, RegisterRequest, JoinFamilyRequest, AuthResponse, User } from '@/types'

export function login(data: LoginRequest) {
  return http.post<AuthResponse>('/auth/login', data)
}

export function register(data: RegisterRequest) {
  return http.post<AuthResponse>('/auth/register', data)
}

export function joinFamily(data: JoinFamilyRequest) {
  return http.post<AuthResponse>('/auth/join-family', data)
}

export function getMe() {
  return http.get<User>('/auth/me')
}

export function refreshToken() {
  return http.post<AuthResponse>('/auth/refresh')
}
