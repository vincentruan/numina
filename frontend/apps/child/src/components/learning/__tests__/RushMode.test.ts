import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { createI18n } from 'vue-i18n'
import zhCN from '@/i18n/locales/zh-CN'
import enUS from '@/i18n/locales/en-US'

vi.mock('@/api/practice', () => ({
  createPracticeSession: vi.fn(),
  batchGetQuestions: vi.fn(),
}))

import { createPracticeSession, batchGetQuestions } from '@/api/practice'
import RushMode from '../RushMode.vue'

const mockCreateSession = vi.mocked(createPracticeSession)
const mockBatchGet = vi.mocked(batchGetQuestions)

function makeQuestions(n: number) {
  return Array.from({ length: n }, (_, i) => ({
    id: `q-${i}`,
    topic_id: 'topic-1',
    question_type: 'multiple_choice' as const,
    stem: `Q${i}?`,
    stem_zh: null,
    options: [
      { key: 'A', text: `Option A${i}` },
      { key: 'B', text: `Option B${i}` },
    ],
    answer: { answer: i % 2 === 0 ? 'A' : 'B' },
    solution: null,
    difficulty: 1,
    bloom_level: 'apply',
    source: 'template',
    review_status: 'approved',
    age_group: 'mid',
    parameters: null,
    times_used: 0,
    correct_count: 0,
  }))
}

function mountRush(props: { topicId?: string; durationSeconds?: number } = {}) {
  const i18n = createI18n({
    legacy: false,
    locale: 'en-US',
    messages: { 'en-US': enUS, 'zh-CN': zhCN },
  })
  return mount(RushMode, {
    props: { topicId: 'topic-1', durationSeconds: 5, ...props },
    global: { plugins: [i18n] },
  })
}

describe('RushMode', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mockCreateSession.mockResolvedValue({
      id: 'rush-session',
      child_id: 'child-1',
      topic_id: 'topic-1',
      session_mode: 'rush',
      question_ids: ['q-0', 'q-1', 'q-2', 'q-3', 'q-4'],
      started_at: new Date().toISOString(),
      ended_at: null,
      total_score: null,
      completed_count: 0,
      source: 'adaptive',
      learning_progress_id: null,
    })
    mockBatchGet.mockResolvedValue(makeQuestions(5))
    vi.useFakeTimers()
  })

  afterEach(() => {
    vi.useRealTimers()
  })

  it('creates a session with session_mode=rush on mount', async () => {
    mountRush()
    await flushPromises()
    expect(mockCreateSession).toHaveBeenCalledWith(
      expect.objectContaining({ session_mode: 'rush' }),
    )
  })

  it('shows loading while fetching questions', () => {
    mockCreateSession.mockReturnValue(new Promise(() => {}))
    const wrapper = mountRush()
    expect(wrapper.find('.rush-state--loading').exists()).toBe(true)
  })

  it('shows error state with retry button when fetching fails', async () => {
    mockCreateSession.mockRejectedValue(new Error('network'))
    const wrapper = mountRush()
    await flushPromises()
    expect(wrapper.find('.rush-state--error').exists()).toBe(true)
    expect(wrapper.find('.rush-retry-btn').exists()).toBe(true)
  })

  it('renders the question stem and options after loading', async () => {
    const wrapper = mountRush()
    await flushPromises()
    expect(wrapper.find('.rush-question__stem').exists()).toBe(true)
    expect(wrapper.findAll('.rush-option')).toHaveLength(2)
  })

  it('counts correct answers client-side', async () => {
    const wrapper = mountRush()
    await flushPromises()
    // Q0 answer is 'A' — correct
    await wrapper.findAll('.rush-option')[0].trigger('click')
    await wrapper.find('.rush-submit').trigger('click')
    expect(wrapper.find('.rush-score').text()).toContain('1')
  })

  it('does not count wrong answers', async () => {
    const wrapper = mountRush()
    await flushPromises()
    // Q0 answer is 'A'; clicking B is wrong
    await wrapper.findAll('.rush-option')[1].trigger('click')
    await wrapper.find('.rush-submit').trigger('click')
    expect(wrapper.find('.rush-score').text()).toContain('0')
  })

  it('ticking the timer decreases secondsLeft', async () => {
    const wrapper = mountRush({ durationSeconds: 3 })
    await flushPromises()
    expect(wrapper.find('.rush-timer').text()).toContain('3')
    await vi.advanceTimersByTimeAsync(1000)
    expect(wrapper.find('.rush-timer').text()).toContain('2')
  })

  it('finishes with remaining time when all questions answered early', async () => {
    const wrapper = mountRush({ durationSeconds: 60 })
    await flushPromises()
    // Answer all 5 questions
    for (let i = 0; i < 5; i++) {
      await wrapper.findAll('.rush-option')[0].trigger('click')
      await wrapper.find('.rush-submit').trigger('click')
      if (i < 4) await flushPromises()
    }
    await flushPromises()
    expect(wrapper.find('.rush-finished').exists()).toBe(true)
    expect(wrapper.find('.rush-finished__time-left').exists()).toBe(true)
  })

  it('emits exit when the exit button is tapped (no confirmation)', async () => {
    const wrapper = mountRush()
    await flushPromises()
    await wrapper.find('.rush-exit').trigger('click')
    expect(wrapper.emitted('exit')).toBeTruthy()
  })

  it('finishes when the timer hits zero', async () => {
    const wrapper = mountRush({ durationSeconds: 2 })
    await flushPromises()
    await vi.advanceTimersByTimeAsync(2000)
    await flushPromises()
    expect(wrapper.find('.rush-finished').exists()).toBe(true)
    // Not an early finish — the timer ran out, not the questions.
    expect(wrapper.find('.rush-finished__time-left').exists()).toBe(false)
  })

  it('does not persist any state in sessionStorage', async () => {
    const wrapper = mountRush()
    await flushPromises()
    await wrapper.findAll('.rush-option')[0].trigger('click')
    await wrapper.find('.rush-submit').trigger('click')
    const rushKeys = Object.keys(sessionStorage).filter((k) => k.includes('rush'))
    expect(rushKeys).toEqual([])
  })
})
