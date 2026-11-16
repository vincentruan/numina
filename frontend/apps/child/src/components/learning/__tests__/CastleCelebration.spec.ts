import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount } from '@vue/test-utils'
import { createI18n } from 'vue-i18n'
import zhCN from '@/i18n/locales/zh-CN'
import enUS from '@/i18n/locales/en-US'
import CastleCelebration from '../CastleCelebration.vue'

let reducedMotion = false

vi.mock('@/composables/useReducedMotion', async () => {
  const { ref } = await import('vue')
  return { useReducedMotion: () => ref(reducedMotion) }
})

function mountCelebration() {
  const i18n = createI18n({
    legacy: false,
    locale: 'zh-CN',
    messages: { 'zh-CN': zhCN, 'en-US': enUS },
  })
  return mount(CastleCelebration, {
    global: { plugins: [i18n] },
  })
}

describe('CastleCelebration (KTD6, OQ3)', () => {
  beforeEach(() => {
    vi.useFakeTimers()
  })

  it('renders confetti and the celebration title with motion allowed', () => {
    reducedMotion = false
    const wrapper = mountCelebration()

    expect(wrapper.findAll('.confetti').length).toBeGreaterThan(0)
    expect(wrapper.text()).toContain(zhCN.learning.castle.celebrationTitle)
  })

  it('falls back to a text toast with no confetti under reduced motion', () => {
    reducedMotion = true
    const wrapper = mountCelebration()

    expect(wrapper.findAll('.confetti')).toHaveLength(0)
    expect(wrapper.text()).toContain(zhCN.learning.castle.reducedMotionToast)
    expect(wrapper.classes()).toContain('castle-celebration--static')
  })

  it('emits done after the celebration finishes', async () => {
    reducedMotion = true
    const wrapper = mountCelebration()
    await vi.advanceTimersByTimeAsync(2000)

    expect(wrapper.emitted('done')).toBeTruthy()
  })
})
