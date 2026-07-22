import { mount, flushPromises } from '@vue/test-utils'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import FinanceCoachCard from '../FinanceCoachCard.vue'

// Mock vue-i18n: component uses useI18n for the title/refresh/disclaimer strings.
// @/api/index → @/i18n also calls createI18n at module load, so stub it too.
vi.mock('vue-i18n', () => ({
  useI18n: () => ({
    t: (key: string) => key,
  }),
  createI18n: () => ({ global: { t: (k: string) => k, te: () => true } }),
}))

// Mock vue-router: component uses useRouter for CTA navigation, and the @/api/ai
// → @/api/index → @/router import chain calls createRouter/createWebHistory at
// module load. Stub both so the transitive load doesn't crash. (vi.mock is
// hoisted above pushMock, so createRouter must not reference it.)
const pushMock = vi.fn()
vi.mock('vue-router', () => ({
  useRouter: () => ({ push: pushMock }),
  createRouter: () => ({ beforeEach: () => {}, afterEach: () => {}, push: () => Promise.resolve() }),
  createWebHistory: () => ({}),
}))

// Mock vant showFailToast so it doesn't touch the DOM
vi.mock('vant', () => ({
  showFailToast: vi.fn(),
}))

// Spy the API client. The component imports getFinanceCoach from '@/api/ai'.
import * as aiApi from '@/api/ai'

const mockSuggestion = (
  id: string,
  severity: 'high' | 'medium' | 'low',
) => ({
  id,
  severity,
  title: `建议${id}`,
  action: '行动',
  target_type: 'liability' as const,
  target_id: '1',
  cta_label: '查看',
})

describe('FinanceCoachCard', () => {
  beforeEach(() => {
    vi.restoreAllMocks()
    pushMock.mockReset()
  })

  it('renders up to 3 suggestions with severity color bars', async () => {
    vi.spyOn(aiApi, 'getFinanceCoach').mockResolvedValue({
      status: 'cached',
      generated_at: '2026-07-19T10:00:00',
      report: {
        suggestions: [
          mockSuggestion('1', 'high'),
          mockSuggestion('2', 'medium'),
          mockSuggestion('3', 'low'),
          mockSuggestion('4', 'high'),
        ],
      },
    })
    const wrapper = mount(FinanceCoachCard, {
      global: { stubs: ['van-button', 'van-skeleton'] },
    })
    await flushPromises()
    // Only top 3 rendered (spec §7.2 "前 3 条").
    expect(wrapper.findAll('[data-test^="suggestion-"]')).toHaveLength(3)
    expect(wrapper.find('[data-test="suggestion-1"]').classes()).toContain(
      'severity-high',
    )
  })

  it('hides silently when suggestions is empty', async () => {
    vi.spyOn(aiApi, 'getFinanceCoach').mockResolvedValue({
      status: 'cached',
      generated_at: '2026-07-19T10:00:00',
      report: { suggestions: [] },
    })
    const wrapper = mount(FinanceCoachCard, {
      global: { stubs: ['van-button', 'van-skeleton'] },
    })
    await flushPromises()
    expect(wrapper.find('[data-test="finance-coach-card"]').exists()).toBe(false)
  })

  it('hides silently on fetch failure', async () => {
    vi.spyOn(aiApi, 'getFinanceCoach').mockRejectedValue(new Error('network'))
    const wrapper = mount(FinanceCoachCard, {
      global: { stubs: ['van-button', 'van-skeleton'] },
    })
    await flushPromises()
    expect(wrapper.find('[data-test="finance-coach-card"]').exists()).toBe(false)
  })
})
