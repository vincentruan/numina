import { computed } from 'vue'
import { useAuthStore } from '@/stores/auth'

export function useAuth() {
  const authStore = useAuthStore()

  // Check login status by user presence (token is in httpOnly Cookie)
  const isLoggedIn = computed(() => !!authStore.user)
  const currentUser = computed(() => authStore.user)
  const isOwner = computed(() => authStore.user?.role === 'owner')

  return {
    isLoggedIn,
    currentUser,
    isOwner,
    login: authStore.login,
    register: authStore.register,
    logout: authStore.logout,
    joinFamily: authStore.joinFamily
  }
}
