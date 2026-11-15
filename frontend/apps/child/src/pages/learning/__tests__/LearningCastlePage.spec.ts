import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { createI18n } from 'vue-i18n'
import zhCN from '@/i18n/locales/zh-CN'
import enUS from '@/i18n/locales/en-US'
import type { CastleIndex } from '@/api/learning'

const mockRouter = { push: vi.fn(), replace: vi.fn() }
let mockQuery: Record<string, unknown> = {}

vi.mock('vue-router', () => ({
  useRouter: () => mockRouter,
  useRoute: () => ({ params: {}, query: mockQuery }),
}))

const mockFetchCastle = vi.fn()
const mockGetTopicDetail = vi.fn()
vi.mock('@/api/learning', () => ({
  fetchCastle: () => mockFetchCastle(),
  getTopicDetail: (id: string) => mockGetTopicDetail(id),
}))

import LearningCastlePage from '../LearningCastlePage.vue'

function makeCastle(overrides: Partial<CastleIndex> = {}): CastleIndex {
  return {
    towers: [
      {
        subject: 'mathematics',
        mastered_count: 1,
        learning_count: 0,
        review_due_count: 0,
        total_count: 4,
        floors: [
          {
            domain: 'Algebra',
            mastered_count: 1,
            learning_count: 0,
            review_due_count: 0,
            total_count: 4,
          },
        ],
      },
    ],
    windows: [
      {
        topic_id: '999',
        topic_name: 'Fractions',
        topic_name_zh: '分数',
        reason: '复习到期',
        subject: 'mathematics',
        domain: 'Algebra',
      },
    ],
    streak_days: 3,
    ...overrides,
  }
}

function mountPage() {
  const i18n = createI18n({
    legacy: false,
    locale: 'zh-CN',
    messages: { 'zh-CN': zhCN, 'en-US': enUS },
  })
  return mount(LearningCastlePage, {
    global: {
      plugins: [i18n],
      stubs: {
        VanPullRefresh: { template: '<div><slot /></div>' },
      },
    },
  })
}

describe('LearningCastlePage', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mockQuery = {}
  })

  it('loads the castle and renders content', async () => {
    mockFetchCastle.mockResolvedValue(makeCastle())
    const wrapper = mountPage()
    await flushPromises()

    expect(mockFetchCastle).toHaveBeenCalledOnce()
    expect(wrapper.find('[data-test="castle-content"]').exists()).toBe(true)
  })

  it('shows the error state when the request fails', async () => {
    mockFetchCastle.mockRejectedValue(new Error('boom'))
    const wrapper = mountPage()
    await flushPromises()

    expect(wrapper.find('[data-test="castle-error"]').exists()).toBe(true)
    // Critically: the failure is never rendered as an empty castle.
    expect(wrapper.find('[data-test="castle-content"]').exists()).toBe(false)
  })

  it('captures ?new= and clears it from the URL', async () => {
    mockQuery = { new: '123' }
    mockFetchCastle.mockResolvedValue(makeCastle())
    mockGetTopicDetail.mockResolvedValue({
      id: '123',
      subject: 'mathematics',
      domain: 'Algebra',
    })
    mountPage()
    await flushPromises()

    expect(mockRouter.replace).toHaveBeenCalledWith({
      query: expect.objectContaining({ new: undefined }),
    })
  })

  it('animates only the floor owning the ?new topic', async () => {
    mockQuery = { new: '123' }
    mockFetchCastle.mockResolvedValue(makeCastle())
    mockGetTopicDetail.mockResolvedValue({
      id: '123',
      subject: 'mathematics',
      domain: 'Algebra',
    })
    const wrapper = mountPage()
    await flushPromises()

    const animated = wrapper.findAll('.floor--brick-drop')
    expect(animated).toHaveLength(1)
  })

  it('animates nothing on a spontaneous open', async () => {
    mockFetchCastle.mockResolvedValue(makeCastle())
    const wrapper = mountPage()
    await flushPromises()

    expect(wrapper.findAll('.floor--brick-drop')).toHaveLength(0)
  })

  it('still renders the castle when the ?new topic cannot be resolved', async () => {
    mockQuery = { new: '404404' }
    mockFetchCastle.mockResolvedValue(makeCastle())
    mockGetTopicDetail.mockRejectedValue(new Error('gone'))
    const wrapper = mountPage()
    await flushPromises()

    expect(wrapper.find('[data-test="castle-content"]').exists()).toBe(true)
    expect(wrapper.findAll('.floor--brick-drop')).toHaveLength(0)
  })

  it('does not touch the URL when there is no ?new=', async () => {
    mockFetchCastle.mockResolvedValue(makeCastle())
    mountPage()
    await flushPromises()

    expect(mockRouter.replace).not.toHaveBeenCalled()
  })

  it('drops the window and the decay marker once the review is done (F2)', async () => {
    // Before: one overdue window, its floor shows cracks.
    mockFetchCastle.mockResolvedValueOnce(
      makeCastle({
        towers: [
          {
            subject: 'mathematics',
            mastered_count: 1,
            learning_count: 0,
            review_due_count: 1,
            total_count: 4,
            floors: [
              {
                domain: 'Algebra',
                mastered_count: 1,
                learning_count: 0,
                review_due_count: 1,
                total_count: 4,
              },
            ],
          },
        ],
      }),
    )
    const wrapper = mountPage()
    await flushPromises()
    expect(wrapper.findAll('[data-test="castle-window"]')).toHaveLength(1)
    expect(wrapper.find('.floor--decayed').exists()).toBe(true)

    // After the review: the server no longer reports it due, and drops the decay flag.
    mockFetchCastle.mockResolvedValueOnce(
      makeCastle({
        towers: [
          {
            subject: 'mathematics',
            mastered_count: 1,
            learning_count: 0,
            review_due_count: 0,
            total_count: 4,
            floors: [
              {
                domain: 'Algebra',
                mastered_count: 1,
                learning_count: 0,
                review_due_count: 0,
                total_count: 4,
              },
            ],
          },
        ],
        windows: [],
      }),
    )
    // Trigger the pull-to-refresh path the page exposes.
    await wrapper.findComponent({ name: 'KnowledgeCastle' }).vm.$emit('retry')
    await flushPromises()

    expect(wrapper.findAll('[data-test="castle-window"]')).toHaveLength(0)
    expect(wrapper.find('.floor--decayed').exists()).toBe(false)
  })

  it('routes review windows to review mode and recommended ones to practice', async () => {
    mockFetchCastle.mockResolvedValue(
      makeCastle({
        windows: [
          {
            topic_id: '111',
            topic_name: 'A',
            topic_name_zh: 'A',
            reason: '复习到期',
            subject: 'mathematics',
            domain: 'Algebra',
          },
          {
            topic_id: '222',
            topic_name: 'B',
            topic_name_zh: 'B',
            reason: '推荐学习',
            subject: 'mathematics',
            domain: 'Algebra',
          },
        ],
      }),
    )
    const wrapper = mountPage()
    await flushPromises()

    const windows = wrapper.findAll('[data-test="castle-window"]')
    expect(windows).toHaveLength(2)

    await windows[0].trigger('click')
    expect(mockRouter.push).toHaveBeenCalledWith('/learning/practice/111?mode=review')

    await windows[1].trigger('click')
    expect(mockRouter.push).toHaveBeenCalledWith('/learning/practice/222?mode=practice')
  })
})
