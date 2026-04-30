// Shared auth-related types for @numina/auth
// Consumed by both frontend (adult app) and frontend-child (child app)

export interface User {
  id: string
  family_id: string
  username: string | null
  display_name: string
  avatar_color: string
  role: 'owner' | 'member' | 'child'
  is_active: boolean
  theme: string
  language: string
  default_currency: string
  view_mode: string
  created_at: string
}

export interface ChildUser {
  id: string
  username: string | null
  display_name: string
  avatar_color: string
  is_active: boolean
}

export interface LoginRequest {
  username: string
  password: string
  altcha?: string
}

export interface RegisterRequest {
  family_name: string
  username: string
  display_name: string
  password: string
  family_invitation_code: string
  altcha?: string
}

export interface JoinFamilyRequest {
  invite_code: string
  username: string
  display_name: string
  password: string
  altcha?: string
}

export interface LoginStep1Request {
  username: string
  password: string
  altcha?: string
}

export interface LoginStep1Response {
  second_factor_required: boolean
  temp_token?: string
  second_factor_type?: string
  // present when second_factor_required=false
  access_token?: string
  refresh_token?: string
  // user info for UI display
  user_id?: number
  display_name?: string
  avatar_color?: string
}

export interface LoginStep2Request {
  temp_token: string
  factor_type: string
  payload: Record<string, unknown>
}
