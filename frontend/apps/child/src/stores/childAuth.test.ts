import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
import { useChildAuthStore } from '../../../../packages/auth/src/stores/childAuth'
import { configureAuthHttp } from '../../../../packages/auth/src/stores/http'
import type { AxiosInstance, AxiosResponse } from 'axios'

interface HttpCall {
  method: 'get' | 'post'
  url: string
  body?: unknown
}

function response<T>(data: T): AxiosResponse<T> {
  return {
    data,
    status: 200,
    statusText: 'OK',
    headers: {},
    config: { headers: {} },
  } as AxiosResponse<T>
}

function createHttpStub() {
  const calls: HttpCall[] = []
  const http = {
    post: async (url: string, body?: unknown) => {
      calls.push({ method: 'post', url, body })
      return response({
        second_factor_required: true,
        temp_token: 'temp-token',
        user_id: 7,
        display_name: '小星星',
        avatar_color: '#ff4d8b',
      })
    },
    get: async (url: string) => {
      calls.push({ method: 'get', url })
      return response({
        id: '7',
        username: 'kiddo',
        display_name: '小星星',
        avatar_color: '#ff4d8b',
      })
    },
  } as Pick<AxiosInstance, 'get' | 'post'>

  return { http: http as AxiosInstance, calls }
}

describe('useChildAuthStore', () => {
  const storage = new Map<string, string>()

  beforeEach(() => {
    setActivePinia(createPinia())
    storage.clear()
    vi.stubGlobal('localStorage', {
      getItem: (key: string) => storage.get(key) ?? null,
      setItem: (key: string, value: string) => storage.set(key, value),
      removeItem: (key: string) => storage.delete(key),
      clear: () => storage.clear(),
    })
  })

  afterEach(() => {
    vi.unstubAllGlobals()
    storage.clear()
  })

  it('uses the unified two-step login endpoints for child login', async () => {
    const { http, calls } = createHttpStub()
    configureAuthHttp(http)
    const store = useChildAuthStore()

    await store.childLoginStep1('kiddo', 'secret')
    await store.childLoginStep2('temp-token', ['🐱', '🐶', '🐸', '🦊'])

    expect(calls).toEqual([
      {
        method: 'post',
        url: '/auth/login/step1',
        body: { username: 'kiddo', password: 'secret' },
      },
      {
        method: 'post',
        url: '/auth/login/step2',
        body: {
          temp_token: 'temp-token',
          factor_type: 'emoji_pin',
          payload: { pin_sequence: ['🐱', '🐶', '🐸', '🦊'] },
        },
      },
      { method: 'get', url: '/auth/child/me' },
    ])
    expect(calls.some(call => call.url === '/auth/child/login')).toBe(false)
  })

  it('does not expose legacy child login helpers', () => {
    const { http } = createHttpStub()
    configureAuthHttp(http)
    const store = useChildAuthStore()
    const keys = Object.keys(store)

    expect(keys).not.toContain('childLogin')
    expect(keys).not.toContain('returnToAdult')
    expect(keys).not.toContain('clearChildSession')
  })
})
