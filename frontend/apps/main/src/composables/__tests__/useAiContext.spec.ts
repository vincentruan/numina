import { describe, it, expect, vi, beforeEach } from 'vitest'
import { ref } from 'vue'

// Mutable route query so tests can vary source/id without vi.doMock races.
const routeQuery = ref<Record<string, string>>({})
const replaceMock = vi.fn()

vi.mock('vue-router', () => ({
  useRoute: () => ({ query: routeQuery.value }),
  useRouter: () => ({ replace: replaceMock }),
  // @/api/ai → @/api/index → @/router calls createRouter/createWebHistory at
  // module load; stub both so the transitive load doesn't crash.
  createRouter: () => ({ beforeEach: () => {}, afterEach: () => {}, push: () => Promise.resolve() }),
  createWebHistory: () => ({}),
}))

vi.mock('vant', () => ({
  showFailToast: vi.fn(),
}))

vi.mock('vue-i18n', () => ({
  useI18n: () => ({
    t: (k: string, params?: Record<string, unknown>) => {
      if (params && typeof params === 'object' && 'source' in params) {
        return `${k}:${String(params.source)}`
      }
      return k
    },
  }),
  // @/api/index → @/i18n calls createI18n at module load; stub it.
  createI18n: () => ({ global: { t: (k: string) => k, te: () => true } }),
}))

import { useAiContext } from '../useAiContext'
import * as aiApi from '@/api/ai'

describe('useAiContext', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    routeQuery.value = {}
    vi.restoreAllMocks()
  })

  it('returns the prefilled message on success', async () => {
    vi.spyOn(aiApi, 'getAiContext').mockResolvedValue({
      source: 'liability_detail',
      summary: '{"id":"1"}',
    })
    routeQuery.value = { source: 'liability_detail', id: '1' }
    const { loadContext } = useAiContext()
    const msg = await loadContext()
    expect(msg).toContain('{"id":"1"}')
  })

  it('returns null + toasts on fetch failure (3s timeout / 404)', async () => {
    vi.spyOn(aiApi, 'getAiContext').mockRejectedValue(new Error('404'))
    routeQuery.value = { source: 'liability_detail', id: '1' }
    const { loadContext } = useAiContext()
    const msg = await loadContext()
    expect(msg).toBeNull()
  })

  it('returns null when no source query param', async () => {
    routeQuery.value = {}
    const { loadContext } = useAiContext()
    expect(await loadContext()).toBeNull()
  })
})
