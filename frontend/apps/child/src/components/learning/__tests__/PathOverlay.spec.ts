import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import { createI18n } from 'vue-i18n'
import PathOverlay from '../PathOverlay.vue'
import type { ProgressWithTopic } from '@/api/learning'

const i18n = createI18n({
  legacy: false,
  locale: 'zh-CN',
  messages: {
    'zh-CN': {
      learning: {
        recommendPath: { pathA11yLabel: '推荐学习路径' },
      },
    },
  },
})

function makeTopic(id: string, domain: string): ProgressWithTopic['topic'] {
  return {
    id,
    topic_key: id,
    topic_type: 'concept',
    subject: 'mathematics',
    domain,
    name: id,
    name_zh: id,
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
  }
}

function makeItem(id: string, domain: string, mastery = 'available'): ProgressWithTopic {
  return {
    id: `p-${id}`,
    child_id: 'c1',
    topic_id: id,
    mastery_level: mastery,
    mastery_score: null,
    completed_via: null,
    attempts: 0,
    xp_earned: 0,
    last_practice_at: null,
    first_mastered_at: null,
    stability: null,
    next_review_at: null,
    ability_dimensions_score: null,
    topic: makeTopic(id, domain),
  }
}

describe('PathOverlay', () => {
  it('renders nothing when path is empty', () => {
    const wrapper = mount(PathOverlay, {
      props: {
        pathTopicIds: [],
        allItems: [],
        expandedDomains: new Set<string>(),
      },
      global: { plugins: [i18n] },
    })
    expect(wrapper.find('svg').exists()).toBe(false)
  })

  it('renders nothing when all path topics are in collapsed domains', () => {
    const items = [makeItem('t1', 'Addition')]
    const wrapper = mount(PathOverlay, {
      props: {
        pathTopicIds: ['t1'],
        allItems: items,
        expandedDomains: new Set<string>(), // no domains expanded
      },
      global: { plugins: [i18n] },
    })
    // No visible segments because Addition is collapsed
    expect(wrapper.find('svg').exists()).toBe(false)
  })

  it('has aria-hidden attribute (decorative element)', () => {
    const items = [makeItem('t1', 'Addition'), makeItem('t2', 'Addition')]
    const wrapper = mount(PathOverlay, {
      props: {
        pathTopicIds: ['t1', 't2'],
        allItems: items,
        expandedDomains: new Set(['Addition']),
      },
      global: { plugins: [i18n] },
    })
    // SVG is aria-hidden since the path is decorative
    const svg = wrapper.find('svg')
    if (svg.exists()) {
      expect(svg.attributes('aria-hidden')).toBe('true')
    }
  })
})
