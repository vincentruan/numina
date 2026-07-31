import { describe, it, expect, beforeEach, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import { createI18n } from 'vue-i18n'
import SignaturePad from '@/components/manifesto/SignaturePad.vue'

const i18n = createI18n({
  legacy: false,
  locale: 'zh-CN',
  messages: {
    'zh-CN': { manifesto: { clearSignature: '清除签名' } },
  },
})

// Mock canvas context
const mockCtx = {
  scale: vi.fn(),
  clearRect: vi.fn(),
  beginPath: vi.fn(),
  moveTo: vi.fn(),
  lineTo: vi.fn(),
  stroke: vi.fn(),
  lineCap: 'round',
  lineJoin: 'round',
  lineWidth: 1,
  strokeStyle: '#000',
}

function mountComponent(props: Record<string, unknown> = {}) {
  return mount(SignaturePad, {
    props: { width: 300, height: 150, ...props },
    global: { plugins: [i18n] },
  })
}

beforeEach(() => {
  vi.spyOn(HTMLCanvasElement.prototype, 'getContext').mockReturnValue(mockCtx as unknown as CanvasRenderingContext2D)
  vi.spyOn(HTMLCanvasElement.prototype, 'toDataURL').mockReturnValue('data:image/png;base64,abc123')
  vi.spyOn(window, 'getComputedStyle').mockReturnValue({
    getPropertyValue: () => '#000',
  } as unknown as CSSStyleDeclaration)
})

describe('SignaturePad — U3', () => {
  it('renders canvas with correct dimensions', () => {
    const wrapper = mountComponent({ width: 300, height: 150 })
    const canvas = wrapper.find('canvas')
    expect(canvas.exists()).toBe(true)
    expect(canvas.attributes('style')).toContain('width: 300px')
    expect(canvas.attributes('style')).toContain('height: 150px')
  })

  it('isEmpty() returns true initially', () => {
    const wrapper = mountComponent()
    expect((wrapper.vm as any).isEmpty()).toBe(true)
  })

  it('after drawing (simulate pointer events), isEmpty() returns false', async () => {
    const wrapper = mountComponent()
    const canvas = wrapper.find('canvas')
    await canvas.trigger('pointerdown', { clientX: 10, clientY: 10 })
    await canvas.trigger('pointermove', { clientX: 20, clientY: 20 })
    await canvas.trigger('pointerup', { clientX: 20, clientY: 20 })
    expect((wrapper.vm as any).isEmpty()).toBe(false)
  })

  it('clear() resets canvas to empty', async () => {
    const wrapper = mountComponent()
    const canvas = wrapper.find('canvas')
    await canvas.trigger('pointerdown', { clientX: 10, clientY: 10 })
    await canvas.trigger('pointermove', { clientX: 20, clientY: 20 })
    await canvas.trigger('pointerup', {})
    expect((wrapper.vm as any).isEmpty()).toBe(false)
    ;(wrapper.vm as any).clear()
    expect((wrapper.vm as any).isEmpty()).toBe(true)
  })

  it('toDataURL() returns valid data URL string', () => {
    const wrapper = mountComponent()
    const result = (wrapper.vm as any).toDataURL()
    expect(result).toBe('data:image/png;base64,abc123')
  })
})
