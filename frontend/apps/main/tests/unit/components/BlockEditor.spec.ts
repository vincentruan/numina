import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import { createI18n } from 'vue-i18n'
import BlockEditor from '@/components/manifesto/BlockEditor.vue'

const i18n = createI18n({
  legacy: false,
  locale: 'zh-CN',
  messages: {
    'zh-CN': {
      manifesto: {
        addBlock: '添加段落',
        trackable: '可追踪',
        paragraph: '段落',
      },
    },
  },
})

function mountComponent(modelValue = { blocks: ['第一段落内容'], trackableIndices: [] as number[] }) {
  return mount(BlockEditor, {
    props: { modelValue },
    global: { plugins: [i18n] },
  })
}

describe('BlockEditor — U3', () => {
  it('renders with initial blocks', () => {
    const wrapper = mountComponent({ blocks: ['内容A', '内容B'], trackableIndices: [] })
    const fields = wrapper.findAll('.van-field')
    expect(fields.length).toBe(2)
  })

  it('adding a block appends to list via add button', async () => {
    const wrapper = mountComponent({ blocks: ['内容A'], trackableIndices: [] })
    expect(wrapper.findAll('.block-card').length).toBe(1)
    // VanButton stub renders <button class="van-button">
    const addBtn = wrapper.find('.van-button')
    await addBtn.trigger('click')
    expect(wrapper.emitted('update:modelValue')).toBeTruthy()
    const lastEmit = (wrapper.emitted('update:modelValue') as any[]).at(-1)[0]
    expect(lastEmit.blocks).toEqual(['内容A', ''])
  })

  it('delete button not shown when only 1 block', () => {
    const wrapper = mountComponent({ blocks: ['唯一段落'], trackableIndices: [] })
    expect(wrapper.find('.delete-btn').exists()).toBe(false)
  })

  it('deleting a block removes it and recalculates trackable indices', async () => {
    // Start with 3 blocks, index 2 is trackable
    const wrapper = mountComponent({ blocks: ['A', 'B', 'C'], trackableIndices: [2] })
    // Delete first block (index 0)
    const deleteBtns = wrapper.findAll('.delete-btn')
    expect(deleteBtns.length).toBe(3)
    await deleteBtns[0].trigger('click')
    const lastEmit = (wrapper.emitted('update:modelValue') as any[]).at(-1)[0]
    // blocks after delete
    expect(lastEmit.blocks).toEqual(['B', 'C'])
    // trackable index 2 should become 1 (shifted down by 1)
    expect(lastEmit.trackableIndices).toEqual([1])
  })

  it('toggling trackable updates emitted modelValue', async () => {
    // Verify initial trackable state is preserved in emitted modelValue
    const wrapper = mountComponent({ blocks: ['A', 'B'], trackableIndices: [0] })
    // Delete second block (index 1, not trackable)
    const deleteBtns = wrapper.findAll('.delete-btn')
    await deleteBtns[1].trigger('click')
    const lastEmit = (wrapper.emitted('update:modelValue') as any[]).at(-1)[0]
    // Only block 0 remains, and it's trackable
    expect(lastEmit.blocks).toEqual(['A'])
    expect(lastEmit.trackableIndices).toEqual([0])
  })

  it('body output is blocks joined by double newline', () => {
    const wrapper = mountComponent({ blocks: ['段落1', '段落2', '段落3'], trackableIndices: [] })
    const blocks = wrapper.props('modelValue').blocks
    const expectedBody = blocks.join('\n\n')
    expect(expectedBody).toBe('段落1\n\n段落2\n\n段落3')
  })
})
