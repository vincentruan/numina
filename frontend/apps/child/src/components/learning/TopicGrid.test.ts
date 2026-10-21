import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import { createI18n } from 'vue-i18n'
import type { ProgressWithTopic, TopicResponse } from '@/api/learning'
import zhCN from '@/i18n/locales/zh-CN'
import enUS from '@/i18n/locales/en-US'
import TopicGrid from './TopicGrid.vue'

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

function mountGrid(items: ProgressWithTopic[], childAgeGroup?: string) {
  const i18n = createI18n({
    legacy: false,
    locale: 'zh-CN',
    messages: { 'zh-CN': zhCN, 'en-US': enUS },
  })
  return mount(TopicGrid, {
    props: { items, childAgeGroup },
    global: {
      plugins: [i18n],
      stubs: { ZoneBadge: { template: '<span class="zone-badge-stub">{{ zone }}</span>', props: ['zone'] } },
    },
  })
}

describe('TopicGrid', () => {
  it('groups items by domain', () => {
    const wrapper = mountGrid([
      makeItem({ id: 'p1', topic: makeTopic({ id: 't1', domain: 'Addition' }) }),
      makeItem({ id: 'p2', topic: makeTopic({ id: 't2', domain: 'Subtraction' }) }),
      makeItem({ id: 'p3', topic: makeTopic({ id: 't3', domain: 'Addition' }) }),
    ])

    const groups = wrapper.findAll('.domain-group')
    expect(groups).toHaveLength(2)
    // Addition has 2 items
    expect(groups[0].findAll('.topic-card')).toHaveLength(2)
    expect(groups[1].findAll('.topic-card')).toHaveLength(1)
  })

  it('applies correct mastery class to cards', () => {
    const wrapper = mountGrid([
      makeItem({ id: 'p1', mastery_level: 'mastered' }),
      makeItem({ id: 'p2', mastery_level: 'learning' }),
      makeItem({ id: 'p3', mastery_level: 'locked' }),
    ])

    const cards = wrapper.findAll('.topic-card')
    expect(cards[0].classes()).toContain('topic-card--mastered')
    expect(cards[1].classes()).toContain('topic-card--learning')
    expect(cards[2].classes()).toContain('topic-card--locked')
  })

  it('marks review-due cards', () => {
    const wrapper = mountGrid([
      makeItem({
        id: 'p1',
        mastery_level: 'mastered',
        next_review_at: new Date(Date.now() - 86_400_000).toISOString(),
      }),
    ])

    expect(wrapper.find('.topic-card').classes()).toContain('topic-card--review-due')
  })

  it('does not mark future review as due', () => {
    const wrapper = mountGrid([
      makeItem({
        id: 'p1',
        mastery_level: 'mastered',
        next_review_at: new Date(Date.now() + 86_400_000).toISOString(),
      }),
    ])

    expect(wrapper.find('.topic-card').classes()).not.toContain('topic-card--review-due')
  })

  it('marks parent_review items as rejected', () => {
    const wrapper = mountGrid([
      makeItem({ id: 'p1', mastery_level: 'parent_review' }),
    ])

    expect(wrapper.find('.topic-card').classes()).toContain('topic-card--rejected')
    expect(wrapper.find('.topic-card__rejected-icon').exists()).toBe(true)
  })

  it('shows attempts count when attempts > 0', () => {
    const wrapper = mountGrid([
      makeItem({ id: 'p1', attempts: 3 }),
    ])

    expect(wrapper.text()).toContain('3')
  })

  it('hides attempts when attempts is 0', () => {
    const wrapper = mountGrid([
      makeItem({ id: 'p1', attempts: 0 }),
    ])

    expect(wrapper.find('.topic-card__meta').exists()).toBe(false)
  })

  it('emits topicClick with topic id on card click', async () => {
    const wrapper = mountGrid([
      makeItem({ id: 'p1', topic: makeTopic({ id: 't42' }) }),
    ])

    await wrapper.find('.topic-card').trigger('click')
    expect(wrapper.emitted('topicClick')).toBeTruthy()
    expect(wrapper.emitted('topicClick')![0]).toEqual(['t42'])
  })

  it('shows zone badge when childAgeGroup matches and zone is computed', () => {
    const wrapper = mountGrid(
      [makeItem({ id: 'p1', topic: makeTopic({ id: 't1', age_group: 'low' }) })],
      'mid', // child is mid, topic is low -> comfort zone
    )

    expect(wrapper.find('.zone-badge-stub').exists()).toBe(true)
    expect(wrapper.find('.zone-badge-stub').text()).toBe('comfort')
  })

  it('shows growth zone when topic matches child age group', () => {
    const wrapper = mountGrid(
      [makeItem({ id: 'p1', topic: makeTopic({ id: 't1', age_group: 'mid' }) })],
      'mid',
    )

    expect(wrapper.find('.zone-badge-stub').text()).toBe('growth')
  })

  it('does not show zone badge when childAgeGroup is not provided', () => {
    const wrapper = mountGrid([
      makeItem({ id: 'p1', topic: makeTopic({ id: 't1', age_group: 'low' }) }),
    ])

    expect(wrapper.find('.zone-badge-stub').exists()).toBe(false)
  })

  it('displays zh name in zh locale', () => {
    const wrapper = mountGrid([
      makeItem({ topic: makeTopic({ name_zh: '分数', name: 'Fractions' }) }),
    ])

    expect(wrapper.find('.topic-card__name').text()).toBe('分数')
  })

  it('falls back to English when zh name is null', () => {
    const i18n = createI18n({
      legacy: false,
      locale: 'zh-CN',
      messages: { 'zh-CN': zhCN, 'en-US': enUS },
    })
    const wrapper = mount(TopicGrid, {
      props: {
        items: [makeItem({ topic: makeTopic({ name_zh: null, name: 'Fractions' }) })],
      },
      global: {
        plugins: [i18n],
        stubs: { ZoneBadge: true },
      },
    })

    expect(wrapper.find('.topic-card__name').text()).toBe('Fractions')
  })

  it('handles assessing mastery as learning', () => {
    const wrapper = mountGrid([
      makeItem({ id: 'p1', mastery_level: 'assessing' }),
    ])

    expect(wrapper.find('.topic-card').classes()).toContain('topic-card--learning')
  })
})
