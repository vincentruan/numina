// Re-export shim: useChildAuthStore now lives in @numina/auth
// All existing imports from '@/stores/childAuth' continue to work unchanged.
export { useChildAuthStore, CHILD_AUTH_ERROR } from '@numina/auth'
export type { ChildAuthErrorCode } from '@numina/auth'
