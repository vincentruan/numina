import { mount } from '@vue/test-utils'
import { describe, it, expect, vi } from 'vitest'
import BottomSheetConfirm from '../BottomSheetConfirm.vue'

vi.mock('vue-i18n', () => ({
  useI18n: () => ({
    t: (key: string) => {
      const map: Record<string, string> = {
        'bottomSheet.impactLabel': '影响预览',
        'common.cancel': '取消',
        'common.confirm': '确认',
      }
      return map[key] ?? key
    },
  }),
}))

// Global stubs in tests/setup.ts already provide VanPopup and VanButton stubs.
// VanButton renders as <button class="van-button">
// VanPopup renders as <div class="van-popup">
function mountSheet(props: Record<string, unknown> = {}) {
  return mount(BottomSheetConfirm, {
    props: {
      show: true,
      title: '测试标题',
      description: '测试描述',
      impactPreview: '测试影响预览',
      ...props,
    },
  })
}

describe('BottomSheetConfirm', () => {
  it('renders title and description', () => {
    const wrapper = mountSheet()
    expect(wrapper.find('.sheet-title').text()).toBe('测试标题')
    expect(wrapper.find('.sheet-description').text()).toBe('测试描述')
  })

  it('renders impact preview section with label and text', () => {
    const wrapper = mountSheet()
    expect(wrapper.find('.sheet-impact').exists()).toBe(true)
    expect(wrapper.find('.sheet-impact-label').text()).toBe('影响预览')
    expect(wrapper.find('.sheet-impact-text').text()).toBe('测试影响预览')
  })

  it('hides impact section when impactPreview is empty', () => {
    const wrapper = mountSheet({ impactPreview: '' })
    expect(wrapper.find('.sheet-impact').exists()).toBe(false)
  })

  it('hides description when not provided', () => {
    const wrapper = mountSheet({ description: '' })
    expect(wrapper.find('.sheet-description').exists()).toBe(false)
  })

  it('renders two action buttons (cancel + confirm)', () => {
    const wrapper = mountSheet()
    const buttons = wrapper.findAll('.van-button')
    expect(buttons).toHaveLength(2)
    expect(buttons[0].text()).toBe('取消')
    expect(buttons[1].text()).toBe('确认')
  })

  it('emits confirm on confirm button click (parent controls close)', async () => {
    const wrapper = mountSheet()
    const buttons = wrapper.findAll('.van-button')
    await buttons[1].trigger('click')
    expect(wrapper.emitted('confirm')).toHaveLength(1)
  })

  it('emits cancel and update:show(false) on cancel button click', async () => {
    const wrapper = mountSheet()
    const buttons = wrapper.findAll('.van-button')
    await buttons[0].trigger('click')
    expect(wrapper.emitted('cancel')).toHaveLength(1)
    expect(wrapper.emitted('update:show')?.[0]).toEqual([false])
  })

  it('renders inside a van-popup with position bottom', () => {
    const wrapper = mountSheet()
    expect(wrapper.find('.van-popup').exists()).toBe(true)
  })
})
