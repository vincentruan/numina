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
import { showToast } from 'vant'
import { clearAuth } from '@/utils/storage'
import router from '@/router'

const http = axios.create({
  baseURL: '/api/v1',
  timeout: 15000,
  headers: {
    'Content-Type': 'application/json'
  },
  // Ensure cookies are sent with cross-origin requests (if needed)
  // For same-origin, this is automatic
  withCredentials: true,
})

// Request interceptor - no manual Authorization header
// Cookie is automatically sent by browser
http.interceptors.request.use(
  (config) => {
    // No Authorization header needed - httpOnly Cookie is sent automatically
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
  (response) => response,
  async (error) => {
    const originalRequest = error.config as AxiosRequestConfig & { _retry?: boolean }

    if (error.response?.status === 401 && !originalRequest._retry) {
      // Don't try to refresh for login/register/refresh endpoints
      if (originalRequest.url?.includes('/auth/login') ||
          originalRequest.url?.includes('/auth/register') ||
          originalRequest.url?.includes('/auth/family/join')) {
        showToast(error.response.data?.detail || '用户名或密码错误')
        return Promise.reject(error)
      }

      // Refresh endpoint failure = session expired
      if (originalRequest.url?.includes('/auth/refresh')) {
        clearAuth()
        router.push('/login')
        showToast('登录已过期，请重新登录')
        return Promise.reject(error)
      }

      // For other 401 errors, try to refresh token
      if (isRefreshing) {
        // Queue this request until refresh completes
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
        // Refresh token - Cookie is sent automatically, no body needed
        await axios.post('/api/v1/auth/refresh', {}, {
          withCredentials: true,
        })
        // Cookie is automatically updated by server response
        onRefreshed()
        return http(originalRequest)
      } catch (refreshError) {
        onRefreshFailed(refreshError)
        clearAuth()
        router.push('/login')
        showToast('登录已过期，请重新登录')
        return Promise.reject(refreshError)
      } finally {
        isRefreshing = false
      }
    }

    // Handle other errors
    if (error.response) {
      const { status, data } = error.response
      if (status === 403) {
        showToast('没有权限执行此操作')
      } else if (status === 422 && data?.detail) {
        const msg = Array.isArray(data.detail)
          ? data.detail.map((e: any) => e.msg).join('; ')
          : data.detail
        showToast(msg)
      } else if (status !== 401) {
        showToast(data?.detail || '请求失败，请稍后重试')
      }
    } else {
      showToast('网络连接失败')
    }
    return Promise.reject(error)
  }
)

export default http