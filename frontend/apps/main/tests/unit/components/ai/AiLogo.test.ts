import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import { createI18n } from 'vue-i18n'
import AiLogo from '@/components/ai/AiLogo.vue'

const i18n = createI18n({
  legacy: false,
  locale: 'zh-CN',
  messages: {
    'zh-CN': {
      aiProcess: {
        title: '执行过程',
        statusRunning: '正在执行',
        statusDone: '已完成',
        statusError: '执行出错',
      },
    },
  },
})

function mountLogo(state: 'idle' | 'thinking' | 'done' | 'error') {
  return mount(AiLogo, {
    props: { state },
    global: { plugins: [i18n] },
  })
}

describe('AiLogo', () => {
  it('applies state-idle class for idle state', () => {
    const wrapper = mountLogo('idle')
    expect(wrapper.classes()).toContain('state-idle')
  })

  it('applies state-thinking class for thinking state', () => {
    const wrapper = mountLogo('thinking')
    expect(wrapper.classes()).toContain('state-thinking')
  })

  it('applies state-done class for done state', () => {
    const wrapper = mountLogo('done')
    expect(wrapper.classes()).toContain('state-done')
  })

  it('applies state-error class for error state', () => {
    const wrapper = mountLogo('error')
    expect(wrapper.classes()).toContain('state-error')
  })

  it('renders an SVG element with role="img"', () => {
    const wrapper = mountLogo('idle')
    expect(wrapper.attributes('role')).toBe('img')
    expect(wrapper.find('svg').exists()).toBe(true)
  })

  it('sets aria-label to status text matching state', () => {
    expect(mountLogo('thinking').attributes('aria-label')).toBe('正在执行')
    expect(mountLogo('done').attributes('aria-label')).toBe('已完成')
    expect(mountLogo('error').attributes('aria-label')).toBe('执行出错')
    expect(mountLogo('idle').attributes('aria-label')).toBe('执行过程')
  })
})
