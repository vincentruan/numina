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
import type { User, LoginRequest, RegisterRequest, JoinFamilyRequest } from '../types'
import type { StoredUser } from '../utils/storage'
import { getUser, setUser, clearAuth } from '../utils/storage'
import { configureAuthHttp, getHttp } from './http'

export { configureAuthHttp }

export const useAuthStore = defineStore('auth', () => {
  const user = ref<User | null>(getUser<User>())
  const showTrustPrompt = ref(false)

  async function login(data: LoginRequest) {
    await getHttp().post('/auth/login', data)
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
      await getHttp().post('/auth/device/trust')
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

  return { user, showTrustPrompt, login, register, joinFamily, fetchMe, logout, trustDevice, dismissTrustPrompt }
})
