import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import AiProcessFootnote from '@/components/ai/AiProcessFootnote.vue'
import { createI18n } from 'vue-i18n'
import zhCN from '@/i18n/locales/zh-CN'

const i18n = createI18n({
  legacy: false,
  locale: 'zh-CN',
  messages: {
    'zh-CN': zhCN,
  },
})

describe('AiProcessFootnote', () => {
  it('shows correct step count in header', () => {
    const wrapper = mount(AiProcessFootnote, {
      global: {
        plugins: [i18n],
      },
      props: {
        stepCount: 5,
        expanded: false,
      },
    })

    const headerText = wrapper.find('.footnote-text').text()
    expect(headerText).toContain('5')
    expect(headerText).toContain('查看推理过程')
  })

  it('collapsed by default when expanded prop is false', () => {
    const wrapper = mount(AiProcessFootnote, {
      global: {
        plugins: [i18n],
      },
      props: {
        stepCount: 3,
        expanded: false,
      },
    })

    expect(wrapper.find('.footnote-body').exists()).toBe(false)
    expect(wrapper.find('[aria-expanded="false"]').exists()).toBe(true)
  })

  it('emits toggle(true) when tapping collapsed footnote', async () => {
    const wrapper = mount(AiProcessFootnote, {
      global: {
        plugins: [i18n],
      },
      props: {
        stepCount: 3,
        expanded: false,
      },
    })

    await wrapper.find('.footnote-header').trigger('click')

    expect(wrapper.emitted('toggle')).toBeTruthy()
    expect(wrapper.emitted('toggle')[0]).toEqual([true])
  })

  it('shows ProcessBlock when expanded', async () => {
    const wrapper = mount(AiProcessFootnote, {
      global: {
        plugins: [i18n],
      },
      props: {
        stepCount: 3,
        expanded: true,
        status: 'done',
        elapsedMs: 1500,
        steps: [
          {
            id: 'step-1',
            type: 'reasoning',
            status: 'done',
            content: 'Thinking...',
            elapsedMs: 500,
          },
        ],
      },
    })

    expect(wrapper.find('.footnote-body').exists()).toBe(true)
    expect(wrapper.findComponent({ name: 'AiProcessBlock' }).exists()).toBe(true)
  })

  it('emits toggle(false) when tapping expanded footnote', async () => {
    const wrapper = mount(AiProcessFootnote, {
      global: {
        plugins: [i18n],
      },
      props: {
        stepCount: 3,
        expanded: true,
      },
    })

    await wrapper.find('.footnote-header').trigger('click')

    expect(wrapper.emitted('toggle')).toBeTruthy()
    expect(wrapper.emitted('toggle')[0]).toEqual([false])
  })

  it('aria-expanded reflects state', () => {
    const wrapperCollapsed = mount(AiProcessFootnote, {
      global: {
        plugins: [i18n],
      },
      props: {
        stepCount: 3,
        expanded: false,
      },
    })

    expect(wrapperCollapsed.find('[aria-expanded="false"]').exists()).toBe(true)

    const wrapperExpanded = mount(AiProcessFootnote, {
      global: {
        plugins: [i18n],
      },
      props: {
        stepCount: 3,
        expanded: true,
      },
    })

    expect(wrapperExpanded.find('[aria-expanded="true"]').exists()).toBe(true)
  })

  it('keyboard navigation: Enter triggers toggle', async () => {
    const wrapper = mount(AiProcessFootnote, {
      global: {
        plugins: [i18n],
      },
      props: {
        stepCount: 3,
        expanded: false,
      },
    })

    await wrapper.find('.footnote-header').trigger('keydown.enter')
    expect(wrapper.emitted('toggle')).toBeTruthy()
    expect(wrapper.emitted('toggle')[0]).toEqual([true])
  })

  it('keyboard navigation: Space triggers toggle', async () => {
    const wrapper = mount(AiProcessFootnote, {
      global: {
        plugins: [i18n],
      },
      props: {
        stepCount: 3,
        expanded: false,
      },
    })

    await wrapper.find('.footnote-header').trigger('keydown.space')
    expect(wrapper.emitted('toggle')).toBeTruthy()
    expect(wrapper.emitted('toggle')[0]).toEqual([true])
  })

  it('has proper accessibility attributes', () => {
    const wrapper = mount(AiProcessFootnote, {
      global: {
        plugins: [i18n],
      },
      props: {
        stepCount: 5,
        expanded: false,
      },
    })

    const header = wrapper.find('.footnote-header')
    expect(header.attributes('role')).toBe('button')
    expect(header.attributes('aria-expanded')).toBe('false')
    expect(header.attributes('aria-label')).toContain('查看推理过程')
    expect(header.attributes('tabindex')).toBe('0')
  })
})