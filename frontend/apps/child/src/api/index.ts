import axios from 'axios'
import { clearAuth } from '@numina/auth'
import { getMainBaseUrl } from '@/utils/mainApp'

const http = axios.create({
  baseURL: '/api/v1',
  timeout: 15000,
  headers: {
    'Content-Type': 'application/json',
  },
  withCredentials: true,
})

// Request interceptor — Cookie sent automatically by browser
http.interceptors.request.use(
  (config) => {
    config.timeout = config.url?.includes('/ai/') ? 120000 : 15000
    return config
  },
  (error) => Promise.reject(error),
)

// Response interceptor — unwrap {code, data} envelope so callers get res.data directly
// On 401, clear stale localStorage session and redirect to main login
http.interceptors.response.use(
  (response) => {
    if (response.data && typeof response.data === 'object' && 'code' in response.data && 'data' in response.data) {
      response.data = response.data.data
    }
    return response
  },
  (error) => {
    const originalRequest = error.config as { method?: string; url?: string; data?: unknown } | undefined
    if (axios.isAxiosError(error) && error.response?.status === 401) {
      const url = originalRequest?.url ?? ''
      // Don't redirect for auth endpoints (login should handle its own errors)
      if (!url.includes('/auth/')) {
        clearAuth()
        // Redirect to main login (child app has no auth pages).
        // Must use getMainBaseUrl() — VITE_MAIN_APP_URL is unset, so fallback ''
        // would resolve to the child server's /login, tripping Vite's base check.
        const baseUrl = getMainBaseUrl()
        window.location.replace(`${baseUrl}/login?redirect=/child/`)
      }
    }

    // Enqueue non-GET mutations for later sync when network is unavailable
    if (!error.response || error.message?.includes('Network Error')) {
      const method = originalRequest?.method?.toUpperCase()
      if (method && method !== 'GET') {
        import('@/utils/offlineQueue').then(({ enqueue }) => {
          enqueue({
            method: method as 'POST' | 'PATCH' | 'DELETE',
            url: originalRequest?.url ?? '',
            body: originalRequest?.data,
            idempotencyKey: crypto.randomUUID(),
            tempId: (originalRequest?.data as { id?: string } | undefined)?.id,
          })
        })
      }
    }

    return Promise.reject(error)
  },
)

export default http
