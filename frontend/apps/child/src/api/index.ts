/**
 * Axios HTTP client for frontend-child.
 * Minimal version — no Vant/router coupling.
 * Error handling is done at the component/store level.
 */

import axios from 'axios'

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

export default http
