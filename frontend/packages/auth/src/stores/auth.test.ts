/**
 * Tests for auth store functions: fetchChildMe()
 */

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
import axios from 'axios'
import { useAuthStore } from './auth'
import { configureAuthHttp } from './http'
import type { User } from '../types'

// Mock axios
vi.mock('axios', () => {
  const mockAxios = {
    get: vi.fn(),
    post: vi.fn(),
  }
  return {
    default: mockAxios,
  }
})

describe('auth store — fetchChildMe', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    configureAuthHttp(axios as any)
    vi.clearAllMocks()
  })

  afterEach(() => {
    vi.restoreAllMocks()
  })

  it('应该调用 /auth/child/me 并返回用户数据', async () => {
    const authStore = useAuthStore()

    const mockUser: User = {
      id: '305975368354902016',
      family_id: '123456789',
      username: 'xiaobao',
      display_name: '小宝',
      avatar_color: '#FF6B6B',
      role: 'child',
      is_active: true,
      theme: 'light',
      language: 'zh-CN',
      default_currency: 'CNY',
      view_mode: 'card',
      created_at: '2026-01-01T00:00:00Z',
    }

    vi.mocked(axios.get).mockResolvedValueOnce({ data: mockUser })

    const result = await authStore.fetchChildMe()

    expect(axios.get).toHaveBeenCalledWith('/auth/child/me')
    expect(result).toEqual(mockUser)
  })

  it('API 失败时应该抛出错误', async () => {
    const authStore = useAuthStore()
    const error = new Error('Unauthorized')

    vi.mocked(axios.get).mockRejectedValueOnce(error)

    await expect(authStore.fetchChildMe()).rejects.toThrow('Unauthorized')
  })

  it('网络错误时应该抛出错误', async () => {
    const authStore = useAuthStore()
    const networkError = new Error('Network error')

    vi.mocked(axios.get).mockRejectedValueOnce(networkError)

    await expect(authStore.fetchChildMe()).rejects.toThrow('Network error')
  })
})
