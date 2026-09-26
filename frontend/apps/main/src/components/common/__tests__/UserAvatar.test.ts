import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
// eslint-disable-next-line @typescript-eslint/ban-ts-comment
// @ts-ignore — vitest resolves .vue via vite plugin
import UserAvatar from '@/components/common/UserAvatar.vue'

function mountAvatar(props: { avatarUrl: string | null; displayName: string }) {
  return mount(UserAvatar, {
    props: {
      avatarColor: '#FF6B6B',
      ...props,
    },
  })
}

describe('UserAvatar text fallback', () => {
  it('shows first character when avatarUrl is null', () => {
    const wrapper = mountAvatar({ avatarUrl: null, displayName: '钓宝' })
    expect(wrapper.find('.avatar-fallback').text()).toBe('钓')
    expect(wrapper.find('.avatar-emoji').exists()).toBe(false)
    expect(wrapper.find('img').exists()).toBe(false)
  })

  it('shows first character when avatarUrl is a multi-char string (not an image path)', () => {
    // Regression: previously "钓宝" was treated as emoji and rendered verbatim
    const wrapper = mountAvatar({ avatarUrl: '钓宝', displayName: '钓宝' })
    expect(wrapper.find('.avatar-fallback').text()).toBe('钓')
    expect(wrapper.find('.avatar-emoji').exists()).toBe(false)
  })

  it('renders single emoji when avatarUrl is a single emoji char', () => {
    const wrapper = mountAvatar({ avatarUrl: '🦊', displayName: '钓宝' })
    expect(wrapper.find('.avatar-emoji').text()).toBe('🦊')
    expect(wrapper.find('.avatar-fallback').exists()).toBe(false)
  })

  it('renders single CJK character as emoji when avatarUrl is one char', () => {
    const wrapper = mountAvatar({ avatarUrl: '钓', displayName: '钓宝' })
    expect(wrapper.find('.avatar-emoji').text()).toBe('钓')
    expect(wrapper.find('.avatar-fallback').exists()).toBe(false)
  })

  it('renders image when avatarUrl starts with /', () => {
    const wrapper = mountAvatar({ avatarUrl: '/uploads/avatar.png', displayName: '钓宝' })
    const img = wrapper.find('img')
    expect(img.exists()).toBe(true)
    expect(img.attributes('src')).toBe('/uploads/avatar.png')
  })

  it('falls back to "?" when displayName is empty and avatarUrl is null', () => {
    const wrapper = mountAvatar({ avatarUrl: null, displayName: '' })
    expect(wrapper.find('.avatar-fallback').text()).toBe('?')
  })
})
