// Re-export shim: useAuthStore now lives in @numina/auth
// All existing imports from '@/stores/auth' continue to work unchanged.
export { useAuthStore } from '@numina/auth'
export type { User, LoginRequest, RegisterRequest, JoinFamilyRequest } from '@numina/auth'
