import { describe, it, expect, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import { createI18n } from 'vue-i18n'
import zhCN from '@/i18n/locales/zh-CN'
import enUS from '@/i18n/locales/en-US'
import type { PracticeResultResponse } from '@/api/practice'
import PracticeResultSummary from '../PracticeResultSummary.vue'

const mockRouter = { push: vi.fn() }
vi.mock('vue-router', () => ({ useRouter: () => mockRouter }))

function makeResult(overrides: Partial<PracticeResultResponse> = {}): PracticeResultResponse {
  return {
    session_id: 's1',
    total_score: 1,
    correct_count: 5,
    total_count: 5,
    xp_earned: 10,
    coins_earned: 10,
    mastery_changed: true,
    new_mastery_level: 'mastered',
    ...overrides,
  }
}

function mountSummary(props: Record<string, unknown>) {
  const i18n = createI18n({
    legacy: false,
    locale: 'zh-CN',
    messages: { 'zh-CN': zhCN, 'en-US': enUS },
  })
  return mount(PracticeResultSummary, {
    props: props as never,
    global: { plugins: [i18n] },
  })
}

describe('PracticeResultSummary — castle CTA (U9, R5, F1)', () => {
  it('renders the castle copy and CTA on first mastery', () => {
    const wrapper = mountSummary({
      result: makeResult(),
      topicId: '123456789012345678',
      isFirstMastery: true,
    })

    expect(wrapper.find('[data-test="castle-cta"]').exists()).toBe(true)
    // Castle copy owns the primary discovery slot (R5).
    expect(wrapper.find('.result-discovery__text').text()).toBe(
      zhCN.learning.castle.brickDropped,
    )
  })

  it('navigates to the castle with ?new=<topicId>', async () => {
    const wrapper = mountSummary({
      result: makeResult(),
      topicId: '123456789012345678',
      isFirstMastery: true,
    })

    await wrapper.find('[data-test="castle-cta"]').trigger('click')
    expect(mockRouter.push).toHaveBeenCalledWith(
      '/learning/castle?new=123456789012345678',
    )
  })

  it('keeps XP in the secondary rewards row, not the primary slot', () => {
    const wrapper = mountSummary({
      result: makeResult(),
      topicId: '123',
      isFirstMastery: true,
    })

    const rewards = wrapper.find('.result-rewards').text()
    expect(rewards).toContain('+10 XP')
    expect(wrapper.find('.result-discovery__text').text()).not.toContain('XP')
  })

  it('does not render the CTA for non-first mastery', () => {
    const wrapper = mountSummary({
      result: makeResult({ mastery_changed: true, new_mastery_level: 'learning' }),
      topicId: '123',
      isFirstMastery: false,
    })

    expect(wrapper.find('[data-test="castle-cta"]').exists()).toBe(false)
    expect(wrapper.find('.result-discovery__text').text()).not.toBe(
      zhCN.learning.castle.brickDropped,
    )
  })

  it('does not render the CTA without a topic id', () => {
    const wrapper = mountSummary({
      result: makeResult(),
      isFirstMastery: true,
    })

    expect(wrapper.find('[data-test="castle-cta"]').exists()).toBe(false)
  })
})
