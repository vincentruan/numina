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

vi.mock('@/stores/family', () => ({
  useFamilyStore: () => ({
    aiEnabled: true,
  }),
}))

vi.mock('@/stores/auth', () => ({
  useAuthStore: () => ({
    user: { role: 'owner' },
  }),
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

const globalStubs = {
  'van-button': true,
  'van-skeleton': true,
  'van-cell-group': true,
  'van-collapse': true,
  'van-collapse-item': true,
  'van-loading': true,
  'van-empty': true,
  IIcon: true,
}

describe('FinanceCoachCard', () => {
  beforeEach(() => {
    vi.restoreAllMocks()
    pushMock.mockReset()
  })

  it('renders up to 3 suggestions with severity color bars when expanded', async () => {
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
    const wrapper = mount(FinanceCoachCard, { global: { stubs: globalStubs } })
    await flushPromises()
    // Card always renders (collapsed by default)
    expect(wrapper.find('[data-test="finance-coach-card"]').exists()).toBe(true)
    // Only top 3 rendered (spec §7.2 "前 3 条")
    expect(wrapper.findAll('[data-test^="suggestion-"]')).toHaveLength(3)
    expect(wrapper.find('[data-test="suggestion-1"]').classes()).toContain(
      'severity-high',
    )
  })

  it('shows empty summary when suggestions is empty', async () => {
    vi.spyOn(aiApi, 'getFinanceCoach').mockResolvedValue({
      status: 'cached',
      generated_at: '2026-07-19T10:00:00',
      report: { suggestions: [] },
    })
    const wrapper = mount(FinanceCoachCard, { global: { stubs: globalStubs } })
    await flushPromises()
    // Card still renders (collapsed), showing empty summary text
    expect(wrapper.find('[data-test="finance-coach-card"]').exists()).toBe(true)
    expect(wrapper.find('.coach-summary--empty').exists()).toBe(true)
  })

  it('shows empty summary on fetch failure', async () => {
    vi.spyOn(aiApi, 'getFinanceCoach').mockRejectedValue(new Error('network'))
    const wrapper = mount(FinanceCoachCard, { global: { stubs: globalStubs } })
    await flushPromises()
    // Card still renders (collapsed), showing empty summary text
    expect(wrapper.find('[data-test="finance-coach-card"]').exists()).toBe(true)
    expect(wrapper.find('.coach-summary--empty').exists()).toBe(true)
  })
})
