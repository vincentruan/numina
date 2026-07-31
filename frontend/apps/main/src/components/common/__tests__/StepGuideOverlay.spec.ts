import { describe, it, expect, vi } from 'vitest'
import { mount } from '@vue/test-utils'

vi.mock('vue-i18n', () => ({
  useI18n: () => ({ t: (key: string) => key }),
}))

import StepGuideOverlay from '../StepGuideOverlay.vue'

const mockSteps = [
  { selector: '.target-1', mode: 'spotlight' as const, title: 'Step 1', desc: 'First step' },
  { selector: '.target-2', mode: 'spotlight' as const, title: 'Step 2', desc: 'Second step' },
]

describe('StepGuideOverlay', () => {
  it('does not render when visible=false', () => {
    const wrapper = mount(StepGuideOverlay, {
      props: { visible: false, steps: mockSteps, currentStep: 0 },
      global: { stubs: { teleport: true } },
    })
    expect(wrapper.find('.stepguide-overlay').exists()).toBe(false)
  })

  it('renders overlay when visible=true', () => {
    const wrapper = mount(StepGuideOverlay, {
      props: { visible: true, steps: mockSteps, currentStep: 0 },
      global: { stubs: { teleport: true } },
    })
    expect(wrapper.find('.stepguide-overlay').exists()).toBe(true)
  })

  it('emits skip when skip button clicked', async () => {
    const wrapper = mount(StepGuideOverlay, {
      props: { visible: true, steps: mockSteps, currentStep: 0 },
      global: { stubs: { teleport: true } },
    })
    await wrapper.find('.stepguide-btn--ghost').trigger('click')
    expect(wrapper.emitted('skip')).toBeTruthy()
  })

  it('emits next when next button clicked on non-last step', async () => {
    const wrapper = mount(StepGuideOverlay, {
      props: { visible: true, steps: mockSteps, currentStep: 0 },
      global: { stubs: { teleport: true } },
    })
    await wrapper.find('.stepguide-btn--primary').trigger('click')
    expect(wrapper.emitted('next')).toBeTruthy()
  })

  it('emits complete when done button clicked on last step', async () => {
    const wrapper = mount(StepGuideOverlay, {
      props: { visible: true, steps: mockSteps, currentStep: 1 },
      global: { stubs: { teleport: true } },
    })
    await wrapper.find('.stepguide-btn--primary').trigger('click')
    expect(wrapper.emitted('complete')).toBeTruthy()
  })

  it('renders aria-live region for screen readers', () => {
    const wrapper = mount(StepGuideOverlay, {
      props: { visible: true, steps: mockSteps, currentStep: 0 },
      global: { stubs: { teleport: true } },
    })
    expect(wrapper.find('[aria-live="polite"]').exists()).toBe(true)
  })
})
