import { describe, it, expect, vi, beforeEach } from 'vitest'

// router/index.ts pulls in nprogress, auth and the loading composable at
// module scope; none of them matter to the guard predicate.
vi.mock('nprogress', () => ({
  default: { start: vi.fn(), done: vi.fn(), configure: vi.fn() },
}))
vi.mock('nprogress/nprogress.css', () => ({}))
vi.mock('@/utils/mainApp', () => ({ getMainBaseUrl: () => 'http://main' }))
vi.mock('@/composables/usePageLoading', () => ({
  globalLoadingCount: { value: 0 },
  completeGlobalLoading: vi.fn(),
  registerRouterTimeout: vi.fn(),
  markRouterNprogressActive: vi.fn(),
}))
vi.mock('@numina/auth', () => ({
  useAuthStore: () => ({ user: null }),
  useChildAuthStore: () => ({}),
  setUser: vi.fn(),
}))
vi.mock('@/api/learning', () => ({
  getMyLearningMapIndex: vi.fn(),
  getMyLearningStats: vi.fn(),
}))

import { getMyLearningMapIndex, getMyLearningStats } from '@/api/learning'
import { isLearningOnboarded } from './index'

const mockIndex = vi.mocked(getMyLearningMapIndex)
const mockStats = vi.mocked(getMyLearningStats)

function indexRow(id: string) {
  return {
    topic_id: id,
    mastery_level: 'available',
    next_review_at: null,
    subject: 'mathematics',
    domain: 'Addition',
    age_group: 'mid',
  }
}

function stats(onboarding_completed: boolean) {
  return {
    child_id: 'c1',
    cumulative_xp: 0,
    level: 1,
    level_name_zh: '初级',
    level_name_en: 'Beginner',
    level_emoji: '🌱',
    next_level_threshold: null,
    learning_streak_days: 0,
    current_zone: 'growth',
    onboarding_completed,
  }
}

beforeEach(() => {
  vi.clearAllMocks()
  mockIndex.mockResolvedValue([])
  mockStats.mockResolvedValue(stats(false))
})

describe('isLearningOnboarded', () => {
  it('treats any progress row as onboarded without asking for stats', async () => {
    mockIndex.mockResolvedValue([indexRow('t1')])

    await expect(isLearningOnboarded()).resolves.toBe(true)
    expect(mockStats).not.toHaveBeenCalled()
  })

  it('diverts a child with no progress and the flag unset', async () => {
    await expect(isLearningOnboarded()).resolves.toBe(false)
  })

  it('keeps a child who finished onboarding but never practised', async () => {
    // Regression: gating on an empty index alone sent this child to the
    // onboarding page, which reads onboarding_completed, redirects home, and
    // left no route into the map.
    mockStats.mockResolvedValue(stats(true))

    await expect(isLearningOnboarded()).resolves.toBe(true)
  })
})
