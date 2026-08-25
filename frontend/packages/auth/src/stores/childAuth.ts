/**
 * Child authentication store for @numina/auth
 *
 * Extracted from frontend/src/stores/childAuth.ts.
 * Hard-coded Chinese strings replaced with error code constants.
 * HTTP client injected via configureAuthHttp() at app startup.
 */

import { ref } from 'vue'
import { defineStore } from 'pinia'
import axios from 'axios'
import type { ChildUser } from '../types'
import { setUser, removeUser } from '../utils/storage'
import { getHttp } from './http'

// Error code constants — app layer maps these to i18n keys
export const CHILD_AUTH_ERROR = {
  PIN_ERROR: 'PIN_ERROR',
  ACCOUNT_LOCKED: 'ACCOUNT_LOCKED',
  INVALID_CREDENTIALS: 'INVALID_CREDENTIALS',
} as const

export type ChildAuthErrorCode = (typeof CHILD_AUTH_ERROR)[keyof typeof CHILD_AUTH_ERROR]

export interface ChildLoginStep1Result {
  second_factor_required: boolean
  temp_token?: string
  second_factor_type?: string
  // user info always present
  user_id?: string
  display_name?: string
  avatar_color?: string
}

export const useChildAuthStore = defineStore('childAuth', () => {
  const childUser = ref<ChildUser | null>(null)
  const loginError = ref<ChildAuthErrorCode | null>(null)
  const isLocked = ref(false)
  const lockMessage = ref<ChildAuthErrorCode | null>(null)

  // Two-stage login: step 1 — username + password + altcha
  async function childLoginStep1(username: string, password: string, altcha?: string): Promise<ChildLoginStep1Result> {
    loginError.value = null
    isLocked.value = false
    lockMessage.value = null
    try {
      const res = await getHttp().post<ChildLoginStep1Result>('/auth/login/step1', {
        username,
        password,
        ...(altcha ? { altcha } : {}),
      })
      return res.data
    } catch (err: unknown) {
      if (axios.isAxiosError(err) && err.response?.status === 423) {
        isLocked.value = true
        lockMessage.value = CHILD_AUTH_ERROR.ACCOUNT_LOCKED
      } else {
        loginError.value = CHILD_AUTH_ERROR.INVALID_CREDENTIALS
      }
      throw err
    }
  }

  // Two-stage login: step 2 — emoji PIN
  async function childLoginStep2(tempToken: string, pinSequence: string[]): Promise<void> {
    loginError.value = null
    try {
      await getHttp().post(
        '/auth/login/step2',
        {
          temp_token: tempToken,
          factor_type: 'emoji_pin',
          payload: { pin_sequence: pinSequence },
        },
      )
      // Fetch user info after successful login
      const meRes = await getHttp().get<{ id: string; display_name: string; avatar_color: string; username: string }>('/auth/child/me')
      const me = meRes.data
      const child: ChildUser = {
        id: String(me.id),
        username: me.username,
        display_name: me.display_name,
        avatar_color: me.avatar_color,
        is_active: true,
      }
      childUser.value = child
      setUser({
        id: child.id,
        display_name: child.display_name,
        avatar_color: child.avatar_color,
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

  async function childLogout() {
    try {
      await getHttp().post('/auth/child/logout')
    } catch {
      // Ignore logout API errors (Cookie might already be invalid)
    }
    childUser.value = null
    removeUser()
  }

  function clearLoginError() {
    loginError.value = null
  }

  return {
    childUser,
    loginError,
    isLocked,
    lockMessage,
    childLoginStep1,
    childLoginStep2,
    childLogout,
    clearLoginError,
  }
})
