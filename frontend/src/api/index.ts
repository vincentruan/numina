import axios from 'axios'
import { showToast } from 'vant'
import { getToken, clearAuth } from '@/utils/storage'
import router from '@/router'

const http = axios.create({
  baseURL: '/api/v1',
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

http.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response) {
      const { status, data } = error.response
      if (status === 401) {
        clearAuth()
        router.push('/login')
        showToast('登录已过期，请重新登录')
      } else if (status === 403) {
        showToast('没有权限执行此操作')
      } else if (status === 422 && data?.detail) {
        const msg = Array.isArray(data.detail)
          ? data.detail.map((e: any) => e.msg).join('; ')
          : data.detail
        showToast(msg)
      } else {
        showToast(data?.detail || '请求失败，请稍后重试')
      }
    } else {
      showToast('网络连接失败')
    }
    return Promise.reject(error)
  }
)

export default http
