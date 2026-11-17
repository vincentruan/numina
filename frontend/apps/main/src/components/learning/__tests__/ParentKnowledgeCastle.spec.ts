import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import { createI18n } from 'vue-i18n'
import zhCN from '@/i18n/locales/zh-CN'
import enUS from '@/i18n/locales/en-US'
import ParentKnowledgeCastle from '../ParentKnowledgeCastle.vue'
import type { CastleIndex } from '@/api/learning'

// Real locale modules — a missing/renamed castle key must fail the suite.
function makeI18n(locale: 'zh-CN' | 'en-US' = 'zh-CN') {
  return createI18n({
    legacy: false,
    locale,
    messages: { 'zh-CN': zhCN, 'en-US': enUS },
  })
}

function makeCastle(overrides: Partial<CastleIndex> = {}): CastleIndex {
  return {
    towers: [
      {
        subject: 'mathematics',
        mastered_count: 2,
        learning_count: 1,
        review_due_count: 0,
        total_count: 10,
        floors: [
          {
            domain: 'Algebra',
            mastered_count: 2,
            learning_count: 1,
            review_due_count: 0,
            total_count: 6,
          },
        ],
      },
    ],
    windows: [
      {
        topic_id: '101',
        topic_name: 'Fractions',
        topic_name_zh: '分数',
        reason: '推荐学习',
        subject: 'mathematics',
        domain: 'Algebra',
      },
    ],
    streak_days: 5,
    ...overrides,
  }
}

function mountCastle(
  props: Record<string, unknown> = {},
  locale: 'zh-CN' | 'en-US' = 'zh-CN',
) {
  return mount(ParentKnowledgeCastle, {
    props: {
      castle: makeCastle(),
      state: 'content' as const,
      ...props,
    },
    global: { plugins: [makeI18n(locale)] },
  })
}

describe('ParentKnowledgeCastle', () => {
  it('renders a skeleton while loading, not the zero-progress castle', () => {
    const wrapper = mountCastle({ castle: null, state: 'loading' })
    expect(wrapper.find('.van-skeleton').exists()).toBe(true)
    expect(wrapper.find('.castle-body').exists()).toBe(false)
  })

  it('shows a distinct error state with a working retry', async () => {
    const wrapper = mountCastle({ castle: null, state: 'error' })
    expect(wrapper.find('.castle-error').exists()).toBe(true)
    // The error must not look like an empty castle.
    expect(wrapper.find('.castle-body').exists()).toBe(false)

    await wrapper.find('.castle-error button, .castle-error .van-button').trigger('click')
    expect(wrapper.emitted('retry')).toHaveLength(1)
  })

  it('renders towers, floors, bricks, windows, and streak for a child with progress', () => {
    const wrapper = mountCastle()
    const body = wrapper.find('.castle-body')
    expect(body.exists()).toBe(true)
    expect(body.findAll('.tower')).toHaveLength(1)
    expect(body.findAll('.floor')).toHaveLength(1)
    expect(body.findAll('.brick').length).toBeGreaterThan(0)
    // Windows render as display-only spans with tooltip (observer mode)
    const win = body.find('.window')
    expect(win.exists()).toBe(true)
    expect(win.attributes('title')).toContain('分数')
    // Streak decoration shows when streak_days > 0
    expect(body.find('.castle-header__streak').exists()).toBe(true)
  })

  it('renders the foundation and empty floor outlines for a zero-progress child', () => {
    const zeroCastle = makeCastle({
      towers: [
        {
          subject: 'science',
          mastered_count: 0,
          learning_count: 0,
          review_due_count: 0,
          total_count: 8,
          floors: [
            {
              domain: 'Physics',
              mastered_count: 0,
              learning_count: 0,
              review_due_count: 0,
              total_count: 8,
            },
          ],
        },
      ],
      windows: [],
      streak_days: 0,
    })
    const wrapper = mountCastle({ castle: zeroCastle })
    const body = wrapper.find('.castle-body')
    expect(body.exists()).toBe(true)
    expect(body.findAll('.tower')).toHaveLength(1)
    // Empty floors still render — the castle exists on day one.
    expect(body.find('.floor--empty').exists()).toBe(true)
    // No streak line when streak is 0
    expect(body.find('.castle-header__streak').exists()).toBe(false)
  })

  it('shows the empty message when there are no towers at all', () => {
    const emptyCastle = makeCastle({ towers: [], windows: [], streak_days: 0 })
    const wrapper = mountCastle({ castle: emptyCastle })
    expect(wrapper.find('.castle-empty').exists()).toBe(true)
    expect(wrapper.find('.tower').exists()).toBe(false)
  })

  it('marks review-due floors as decayed (never removes them)', () => {
    const decayedCastle = makeCastle({
      towers: [
        {
          subject: 'mathematics',
          mastered_count: 3,
          learning_count: 0,
          review_due_count: 1,
          total_count: 6,
          floors: [
            {
              domain: 'Algebra',
              mastered_count: 3,
              learning_count: 0,
              review_due_count: 1,
              total_count: 6,
            },
          ],
        },
      ],
    })
    const wrapper = mountCastle({ castle: decayedCastle })
    expect(wrapper.find('.floor--decayed').exists()).toBe(true)
  })

  it('windows are display-only — no click handler, no router navigation', async () => {
    const wrapper = mountCastle()
    const win = wrapper.find('.window')
    expect(win.exists()).toBe(true)
    // Observer mode: a span, not a button, and clicking emits nothing.
    expect(win.element.tagName).toBe('SPAN')
    expect(win.attributes('role')).toBeUndefined()
    await win.trigger('click')
    expect(wrapper.emitted()).not.toHaveProperty('windowSelect')
  })

  it('localises the tower a11y summary using the real subject label', () => {
    const wrapper = mountCastle()
    const sr = wrapper.find('.sr-only')
    expect(sr.exists()).toBe(true)
    // learning.subjectMathematics = 数学 — not the raw slug.
    expect(sr.text()).toContain('数学')
    expect(sr.text()).toContain('2')
    expect(sr.text()).toContain('10')
  })

  it('renders the review-due reason in the active locale, not the raw Chinese sentinel', () => {
    const reviewCastle = makeCastle({
      windows: [
        {
          topic_id: '202',
          topic_name: 'Fractions',
          topic_name_zh: 'Fractions',
          reason: '复习到期',
          subject: 'mathematics',
          domain: 'Algebra',
        },
      ],
    })
    const wrapper = mountCastle({ castle: reviewCastle }, 'en-US')
    const win = wrapper.find('.window')
    // en-US tooltip must not leak the Chinese reason string.
    expect(win.attributes('title')).toContain('Review due')
    expect(win.classes()).toContain('window--review')
  })
})
