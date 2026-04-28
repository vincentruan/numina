/**
 * Child authentication store for @numina/auth
 *
 * Extracted from frontend/src/stores/childAuth.ts.
 * Hard-coded Chinese strings replaced with error code constants.
 * HTTP client injected via configureAuthHttp() at app startup.
 */

import { ref, computed } from 'vue'
import { defineStore } from 'pinia'
import axios from 'axios'
import type { ChildUser } from '../types'
import { setUser, removeUser } from '../utils/storage'
import { getHttp } from './http'

// Error code constants — app layer maps these to i18n keys
export const CHILD_AUTH_ERROR = {
  PIN_ERROR: 'PIN_ERROR',
  ACCOUNT_LOCKED: 'ACCOUNT_LOCKED',
} as const

export type ChildAuthErrorCode = (typeof CHILD_AUTH_ERROR)[keyof typeof CHILD_AUTH_ERROR]

export const useChildAuthStore = defineStore('childAuth', () => {
  const childUser = ref<ChildUser | null>(null)
  const isChildSession = computed(() => childUser.value !== null)
  const loginError = ref<ChildAuthErrorCode | null>(null)
  const isLocked = ref(false)
  const lockMessage = ref<ChildAuthErrorCode | null>(null)

  async function childLogin(selectedChild: ChildUser, pin: string[]) {
    loginError.value = null
    isLocked.value = false
    lockMessage.value = null
    try {
      const payload: { pin_sequence: string[]; child_id?: string; username?: string } = {
        pin_sequence: pin,
      }
      if (selectedChild.username) {
        payload.username = selectedChild.username
      } else {
        payload.child_id = selectedChild.id
      }
      await getHttp().post('/auth/child/login', payload)
      childUser.value = selectedChild
      setUser({
        id: selectedChild.id,
        display_name: selectedChild.display_name,
        avatar_color: selectedChild.avatar_color,
        role: 'child',
      })
    } catch (err: unknown) {
      if (axios.isAxiosError(err) && err.response?.status === 423) {
        isLocked.value = true
        lockMessage.value = CHILD_AUTH_ERROR.ACCOUNT_LOCKED
      } else {
        loginError.value = CHILD_AUTH_ERROR.PIN_ERROR
      }
      throw err
    }
  }

  async function returnToAdult(password: string) {
    await getHttp().post('/auth/child/verify-parent', { password })
    childUser.value = null
    removeUser()
    try {
      await getHttp().post('/auth/child/logout')
    } catch {
      // Best-effort: server-side cookie cleared when it expires
    }
  }

  function clearChildSession() {
    childUser.value = null
  }

  function clearLoginError() {
    loginError.value = null
  }

  return {
    childUser,
    isChildSession,
    loginError,
    isLocked,
    lockMessage,
    childLogin,
    returnToAdult,
    clearChildSession,
    clearLoginError,
  }
})
