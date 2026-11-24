import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { createI18n } from 'vue-i18n'
import zhCN from '@/i18n/locales/zh-CN'
import enUS from '@/i18n/locales/en-US'
import pageSource from './LearningProgressPage.vue?raw'

// --- Mocks ---

vi.mock('@/api/learning', () => ({
  getMyLearningMap: vi.fn().mockResolvedValue([]),
  getMyProgress: vi.fn().mockResolvedValue([]),
  getMyLearningStats: vi.fn().mockResolvedValue(null),
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

  it('source has no commented-out panel markers (regression guard)', () => {
    const src = pageSource as string
    const markers = [
      'xp-level-section',
      'stats-grid',
      'study-section',
      'activity-section',
      'weak-topics-section',
      'sessions-section',
    ]
    for (const marker of markers) {
      expect(src).not.toContain(marker)
    }
  })

  it('calls getMyLearningMap but NOT getMyProgress or getMyLearningStats', async () => {
    await mountPage()
    expect(mockGetMyLearningMap).toHaveBeenCalled()
    expect(mockGetMyProgress).not.toHaveBeenCalled()
    expect(mockGetMyLearningStats).not.toHaveBeenCalled()
  })

  it('heatmap renders locale-aware day labels', async () => {
    const zh = await mountPage('zh-CN')
    const en = await mountPage('en-US')
    const zhLabels = zh.findAll('.streak-dot__day').map((n) => n.text())
    const enLabels = en.findAll('.streak-dot__day').map((n) => n.text())
    expect(zhLabels).toHaveLength(7)
    expect(enLabels).toHaveLength(7)
    expect(zhLabels.join('')).not.toBe(enLabels.join(''))
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
})
