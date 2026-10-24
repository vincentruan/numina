import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { createI18n } from 'vue-i18n'
import type { ProgressWithTopic, TopicResponse } from '@/api/learning'
import zhCN from '@/i18n/locales/zh-CN'
import enUS from '@/i18n/locales/en-US'
import PrerequisiteGuidance from './PrerequisiteGuidance.vue'

vi.mock('@/api/learning', async () => {
  const actual = await vi.importActual<typeof import('@/api/learning')>('@/api/learning')
  return {
    ...actual,
    getTopicGraph: vi.fn(),
  }
})

import { getTopicGraph } from '@/api/learning'
const mockGetTopicGraph = vi.mocked(getTopicGraph)

function makeTopic(overrides: Partial<TopicResponse> = {}): TopicResponse {
  return {
    id: 't1',
    topic_key: 'math.add.01',
    topic_type: 'CONCEPTUAL',
    subject: 'mathematics',
    domain: 'Addition',
    name: 'Addition',
    name_zh: '加法',
    description: '',
    description_zh: null,
    age_range_start: 6,
    age_range_end: 8,
    age_group: 'mid',
    centrality: null,
    evidence: [],
    evidence_zh: null,
    assessment_prompt: null,
    assessment_prompt_zh: null,
    standards: [],
    ability_dimensions: null,
    deprecated: false,
    source_taxonomy: 'beijing',
    curriculum_standards: null,
    ...overrides,
  }
}

function makeItem(overrides: Partial<ProgressWithTopic> = {}): ProgressWithTopic {
  return {
    id: 'p1',
    child_id: 'c1',
    topic_id: 't1',
    mastery_level: 'locked',
    mastery_score: null,
    completed_via: null,
    attempts: 0,
    xp_earned: 0,
    last_practice_at: null,
    first_mastered_at: null,
    stability: null,
    next_review_at: null,
    ability_dimensions_score: null,
    topic: makeTopic(),
    ...overrides,
  }
}

function mountGuidance(
  topic: ProgressWithTopic,
  allItems: ProgressWithTopic[] = [],
) {
  const i18n = createI18n({
    legacy: false,
    locale: 'zh-CN',
    messages: { 'zh-CN': zhCN, 'en-US': enUS },
  })
  return mount(PrerequisiteGuidance, {
    props: { topic, allItems },
    global: {
      plugins: [i18n],
      stubs: {
        VanPopup: { template: '<div><slot /></div>' },
      },
    },
  })
}

beforeEach(() => {
  vi.clearAllMocks()
})

describe('PrerequisiteGuidance', () => {
  it('shows "all met" message when all prerequisites are mastered', async () => {
    const topic = makeItem({ topic: makeTopic({ id: 't2', name_zh: '乘法' }) })
    const prereqTopic = makeTopic({ id: 't1', name_zh: '加法' })

    mockGetTopicGraph.mockResolvedValue({
      topic: topic.topic,
      prerequisites: [{ topic: prereqTopic, review_status: null }],
      dependents: [],
    })

    const allItems = [
      makeItem({ id: 'p1', topic_id: 't1', mastery_level: 'mastered', topic: prereqTopic }),
      topic,
    ]

    const wrapper = mountGuidance(topic, allItems)
    await flushPromises()

    expect(wrapper.text()).toContain('已满足')
    expect(wrapper.findAll('.prereq-item')).toHaveLength(0)
  })

  it('lists unmet prerequisites with their mastery status', async () => {
    const topic = makeItem({ topic: makeTopic({ id: 't3', name_zh: '除法' }) })
    const prereq1 = makeTopic({ id: 't1', name_zh: '加法' })
    const prereq2 = makeTopic({ id: 't2', name_zh: '乘法' })

    mockGetTopicGraph.mockResolvedValue({
      topic: topic.topic,
      prerequisites: [
        { topic: prereq1, review_status: null },
        { topic: prereq2, review_status: null },
      ],
      dependents: [],
    })

    const allItems = [
      makeItem({ id: 'p1', topic_id: 't1', mastery_level: 'mastered', topic: prereq1 }),
      makeItem({ id: 'p2', topic_id: 't2', mastery_level: 'locked', topic: prereq2 }),
      topic,
    ]

    const wrapper = mountGuidance(topic, allItems)
    await flushPromises()

    // Only unmet prereqs shown (mastered ones filtered out)
    const items = wrapper.findAll('.prereq-item')
    expect(items).toHaveLength(1)
    expect(wrapper.text()).toContain('乘法')
    // Locked prereq shows ❌
    expect(items[0].text()).toContain('❌')
  })

  it('excludes the topic itself from the prerequisite list', async () => {
    const topic = makeItem({ topic: makeTopic({ id: 't1', name_zh: '加法' }) })

    mockGetTopicGraph.mockResolvedValue({
      topic: topic.topic,
      prerequisites: [{ topic: topic.topic, review_status: null }],
      dependents: [],
    })

    const wrapper = mountGuidance(topic, [topic])
    await flushPromises()

    // The topic itself is filtered out — no prereqs left
    expect(wrapper.findAll('.prereq-item')).toHaveLength(0)
  })

  it('emits goTo when a prerequisite "go to" button is clicked', async () => {
    const topic = makeItem({ topic: makeTopic({ id: 't2' }) })
    const prereq = makeTopic({ id: 't1', name_zh: '加法' })

    mockGetTopicGraph.mockResolvedValue({
      topic: topic.topic,
      prerequisites: [{ topic: prereq, review_status: null }],
      dependents: [],
    })

    const wrapper = mountGuidance(topic, [])
    await flushPromises()

    await wrapper.find('.prereq-item__go').trigger('click')
    expect(wrapper.emitted('goTo')).toBeTruthy()
    expect(wrapper.emitted('goTo')![0]).toEqual(['t1'])
  })

  it('handles API error gracefully', async () => {
    mockGetTopicGraph.mockRejectedValue(new Error('network error'))
    const topic = makeItem()

    const wrapper = mountGuidance(topic)
    await flushPromises()

    // graph is null -> no prereqs listed, shows "all met" (empty state)
    expect(wrapper.findAll('.prereq-item')).toHaveLength(0)
  })
})
