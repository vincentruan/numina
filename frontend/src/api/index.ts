import axios from 'axios'
import type { AxiosRequestConfig } from 'axios'
import { showToast } from 'vant'
import { getToken, setToken, setRefreshToken, getRefreshToken, clearAuth } from '@/utils/storage'
import router from '@/router'

const http = axios.create({
  baseURL: '/numina/api/v1',
  timeout: 15000,
  headers: {
    'Content-Type': 'application/json'
  }
})

http.interceptors.request.use(
  (config) => {
    const token = getToken()
    if (token) {
      config.headers.Authorization = `Bearer ${token}`
    }
    return config
  },
  (error) => Promise.reject(error)
)

// Token refresh state
let isRefreshing = false
let pendingRequests: Array<{
  resolve: (token: string) => void
  reject: (error: unknown) => void
}> = []

function onRefreshed(newToken: string) {
  pendingRequests.forEach(({ resolve }) => resolve(newToken))
  pendingRequests = []
}

function onRefreshFailed(error: unknown) {
  pendingRequests.forEach(({ reject }) => reject(error))
  pendingRequests = []
}

http.interceptors.response.use(
  (response) => response,
  async (error) => {
    const originalRequest = error.config as AxiosRequestConfig & { _retry?: boolean }

    if (error.response?.status === 401 && !originalRequest._retry) {
      // Don't try to refresh if this was already a refresh request
      if (originalRequest.url?.includes('/auth/refresh')) {
        clearAuth()
        router.push('/login')
        showToast('登录已过期，请重新登录')
        return Promise.reject(error)
      }

      const refreshTokenValue = getRefreshToken()
      if (!refreshTokenValue) {
        clearAuth()
        router.push('/login')
        showToast('登录已过期，请重新登录')
        return Promise.reject(error)
      }

      if (isRefreshing) {
        // Queue this request until refresh completes
        return new Promise((resolve, reject) => {
          pendingRequests.push({
            resolve: (token: string) => {
              originalRequest.headers = { ...originalRequest.headers, Authorization: `Bearer ${token}` }
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
        const res = await axios.post('/numina/api/v1/auth/refresh', {
          refresh_token: refreshTokenValue
        })
        const { access_token, refresh_token } = res.data
        setToken(access_token)
        setRefreshToken(refresh_token)
        onRefreshed(access_token)
        originalRequest.headers = { ...originalRequest.headers, Authorization: `Bearer ${access_token}` }
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
