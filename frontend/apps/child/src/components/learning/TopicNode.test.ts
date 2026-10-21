import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import { createI18n } from 'vue-i18n'
import type { ProgressWithTopic, TopicResponse } from '@/api/learning'
import zhCN from '@/i18n/locales/zh-CN'
import enUS from '@/i18n/locales/en-US'
import TopicNode from './TopicNode.vue'

function makeTopic(overrides: Partial<TopicResponse> = {}): TopicResponse {
  return {
    id: 't1',
    topic_key: 'math.add.01',
    topic_type: 'CONCEPTUAL',
    subject: 'mathematics',
    domain: 'Addition',
    name: 'Addition Basics',
    name_zh: '加法基础',
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
    mastery_level: 'available',
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

function mountNode(item: ProgressWithTopic, isFrontier = false) {
  const i18n = createI18n({
    legacy: false,
    locale: 'zh-CN',
    messages: { 'zh-CN': zhCN, 'en-US': enUS },
  })
  return mount(TopicNode, {
    props: { item, isFrontier },
    global: { plugins: [i18n] },
  })
}

describe('TopicNode', () => {
  it('renders mastered class for mastered items', () => {
    const wrapper = mountNode(makeItem({ mastery_level: 'mastered' }))
    expect(wrapper.find('.topic-node').classes()).toContain('topic-node--mastered')
  })

  it('renders learning class for learning items', () => {
    const wrapper = mountNode(makeItem({ mastery_level: 'learning' }))
    expect(wrapper.find('.topic-node').classes()).toContain('topic-node--learning')
  })

  it('renders learning class for assessing items', () => {
    const wrapper = mountNode(makeItem({ mastery_level: 'assessing' }))
    expect(wrapper.find('.topic-node').classes()).toContain('topic-node--learning')
  })

  it('renders available class for available items', () => {
    const wrapper = mountNode(makeItem({ mastery_level: 'available' }))
    expect(wrapper.find('.topic-node').classes()).toContain('topic-node--available')
  })

  it('renders locked class for locked items', () => {
    const wrapper = mountNode(makeItem({ mastery_level: 'locked' }))
    expect(wrapper.find('.topic-node').classes()).toContain('topic-node--locked')
  })

  it('renders review class when mastered but review is due', () => {
    const wrapper = mountNode(
      makeItem({
        mastery_level: 'mastered',
        next_review_at: new Date(Date.now() - 86_400_000).toISOString(),
      }),
    )
    expect(wrapper.find('.topic-node').classes()).toContain('topic-node--review')
  })

  it('stays mastered when review date is in the future', () => {
    const wrapper = mountNode(
      makeItem({
        mastery_level: 'mastered',
        next_review_at: new Date(Date.now() + 86_400_000).toISOString(),
      }),
    )
    expect(wrapper.find('.topic-node').classes()).toContain('topic-node--mastered')
  })

  it('shows frontier marker when isFrontier is true', () => {
    const wrapper = mountNode(makeItem(), true)
    expect(wrapper.find('.topic-node__here').exists()).toBe(true)
  })

  it('hides frontier marker when isFrontier is false', () => {
    const wrapper = mountNode(makeItem(), false)
    expect(wrapper.find('.topic-node__here').exists()).toBe(false)
  })

  it('adds frontier class to the node when isFrontier', () => {
    const wrapper = mountNode(makeItem(), true)
    expect(wrapper.find('.topic-node').classes()).toContain('topic-node--frontier')
  })

  it('emits tap with the item on click', async () => {
    const item = makeItem()
    const wrapper = mountNode(item)
    await wrapper.find('.topic-node-wrapper').trigger('click')
    expect(wrapper.emitted('tap')).toBeTruthy()
    expect(wrapper.emitted('tap')![0]).toEqual([item])
  })

  it('displays zh name in zh locale', () => {
    const wrapper = mountNode(
      makeItem({ topic: makeTopic({ name_zh: '分数加法', name: 'Fraction Addition' }) }),
    )
    expect(wrapper.find('.topic-node__label').text()).toBe('分数加法')
  })

  it('falls back to English name when zh name is null', () => {
    const i18n = createI18n({
      legacy: false,
      locale: 'zh-CN',
      messages: { 'zh-CN': zhCN, 'en-US': enUS },
    })
    const wrapper = mount(TopicNode, {
      props: { item: makeItem({ topic: makeTopic({ name_zh: null, name: 'Fractions' }) }) },
      global: { plugins: [i18n] },
    })
    expect(wrapper.find('.topic-node__label').text()).toBe('Fractions')
  })
})
