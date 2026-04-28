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
  username: string | null  // 儿童用户名（迁移后必填，迁移前可能为 null）
  display_name: string
  avatar_color: string
  is_active: boolean
}

export interface ChildBindInfo {
  family_id: string
  family_name: string
  children: ChildUser[]
}

export interface ChildPinLoginRequest {
  child_id?: string  // 可选：UUID 方式
  username?: string  // 新增：username 方式
  pin_sequence: string[]
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
