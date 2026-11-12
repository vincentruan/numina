import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { createI18n } from 'vue-i18n'
import type { QuestionResponse } from '@/api/practice'
import type { TopicResponse } from '@/api/learning'
import type { ChallengeConfig } from '@/types/learning-challenge'
import zhCN from '@/i18n/locales/zh-CN'
import enUS from '@/i18n/locales/en-US'

// --- Mocks ---

vi.mock('@/api/practice', () => ({
  createPracticeSession: vi.fn(),
  batchGetQuestions: vi.fn(),
  submitPracticeAnswer: vi.fn(),
  finishPracticeSession: vi.fn(),
  getPracticeRecommendations: vi.fn().mockResolvedValue([]),
}))

vi.mock('@/api/learning', () => ({
  getTopicDetail: vi.fn(),
  createSession: vi.fn(),
}))

vi.mock('@/data/learning-challenge/fair-distribution', () => ({
  getChallengeForTopic: vi.fn(),
}))

const mockRouterPush = vi.fn()
vi.mock('vue-router', () => ({
  useRoute: () => ({ params: { topicId: 'topic-1' } }),
  useRouter: () => ({ push: mockRouterPush, back: vi.fn() }),
}))

import { createPracticeSession, batchGetQuestions } from '@/api/practice'
import { getTopicDetail } from '@/api/learning'
import { getChallengeForTopic } from '@/data/learning-challenge/fair-distribution'

const mockCreateSession = vi.mocked(createPracticeSession)
const mockBatchGet = vi.mocked(batchGetQuestions)
const mockGetTopicDetail = vi.mocked(getTopicDetail)
const mockGetChallenge = vi.mocked(getChallengeForTopic)

// --- Helpers ---

function baseTopic(overrides: Partial<TopicResponse> = {}): TopicResponse {
  return {
    id: 'topic-1',
    topic_key: 'math.fractions.understanding',
    topic_type: 'concept',
    subject: 'mathematics',
    domain: 'number-sense',
    name: 'Fraction Understanding',
    name_zh: '分数理解',
    description: 'Learn fractions',
    description_zh: '学习分数',
    age_range_start: 8,
    age_range_end: 10,
    age_group: 'child',
    centrality: 0.5,
    evidence: [],
    evidence_zh: [],
    assessment_prompt: null,
    assessment_prompt_zh: null,
    standards: [],
    ability_dimensions: null,
    deprecated: false,
    source_taxonomy: 'beijing',
    curriculum_standards: null,
    real_world_connections: null,
    real_world_connections_zh: null,
    ...overrides,
  }
}

function baseQuestion(overrides: Partial<QuestionResponse> = {}): QuestionResponse {
  return {
    id: 'q-1',
    topic_id: 'topic-1',
    question_type: 'multiple_choice',
    stem: 'What is 1/2 + 1/2?',
    stem_zh: null,
    options: [
      { key: 'A', text: '1' },
      { key: 'B', text: '2' },
    ],
    answer: { selected: 'A' },
    solution: null,
    difficulty: 2,
    bloom_level: 'apply',
    source: 'template',
    review_status: 'approved',
    age_group: 'mid',
    parameters: null,
    times_used: 0,
    correct_count: 0,
    ...overrides,
  }
}

function baseChallengeConfig(overrides: Record<string, unknown> = {}): ChallengeConfig {
  return {
    id: 'test-challenge',
    topicId: 'math.fractions.understanding',
    type: 'order',
    difficulty: 2,
    ageGroup: 'mid',
    scenario: 'Put in order.',
    scenarioZh: '排一排。',
    discoveryMessage: 'Well done!',
    discoveryMessageZh: '做得好！',
    objects: [
      { id: 'a', label: 'A', icon: '🔵' },
      { id: 'b', label: 'B', icon: '🟡' },
      { id: 'c', label: 'C', icon: '🔴' },
    ],
    correctOrder: ['a', 'b', 'c'],
    ...overrides,
  } as unknown as ChallengeConfig
}

function i18n(locale: string) {
  return createI18n({
    legacy: false,
    locale,
    fallbackLocale: 'en-US',
    messages: { 'zh-CN': zhCN, 'en-US': enUS },
  })
}

async function mountPage() {
  const { default: PracticeSessionPage } = await import('./PracticeSessionPage.vue')
  const wrapper = mount(PracticeSessionPage, {
    global: {
      plugins: [i18n('en-US')],
      stubs: {
        RoleShimmer: { template: '<div class="role-shimmer-stub" />' },
        VanProgress: { template: '<div class="van-progress-stub" />', props: ['percentage', 'strokeWidth'] },
        PracticeQuestionCard: { template: '<div class="pq-card-stub" />' },
        PracticeAnswerInput: { template: '<div class="pai-stub" />' },
        PracticeResultSummary: { template: '<div class="prs-stub" />' },
        ManipulateObserveReflect: {
          template: '<div class="mor-stub" />',
          emits: ['complete', 'requestTutor'],
        },
        DiscoveryChallengeIntro: {
          name: 'DiscoveryChallengeIntro',
          template: '<div class="dci-stub" />',
          emits: ['complete', 'request-tutor'],
        },
      },
    },
  })
  await flushPromises()
  return wrapper
}

// --- Tests ---

describe('PracticeSessionPage — #210 stage-flow regression (R1)', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mockGetTopicDetail.mockResolvedValue(baseTopic())
    mockCreateSession.mockResolvedValue({
      id: 'session-1',
      child_id: 'child-1',
      topic_id: 'topic-1',
      session_mode: 'practice',
      question_ids: ['q-1', 'q-2'],
      started_at: '2026-01-01T00:00:00Z',
      ended_at: null,
      total_score: null,
      completed_count: 0,
      source: 'adaptive',
      learning_progress_id: null,
    })
    mockBatchGet.mockResolvedValue([baseQuestion({ id: 'q-1' }), baseQuestion({ id: 'q-2' })])
  })

  it('no-challenge topic: picking a mode advances to answering directly (not stuck on mode page)', async () => {
    // No challenge configured for this topic
    mockGetChallenge.mockReturnValue(null)

    const wrapper = await mountPage()

    // Initial phase should be 'mode' (mode-selection screen visible)
    expect(wrapper.find('.mode-phase').exists()).toBe(true)

    // Click a mode button → startSession(5)
    const modeBtns = wrapper.findAll('.mode-btn')
    expect(modeBtns.length).toBeGreaterThan(0)
    await modeBtns[0].trigger('click')
    await flushPromises()

    // After startSession with no challenge: should advance to 'answering' (R1 fix)
    // Current BUG: stays on 'mode' (no reaction)
    expect(wrapper.find('.answer-phase').exists()).toBe(true)
    expect(wrapper.find('.mode-phase').exists()).toBe(false)
    expect(mockCreateSession).toHaveBeenCalledTimes(1)
  })

  it('challenge topic: discovery → mode → answering does not re-enter discovery', async () => {
    // Challenge configured
    mockGetChallenge.mockReturnValue(baseChallengeConfig())

    const wrapper = await mountPage()

    // Initial phase should be 'mode' (current bug: challenge resolved only inside startSession)
    // After the fix (KTD1): challenge resolved on page entry → phase='discovery' immediately
    // Either initial state works for this test — the key assertion is the flow below.
    await flushPromises()

    // Simulate discovery flow: DiscoveryChallengeIntro emits 'complete'
    const dciStub = wrapper.findComponent({ name: 'DiscoveryChallengeIntro' })
    if (dciStub.exists()) {
      await dciStub.vm.$emit('complete')
      await flushPromises()
      // After discovery complete → should be on mode selection
      expect(wrapper.find('.mode-phase').exists()).toBe(true)
    }

    // Pick a mode → startSession(5)
    // Reset mock to track the second call count
    mockCreateSession.mockClear()
    mockBatchGet.mockClear()

    const modeBtns = wrapper.findAll('.mode-btn')
    await modeBtns[0].trigger('click')
    await flushPromises()

    // After startSession: should advance to 'answering' directly, NOT re-enter 'discovery'
    // Current BUG: re-enters 'discovery' (infinite loop)
    expect(wrapper.find('.answer-phase').exists()).toBe(true)
    expect(wrapper.find('.discovery-phase').exists()).toBe(false)
    expect(mockCreateSession).toHaveBeenCalledTimes(1)
  })
})
