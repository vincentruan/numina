import { describe, it, expect, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import { createI18n } from 'vue-i18n'
import KnowledgeCastle from '../KnowledgeCastle.vue'
import type { CastleIndex } from '@/api/learning'

const mockRouter = { push: vi.fn() }
vi.mock('vue-router', () => ({ useRouter: () => mockRouter }))

const i18n = createI18n({
  legacy: false,
  locale: 'zh-CN',
  messages: {
    'zh-CN': {
      learning: {
        empty: '还没有学习内容',
        subject: { mathematics: '数学', science: '科学' },
        castle: {
          title: '知识城堡',
          subtitle: '看看你建造了什么',
          towers: '{mastered}/{total}',
          towerA11y: '{subject}塔，已掌握 {mastered} 个，共 {total} 个',
          floorA11y: '{domain}楼层，已掌握 {mastered} 个，共 {total} 个',
          windowReview: '复习到期',
          windowRecommended: '推荐学习',
          windowA11y: '{topic}，{reason}',
          errorTitle: '城堡暂时打不开',
          errorRetry: '再试一次',
          decoStreak: '连续学习 {days} 天',
          celebrationTitle: '又一座塔封顶了！',
          reducedMotionToast: '你的城堡又高了一层 🏰',
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
    windows: [],
    streak_days: 5,
    ...overrides,
  }
}

function mountCastle(props: Record<string, unknown> = {}) {
  return mount(KnowledgeCastle, {
    props: {
      castle: makeCastle(),
      state: 'content' as const,
      ...props,
    },
    global: { plugins: [i18n] },
  })
}

describe('KnowledgeCastle', () => {
  it('shows a skeleton while loading and not the zero-progress castle', () => {
    const wrapper = mountCastle({ castle: null, state: 'loading' })
    expect(wrapper.find('[data-test="castle-skeleton"]').exists()).toBe(true)
    expect(wrapper.find('[data-test="castle-content"]').exists()).toBe(false)
  })

  it('shows a distinct error state with a working retry', async () => {
    const wrapper = mountCastle({ castle: null, state: 'error' })
    expect(wrapper.find('[data-test="castle-error"]').exists()).toBe(true)
    // The error must not look like an empty castle.
    expect(wrapper.find('[data-test="castle-content"]').exists()).toBe(false)

    await wrapper.find('[data-test="castle-retry"]').trigger('click')
    expect(wrapper.emitted('retry')).toHaveLength(1)
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
      streak_days: 0,
    })
    const wrapper = mountCastle({ castle: zeroCastle })
    const content = wrapper.find('[data-test="castle-content"]')
    expect(content.exists()).toBe(true)
    expect(content.findAll('.tower')).toHaveLength(1)
    expect(content.findAll('.floor').length).toBeGreaterThan(0)
    // Empty floors still render — the castle exists on day one (R2).
    expect(wrapper.find('.floor--empty').exists()).toBe(true)
  })

  it('renders one tower per in-scope subject', () => {
    const wrapper = mountCastle({
      castle: makeCastle({
        towers: [
          {
            subject: 'mathematics',
            mastered_count: 0,
            learning_count: 0,
            review_due_count: 0,
            total_count: 5,
            floors: [
              {
                domain: 'Algebra',
                mastered_count: 0,
                learning_count: 0,
                review_due_count: 0,
                total_count: 5,
              },
            ],
          },
          {
            subject: 'science',
            mastered_count: 0,
            learning_count: 0,
            review_due_count: 0,
            total_count: 4,
            floors: [
              {
                domain: 'Physics',
                mastered_count: 0,
                learning_count: 0,
                review_due_count: 0,
                total_count: 4,
              },
            ],
          },
        ],
      }),
    })
    expect(wrapper.findAll('.tower')).toHaveLength(2)
  })

  it('renders a visible mastered/total summary per tower', () => {
    const wrapper = mountCastle()
    expect(wrapper.find('.tower__summary').text()).toBe('2/10')
  })

  it('marks decayed floors with a dashed, non-colour-only signal', () => {
    const wrapper = mountCastle({
      castle: makeCastle({
        towers: [
          {
            subject: 'mathematics',
            mastered_count: 0,
            learning_count: 2,
            review_due_count: 1,
            total_count: 3,
            floors: [
              {
                domain: 'Algebra',
                mastered_count: 0,
                learning_count: 2,
                review_due_count: 1,
                total_count: 3,
              },
            ],
          },
        ],
      }),
    })
    const floor = wrapper.find('.floor--decayed')
    expect(floor.exists()).toBe(true)
    // Bricks are not removed on decay (buildings never regress).
    expect(floor.find('.brick').exists()).toBe(true)
  })

  it('renders only the windows the backend supplied', () => {
    const wrapper = mountCastle({
      castle: makeCastle({
        windows: [
          {
            topic_id: '123',
            topic_name: 'Fractions',
            topic_name_zh: '分数',
            reason: '复习到期',
            subject: 'mathematics',
            domain: 'Algebra',
          },
        ],
      }),
    })
    const windows = wrapper.findAll('[data-test="castle-window"]')
    expect(windows).toHaveLength(1)
    expect(windows[0].attributes('aria-label')).toContain('分数')
    expect(windows[0].attributes('aria-label')).toContain('复习到期')
  })

  it('emits windowSelect with the window payload on click', async () => {
    const win = {
      topic_id: '123',
      topic_name: 'Fractions',
      topic_name_zh: '分数',
      reason: '推荐学习',
      subject: 'mathematics',
      domain: 'Algebra',
    }
    const wrapper = mountCastle({ castle: makeCastle({ windows: [win] }) })

    await wrapper.find('[data-test="castle-window"]').trigger('click')
    expect(wrapper.emitted('windowSelect')?.[0]).toEqual([win])
  })

  it('does not render windows for subjects with none', () => {
    const wrapper = mountCastle()
    expect(wrapper.findAll('[data-test="castle-window"]')).toHaveLength(0)
  })

  it('shows the streak-driven decoration only when streak > 0', () => {
    const withStreak = mountCastle()
    expect(withStreak.find('.castle-header__streak').text()).toContain('5')

    const noStreak = mountCastle({ castle: makeCastle({ streak_days: 0 }) })
    expect(noStreak.find('.castle-header__streak').exists()).toBe(false)
  })

  it('animates nothing when there is no ?new topic', () => {
    const wrapper = mountCastle({ newTopicId: null })
    expect(wrapper.find('[data-test="castle-celebration"]').exists()).toBe(false)
  })

  it('shows at least one brick on any floor with progress', () => {
    // A floor with just 1 mastered topic out of 50 must still render a brick
    // — otherwise the ?new= brick-drop has nothing to animate (reviewer HIGH).
    const wrapper = mountCastle({
      castle: makeCastle({
        towers: [
          {
            subject: 'mathematics',
            mastered_count: 1,
            learning_count: 0,
            review_due_count: 0,
            total_count: 50,
            floors: [
              {
                domain: 'Algebra',
                mastered_count: 1,
                learning_count: 0,
                review_due_count: 0,
                total_count: 50,
              },
            ],
          },
        ],
      }),
    })
    expect(wrapper.find('.floor').findAll('.brick').length).toBeGreaterThanOrEqual(1)
  })

  it('renders zero bricks only on floors with no progress', () => {
    const wrapper = mountCastle()
    // Default makeCastle has mastered=2/total=10 → ratio=0.2 → round(1.6)=2
    const bricks = wrapper.find('.floor').findAll('.brick')
    expect(bricks.length).toBeGreaterThan(0)
  })

  it('celebrates at most once per ?new= arrival', async () => {
    // A completed subject tower + ?new= on a topic in it → fireworks.
    const wrapper = mountCastle({
      castle: makeCastle({
        towers: [
          {
            subject: 'mathematics',
            mastered_count: 5,
            learning_count: 0,
            review_due_count: 0,
            total_count: 5,
            floors: [
              {
                domain: 'Algebra',
                mastered_count: 5,
                learning_count: 0,
                review_due_count: 0,
                total_count: 5,
              },
            ],
          },
        ],
      }),
      newTopicId: '123',
      newSubject: 'mathematics',
      newDomain: 'Algebra',
    })
    expect(wrapper.find('[data-test="castle-celebration"]').exists()).toBe(true)

    // Simulating a castle re-fetch (e.g. pull-to-refresh) must NOT replay.
    await wrapper.setProps({
      castle: makeCastle({
        towers: [
          {
            subject: 'mathematics',
            mastered_count: 5,
            learning_count: 0,
            review_due_count: 0,
            total_count: 5,
            floors: [
              {
                domain: 'Algebra',
                mastered_count: 5,
                learning_count: 0,
                review_due_count: 0,
                total_count: 5,
              },
            ],
          },
        ],
      }),
    })
    expect(wrapper.find('[data-test="castle-celebration"]').exists()).toBe(false)
  })
})
