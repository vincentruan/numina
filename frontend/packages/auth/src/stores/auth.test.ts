/**
 * Tests for auth store functions: fetchChildMe() and switchToChildAndFetch()
 */

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
import axios from 'axios'
import { useAuthStore } from './auth'
import { configureAuthHttp } from './http'
import { getUser, setUser } from '../utils/storage'
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

// Mock localStorage
const localStorageMock = (() => {
  let store: Record<string, string> = {}
  return {
    getItem: vi.fn((key: string) => store[key] || null),
    setItem: vi.fn((key: string, value: string) => {
      store[key] = value
    }),
    removeItem: vi.fn((key: string) => {
      delete store[key]
    }),
    clear: vi.fn(() => {
      store = {}
    }),
  }
})()

Object.defineProperty((globalThis as any), 'localStorage', {
  value: localStorageMock,
})

describe('auth store — switchToChildAndFetch', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    configureAuthHttp(axios as any)
    localStorageMock.clear()
    vi.clearAllMocks()
  })

  afterEach(() => {
    vi.restoreAllMocks()
  })

  const mockChildUser: User = {
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

  describe('成功路径测试', () => {
    it('应该依次调用 switch-child API、获取用户信息、更新 localStorage', async () => {
      const authStore = useAuthStore()
      const childId = '305975368354902016'

      // Mock API responses
      vi.mocked(axios.post).mockResolvedValueOnce({ status: 200 })
      vi.mocked(axios.get).mockResolvedValueOnce({ data: mockChildUser })

      // Execute
      await authStore.switchToChildAndFetch(childId)

      // Verify API call sequence
      expect(axios.post).toHaveBeenCalledWith(`/auth/admin/switch-child/${childId}`)
      expect(axios.get).toHaveBeenCalledWith('/auth/child/me')

      // Verify localStorage update
      const storedUser = getUser()
      expect(storedUser).not.toBeNull()
      expect(storedUser?.id).toBe(mockChildUser.id)
      expect(storedUser?.display_name).toBe(mockChildUser.display_name)
      expect(storedUser?.role).toBe('child')

      // Verify store state
      expect(authStore.user).toEqual(mockChildUser)
    })

    it('应该在成功后设置 user.value 为孩子用户', async () => {
      const authStore = useAuthStore()
      const childId = '305975368354902016'

      vi.mocked(axios.post).mockResolvedValueOnce({ status: 200 })
      vi.mocked(axios.get).mockResolvedValueOnce({ data: mockChildUser })

      await authStore.switchToChildAndFetch(childId)

      expect(authStore.user).toEqual(mockChildUser)
      expect(authStore.user?.role).toBe('child')
    })
  })

  describe('API 失败处理测试', () => {
    it('switch-child API 失败时应该抛出错误，不调用 child/me', async () => {
      const authStore = useAuthStore()
      const childId = 'invalid-child-id'
      const error = new Error('Child not found')

      vi.mocked(axios.post).mockRejectedValueOnce(error)

      // Execute and expect error
      await expect(authStore.switchToChildAndFetch(childId)).rejects.toThrow('Child not found')

      // Verify no subsequent API call
      expect(axios.get).not.toHaveBeenCalled()

      // Verify localStorage not updated
      expect(getUser()).toBeNull()
      expect(authStore.user).toBeNull()
    })

    it('child/me API 失败时应该抛出错误，localStorage 保持不变', async () => {
      const authStore = useAuthStore()
      const childId = '305975368354902016'
      const error = new Error('Session expired')

      // Pre-populate localStorage with adult user
      const adultUser = {
        id: '123456789',
        display_name: '测试用户',
        avatar_color: '#8B5CF6',
        role: 'owner',
      }
      setUser(adultUser)

      vi.mocked(axios.post).mockResolvedValueOnce({ status: 200 })
      vi.mocked(axios.get).mockRejectedValueOnce(error)

      // Execute and expect error
      await expect(authStore.switchToChildAndFetch(childId)).rejects.toThrow('Session expired')

      // Verify localStorage unchanged (adult user still there)
      const storedUser = getUser()
      expect(storedUser?.role).toBe('owner')
      expect(storedUser?.id).toBe(adultUser.id)

      // Verify store state unchanged
      expect(authStore.user).toBeNull()
    })

    it('网络错误时应该正确处理并抛出错误', async () => {
      const authStore = useAuthStore()
      const childId = '305975368354902016'
      const networkError = new Error('Network timeout')

      vi.mocked(axios.post).mockRejectedValueOnce(networkError)

      await expect(authStore.switchToChildAndFetch(childId)).rejects.toThrow('Network timeout')

      expect(axios.get).not.toHaveBeenCalled()
      expect(getUser()).toBeNull()
    })
  })

  describe('边缘情况测试', () => {
    it('无效 childId 格式应该由后端验证，前端正常传递', async () => {
      const authStore = useAuthStore()
      const invalidId = 'not-a-number'

      const error = new Error('Invalid child ID format')
      vi.mocked(axios.post).mockRejectedValueOnce(error)

      await expect(authStore.switchToChildAndFetch(invalidId)).rejects.toThrow()

      // Verify request was still made (backend validates)
      expect(axios.post).toHaveBeenCalledWith(`/auth/admin/switch-child/${invalidId}`)
    })

    it('空 childId 应该导致请求失败', async () => {
      const authStore = useAuthStore()
      const emptyId = ''

      const error = new Error('Bad request')
      vi.mocked(axios.post).mockRejectedValueOnce(error)

      await expect(authStore.switchToChildAndFetch(emptyId)).rejects.toThrow()
    })

    it('API 返回 null 用户数据时应该正确处理', async () => {
      const authStore = useAuthStore()
      const childId = '305975368354902016'

      vi.mocked(axios.post).mockResolvedValueOnce({ status: 200 })
      vi.mocked(axios.get).mockResolvedValueOnce({ data: null })

      // This would cause setUser to fail if not handled
      await expect(authStore.switchToChildAndFetch(childId)).rejects.toThrow()
    })

    it('并发调用应该各自独立执行（无竞态条件）', async () => {
      const authStore = useAuthStore()
      const childId1 = '305975368354902016'
      const childId2 = '305975368560422912'

      const child1User = { ...mockChildUser, id: childId1 }
      const child2User = { ...mockChildUser, id: childId2, display_name: '大宝' }

      vi.mocked(axios.post)
        .mockResolvedValueOnce({ status: 200 })
        .mockResolvedValueOnce({ status: 200 })
      vi.mocked(axios.get)
        .mockResolvedValueOnce({ data: child1User })
        .mockResolvedValueOnce({ data: child2User })

      // Execute both concurrently
      const promise1 = authStore.switchToChildAndFetch(childId1)
      const promise2 = authStore.switchToChildAndFetch(childId2)

      await Promise.all([promise1, promise2])

      // Verify both API calls happened
      expect(axios.post).toHaveBeenCalledTimes(2)
      expect(axios.get).toHaveBeenCalledTimes(2)

      // Final state depends on completion order (last write wins)
      const storedUser = getUser()
      expect(storedUser).not.toBeNull()
      expect(storedUser?.role).toBe('child')
    })
  })

  describe('console.error 日志测试', () => {
    it('失败时应该记录错误到 console.error', async () => {
      const authStore = useAuthStore()
      const childId = '305975368354902016'
      const error = new Error('Test error')

      const consoleSpy = vi.spyOn(console, 'error').mockImplementation(() => {})

      vi.mocked(axios.post).mockRejectedValueOnce(error)

      await expect(authStore.switchToChildAndFetch(childId)).rejects.toThrow()

      expect(consoleSpy).toHaveBeenCalledWith('Failed to switch to child:', error)
      consoleSpy.mockRestore()
    })
  })
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