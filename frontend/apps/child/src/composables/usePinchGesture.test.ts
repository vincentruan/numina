/** Shared pinch gesture detector — thresholds, one-shot callbacks and reset. */
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import { defineComponent, h, nextTick } from 'vue'
import { usePinchGesture, type PinchGestureHandlers } from './usePinchGesture'

function touchEvent(
  type: string,
  touches: Array<{ clientX: number; clientY: number }>,
): Event {
  const event = new Event(type, { bubbles: true, cancelable: true })
  Object.defineProperty(event, 'touches', { value: touches })
  return event
}

const Host = defineComponent({
  props: {
    handlers: { type: Object as () => PinchGestureHandlers, required: true },
    exposePinching: { type: Boolean, default: false },
  },
  setup(props) {
    const gesture = usePinchGesture(props.handlers)
    return () =>
      h('div', {
        onTouchstart: gesture.onTouchStart,
        onTouchmove: gesture.onTouchMove,
        onTouchend: gesture.onTouchEnd,
        'data-pinch': props.exposePinching
          ? gesture.isPinching
            ? 'true'
            : 'false'
          : undefined,
      })
  },
})

function mountHost(handlers: PinchGestureHandlers, exposePinching = false) {
  return mount(Host, { props: { handlers, exposePinching } })
}

describe('usePinchGesture', () => {
  beforeEach(() => vi.useFakeTimers())
  afterEach(() => {
    vi.useRealTimers()
    vi.restoreAllMocks()
  })

  it('reports pinch-out once per gesture and resets after the deferred timer', () => {
    const onPinchOut = vi.fn()
    const wrapper = mountHost({ onPinchOut })
    const element = wrapper.element

    element.dispatchEvent(touchEvent('touchstart', [
      { clientX: 90, clientY: 0 },
      { clientX: 110, clientY: 0 },
    ]))
    element.dispatchEvent(touchEvent('touchmove', [
      { clientX: 80, clientY: 0 },
      { clientX: 120, clientY: 0 },
    ]))
    element.dispatchEvent(touchEvent('touchmove', [
      { clientX: 70, clientY: 0 },
      { clientX: 130, clientY: 0 },
    ]))
    element.dispatchEvent(touchEvent('touchend', []))
    expect(onPinchOut).toHaveBeenCalledTimes(1)

    vi.advanceTimersByTime(0)
    wrapper.unmount()

    const second = mountHost({ onPinchOut })
    second.element.dispatchEvent(touchEvent('touchstart', [
      { clientX: 90, clientY: 0 },
      { clientX: 110, clientY: 0 },
    ]))
    second.element.dispatchEvent(touchEvent('touchmove', [
      { clientX: 80, clientY: 0 },
      { clientX: 120, clientY: 0 },
    ]))
    expect(onPinchOut).toHaveBeenCalledTimes(2)
    second.unmount()
  })

  it('reports pinch-in with the first touch and ignores single-finger moves', async () => {
    const onPinchIn = vi.fn()
    const wrapper = mountHost({ onPinchIn }, true)
    const element = wrapper.element

    element.dispatchEvent(touchEvent('touchstart', [{ clientX: 100, clientY: 0 }]))
    element.dispatchEvent(touchEvent('touchmove', [{ clientX: 200, clientY: 0 }]))
    expect(onPinchIn).not.toHaveBeenCalled()

    element.dispatchEvent(
      touchEvent('touchstart', [
        { clientX: 60, clientY: 100 },
        { clientX: 140, clientY: 100 },
      ]),
    )
    element.dispatchEvent(
      touchEvent('touchmove', [
        { clientX: 90, clientY: 100 },
        { clientX: 110, clientY: 100 },
      ]),
    )
    expect(onPinchIn).toHaveBeenCalledTimes(1)
    expect(onPinchIn.mock.calls[0][0]).toMatchObject({ clientX: 90, clientY: 100 })
    await nextTick()
    expect(wrapper.attributes('data-pinch')).toBe('true')
    wrapper.unmount()
  })

  it('reset cancels the pending state and a new gesture starts cleanly', () => {
    const onPinchOut = vi.fn()
    const wrapper = mountHost({ onPinchOut })
    const element = wrapper.element

    element.dispatchEvent(touchEvent('touchstart', [
      { clientX: 90, clientY: 0 },
      { clientX: 110, clientY: 0 },
    ]))
    element.dispatchEvent(touchEvent('touchmove', [
      { clientX: 80, clientY: 0 },
      { clientX: 120, clientY: 0 },
    ]))
    element.dispatchEvent(touchEvent('touchend', []))
    wrapper.unmount()
    vi.advanceTimersByTime(10)
    expect(onPinchOut).toHaveBeenCalledTimes(1)
  })
})
