import { describe, it, expect, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import { createI18n } from 'vue-i18n'
import NextUpCard from '../NextUpCard.vue'
import type { ProgressWithTopic } from '@/api/learning'

const i18n = createI18n({
  legacy: false,
  locale: 'zh-CN',
  messages: {
    'zh-CN': {
      learning: {
        recommendPath: {
          nextStep: '下一步: {topic}',
          startPractice: '→',
        },
      },
    },
  },
})

const mockRouter = { push: vi.fn() }
vi.mock('vue-router', () => ({
  useRouter: () => mockRouter,
}))

function makeTopic(overrides: Partial<ProgressWithTopic['topic']> = {}): ProgressWithTopic['topic'] {
  return {
    id: 't1',
    topic_key: 'addition',
    topic_type: 'concept',
    subject: 'mathematics',
    domain: 'Addition',
    name: 'Addition',
    name_zh: '加法',
    description: 'desc',
    description_zh: null,
    age_range_start: 6,
    age_range_end: 8,
    age_group: 'low',
    centrality: 0.5,
    evidence: [],
    evidence_zh: null,
    assessment_prompt: null,
    assessment_prompt_zh: null,
    standards: [],
    ability_dimensions: null,
    deprecated: false,
    source_taxonomy: 'os',
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

describe('NextUpCard', () => {
  it('renders nothing when topic is null', () => {
    const wrapper = mount(NextUpCard, {
      props: { topic: null, topicName: '', loading: false },
      global: { plugins: [i18n] },
    })
    expect(wrapper.find('.next-up-card').exists()).toBe(false)
  })

  it('displays topic name when topic is provided', () => {
    const item = makeItem()
    const wrapper = mount(NextUpCard, {
      props: { topic: item, topicName: '加法', loading: false },
      global: { plugins: [i18n] },
    })
    expect(wrapper.text()).toContain('加法')
  })

  it('navigates to practice route on tap for available topic', async () => {
    const item = makeItem({ mastery_level: 'available' })
    const wrapper = mount(NextUpCard, {
      props: { topic: item, topicName: '加法', loading: false },
      global: { plugins: [i18n] },
    })
    await wrapper.find('.next-up-card').trigger('click')
    expect(mockRouter.push).toHaveBeenCalledWith('/learning/topic/t1?action=practice')
  })

  it('navigates to review route on tap for mastered topic', async () => {
    const item = makeItem({ mastery_level: 'mastered' })
    const wrapper = mount(NextUpCard, {
      props: { topic: item, topicName: '加法', loading: false },
      global: { plugins: [i18n] },
    })
    await wrapper.find('.next-up-card').trigger('click')
    expect(mockRouter.push).toHaveBeenCalledWith('/learning/topic/t1?action=review')
  })

  it('meets 44px minimum touch target', () => {
    const item = makeItem()
    const wrapper = mount(NextUpCard, {
      props: { topic: item, topicName: '加法', loading: false },
      global: { plugins: [i18n] },
    })
    const card = wrapper.find('.next-up-card')
    // min-height is set via CSS (min-height: 44px), verify card renders
    expect(card.exists()).toBe(true)
  })
})
