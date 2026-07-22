import { mount } from '@vue/test-utils'
import { describe, it, expect, vi, beforeEach } from 'vitest'

vi.mock('vue-i18n', () => ({
  useI18n: () => ({ t: (key: string) => key }),
  createI18n: () => ({ global: { t: (k: string) => k, te: () => true } }),
}))

const pushMock = vi.fn()
const routePath = { value: '/' }
vi.mock('vue-router', () => ({
  useRouter: () => ({ push: pushMock }),
  useRoute: () => ({ path: routePath.value }),
  createRouter: () => ({ beforeEach: () => {}, afterEach: () => {}, push: () => Promise.resolve() }),
  createWebHistory: () => ({}),
}))

// Controllable auth role.
const userRef = { value: null as null | { role: string } }
vi.mock('@/stores/auth', () => ({
  useAuthStore: () => ({
    get user() { return userRef.value },
  }),
}))

import AppTabBar from '../AppTabBar.vue'

const stubs = {
  'van-tabbar': {
    name: 'VanTabbar',
    props: ['modelValue'],
    template: '<div class="van-tabbar"><slot /></div>',
  },
  'van-tabbar-item': {
    name: 'VanTabbarItem',
    props: ['name', 'icon'],
    template: '<div class="van-tabbar-item" :data-name="name"><slot /></div>',
  },
  AIBrainIcon: true,
}

function resetState() {
  userRef.value = null
  routePath.value = '/'
  pushMock.mockReset()
}

describe('AppTabBar (U6)', () => {
  beforeEach(() => {
    resetState()
  })

  it('non-owner renders 4 tabs and NO wishes tab', () => {
    userRef.value = { role: 'member' }
    const wrapper = mount(AppTabBar, { global: { stubs } })

    const names = wrapper.findAll('.van-tabbar-item').map((n) => n.attributes('data-name'))
    expect(names).toEqual(['dashboard', 'finance', 'ai', 'settings'])
    expect(names).not.toContain('wishes')
    expect(names).not.toContain('baby')
  })

  it('owner renders 5 tabs (with baby) and still NO wishes tab', () => {
    userRef.value = { role: 'owner' }
    const wrapper = mount(AppTabBar, { global: { stubs } })

    const names = wrapper.findAll('.van-tabbar-item').map((n) => n.attributes('data-name'))
    expect(names).toEqual(['dashboard', 'finance', 'ai', 'baby', 'settings'])
    expect(names).not.toContain('wishes')
  })

  it('highlights finance on /finance, /assets/:id, /wishes/:id, /liabilities/:id', () => {
    userRef.value = { role: 'owner' }
    for (const path of ['/finance', '/assets/123', '/wishes/7', '/liabilities/9']) {
      routePath.value = path
      const wrapper = mount(AppTabBar, { global: { stubs } })
      expect((wrapper.vm as unknown as { activeTab: string }).activeTab ?? wrapper.vm.$el).toBeTruthy()
      // activeTab is exposed via the component's computed; assert through the tabbar model.
      expect(wrapper.findComponent({ name: 'VanTabbar' }).props('modelValue')).toBe('finance')
    }
  })

  it('highlights dashboard on / and ai on /ai/*', () => {
    userRef.value = { role: 'member' }
    routePath.value = '/'
    let wrapper = mount(AppTabBar, { global: { stubs } })
    expect(wrapper.findComponent({ name: 'VanTabbar' }).props('modelValue')).toBe('dashboard')

    routePath.value = '/ai/chat'
    wrapper = mount(AppTabBar, { global: { stubs } })
    expect(wrapper.findComponent({ name: 'VanTabbar' }).props('modelValue')).toBe('ai')
  })
})
