import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import AiUserBubble from '@/components/ai/AiUserBubble.vue'

describe('AiUserBubble', () => {
  it('renders empty when content is empty', () => {
    const wrapper = mount(AiUserBubble, { props: { content: '' } })
    expect(wrapper.html()).toContain('ai-user-bubble')
    expect(wrapper.text()).toBe('')
  })

  it('renders plain text', () => {
    const wrapper = mount(AiUserBubble, { props: { content: 'hello world' } })
    expect(wrapper.text()).toContain('hello world')
  })

  it('renders inline markdown', () => {
    const wrapper = mount(AiUserBubble, { props: { content: '**bold** _italic_' } })
    expect(wrapper.find('strong').text()).toBe('bold')
    expect(wrapper.find('em').text()).toBe('italic')
  })

  it('blocks <script> injection', () => {
    const wrapper = mount(AiUserBubble, {
      props: { content: '<script>window.__pwn = 1</script>safe' },
    })
    expect(wrapper.html()).not.toContain('<script')
    expect(wrapper.text()).toContain('safe')
  })

  it('blocks javascript: URL', () => {
    const wrapper = mount(AiUserBubble, {
      props: { content: '[xss](javascript:alert(1))' },
    })
    expect(wrapper.html()).not.toContain('javascript:')
  })

  it('forces target=_blank rel=noopener noreferrer on links', () => {
    const wrapper = mount(AiUserBubble, {
      props: { content: 'visit https://example.com' },
    })
    const a = wrapper.find('a')
    expect(a.attributes('target')).toBe('_blank')
    expect(a.attributes('rel')).toBe('noopener noreferrer')
  })

  it('reactively re-renders when content changes', async () => {
    const wrapper = mount(AiUserBubble, { props: { content: 'first' } })
    expect(wrapper.text()).toContain('first')
    await wrapper.setProps({ content: 'second' })
    expect(wrapper.text()).toContain('second')
  })
})
