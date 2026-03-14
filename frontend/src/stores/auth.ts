import { defineStore } from 'pinia'
import { ref } from 'vue'
import type { User, LoginRequest, RegisterRequest, JoinFamilyRequest } from '@/types'
import * as authApi from '@/api/auth'
import { getToken, setToken, removeToken, getUser, setUser, clearAuth } from '@/utils/storage'
import router from '@/router'

export const useAuthStore = defineStore('auth', () => {
  const user = ref<User | null>(getUser<User>())
  const token = ref<string | null>(getToken())

  async function login(data: LoginRequest) {
    const res = await authApi.login(data)
    token.value = res.data.access_token
    user.value = res.data.user
    setToken(res.data.access_token)
    setUser(res.data.user)
  }

  async function register(data: RegisterRequest) {
    const res = await authApi.register(data)
    token.value = res.data.access_token
    user.value = res.data.user
    setToken(res.data.access_token)
    setUser(res.data.user)
  }

  async function joinFamily(data: JoinFamilyRequest) {
    const res = await authApi.joinFamily(data)
    token.value = res.data.access_token
    user.value = res.data.user
    setToken(res.data.access_token)
    setUser(res.data.user)
  }

  async function fetchMe() {
    const res = await authApi.getMe()
    user.value = res.data
    setUser(res.data)
  }

  function logout() {
    token.value = null
    user.value = null
    clearAuth()
    router.push('/login')
  }

  return { user, token, login, register, joinFamily, fetchMe, logout }
})
