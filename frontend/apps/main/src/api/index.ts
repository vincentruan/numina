/**
 * Axios HTTP client with Cookie-based authentication.
 *
 * Security Strategy (Phase 2):
 * - Tokens stored in httpOnly Cookie (server-set, XSS-resistant)
 * - No manual Authorization header (browser sends Cookie automatically)
 * - Refresh uses Cookie (no refresh_token in localStorage or body)
 *
 * Cookie is automatically included in requests due to:
 * - Same origin (browser behavior)
 * - withCredentials: true (for cross-origin if needed)
 */

import axios from 'axios'
import type { AxiosRequestConfig } from 'axios'
import { showToast, showDialog } from 'vant'
import { clearAuth } from '@/utils/storage'
import router from '@/router'
import i18n from '@/i18n'

const MAX_RETRIES = 2
const RETRY_BASE_DELAY_MS = 800

// Helper: resolve error code to local i18n message, fallback to backend message
function resolveErrorMsg(code: string | undefined, fallback: string): string {
  if (code) {
    const key = `errors.${code}`
    if (i18n.global.te(key)) return i18n.global.t(key)
  }
  return fallback
}

function t(key: string, params?: Record<string, unknown>): string {
  return i18n.global.t(key, params ?? {})
}

interface ApiEnvelope<T = unknown> {
  code: string
  message: string
  data: T
  request_id?: string
  details?: Array<{ field: string; code: string; msg: string }>
}

type RetryableConfig = AxiosRequestConfig & { _retry?: boolean; _retryCount?: number }

const http = axios.create({
  baseURL: '/api/v1',
  timeout: 15000,
  headers: {
    'Content-Type': 'application/json'
  },
  withCredentials: true,
})

// Request interceptor - no manual Authorization header
// Cookie is automatically sent by browser
http.interceptors.request.use(
  (config) => {
    // AI endpoints need a longer timeout for LLM response latency
    config.timeout = config.url?.includes('/ai/') ? 120000 : 15000
    return config
  },
  (error) => Promise.reject(error)
)

// Token refresh state
let isRefreshing = false
let pendingRequests: Array<{
  resolve: () => void
  reject: (error: unknown) => void
}> = []

function onRefreshed() {
  pendingRequests.forEach(({ resolve }) => resolve())
  pendingRequests = []
}

function onRefreshFailed(error: unknown) {
  pendingRequests.forEach(({ reject }) => reject(error))
  pendingRequests = []
}

// Response interceptor - handle 401 with automatic refresh
http.interceptors.response.use(
  (response) => {
    const url = response.config.url ?? ''
    // Unwrap most endpoints; keep login/register/refresh/family-join wrapped (they return tokens directly)
    // /auth/devices, /auth/me, /auth/login/step1, /auth/login/step2 should be unwrapped like regular endpoints
    const isAuthEndpoint =
      url.includes('/auth/') &&
      !url.includes('/auth/me') &&
      !url.includes('/auth/devices') &&
      !url.includes('/auth/login/step1') &&
      !url.includes('/auth/login/step2')

    // If response has envelope format, unwrap for non-auth endpoints (and /auth/me)
    if (
      !isAuthEndpoint &&
      response.data &&
      typeof response.data === 'object' &&
      'code' in response.data &&
      (response.data as ApiEnvelope).code === 'OK'
    ) {
      return { ...response, data: (response.data as ApiEnvelope).data }
    }
    return response
  },
  async (error) => {
    const originalRequest = error.config as RetryableConfig

    if (error.response?.status === 401 && !originalRequest._retry) {
      // Don't try to refresh or redirect for auth endpoints — they handle their own errors
      // This prevents a loop: LoginPage.onMounted calls checkDevice → 401 → router.push('/login') → loop
      if (originalRequest.url?.includes('/auth/')) {
        showToast(resolveErrorMsg(error.response.data?.code, error.response.data?.message || error.response.data?.detail || t('errors.AUTH_INVALID_CREDENTIALS')))
        return Promise.reject(error)
      }

      // Refresh endpoint failure = session expired
      if (originalRequest.url?.includes('/auth/refresh')) {
        clearAuth()
        showDialog({
          title: t('device.sessionExpiredTitle'),
          message: t('device.sessionExpiredMessage'),
          confirmButtonText: t('device.sessionExpiredConfirm'),
        }).then(() => {
          router.push('/login')
        })
        return Promise.reject(error)
      }

      if (isRefreshing) {
        return new Promise((resolve, reject) => {
          pendingRequests.push({
            resolve: () => {
              originalRequest._retry = true
              resolve(http(originalRequest))
            },
            reject
          })
        })
      }

      isRefreshing = true
      originalRequest._retry = true

      try {
        // IMPORTANT: Send null (not {}) to avoid 422 from Pydantic validation
        await axios.post('/api/v1/auth/refresh', null, {
          withCredentials: true,
        })
        onRefreshed()
        return http(originalRequest)
      } catch (refreshError) {
        onRefreshFailed(refreshError)
        clearAuth()
        router.push('/login')
        const re = refreshError as { response?: { data?: { code?: string; message?: string; detail?: string } } }
        showToast(resolveErrorMsg(re.response?.data?.code, re.response?.data?.message || re.response?.data?.detail || t('errors.AUTH_REFRESH_FAILED')))
        return Promise.reject(refreshError)
      } finally {
        isRefreshing = false
      }
    }

    // Retry GET requests on network error or timeout
    const isRetryable =
      !error.response &&
      originalRequest.method?.toUpperCase() === 'GET' &&
      (originalRequest._retryCount ?? 0) < MAX_RETRIES
    if (isRetryable) {
      originalRequest._retryCount = (originalRequest._retryCount ?? 0) + 1
      const delay = RETRY_BASE_DELAY_MS * 2 ** (originalRequest._retryCount - 1)
      await new Promise((r) => setTimeout(r, delay))
      return http(originalRequest)
    }

    if (error.response) {
      const { status, data } = error.response
      if (status === 403) {
        showToast(resolveErrorMsg(data?.code, data?.message || data?.detail || t('errors.FORBIDDEN')))
      } else if (status === 422) {
        if (data?.details && Array.isArray(data.details)) {
          const msg = data.details.map((e: { msg: string }) => e.msg).join('; ')
          showToast(msg || data.message || t('errors.VALIDATION_ERROR'))
        } else if (data?.detail) {
          const msg = Array.isArray(data.detail)
            ? data.detail.map((e: { msg: string }) => e.msg).join('; ')
            : data.detail
          showToast(msg)
        } else {
          showToast(data?.message || t('errors.VALIDATION_ERROR'))
        }
      } else if (status !== 401) {
        showToast(resolveErrorMsg(data?.code, data?.message || data?.detail || t('toast.requestFailed')))
      }
    } else if (error.code === 'ECONNABORTED') {
      showToast(t('toast.networkTimeout'))
    } else if (error.message?.includes('Network Error')) {
      showToast(t('toast.networkError'))
    } else {
      const errMessage = error.message || '未知错误'
      console.error('[API Error]', errMessage, error)
      showToast(errMessage.includes('CORS') ? t('toast.corsError') : t('toast.requestFailed'))
    }
    return Promise.reject(error)
  }
)

export default http
