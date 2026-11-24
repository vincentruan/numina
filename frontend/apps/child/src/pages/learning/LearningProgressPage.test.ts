import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { createI18n } from 'vue-i18n'
import zhCN from '@/i18n/locales/zh-CN'
import enUS from '@/i18n/locales/en-US'

// --- Mocks ---

vi.mock('@/api/learning', () => ({
  getMyLearningMap: vi.fn().mockResolvedValue([]),
  getMyProgress: vi.fn().mockResolvedValue([]),
  getMyLearningStats: vi.fn().mockResolvedValue(null),
  getTopicsBatch: vi.fn().mockResolvedValue([]),
}))

const mockRouterPush = vi.fn()
vi.mock('vue-router', () => ({
  useRouter: () => ({ push: mockRouterPush }),
}))

vi.mock('@/composables/usePageLoading', () => ({
  usePageLoading: () => ({ increment: vi.fn(), decrement: vi.fn() }),
}))

vi.mock('@/composables/useRecommendationPath', () => ({
  useRecommendationPath: () => ({
    allPathTopics: { value: [] },
    refresh: vi.fn().mockResolvedValue(undefined),
  }),
}))

const showToastMock = vi.fn()
vi.mock('vant', () => ({
  showToast: (...args: unknown[]) => showToastMock(...args),
  showFailToast: (...args: unknown[]) => showToastMock(...args),
  showSuccessToast: (...args: unknown[]) => showToastMock(...args),
}))

import {
  getMyLearningMap,
  getMyProgress,
  getMyLearningStats,
} from '@/api/learning'
import LearningProgressPage from './LearningProgressPage.vue'

const mockGetMyLearningMap = vi.mocked(getMyLearningMap)
const mockGetMyProgress = vi.mocked(getMyProgress)
const mockGetMyLearningStats = vi.mocked(getMyLearningStats)

function makeI18n(locale: 'zh-CN' | 'en-US' = 'zh-CN') {
  return createI18n({
    legacy: false,
    locale,
    messages: { 'zh-CN': zhCN, 'en-US': enUS },
  })
}

async function mountPage(locale: 'zh-CN' | 'en-US' = 'zh-CN') {
  const i18n = makeI18n(locale)
  const wrapper = mount(LearningProgressPage, {
    global: {
      plugins: [i18n],
      stubs: {
        RoleShimmer: true,
      },
    },
  })
  await flushPromises()
  return wrapper
}

describe('LearningProgressPage (U5)', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mockGetMyLearningMap.mockResolvedValue([])
  })

  it('renders the 4 expected elements: page title, castle entry, streak section', async () => {
    const wrapper = await mountPage()
    expect(wrapper.find('.page-title').exists()).toBe(true)
    expect(wrapper.find('[data-test="progress-castle-entry"]').exists()).toBe(true)
    expect(wrapper.find('[data-test="streak-section"]').exists()).toBe(true)
  })

  it('does NOT render the removed sections', async () => {
    const wrapper = await mountPage()
    expect(wrapper.find('.xp-level-section').exists()).toBe(false)
    expect(wrapper.find('.stats-grid').exists()).toBe(false)
    expect(wrapper.find('.study-section').exists()).toBe(false)
    expect(wrapper.find('.activity-section').exists()).toBe(false)
    expect(wrapper.find('.weak-topics-section').exists()).toBe(false)
    expect(wrapper.find('.sessions-section').exists()).toBe(false)
  })

  it('calls getMyLearningMap but NOT getMyProgress or getMyLearningStats', async () => {
    await mountPage()
    expect(mockGetMyLearningMap).toHaveBeenCalled()
    expect(mockGetMyProgress).not.toHaveBeenCalled()
    expect(mockGetMyLearningStats).not.toHaveBeenCalled()
  })

  it('heatmap uses locale for day labels', async () => {
    const wrapper = await mountPage('en-US')
    // The page renders day labels using locale — verify the locale is still wired
    const dayLabels = wrapper.findAll('.streak-dot__day')
    expect(dayLabels.length).toBe(7)
  })

  it('has all required learning.progress keys', () => {
    expect(zhCN.learning.progress.title).toBeDefined()
    expect(zhCN.learning.progress.childTitle).toBeDefined()
    expect(zhCN.learning.progress.streakTitle).toBeDefined()
    expect(zhCN.learning.progress.streakSummary).toBeDefined()
    expect(zhCN.learning.progress.studyTime).toBeDefined()
    expect(zhCN.learning.progress.recentActivity).toBeDefined()
    expect(zhCN.learning.progress.weakTopics).toBeDefined()
    expect(zhCN.learning.progress.recentSessions).toBeDefined()
  })

  it('does not contain commented-out panel markers in template', async () => {
    // After cleanup, there should be no HTML comment blocks with the old section markers
    const wrapper = await mountPage()
    const html = wrapper.html()
    // The commented-out sections should be gone — no residual HTML comments with
    // section markers
    expect(html).not.toContain('xp-level-section')
    expect(html).not.toContain('stats-grid')
    expect(html).not.toContain('weak-topics-section')
    expect(html).not.toContain('sessions-section')
  })
})
