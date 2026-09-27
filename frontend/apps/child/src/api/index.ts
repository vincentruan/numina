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

// ── Token refresh state ──
let isRefreshing = false
let pendingRequests: Array<{
  resolve: () => void
  reject: (error: unknown) => void
}> = []
let sessionExpired = false

function onRefreshed() {
  pendingRequests.forEach(({ resolve }) => resolve())
  pendingRequests = []
}

function onRefreshFailed(error: unknown) {
  pendingRequests.forEach(({ reject }) => reject(error))
  pendingRequests = []
}

function redirectToLogin() {
  clearAuth()
  const baseUrl = getMainBaseUrl()
  window.location.replace(`${baseUrl}/login?redirect=/child/`)
}

// Response interceptor — unwrap {code, data} envelope so callers get res.data directly
// On 401, attempt token refresh before redirecting to main login
http.interceptors.response.use(
  (response) => {
    if (response.data && typeof response.data === 'object' && 'code' in response.data && 'data' in response.data) {
      response.data = response.data.data
    }
    return response
  },
  async (error) => {
    const originalRequest = error.config as { method?: string; url?: string; data?: unknown; _retry?: boolean; _skipAuthRedirect?: boolean } | undefined

    if (axios.isAxiosError(error) && error.response?.status === 401 && !originalRequest?._retry) {
      const url = originalRequest?.url ?? ''

      // Don't redirect for auth endpoints (login should handle its own errors)
      // or when the caller explicitly opts out (non-critical calls that handle errors locally)
      if (url.includes('/auth/') || originalRequest?._skipAuthRedirect) {
        return Promise.reject(error)
      }

      // Once session is known expired, skip further refresh attempts
      if (sessionExpired) {
        redirectToLogin()
        return Promise.reject(error)
      }

      // Refresh endpoint failure = session truly expired
      if (url.includes('/auth/child/refresh')) {
        sessionExpired = true
        redirectToLogin()
        return Promise.reject(error)
      }

      // Try to refresh the child access token
      if (isRefreshing) {
        return new Promise((resolve, reject) => {
          pendingRequests.push({
            resolve: () => {
              originalRequest!._retry = true
              resolve(http(originalRequest!))
            },
            reject,
          })
        })
      }

      isRefreshing = true
      originalRequest!._retry = true

      try {
        // IMPORTANT: Send null (not {}) to avoid 422 from Pydantic validation
        await axios.post('/api/v1/auth/child/refresh', null, {
          withCredentials: true,
        })
        onRefreshed()
        return http(originalRequest!)
      } catch (refreshError) {
        onRefreshFailed(refreshError)
        sessionExpired = true
        redirectToLogin()
        return Promise.reject(refreshError)
      } finally {
        isRefreshing = false
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

// ── Export refresh logic for proactive token keep-alive ──

export async function refreshTokenIfNeeded(): Promise<void> {
  if (isRefreshing) {
    return new Promise((resolve, reject) => {
      pendingRequests.push({ resolve, reject })
    })
  }

  isRefreshing = true
  try {
    await axios.post('/api/v1/auth/child/refresh', null, {
      withCredentials: true,
    })
    onRefreshed()
  } catch (refreshError) {
    onRefreshFailed(refreshError)
    throw refreshError
  } finally {
    isRefreshing = false
  }
}
