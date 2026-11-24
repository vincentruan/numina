import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { createI18n } from 'vue-i18n'
import { createPinia, setActivePinia } from 'pinia'
import zhCN from '@/i18n/locales/zh-CN'
import enUS from '@/i18n/locales/en-US'
import BabyLearningPage from '../BabyLearningPage.vue'
import type {
  ParentChildLearningStats,
  ParentWeakTopicItem,
  ParentPracticeSessionItem,
} from '@/api/learning'

function makeI18n(locale: 'zh-CN' | 'en-US' = 'zh-CN') {
  return createI18n({
    legacy: false,
    locale,
    messages: { 'zh-CN': zhCN, 'en-US': enUS },
  })
}

// Mock API functions
vi.mock('@/api/learning', async (importOriginal) => {
  const actual = await importOriginal<typeof import('@/api/learning')>()
  return {
    ...actual,
    getLearningChildren: vi.fn().mockResolvedValue([
      {
        child_id: '1001',
        child_name: 'Kid1',
        mastered_count: 5,
        learning_count: 3,
        available_count: 10,
        locked_count: 2,
        review_count: 1,
        total_study_minutes: 100,
        cumulative_xp: 250,
        level: 3,
        level_name_zh: '花蕾',
        learning_streak_days: 5,
      },
    ]),
    getReviews: vi.fn().mockResolvedValue([]),
    getPaths: vi.fn().mockResolvedValue([]),
    getPresetPaths: vi.fn().mockResolvedValue([]),
    getChildMap: vi.fn().mockResolvedValue([]),
    getChildSmartTutorSessions: vi.fn().mockResolvedValue([]),
    fetchChildCastle: vi.fn().mockResolvedValue({ towers: [], windows: [], streak_days: 0 }),
    getChildLearningStats: vi.fn().mockResolvedValue(null),
    getChildWeakTopics: vi.fn().mockResolvedValue([]),
    getChildPracticeSessions: vi.fn().mockResolvedValue([]),
  }
})

const mockStats: ParentChildLearningStats = {
  child_id: '1001',
  cumulative_xp: 250,
  level: 3,
  level_name_zh: '花蕾',
  level_name_en: 'Bud',
  level_emoji: '🌷',
  next_level_threshold: 600,
  next_level_name_zh: '花朵',
  learning_streak_days: 5,
  total_study_minutes: 15,
  today_study_minutes: 5,
  mastered_count: 3,
  learning_count: 2,
  available_count: 10,
  review_count: 1,
}

const mockWeakTopics: ParentWeakTopicItem[] = [
  {
    topic_id: '201',
    topic_name: 'Fractions',
    topic_name_zh: '分数',
    total_attempts: 4,
    correct_attempts: 1,
    accuracy: 0.25,
    last_practice_at: '2026-11-24T10:00:00Z',
    mastery_level: 'learning',
  },
]

const mockSessions: ParentPracticeSessionItem[] = [
  {
    session_id: '301',
    topic_id: '201',
    topic_name: 'Fractions',
    topic_name_zh: '分数',
    session_mode: 'practice',
    total_score: 0.8,
    completed_count: 5,
    total_count: 5,
    started_at: '2026-11-24T09:00:00Z',
    ended_at: '2026-11-24T09:10:00Z',
  },
]

// Mock baby store
vi.mock('@/stores/baby', () => ({
  useBabyStore: () => ({
    selectedChildId: '1001',
    selectedChildName: 'Kid1',
    selectChild: vi.fn(),
  }),
}))

import {
  getChildLearningStats,
  getChildWeakTopics,
  getChildPracticeSessions,
} from '@/api/learning'


async function mountPage(locale: 'zh-CN' | 'en-US' = 'zh-CN') {
  const pinia = createPinia()
  setActivePinia(pinia)
  const i18n = makeI18n(locale)

  const wrapper = mount(BabyLearningPage, {
    global: {
      plugins: [i18n, pinia],
      stubs: {
        PageHeader: true,
        DnaGraph2D: true,
        ParentClusterMap: true,
        ParentKnowledgeCastle: true,
        EmptyState: true,
        IIcon: true,
      },
    },
  })

  await flushPromises()
  return wrapper
}

describe('BabyLearningPage - Progress Overview', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('has progressOverview.title key in both locales', () => {
    expect(zhCN.learning.progressOverview.title).toBe('学习概览')
    expect(enUS.learning.progressOverview.title).toBe('Learning Overview')
  })

  it('has all required progressOverview keys in zh-CN', () => {
    const keys = [
      'title',
      'availableHint',
      'studyTime',
      'totalMinutes',
      'todayMinutes',
      'recentActivity',
      'noActivity',
      'weakTopics',
      'weakTopicsEmpty',
      'attempts',
      'recentSessions',
      'sessionsEmpty',
      'xp',
      'level',
      'nextLevel',
      'streakDays',
      'loadFailed',
      'retry',
    ]
    for (const key of keys) {
      expect((zhCN.learning.progressOverview as Record<string, string>)[key]).toBeDefined()
    }
  })

  it('has all required progressOverview keys in en-US', () => {
    const keys = [
      'title',
      'availableHint',
      'studyTime',
      'totalMinutes',
      'todayMinutes',
      'recentActivity',
      'noActivity',
      'weakTopics',
      'weakTopicsEmpty',
      'attempts',
      'recentSessions',
      'sessionsEmpty',
      'xp',
      'level',
      'nextLevel',
      'streakDays',
      'loadFailed',
      'retry',
    ]
    for (const key of keys) {
      expect((enUS.learning.progressOverview as Record<string, string>)[key]).toBeDefined()
    }
  })

  it('has review key distinct from pendingReview', () => {
    expect(zhCN.learning.review).toBe('待复习')
    expect(zhCN.learning.pendingReview).toBe('待审核')
    expect(zhCN.learning.review).not.toBe(zhCN.learning.pendingReview)

    expect(enUS.learning.review).toBe('Review')
    expect(enUS.learning.pendingReview).toBe('Pending Review')
    expect(enUS.learning.review).not.toBe(enUS.learning.pendingReview)
  })

  it('module defaults to collapsed', async () => {
    const wrapper = await mountPage()
      await flushPromises()
    const page = wrapper.vm as unknown as { expandedModules: string[] }
    expect(page.expandedModules).not.toContain('progressOverview')
  })

  it('renders the Learning Overview panel with mocked data when expanded', async () => {
    vi.mocked(getChildLearningStats).mockResolvedValueOnce(mockStats)
    vi.mocked(getChildWeakTopics).mockResolvedValueOnce(mockWeakTopics)
    vi.mocked(getChildPracticeSessions).mockResolvedValueOnce(mockSessions)

    const wrapper = await mountPage()
    await flushPromises()
    const page = wrapper.vm as unknown as { expandedModules: string[] }
    page.expandedModules.push('progressOverview')
    await flushPromises()
    await flushPromises()

    const text = wrapper.text()
    expect(text).toContain('学习概览')
    expect(text).toContain('花蕾')
    expect(text).toContain('250')  // cumulative XP
    expect(text).toContain('5')    // streak days
    expect(text).toContain('分数') // weak topic name
    expect(text).toContain('25%')  // weak topic accuracy
    expect(text).toContain('80%')  // session score (0.8)
    expect(text).toContain('5/5')  // session completed/total

    expect(getChildLearningStats).toHaveBeenCalledWith('1001')
    expect(getChildWeakTopics).toHaveBeenCalledWith('1001')
    expect(getChildPracticeSessions).toHaveBeenCalledWith('1001', 10, 0)
  })

  it('renders each sub-block independently on partial failure', async () => {
    vi.mocked(getChildLearningStats).mockResolvedValueOnce(mockStats)
    vi.mocked(getChildWeakTopics).mockRejectedValueOnce(new Error('fail'))
    vi.mocked(getChildPracticeSessions).mockResolvedValueOnce(mockSessions)

    const wrapper = await mountPage()
    await flushPromises()
    const page = wrapper.vm as unknown as { expandedModules: string[] }
    page.expandedModules.push('progressOverview')
    await flushPromises()
    await flushPromises()

    const text = wrapper.text()
    // Stats and sessions render despite weak-topics failure
    expect(text).toContain('花蕾')
    expect(text).toContain('80%')
    // Weak-topics error branch renders its load-failed message
    expect(text).toContain('加载失败')
  })
})

// --- Shared-concept wording, locked against the child app's locale modules ---

describe('Parent/child shared wording', () => {
  // Keys that exist on both sides with the same shape, so they must match
  // verbatim. totalMinutes/todayMinutes are excluded: the child app renders
  // them as compound strings ("分钟（总计）") while the parent uses standalone
  // labels.
  const SHARED_KEYS = [
    'studyTime',
    'recentActivity',
    'weakTopics',
    'attempts',
    'recentSessions',
  ] as const

  const STATUS_KEYS = ['mastered', 'learning', 'available', 'locked', 'review'] as const

  it('zh-CN shared progress keys match the child app verbatim', async () => {
    const child = (await import('@child-i18n/zh-CN')).default
    for (const key of SHARED_KEYS) {
      expect(
        (zhCN.learning.progressOverview as Record<string, string>)[key],
        `zh-CN ${key}`,
      ).toBe(child.learning.progress[key])
    }
  })

  it('en-US shared progress keys match the child app verbatim', async () => {
    const child = (await import('@child-i18n/en-US')).default
    for (const key of SHARED_KEYS) {
      expect(
        (enUS.learning.progressOverview as Record<string, string>)[key],
        `en-US ${key}`,
      ).toBe(child.learning.progress[key])
    }
  })

  it('zh-CN status words match the child app verbatim', async () => {
    const child = (await import('@child-i18n/zh-CN')).default
    for (const key of STATUS_KEYS) {
      expect((zhCN.learning as Record<string, string>)[key], `zh-CN ${key}`).toBe(
        (child.learning.status as Record<string, string>)[key],
      )
    }
  })

  it('en-US status words match the child app verbatim', async () => {
    const child = (await import('@child-i18n/en-US')).default
    for (const key of STATUS_KEYS) {
      expect((enUS.learning as Record<string, string>)[key], `en-US ${key}`).toBe(
        (child.learning.status as Record<string, string>)[key],
      )
    }
  })

  it('review is never rendered as the pending-review wording', () => {
    expect(zhCN.learning.review).not.toBe(zhCN.learning.pendingReview)
    expect(enUS.learning.review).not.toBe(enUS.learning.pendingReview)
  })
})
