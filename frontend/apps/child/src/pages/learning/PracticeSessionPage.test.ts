import { describe, it, expect, vi, beforeEach } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import { createI18n } from 'vue-i18n'
import { reactive } from 'vue'
import zhCN from '@/i18n/locales/zh-CN'
import enUS from '@/i18n/locales/en-US'

const push = vi.fn()
const routeState = reactive({
  params: { topicId: '2001' } as Record<string, string>,
  query: {} as Record<string, string>,
})

vi.mock('vue-router', () => ({
  useRoute: () => routeState,
  useRouter: () => ({ push, back: vi.fn() }),
}))

const getPracticeRecommendations = vi.fn()
const createPracticeSession = vi.fn()
const batchGetQuestionsMock = vi.fn().mockResolvedValue([])

vi.mock('@/api/learning', () => ({
  getTopicDetail: vi.fn().mockResolvedValue({
    id: '2001',
    topic_key: 'fractions-addition',
    name: 'Fractions Addition',
    name_zh: '分数加法',
  }),
  // Required by the page's entry-time challenge/mastery resolution; without
  // it the Promise.all rejects and the page falls back to mode selection.
  getMyLearningMap: vi.fn().mockResolvedValue([]),
  createSession: vi.fn(),
}))

vi.mock('@/api/practice', () => ({
  getPracticeRecommendations: (...args: unknown[]) => getPracticeRecommendations(...args),
  createPracticeSession: (...args: unknown[]) => createPracticeSession(...args),
  batchGetQuestions: (...args: unknown[]) => batchGetQuestionsMock(...args),
  submitPracticeAnswer: vi.fn(),
  finishPracticeSession: vi.fn(),
}))

const { getChallengeForTopicMock } = vi.hoisted(() => ({
  getChallengeForTopicMock: vi.fn().mockReturnValue(null),
}))

vi.mock('@/data/learning-challenge/fair-distribution', () => ({
  getChallengeForTopic: (...args: unknown[]) => getChallengeForTopicMock(...args),
}))

const { default: PracticeSessionPage } = await import('./PracticeSessionPage.vue')

function mountPage() {
  const i18n = createI18n({
    legacy: false,
    locale: 'zh-CN',
    fallbackLocale: 'en-US',
    messages: { 'zh-CN': zhCN, 'en-US': enUS },
  })
  return mount(PracticeSessionPage, {
    global: {
      plugins: [i18n],
      stubs: {
        RoleShimmer: true,
        // Stub the challenge/answering children so phase assertions read the
        // page's own markup instead of deep child rendering.
        DiscoveryChallengeIntro: {
          name: 'DiscoveryChallengeIntro',
          template: '<div class="discovery-phase" />',
          emits: ['complete', 'request-tutor'],
        },
        PracticeQuestionCard: { template: '<div class="pq-card-stub" />' },
        PracticeAnswerInput: { template: '<div class="pai-stub" />' },
        VanProgress: { template: '<div />' },
      },
    },
  })
}

const weakPrereq = {
  topic_id: '1001',
  topic_name: 'Common Denominator',
  topic_name_zh: '通分',
  mastery_level: 'learning',
  accuracy: 0,
  is_prerequisite: true,
  prerequisite_of_topic_id: '2001',
  is_diagnosis: true,
  depth: 2,
  bkt_mastery: 0.35,
  sample_size: 5,
}

describe('PracticeSessionPage — prerequisite diagnosis', () => {
  beforeEach(() => {
    push.mockReset()
    getPracticeRecommendations.mockReset()
    createPracticeSession.mockReset()
    routeState.params.topicId = '2001'
    routeState.query = {}
  })

  it('requests the diagnosis once on load and renders the card above the mode buttons', async () => {
    getPracticeRecommendations.mockResolvedValue([weakPrereq])
    const wrapper = mountPage()
    await flushPromises()

    expect(getPracticeRecommendations).toHaveBeenCalledTimes(1)
    expect(getPracticeRecommendations).toHaveBeenCalledWith('2001', true)
    const card = wrapper.find('[data-test="diagnosis-card-wrapper"]')
    expect(card.exists()).toBe(true)
    expect(card.text()).toContain('通分')
    expect(card.text()).toContain('分数加法')
    expect(wrapper.findAll('.mode-btn').length).toBeGreaterThan(0)
  })

  it('reserves the card height with a skeleton while the request is in flight', async () => {
    let resolve!: (v: unknown[]) => void
    getPracticeRecommendations.mockReturnValue(new Promise((r) => (resolve = r)))
    const wrapper = mountPage()
    await flushPromises()

    expect(wrapper.find('[data-test="diagnosis-skeleton"]').exists()).toBe(true)
    resolve([weakPrereq])
    await flushPromises()
    expect(wrapper.find('[data-test="diagnosis-skeleton"]').exists()).toBe(false)
  })

  it('silently omits the card when the request fails', async () => {
    getPracticeRecommendations.mockRejectedValue(new Error('401'))
    const wrapper = mountPage()
    await flushPromises()

    expect(wrapper.find('[data-test="diagnosis-card-wrapper"]').exists()).toBe(false)
    expect(wrapper.find('[data-test="diagnosis-skeleton"]').exists()).toBe(false)
    expect(wrapper.findAll('.mode-btn').length).toBeGreaterThan(0)
    expect(getPracticeRecommendations).toHaveBeenCalledTimes(1)
  })

  it('hides the card for this mount after "continue anyway"', async () => {
    getPracticeRecommendations.mockResolvedValue([weakPrereq])
    const wrapper = mountPage()
    await flushPromises()

    await wrapper.find('[data-test="continue-btn"]').trigger('click')
    expect(wrapper.find('[data-test="diagnosis-card-wrapper"]').exists()).toBe(false)
    expect(getPracticeRecommendations).toHaveBeenCalledTimes(1)
  })

  it('navigates to the prerequisite with the fromDiagnosis marker', async () => {
    getPracticeRecommendations.mockResolvedValue([weakPrereq])
    const wrapper = mountPage()
    await flushPromises()

    await wrapper.find('[data-test="practice-first-btn"]').trigger('click')
    expect(push).toHaveBeenCalledTimes(1)
    expect(push.mock.calls[0][0]).toMatchObject({
      params: { topicId: '1001' },
      query: { fromDiagnosis: '2001' },
    })
  })

  it('does not request the diagnosis when arriving with a valid fromDiagnosis marker', async () => {
    routeState.query = { fromDiagnosis: '2001' }
    const wrapper = mountPage()
    await flushPromises()

    expect(getPracticeRecommendations).not.toHaveBeenCalled()
    expect(wrapper.find('[data-test="diagnosis-card-wrapper"]').exists()).toBe(false)
  })

  it('requests the diagnosis when the fromDiagnosis marker is not numeric', async () => {
    routeState.query = { fromDiagnosis: 'abc' }
    getPracticeRecommendations.mockResolvedValue([])
    mountPage()
    await flushPromises()

    expect(getPracticeRecommendations).toHaveBeenCalledTimes(1)
  })

  it('resets session state for the new topic when the route is reused (R13)', async () => {
    getPracticeRecommendations.mockResolvedValue([weakPrereq])
    const wrapper = mountPage()
    await flushPromises()

    // Reuse the same component instance for the referred prerequisite, as the
    // card's "practice X first" navigation does.
    await wrapper.find('[data-test="practice-first-btn"]').trigger('click')
    routeState.params.topicId = '1001'
    await flushPromises()

    // No residual state from the previous topic: the page is back at mode
    // selection with no session, questions, or result carried over.
    expect(wrapper.findAll('.mode-btn').length).toBeGreaterThan(0)
    expect(wrapper.find('.page-title').exists()).toBe(true)
    expect(wrapper.find('[data-test="question-card"]').exists()).toBe(false)
    // The diagnosis is re-evaluated for the newly opened topic.
    expect(getPracticeRecommendations).toHaveBeenLastCalledWith('1001', true)
  })
})

// --- U1: #210 stage-flow regression tests ---

function baseChallengeConfig() {
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
  } as unknown as import('@/types/learning-challenge').ChallengeConfig
}

describe('PracticeSessionPage — #210 stage-flow regression', () => {
  beforeEach(() => {
    push.mockReset()
    createPracticeSession.mockReset()
    batchGetQuestionsMock.mockReset()
    batchGetQuestionsMock.mockResolvedValue([
      {
        id: 'q-1',
        topic_id: '2001',
        question_type: 'multiple_choice',
        stem: 'Q1?',
        stem_zh: null,
        options: [{ key: 'A', text: 'A' }],
        answer: { answer: 'A' },
        solution: null,
        difficulty: 1,
        bloom_level: 'apply',
        source: 'template',
        review_status: 'approved',
        age_group: 'mid',
        parameters: null,
        times_used: 0,
        correct_count: 0,
      },
    ])
    createPracticeSession.mockResolvedValue({
      id: 'session-1',
      child_id: 'child-1',
      topic_id: '2001',
      session_mode: 'practice',
      question_ids: ['q-1'],
      started_at: '2026-01-01T00:00:00Z',
      ended_at: null,
      total_score: null,
      completed_count: 0,
      source: 'adaptive',
      learning_progress_id: null,
    })
  })

  it('no-challenge topic: picking a mode advances directly to answering', async () => {
    getChallengeForTopicMock.mockReturnValue(null)
    const wrapper = mountPage()
    await flushPromises()

    expect(wrapper.find('.mode-phase').exists()).toBe(true)

    const modeBtns = wrapper.findAll('.mode-btn')
    expect(modeBtns.length).toBeGreaterThan(0)
    await modeBtns[0].trigger('click')
    await flushPromises()

    expect(wrapper.find('.answer-phase').exists()).toBe(true)
    expect(wrapper.find('.mode-phase').exists()).toBe(false)
    expect(createPracticeSession).toHaveBeenCalledTimes(1)
  })

  it('challenge topic: discovery → mode → answering does not re-enter discovery', async () => {
    getChallengeForTopicMock.mockReturnValue(baseChallengeConfig())
    const wrapper = mountPage()
    await flushPromises()

    // Initial phase: discovery (challenge resolved on mount)
    expect(wrapper.find('.discovery-phase').exists()).toBe(true)

    // Complete discovery
    const dci = wrapper.findComponent({ name: 'DiscoveryChallengeIntro' })
    await dci.vm.$emit('complete')
    await flushPromises()

    // Should now be in mode selection
    expect(wrapper.find('.mode-phase').exists()).toBe(true)

    // Pick a mode
    createPracticeSession.mockClear()
    const modeBtns = wrapper.findAll('.mode-btn')
    await modeBtns[0].trigger('click')
    await flushPromises()

    // Should advance to answering, NOT re-enter discovery
    expect(wrapper.find('.answer-phase').exists()).toBe(true)
    expect(wrapper.find('.discovery-phase').exists()).toBe(false)
    expect(createPracticeSession).toHaveBeenCalledTimes(1)
  })
})
