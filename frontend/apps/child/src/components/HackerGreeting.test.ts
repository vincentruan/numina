import { describe, it, expect, beforeEach, vi } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { createI18n } from 'vue-i18n'

const i18n = createI18n({
  legacy: false,
  locale: 'zh-CN',
  messages: {
    'zh-CN': {
      home: {
        greetingPhrases: [
          '你好，{name}！已加载 {balance} 颗星 ⭐',
          '系统就绪 // {name} 的星库：{balance} ⭐',
        ],
        greetingFallback: '你好，{name}！已加载 {balance} 颗星 ⭐',
        greetingFallbackName: '小探险家',
      },
    },
  },
})

let mqMatches: boolean
let rafQueue: Array<() => void>

function flushRaf(count: number) {
  for (let i = 0; i < count; i++) {
    const next = rafQueue.shift()
    if (next) next()
  }
}

describe('HackerGreeting', () => {
  beforeEach(() => {
    mqMatches = false
    rafQueue = []
    vi.stubGlobal('requestAnimationFrame', (cb: () => void) => {
      rafQueue.push(cb)
      return rafQueue.length
    })
    vi.stubGlobal('cancelAnimationFrame', () => {
      /* no-op */
    })
    Object.defineProperty(window, 'matchMedia', {
      configurable: true,
      writable: true,
      value: vi.fn().mockImplementation(() => ({
        get matches() {
          return mqMatches
        },
        addEventListener: vi.fn(),
        removeEventListener: vi.fn(),
        addListener: vi.fn(),
        removeListener: vi.fn(),
        dispatchEvent: vi.fn(),
        media: '(prefers-reduced-motion: reduce)',
        onchange: null,
      })),
    })
  })

  it('interpolates name + balance into the first phrase after decoding', async () => {
    const { default: HackerGreeting } = await import('./HackerGreeting.vue')
    const wrapper = mount(HackerGreeting, {
      props: { name: '小明', balance: 42 },
      global: { plugins: [i18n] },
    })
    await flushPromises()
    // Drive rAF enough frames to fully decode the first phrase.
    flushRaf(200)
    await flushPromises()
    expect(wrapper.find('.hg-text').text()).toContain('小明')
    expect(wrapper.find('.hg-text').text()).toContain('42')
    expect(wrapper.find('.hg-text').text()).toContain('⭐')
    wrapper.unmount()
  })

  it('shows scrambled glyphs (not the final text) before decoding completes', async () => {
    const { default: HackerGreeting } = await import('./HackerGreeting.vue')
    const wrapper = mount(HackerGreeting, {
      props: { name: '小明', balance: 42 },
      global: { plugins: [i18n] },
    })
    await flushPromises()
    // No frames flushed yet — display should not equal the final phrase.
    const final = '你好，小明！已加载 42 颗星 ⭐'
    expect(wrapper.find('.hg-text').text()).not.toBe(final)
    wrapper.unmount()
  })

  it('rotates to the next phrase after settling', async () => {
    // Fake only setTimeout/setInterval; keep rAF on our manual queue so
    // flushRaf() can step the decode frames.
    vi.useFakeTimers({ toFake: ['setTimeout', 'clearTimeout', 'setInterval', 'clearInterval'] })
    const { default: HackerGreeting } = await import('./HackerGreeting.vue')
    const wrapper = mount(HackerGreeting, {
      props: { name: '小明', balance: 42 },
      global: { plugins: [i18n] },
    })
    await flushPromises()
    // Decode first phrase fully.
    flushRaf(200)
    await flushPromises()
    expect(wrapper.find('.hg-text').text()).toBe('你好，小明！已加载 42 颗星 ⭐')
    // Advance the hold timer scheduled by the settled-watch.
    vi.advanceTimersByTime(4000)
    await flushPromises()
    // advance() called setTarget → new rAF queued; decode the second phrase.
    flushRaf(200)
    await flushPromises()
    expect(wrapper.find('.hg-text').text()).toBe('系统就绪 // 小明 的星库：42 ⭐')
    vi.useRealTimers()
    wrapper.unmount()
  })

  it('snaps to final text immediately under reduced motion', async () => {
    mqMatches = true
    vi.resetModules()
    const { default: HackerGreeting } = await import('./HackerGreeting.vue')
    const wrapper = mount(HackerGreeting, {
      props: { name: '小红', balance: 7 },
      global: { plugins: [i18n] },
    })
    await flushPromises()
    // No rAF frames should be needed — final text shown synchronously.
    expect(wrapper.find('.hg-text').text()).toBe('你好，小红！已加载 7 颗星 ⭐')
    expect(rafQueue.length).toBe(0)
    wrapper.unmount()
  })
})
