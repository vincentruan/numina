import { describe, it, expect, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import type { ProgressWithTopic, TopicResponse } from '@/api/learning'
import ParentContinentOverlay from '../ParentContinentOverlay.vue'

vi.mock('vue-i18n', () => ({
  useI18n: () => ({
    t: (key: string, params?: Record<string, unknown>) => {
      if (!params) return key
      return key.replace(/\{\s*(\w+)\s*\}/g, (_m: string, p: string) => String(params[p] ?? ''))
    },
    locale: { value: 'en-US' },
  }),
}))

function makeTopic(overrides: Partial<TopicResponse> = {}): TopicResponse {
  return {
    id: 't1',
    topic_key: 'math.fractions.01',
    topic_type: 'CONCEPTUAL',
    subject: 'mathematics',
    domain: 'Fractions',
    name: 'Fractions',
    name_zh: '分数',
    description: '',
    description_zh: null,
    age_range_start: 8,
    age_range_end: 10,
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

function mountOverlay(
  items: ProgressWithTopic[] = [],
  territories: Array<{ domain: string; items: ProgressWithTopic[]; masteredCount: number }> = [],
) {
  return mount(ParentContinentOverlay, { props: { items, territories } })
}

describe('ParentContinentOverlay (U7)', () => {
  it('shows empty state when child has no learning progress', () => {
    const items = [
      makeItem({ mastery_level: 'locked' }),
      makeItem({ id: 'p2', topic_id: 't2', mastery_level: 'available' }),
    ]
    const wrapper = mountOverlay(items, [])
    expect(wrapper.find('.overlay-empty').exists()).toBe(true)
  })

  it('shows territory depth annotations', () => {
    const items = [
      makeItem({ mastery_level: 'mastered' }),
      makeItem({ id: 'p2', topic_id: 't2', mastery_level: 'learning' }),
    ]
    const territories = [{ domain: 'Fractions', items, masteredCount: 1 }]
    const wrapper = mountOverlay(items, territories)
    expect(wrapper.find('.overlay-territory__name').exists()).toBe(true)
    expect(wrapper.find('.overlay-territory__depth').exists()).toBe(true)
    expect(wrapper.find('.overlay-territory__fill').exists()).toBe(true)
  })

  it('shows recent activity badge for territory with activity in last 24h', () => {
    const recent = new Date().toISOString()
    const items = [makeItem({ mastery_level: 'learning', last_practice_at: recent })]
    const territories = [{ domain: 'Fractions', items, masteredCount: 0 }]
    const wrapper = mountOverlay(items, territories)
    expect(wrapper.find('.overlay-territory__recent').exists()).toBe(true)
  })

  it('does not show recent badge for old activity', () => {
    const old = new Date(Date.now() - 48 * 60 * 60 * 1000).toISOString()
    const items = [makeItem({ mastery_level: 'learning', last_practice_at: old })]
    const territories = [{ domain: 'Fractions', items, masteredCount: 0 }]
    const wrapper = mountOverlay(items, territories)
    expect(wrapper.find('.overlay-territory__recent').exists()).toBe(false)
  })

  it('shows practice suggestions section', () => {
    const items = [
      makeItem({ mastery_level: 'mastered' }),
      makeItem({ id: 'p2', topic_id: 't2', mastery_level: 'available' }),
    ]
    const territories = [{ domain: 'Fractions', items, masteredCount: 1 }]
    const wrapper = mountOverlay(items, territories)
    expect(wrapper.find('.overlay-suggestions').exists()).toBe(true)
  })

  it('does not show XP or coin counts', () => {
    const items = [makeItem({ mastery_level: 'learning', xp_earned: 100 })]
    const territories = [{ domain: 'Fractions', items, masteredCount: 0 }]
    const wrapper = mountOverlay(items, territories)
    const html = wrapper.html()
    expect(html).not.toContain('XP')
    expect(html).not.toContain('coin')
  })

  it('progress bar width matches mastery depth percent', () => {
    const items = [
      makeItem({ mastery_level: 'mastered' }),
      makeItem({ id: 'p2', topic_id: 't2', mastery_level: 'mastered' }),
      makeItem({ id: 'p3', topic_id: 't3', mastery_level: 'available' }),
      makeItem({ id: 'p4', topic_id: 't4', mastery_level: 'available' }),
    ]
    const territories = [{ domain: 'Fractions', items, masteredCount: 2 }]
    const wrapper = mountOverlay(items, territories)
    const fill = wrapper.find('.overlay-territory__fill')
    expect(fill.attributes('style')).toContain('width: 50%')
  })
})
