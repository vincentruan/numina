import type { AxiosInstance } from 'axios'

// Loading interceptors are managed directly in api/index.ts because the
// retry and token-refresh paths require precise increment/decrement placement
// that a generic interceptor cannot replicate safely.
// This function exists so main.ts can call it without error; it is intentionally empty.
 
export function setupLoadingInterceptor(_http: AxiosInstance) {
  // no-op: see comment above
}
