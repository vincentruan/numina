// Barrel export for @numina/auth

// Components
export { default as AuthStep1Form } from './components/AuthStep1Form.vue'
export { default as TrustedDeviceCard } from './components/TrustedDeviceCard.vue'
export { default as LoadingOverlay } from './components/LoadingOverlay.vue'
export { default as PixelLoading } from './components/PixelLoading.vue'
export { default as PixelLoadingOverlay } from './components/PixelLoadingOverlay.vue'

// Composables
export { useLoadingOverlay } from './composables/useLoadingOverlay'

// HTTP client configuration — call configureAuthHttp(http) in main.ts before using stores
export { configureAuthHttp } from './stores/http'

// Types
export type {
  User,
  ChildUser,
  LoginRequest,
  RegisterRequest,
  JoinFamilyRequest,
  LoginStep1Request,
  LoginStep1Response,
  LoginStep2Request,
} from './types'

// Storage utils (shared between apps)
export type { StoredUser } from './utils/storage'
export {
  getUser, setUser, removeUser, clearAuth,
} from './utils/storage'

// Device fingerprint
export { getDeviceFingerprint } from './utils/fingerprint'

// Device identity (replaces fingerprint-based device trust)
export { readDeviceId, writeDeviceId, clearDeviceId } from './utils/deviceIdentity'

// Stores
export { useAuthStore } from './stores/auth'
export { useChildAuthStore, CHILD_AUTH_ERROR } from './stores/childAuth'
export type { ChildAuthErrorCode, ChildLoginStep1Result } from './stores/childAuth'
