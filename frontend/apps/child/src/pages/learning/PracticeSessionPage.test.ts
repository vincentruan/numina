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

vi.mock('@/api/learning', () => ({
  getTopicDetail: vi.fn().mockResolvedValue({
    id: '2001',
    topic_key: 'fractions-addition',
    name: 'Fractions Addition',
    name_zh: '分数加法',
  }),
  createSession: vi.fn(),
}))

vi.mock('@/api/practice', () => ({
  getPracticeRecommendations: (...args: unknown[]) => getPracticeRecommendations(...args),
  createPracticeSession: (...args: unknown[]) => createPracticeSession(...args),
  batchGetQuestions: vi.fn().mockResolvedValue([]),
  submitPracticeAnswer: vi.fn(),
  finishPracticeSession: vi.fn(),
}))

vi.mock('@/data/learning-challenge/fair-distribution', () => ({
  getChallengeForTopic: () => null,
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
      stubs: { RoleShimmer: true },
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
})
