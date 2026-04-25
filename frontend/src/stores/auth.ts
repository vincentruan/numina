/**
 * Authentication store with Cookie-based auth.
 *
 * Security Strategy (Phase 2):
 * - Tokens in httpOnly Cookie (XSS-resistant)
 * - No token stored in localStorage
 * - Logout via API call (clears server Cookie)
 */

import { defineStore } from 'pinia'
import { ref } from 'vue'
import { showToast } from 'vant'
import type { User, LoginRequest, RegisterRequest, JoinFamilyRequest } from '@/types'
import * as authApi from '@/api/auth'
import * as deviceApi from '@/api/device'
import { getUser, setUser, clearAuth } from '@/utils/storage'
import type { StoredUser } from '@/utils/storage'
import router from '@/router'
import i18n from '@/i18n'

export const useAuthStore = defineStore('auth', () => {
  // User info from localStorage (non-sensitive fields only)
  const user = ref<User | null>(getUser<User>())

  // Token ref removed - tokens now in httpOnly Cookie

  const showTrustPrompt = ref(false)

  async function login(data: LoginRequest) {
    const res = await authApi.login(data)
    // Server sets httpOnly Cookie automatically
    // Store only non-sensitive user info
    await fetchMe()
    showTrustPrompt.value = true // trigger post-login device trust prompt
  }

  async function register(data: RegisterRequest) {
    const res = await authApi.register(data)
    // Server sets httpOnly Cookie automatically
    await fetchMe()
  }

  async function joinFamily(data: JoinFamilyRequest) {
    const res = await authApi.joinFamily(data)
    // Server sets httpOnly Cookie automatically
    await fetchMe()
  }

  async function fetchMe() {
    const res = await authApi.getMe()
    user.value = res.data
    setUser(res.data as StoredUser)
  }

  async function logout() {
    // Call logout API to clear server Cookie
    try {
      await authApi.logout()
    } catch {
      // Ignore logout API errors (Cookie might already be invalid)
    }
    // Clear local state
    user.value = null
    clearAuth()
    router.push('/login')
  }

  async function trustDevice() {
    try {
      await deviceApi.trustDevice()
      showToast(i18n.global.t('toast.deviceTrustSuccess'))
    } catch {
      showToast(i18n.global.t('toast.deviceTrustFailed'))
    } finally {
      showTrustPrompt.value = false
    }
  }

  function dismissTrustPrompt() {
    showTrustPrompt.value = false
  }

  return { user, showTrustPrompt, login, register, joinFamily, fetchMe, logout, trustDevice, dismissTrustPrompt }
})