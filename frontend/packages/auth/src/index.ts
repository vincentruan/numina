// Barrel export for @numina/auth

// HTTP client configuration — call configureAuthHttp(http) in main.ts before using stores
export { configureAuthHttp } from './stores/http'

// Types
export type {
  User,
  ChildUser,
  LoginRequest,
  RegisterRequest,
  JoinFamilyRequest,
  ChildBindInfo,
  ChildPinLoginRequest,
} from './types'

// Storage utils (shared between apps)
export type { StoredUser } from './utils/storage'
export {
  getUser, setUser, removeUser, clearAuth,
  getChildFamilyId, setChildFamilyId, clearChildFamilyId,
} from './utils/storage'

// Stores
export { useAuthStore } from './stores/auth'
export { useChildAuthStore, CHILD_AUTH_ERROR } from './stores/childAuth'
export type { ChildAuthErrorCode } from './stores/childAuth'
