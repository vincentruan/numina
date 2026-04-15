import { ref, computed } from 'vue'
import { defineStore } from 'pinia'
import type { ChildUser } from '@/types'
import { childPinLogin, verifyParentPassword, childLogout } from '@/api/children'
import { setUser } from '@/utils/storage'

export const useChildAuthStore = defineStore('childAuth', () => {
  const childUser = ref<ChildUser | null>(null)
  const isChildSession = computed(() => childUser.value !== null)
  const loginError = ref<string | null>(null)
  const isLocked = ref(false)
  const lockMessage = ref<string | null>(null)

  async function childLogin(selectedChild: ChildUser, pin: string[]) {
    loginError.value = null
    isLocked.value = false
    lockMessage.value = null
    try {
      await childPinLogin(selectedChild.id, pin)
      childUser.value = selectedChild
      // Store child user in localStorage for route guard role check
      setUser({
        id: selectedChild.id,
        display_name: selectedChild.display_name,
        avatar_color: selectedChild.avatar_color,
        role: 'child',
      })
    } catch (err: unknown) {
      const axiosErr = err as { response?: { status?: number } }
      if (axiosErr.response?.status === 423) {
        isLocked.value = true
        lockMessage.value = '请让爸爸妈妈帮你解锁'
      } else {
        loginError.value = 'PIN错误，请重试'
      }
      throw err
    }
  }

  async function returnToAdult(password: string) {
    await verifyParentPassword(password)
    await childLogout()
    childUser.value = null
  }

  function clearChildSession() {
    childUser.value = null
  }

  return { childUser, isChildSession, loginError, isLocked, lockMessage, childLogin, returnToAdult, clearChildSession }
})
