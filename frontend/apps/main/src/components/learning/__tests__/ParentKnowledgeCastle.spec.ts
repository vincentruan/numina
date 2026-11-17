import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import { createI18n } from 'vue-i18n'
import ParentKnowledgeCastle from '../ParentKnowledgeCastle.vue'
import type { CastleIndex } from '@/api/learning'

const i18n = createI18n({
  legacy: false,
  locale: 'zh-CN',
  messages: {
    'zh-CN': {
      learning: {
        subject: { mathematics: '数学', science: '科学' },
        castle: {
          parentTitle: '知识城堡',
          parentSubtitle: '看看孩子建造了什么',
          parentEmpty: '暂无学习内容',
          towers: '{mastered}/{total}',
          towerA11y: '{subject}塔，已掌握 {mastered} 个，共 {total} 个',
          floorA11y: '{domain}楼层，已掌握 {mastered} 个，共 {total} 个',
          windowReview: '复习到期',
          windowRecommended: '推荐学习',
          windowA11y: '{topic}，{reason}',
          decoStreak: '连续学习 {days} 天',
          errorTitle: '城堡暂时打不开',
          errorRetry: '再试一次',
        },
      },
    },
  },
})

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

function mountCastle(props: Record<string, unknown> = {}) {
  return mount(ParentKnowledgeCastle, {
    props: {
      castle: makeCastle(),
      state: 'content' as const,
      ...props,
    },
    global: { plugins: [i18n] },
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
})
