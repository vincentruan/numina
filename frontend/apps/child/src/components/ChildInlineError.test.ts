import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { mount } from '@vue/test-utils'
import ChildInlineError from './ChildInlineError.vue'

describe('ChildInlineError', () => {
  beforeEach(() => {
    vi.useFakeTimers()
  })

  afterEach(() => {
    vi.useRealTimers()
  })

  it('renders nothing when visible is false', () => {
    const wrapper = mount(ChildInlineError, {
      props: { visible: false, message: 'Oops' },
    })
    expect(wrapper.find('.child-inline-error').exists()).toBe(false)
  })

  it('renders message when visible is true', () => {
    const wrapper = mount(ChildInlineError, {
      props: { visible: true, message: 'Something went wrong' },
    })
    expect(wrapper.find('.child-inline-error').exists()).toBe(true)
    expect(wrapper.text()).toContain('Something went wrong')
  })

  it('has accessible role="alert" and aria-live="polite"', () => {
    const wrapper = mount(ChildInlineError, {
      props: { visible: true, message: 'Test' },
    })
    const el = wrapper.find('.child-inline-error')
    expect(el.attributes('role')).toBe('alert')
    expect(el.attributes('aria-live')).toBe('polite')
  })

  it('auto-dismisses after 3 seconds', async () => {
    const wrapper = mount(ChildInlineError, {
      props: { visible: false, message: 'Test' },
    })
    await wrapper.setProps({ visible: true })
    expect(wrapper.emitted('update:visible')).toBeUndefined()

    await vi.advanceTimersByTimeAsync(3000)
    expect(wrapper.emitted('update:visible')).toEqual([[false]])
  })

  it('does not use error class or inline red color', () => {
    const wrapper = mount(ChildInlineError, {
      props: { visible: true, message: 'Test' },
    })
    const el = wrapper.find('.child-inline-error')
    // Uses CSS variables, no hardcoded red color
    expect((el.element as HTMLElement).style.color).not.toBe('red')
    expect(el.classes()).not.toContain('error')
  })
})
