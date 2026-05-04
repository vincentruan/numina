import axios from 'axios'
import { clearAuth, useLoadingOverlay } from '@numina/auth'

const http = axios.create({
  baseURL: '/api/v1',
  timeout: 15000,
  headers: {
    'Content-Type': 'application/json',
  },
  withCredentials: true,
})

const { increment: loadingIncrement, decrement: loadingDecrement } = useLoadingOverlay()

// Request interceptor — Cookie sent automatically by browser
http.interceptors.request.use(
  (config) => {
    config.timeout = config.url?.includes('/ai/') ? 120000 : 15000
    loadingIncrement()
    return config
  },
  (error) => {
    loadingDecrement()
    return Promise.reject(error)
  },
)

// Response interceptor — unwrap {code, data} envelope so callers get res.data directly
// On 401, clear stale localStorage session and redirect to login
http.interceptors.response.use(
  (response) => {
    loadingDecrement()
    if (response.data && typeof response.data === 'object' && 'code' in response.data && 'data' in response.data) {
      response.data = response.data.data
    }
    return response
  },
  (error) => {
    loadingDecrement()
    if (axios.isAxiosError(error) && error.response?.status === 401) {
      const url = error.config?.url ?? ''
      // Don't redirect on auth endpoints themselves (login, refresh)
      if (!url.includes('/auth/')) {
        clearAuth()
        window.location.replace('/child/auth')
      }
    }
    return Promise.reject(error)
  },
)

export default http
