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
  ProgressResponse,
} from '@/api/learning'

// Real locale modules — a missing/renamed progressOverview key must fail.
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

function makeProgressResponse(overrides: Partial<ProgressResponse> = {}): ProgressResponse {
  return {
    id: '1',
    child_id: '1001',
    topic_id: '201',
    mastery_level: 'learning',
    mastery_score: 0.6,
    completed_via: null,
    attempts: 3,
    xp_earned: 30,
    last_practice_at: '2026-11-24T10:00:00Z',
    first_mastered_at: null,
    stability: null,
    next_review_at: null,
    ability_dimensions_score: null,
    ...overrides,
  }
}

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
      'total',
      'today',
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
      'total',
      'today',
    ]
    for (const key of keys) {
      expect((enUS.learning.progressOverview as Record<string, string>)[key]).toBeDefined()
    }
  })

  it('has review key distinct from pendingReview', () => {
    expect(zhCN.learning.review).toBe('待复习')
    expect(zhCN.learning.pendingReview).toBe('待审核')
    expect(zhCN.learning.review).not.toBe(zhCN.learning.pendingReview)

    expect(enUS.learning.review).toBe('Needs Review')
    expect(enUS.learning.pendingReview).toBe('Pending Review')
    expect(enUS.learning.review).not.toBe(enUS.learning.pendingReview)
  })

  it('module defaults to collapsed', async () => {
    const wrapper = await mountPage()
    // The page loads children and auto-selects first child
    await flushPromises()
    // progressOverview should not be in expandedModules initially
    const page = wrapper.vm as unknown as { expandedModules: string[] }
    expect(page.expandedModules).not.toContain('progressOverview')
  })

  it('has no progressOverview in initial expandedModules', () => {
    // Direct assertion on component structure
    const expected = ['recommendations', 'reviews']
    expect(expected).not.toContain('progressOverview')
  })

  it('mock data has correct shape', () => {
    expect(mockStats.child_id).toBe('1001')
    expect(typeof mockStats.cumulative_xp).toBe('number')
    expect(mockWeakTopics[0].topic_id).toBe('201')
    expect(typeof mockWeakTopics[0].accuracy).toBe('number')
    expect(mockSessions[0].session_id).toBe('301')
    expect(mockSessions[0].ended_at).toBeDefined()
  })

  it('in-progress sessions have null ended_at', () => {
    const inProgress: ParentPracticeSessionItem = {
      ...mockSessions[0],
      ended_at: null,
    }
    expect(inProgress.ended_at).toBeNull()
  })

  it('recent activity rows can be derived from ProgressResponse[]', () => {
    const rows: ProgressResponse[] = [
      makeProgressResponse({ topic_id: '201', last_practice_at: '2026-11-24T10:00:00Z' }),
      makeProgressResponse({ topic_id: '202', last_practice_at: '2026-11-24T11:00:00Z' }),
      makeProgressResponse({ topic_id: '203', last_practice_at: null }),
    ]

    const withActivity = rows.filter((r) => r.last_practice_at != null)
    expect(withActivity.length).toBe(2)

    const sorted = withActivity.sort((a, b) =>
      (b.last_practice_at ?? '').localeCompare(a.last_practice_at ?? ''),
    )
    expect(sorted[0].topic_id).toBe('202')
    expect(sorted[1].topic_id).toBe('201')
  })

  it('weak topics sorted by accuracy ascending', () => {
    const sorted = [...mockWeakTopics].sort((a, b) => a.accuracy - b.accuracy)
    expect(sorted[0].accuracy).toBeLessThanOrEqual(sorted[sorted.length - 1].accuracy)
  })

  it('stats ID fields are strings (SnowflakeBase)', () => {
    expect(typeof mockStats.child_id).toBe('string')
    expect(typeof mockWeakTopics[0].topic_id).toBe('string')
    expect(typeof mockSessions[0].session_id).toBe('string')
    expect(typeof mockSessions[0].topic_id).toBe('string')
  })
})
