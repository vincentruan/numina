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
import { showFailToast } from 'vant'
import { clearAuth } from '@/utils/storage'
import router from '@/router'
import i18n from '@/i18n'

// Extend AxiosRequestConfig to support silent error code suppression.
// When a request's error code is in this list, the global interceptor skips the toast
// so the caller can handle it locally (e.g. empty state instead of error).
declare module 'axios' {
  interface AxiosRequestConfig<D = any> {
    _silentErrorCodes?: string[]
  }
}

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

// Prevent concurrent router.push('/login') calls from racing with user-initiated navigation.
// Without this, multiple 401 responses can abort an in-flight tab navigation and then
// bounce back to the original page if localStorage is restored by a concurrent fetchMe().
let isRedirectingToLogin = false
function redirectToLogin() {
  if (isRedirectingToLogin) return
  const currentPath = router.currentRoute.value.path
  if (currentPath === '/login' || currentPath === '/register' || currentPath === '/join-family') return
  isRedirectingToLogin = true
  router.replace('/login').finally(() => {
    isRedirectingToLogin = false
  })
}

// Once the session is known expired, suppress further refresh attempts to
// prevent cascading 401 → refresh → 401 loops from concurrent requests.
let sessionExpired = false

// Response interceptor - handle 401 with automatic refresh
http.interceptors.response.use(
  (response) => {
    const url = response.config.url ?? ''
    // Unwrap most endpoints; keep login/register/refresh/family-join wrapped (they return tokens directly)
    // /auth/device/*, /auth/devices/*, /auth/me, /auth/login/step1, /auth/login/step2
    // return EnvelopeResponse and must be unwrapped like regular endpoints.
    // Note: '/auth/device' matches both singular (/device/trust) and plural (/devices).
    const isAuthEndpoint =
      url.includes('/auth/') &&
      !url.includes('/auth/me') &&
      !url.includes('/auth/device') &&
      !url.includes('/auth/login/step1') &&
      !url.includes('/auth/login/step2')


    // Check for auth errors in response body (HTTP 200 with code like AUTH_TOKEN_EXPIRED)
    // Backend sometimes returns 200 with error code instead of 401 for certain auth failures
    if (
      response.data &&
      typeof response.data === 'object' &&
      'code' in response.data
    ) {
      const code = (response.data as ApiEnvelope).code
      if (
        code === 'AUTH_TOKEN_EXPIRED' ||
        code === 'AUTH_INVALID_TOKEN' ||
        code === 'AUTH_SESSION_NOT_FOUND'
      ) {
        clearAuth()
        redirectToLogin()
        showFailToast(resolveErrorMsg(code, (response.data as ApiEnvelope).message || t('errors.AUTH_TOKEN_EXPIRED')))
        return Promise.reject(new Error(code))
      }
    }

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
      // Once session is known expired, skip further refresh attempts to
      // prevent cascading 401 → refresh → 401 loops from concurrent requests.
      if (sessionExpired) {
        return Promise.reject(error)
      }

      // Refresh endpoint failure = session expired (check before the broader
      // auth exclusion so it is not unreachable)
      if (originalRequest.url?.includes('/auth/refresh')) {
        clearAuth()
        sessionExpired = true
        // Redirect immediately — do NOT block on showDialog, which may fail
        // to render in embedded browsers (Lark/Feishu WebView) and leave the
        // user stuck on a blank page with no interactive element.
        redirectToLogin()
        showFailToast(t('device.sessionExpiredMessage'))
        return Promise.reject(error)
      }

      // Don't try to refresh or redirect for login/register endpoints — they
      // handle their own errors. This prevents a loop: LoginPage.onMounted
      // calls checkDevice → 401 → router.push('/login') → loop.
      // /auth/me and /auth/devices ARE allowed to trigger refresh so that an
      // expired access cookie is silently renewed instead of showing a toast.
      if (
        originalRequest.url?.includes('/auth/login') ||
        originalRequest.url?.includes('/auth/register')
      ) {
        showFailToast(resolveErrorMsg(error.response.data?.code, error.response.data?.message || error.response.data?.detail || t('errors.AUTH_INVALID_CREDENTIALS')))
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
        sessionExpired = true
        redirectToLogin()
        // Safe type narrowing with axios.isAxiosError()
        if (axios.isAxiosError(refreshError)) {
          showFailToast(resolveErrorMsg(refreshError.response?.data?.code, refreshError.response?.data?.message || refreshError.response?.data?.detail || t('errors.AUTH_REFRESH_FAILED')))
        } else {
          showFailToast(t('errors.AUTH_REFRESH_FAILED'))
        }
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
      const silentCodes = (error.config as RetryableConfig)?._silentErrorCodes
      if (silentCodes?.includes(data?.code)) {
        // Caller handles this error code locally — skip global toast
      } else if (status === 403) {
        showFailToast(resolveErrorMsg(data?.code, data?.message || data?.detail || t('errors.FORBIDDEN')))
      } else if (status === 422) {
        if (data?.details && Array.isArray(data.details)) {
          const msg = data.details.map((e: { msg: string }) => e.msg).join('; ')
          showFailToast(msg || data.message || t('errors.VALIDATION_ERROR'))
        } else if (data?.detail) {
          const msg = Array.isArray(data.detail)
            ? data.detail.map((e: { msg: string }) => e.msg).join('; ')
            : data.detail
          showFailToast(msg)
        } else {
          showFailToast(data?.message || t('errors.VALIDATION_ERROR'))
        }
      } else if (status !== 401) {
        showFailToast(resolveErrorMsg(data?.code, data?.message || data?.detail || t('toast.requestFailed')))
      }
    } else if (error.code === 'ECONNABORTED') {
      showFailToast(t('toast.networkTimeout'))
    } else if (error.message?.includes('Network Error')) {
      showFailToast(t('toast.networkError'))
    } else {
      const errMessage = error.message || '未知错误'
      console.error('[API Error]', errMessage, error)
      showFailToast(errMessage.includes('CORS') ? t('toast.corsError') : t('toast.requestFailed'))
    }
    return Promise.reject(error)
  }
)

export default http

// ── Export refresh logic for fetch-based streaming requests ─────────────────────

export async function refreshTokenIfNeeded(): Promise<void> {
  // If already refreshing, wait for it to complete
  if (isRefreshing) {
    return new Promise((resolve, reject) => {
      pendingRequests.push({ resolve, reject })
    })
  }

  isRefreshing = true
  try {
    // IMPORTANT: Send null (not {}) to avoid 422 from Pydantic validation
    await axios.post('/api/v1/auth/refresh', null, {
      withCredentials: true,
    })
    onRefreshed()
  } catch (refreshError) {
    onRefreshFailed(refreshError)
    clearAuth()
    sessionExpired = true
    redirectToLogin()
    // Safe type narrowing with axios.isAxiosError()
    if (axios.isAxiosError(refreshError)) {
      showFailToast(resolveErrorMsg(refreshError.response?.data?.code, refreshError.response?.data?.message || refreshError.response?.data?.detail || t('errors.AUTH_REFRESH_FAILED')))
    } else {
      showFailToast(t('errors.AUTH_REFRESH_FAILED'))
    }
    throw refreshError
  } finally {
    isRefreshing = false
  }
}
