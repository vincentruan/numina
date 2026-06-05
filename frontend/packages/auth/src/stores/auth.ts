/**
 * Authentication store for @numina/auth
 *
 * Extracted from frontend/src/stores/auth.ts.
 * Router navigation and toast calls removed — handled by app layer via callbacks.
 * HTTP client injected via configureAuthHttp() at app startup.
 *
 * Security Strategy:
 * - Tokens in httpOnly Cookie (XSS-resistant)
 * - No token stored in localStorage
 * - Logout via API call (clears server Cookie)
 */

import { defineStore } from 'pinia'
import { ref } from 'vue'
import type { User, LoginRequest, RegisterRequest, JoinFamilyRequest, LoginStep1Request, LoginStep1Response, LoginStep2Request } from '../types'
import type { StoredUser } from '../utils/storage'
import { getUser, setUser, clearAuth } from '../utils/storage'
import { configureAuthHttp, getHttp } from './http'
import { readDeviceId, writeDeviceId } from '../utils/deviceIdentity'

export { configureAuthHttp }

export const useAuthStore = defineStore('auth', () => {
  const user = ref<User | null>(getUser() as User | null)
  const showTrustPrompt = ref(false)

  async function login(data: LoginRequest) {
    await getHttp().post('/auth/login', data)
    await fetchMe()
    showTrustPrompt.value = true
  }

  async function loginStep1(data: LoginStep1Request): Promise<LoginStep1Response> {
    const res = await getHttp().post<LoginStep1Response>('/auth/login/step1', data)
    return res.data
  }

  async function loginStep2(data: LoginStep2Request): Promise<void> {
    await getHttp().post('/auth/login/step2', data)
    await fetchMe()
    showTrustPrompt.value = true
  }
  async function register(data: RegisterRequest) {
    await getHttp().post('/auth/register', data)
    await fetchMe()
  }

  async function joinFamily(data: JoinFamilyRequest) {
    await getHttp().post('/auth/family/join', data)
    await fetchMe()
  }

  async function fetchMe() {
    const res = await getHttp().get<User>('/auth/me')
    user.value = res.data
    setUser(res.data as StoredUser)
  }

  async function fetchChildMe(): Promise<User> {
    const res = await getHttp().get<User>('/auth/child/me')
    return res.data
  }

  async function logout(options?: { onLogout?: () => void }) {
    try {
      await getHttp().post('/auth/logout')
    } catch {
      // Ignore logout API errors (Cookie might already be invalid)
    }
    user.value = null
    clearAuth()
    options?.onLogout?.()
  }

  async function trustDevice(options?: { onSuccess?: () => void; onError?: () => void }) {
    try {
      const deviceId = await readDeviceId()
      const { data } = await getHttp().post<{ device_id: string }>('/auth/device/trust', { device_id: deviceId })
      await writeDeviceId(data.device_id)
      // Establish ETag in browser HTTP cache so device_id survives cookie + localStorage clearing
      fetch('/api/v1/auth/device-ping', {
        credentials: 'same-origin',
        headers: { 'If-None-Match': `"${data.device_id}"` },
      })
      options?.onSuccess?.()
    } catch {
      options?.onError?.()
    } finally {
      showTrustPrompt.value = false
    }
  }

  function dismissTrustPrompt() {
    showTrustPrompt.value = false
  }

  return { user, showTrustPrompt, login, loginStep1, loginStep2, register, joinFamily, fetchMe, fetchChildMe, logout, trustDevice, dismissTrustPrompt }
})
