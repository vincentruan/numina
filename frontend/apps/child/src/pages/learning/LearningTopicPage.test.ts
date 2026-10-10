import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { createI18n } from 'vue-i18n'
import type { TopicResponse, TopicGraphResponse } from '@/api/learning'
import zhCN from '@/i18n/locales/zh-CN'
import enUS from '@/i18n/locales/en-US'

// --- Mocks ---

vi.mock('@/api/learning', () => ({
  getTopicDetail: vi.fn(),
  getTopicGraph: vi.fn().mockResolvedValue(null),
  getMyLearningMap: vi.fn().mockResolvedValue([]),
  getMyAssignments: vi.fn().mockResolvedValue([]),
  createSession: vi.fn(),
  submitAssignment: vi.fn(),
  translateTopic: vi.fn(),
  getMyPaths: vi.fn().mockResolvedValue([]),
}))

const mockRouterPush = vi.fn()
vi.mock('vue-router', () => ({
  useRoute: () => ({ params: { id: 'topic-1' } }),
  useRouter: () => ({ push: mockRouterPush }),
}))

vi.mock('@/composables/usePageLoading', () => ({
  usePageLoading: () => ({ increment: vi.fn(), decrement: vi.fn() }),
}))

import { getTopicDetail, getTopicGraph } from '@/api/learning'
const mockGetTopicDetail = vi.mocked(getTopicDetail)
const mockGetTopicGraph = vi.mocked(getTopicGraph)

// --- Helpers ---

function baseTopic(overrides: Partial<TopicResponse> = {}): TopicResponse {
  return {
    id: 'topic-1',
    topic_key: 'fraction-addition',
    topic_type: 'concept',
    subject: 'mathematics',
    domain: 'number-sense',
    name: 'Fraction Addition',
    name_zh: '分数加法',
    description: 'Learn to add fractions',
    description_zh: '学习分数相加',
    age_range_start: 8,
    age_range_end: 10,
    age_group: 'child',
    centrality: 0.5,
    evidence: ['evidence 1'],
    evidence_zh: ['证据 1'],
    assessment_prompt: null,
    assessment_prompt_zh: null,
    standards: [],
    ability_dimensions: null,
    deprecated: false,
    curriculum_standards: null,
    ...overrides,
  }
}

function edgeTopic(overrides: Partial<TopicResponse> = {}): TopicResponse {
  return baseTopic(overrides)
}

function graphWith(
  prereqs: Array<{ topic: TopicResponse; review_status: string | null }> = [],
  dependents: Array<{ topic: TopicResponse; review_status: string | null }> = [],
): TopicGraphResponse {
  return {
    topic: baseTopic(),
    prerequisites: prereqs,
    dependents,
  }
}

function i18n(locale: string) {
  return createI18n({
    legacy: false,
    locale,
    fallbackLocale: 'en-US',
    messages: { 'zh-CN': zhCN, 'en-US': enUS },
  })
}

async function mountPage({ locale = 'en-US', topic = baseTopic() } = {}) {
  mockGetTopicDetail.mockResolvedValue(topic)
  const { default: LearningTopicPage } = await import('./LearningTopicPage.vue')
  const wrapper = mount(LearningTopicPage, {
    global: {
      plugins: [i18n(locale)],
      stubs: {
        RoleShimmer: { template: '<div class="role-shimmer-stub" />' },
        VanDialog: {
          template: '<div class="van-dialog-stub"><slot /></div>',
          props: ['show', 'title'],
        },
        VanButton: {
          template: '<button class="van-button" :disabled="disabled"><slot /></button>',
          props: ['type', 'size', 'disabled', 'loading'],
        },
        VanTag: {
          template: '<span class="van-tag" @click="$emit(\'click\')"><slot /></span>',
          props: ['type', 'plain', 'size'],
          emits: ['click'],
        },
        VanIcon: { template: '<i class="van-icon" />', props: ['name', 'size', 'aria-label'] },
      },
    },
  })
  // Wait for onMounted → load() to resolve
  await flushPromises()
  return wrapper
}

// --- Tests ---

describe('LearningTopicPage — curriculum badge and callout', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('renders badge and callout for a topic with one resolved standard', async () => {
    const wrapper = await mountPage({
      topic: baseTopic({
        curriculum_standards: [
          { key: 'S1.NA.02', name: '义务教育数学课程标准（2022年版）', code: 'S1.NA.02' },
        ],
      }),
    })

    expect(wrapper.find('.curriculum-badge').exists()).toBe(true)
    expect(wrapper.find('.curriculum-badge').text()).toBe('课')

    const callout = wrapper.find('.curriculum-callout')
    expect(callout.exists()).toBe(true)
    expect(callout.text()).toContain('义务教育数学课程标准（2022年版）')
    expect(callout.text()).toContain('S1.NA.02')
    expect(callout.text()).toContain('·')
    wrapper.unmount()
  })

  it('renders neither badge nor callout when curriculum_standards is null', async () => {
    const wrapper = await mountPage({
      topic: baseTopic({ curriculum_standards: null }),
    })

    expect(wrapper.find('.curriculum-badge').exists()).toBe(false)
    expect(wrapper.find('.curriculum-callout').exists()).toBe(false)
    wrapper.unmount()
  })

  it('renders neither badge nor callout when curriculum_standards is empty', async () => {
    const wrapper = await mountPage({
      topic: baseTopic({ curriculum_standards: [] }),
    })

    expect(wrapper.find('.curriculum-badge').exists()).toBe(false)
    expect(wrapper.find('.curriculum-callout').exists()).toBe(false)
    wrapper.unmount()
  })

  it('renders only the first standard when multiple are present', async () => {
    const wrapper = await mountPage({
      topic: baseTopic({
        curriculum_standards: [
          { key: 'first', name: 'First Standard', code: 'F.01' },
          { key: 'second', name: 'Second Standard', code: 'S.02' },
        ],
      }),
    })

    const callout = wrapper.find('.curriculum-callout')
    expect(callout.exists()).toBe(true)
    expect(callout.text()).toContain('First Standard')
    expect(callout.text()).toContain('F.01')
    expect(callout.text()).not.toContain('Second Standard')
    expect(callout.text()).not.toContain('S.02')
    wrapper.unmount()
  })

  it('renders no badge/callout when all entries have code: null (legacy)', async () => {
    const wrapper = await mountPage({
      topic: baseTopic({
        curriculum_standards: [
          { key: 'legacy', name: 'Legacy Document', code: null },
        ],
      }),
    })

    expect(wrapper.find('.curriculum-badge').exists()).toBe(false)
    expect(wrapper.find('.curriculum-callout').exists()).toBe(false)
    wrapper.unmount()
  })

  it('badge has a non-empty aria-label in both locales', async () => {
    const enWrapper = await mountPage({
      locale: 'en-US',
      topic: baseTopic({
        curriculum_standards: [
          { key: 'k', name: 'Math Standard', code: 'M.01' },
        ],
      }),
    })

    const enBadge = enWrapper.find('.curriculum-badge')
    expect(enBadge.attributes('aria-label')).toBeTruthy()
    expect(enBadge.attributes('aria-label')).toBe(enUS.learning.curriculum.ariaLabel)
    enWrapper.unmount()

    const zhWrapper = await mountPage({
      locale: 'zh-CN',
      topic: baseTopic({
        curriculum_standards: [
          { key: 'k', name: '数学标准', code: 'M.01' },
        ],
      }),
    })

    const zhBadge = zhWrapper.find('.curriculum-badge')
    expect(zhBadge.attributes('aria-label')).toBeTruthy()
    expect(zhBadge.attributes('aria-label')).toBe(zhCN.learning.curriculum.ariaLabel)
    zhWrapper.unmount()
  })
})

// --- U5: Machine-edge chip styling ---

describe('LearningTopicPage — machine-edge chip styling', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('renders reviewed and machine chips with different styles (AE3)', async () => {
    const tReviewed = edgeTopic({ id: 'prereq-reviewed', name: 'Reviewed Topic', name_zh: '已审主题' })
    const tMachine = edgeTopic({ id: 'prereq-machine', name: 'Machine Topic', name_zh: '机器主题' })

    mockGetTopicGraph.mockResolvedValue(
      graphWith([
        { topic: tReviewed, review_status: 'reviewed' },
        { topic: tMachine, review_status: 'machine' },
      ]),
    )

    const wrapper = await mountPage()
    const chips = wrapper.findAll('.topic-chip')
    expect(chips.length).toBe(2)

    // Reviewed chip: no machine modifier, no AI badge
    expect(chips[0].classes()).not.toContain('topic-chip--machine')
    expect(chips[0].find('.ai-badge').exists()).toBe(false)

    // Machine chip: dashed modifier + AI badge
    expect(chips[1].classes()).toContain('topic-chip--machine')
    expect(chips[1].find('.ai-badge').exists()).toBe(true)
    expect(chips[1].find('.ai-badge').text()).toBe('AI')
    wrapper.unmount()
  })

  it('renders null status chip identically to reviewed', async () => {
    const tNull = edgeTopic({ id: 'prereq-null', name: 'OS Topic' })
    const tReviewed = edgeTopic({ id: 'prereq-rev', name: 'Reviewed Topic' })

    mockGetTopicGraph.mockResolvedValue(
      graphWith([
        { topic: tNull, review_status: null },
        { topic: tReviewed, review_status: 'reviewed' },
      ]),
    )

    const wrapper = await mountPage()
    const chips = wrapper.findAll('.topic-chip')
    expect(chips.length).toBe(2)

    // Neither should have machine modifier or AI badge
    for (const chip of chips) {
      expect(chip.classes()).not.toContain('topic-chip--machine')
      expect(chip.find('.ai-badge').exists()).toBe(false)
    }
    wrapper.unmount()
  })

  it('machine chip retains mastery icon alongside AI badge', async () => {
    const tMachine = edgeTopic({ id: 'prereq-machine', name: 'Machine Topic' })

    mockGetTopicGraph.mockResolvedValue(
      graphWith([{ topic: tMachine, review_status: 'machine' }]),
    )

    const wrapper = await mountPage()
    const machineChip = wrapper.find('.topic-chip--machine')
    expect(machineChip.exists()).toBe(true)

    // Mastery icon is present (van-icon stub renders as <i class="van-icon">)
    expect(machineChip.find('.van-icon').exists()).toBe(true)
    // AI badge is also present
    expect(machineChip.find('.ai-badge').exists()).toBe(true)
    wrapper.unmount()
  })

  it('machine chip carries accessible name with machine-generated wording', async () => {
    const tMachine = edgeTopic({ id: 'prereq-machine', name: 'Machine Topic', name_zh: '机器主题' })

    mockGetTopicGraph.mockResolvedValue(
      graphWith([{ topic: tMachine, review_status: 'machine' }]),
    )

    const wrapper = await mountPage({ locale: 'en-US' })
    const machineChip = wrapper.find('.topic-chip--machine')
    expect(machineChip.exists()).toBe(true)

    const ariaLabel = machineChip.attributes('aria-label')
    expect(ariaLabel).toBeTruthy()
    expect(ariaLabel).toContain('AI suggested')
    wrapper.unmount()
  })

  it('chip click navigates using the edge topic id', async () => {
    const tPrereq = edgeTopic({ id: 'target-id', name: 'Target Topic' })

    mockGetTopicGraph.mockResolvedValue(
      graphWith([{ topic: tPrereq, review_status: 'reviewed' }]),
    )

    const wrapper = await mountPage()
    const chip = wrapper.find('.topic-chip')
    await chip.trigger('click')

    expect(mockRouterPush).toHaveBeenCalledWith('/learning/topic/target-id')
    wrapper.unmount()
  })

  it('both locale files define the machine-edge aria-label', async () => {
    expect(enUS.learning.machineEdge.ariaLabel).toBeTruthy()
    expect(zhCN.learning.machineEdge.ariaLabel).toBeTruthy()
    // en-US should mention AI
    expect(enUS.learning.machineEdge.ariaLabel).toContain('AI')
    // zh-CN should mention AI
    expect(zhCN.learning.machineEdge.ariaLabel).toContain('AI')
  })

  it('applies machine styling to next-steps (dependents) chips as well', async () => {
    const tReviewed = edgeTopic({ id: 'next-reviewed', name: 'Reviewed Next' })
    const tMachine = edgeTopic({ id: 'next-machine', name: 'Machine Next' })

    mockGetTopicGraph.mockResolvedValue(
      graphWith(
        [], // no prerequisites
        [
          { topic: tReviewed, review_status: 'reviewed' },
          { topic: tMachine, review_status: 'machine' },
        ],
      ),
    )

    const wrapper = await mountPage()
    const chips = wrapper.findAll('.topic-chip')
    expect(chips.length).toBe(2)

    // Reviewed next-step: no machine modifier, no AI badge
    expect(chips[0].classes()).not.toContain('topic-chip--machine')
    expect(chips[0].find('.ai-badge').exists()).toBe(false)

    // Machine next-step: dashed modifier + AI badge + accessible name
    expect(chips[1].classes()).toContain('topic-chip--machine')
    expect(chips[1].find('.ai-badge').exists()).toBe(true)
    expect(chips[1].find('.ai-badge').text()).toBe('AI')
    expect(chips[1].attributes('aria-label')).toContain('AI suggested')
    wrapper.unmount()
  })
})
