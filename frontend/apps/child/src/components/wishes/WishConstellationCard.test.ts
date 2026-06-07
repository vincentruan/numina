import { describe, it, expect, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import { createI18n } from 'vue-i18n'
import { nextTick } from 'vue'
import WishConstellationCard from './WishConstellationCard.vue'
import type { ChildWish } from '@/api/childWishes'

const i18n = createI18n({
  legacy: false,
  locale: 'zh-CN',
  messages: {
    'zh-CN': {
      wishes: {
        tint: {
          green: { aria: '可以兑换啦' },
          yellow: { aria: '快可以兑换了' },
          red: { aria: '还要再等一阵子' },
          gray: { aria: '继续做家务，几天后能更准估计' },
        },
        timeUnitDays: '≈ {days} 天',
        timeUnitPlaceholder: '继续做家务，几天后能更准估计',
        peek: {
          confirmTag: '这个就能拿到啦 ✨',
          daysAdded: '+{n} 天',
        },
      },
    },
  },
})

const wish: ChildWish = {
  id: 'w1',
  family_id: 'f1',
  child_user_id: 'c1',
  name: 'Lego Set',
  description: null,
  emoji: '🧱',
  priority: 'high',
  status: 'active',
  has_cost_set: true,
  star_coin_cost: null,
  progress: 0.5,
  rejection_reason: null,
  realized_asset_id: null,
  fulfilled_at: null,
  created_at: '',
  updated_at: '',
}

describe('WishConstellationCard', () => {
  it('AE1 green: covered wish renders tint-green class, ✅ icon, green ARIA', () => {
    const wrapper = mount(WishConstellationCard, {
      props: { wish, tint: 'green', daysEstimateValue: null, progress: 1 },
      global: { plugins: [i18n] },
    })
    const root = wrapper.find('.wish-constellation-card')
    expect(root.classes()).toContain('tint-green')
    expect(wrapper.find('.status-icon').text()).toBe('✅')
    expect(root.attributes('aria-label')).toContain('可以兑换啦')
    expect(root.attributes('aria-label')).toContain('Lego Set')
  })

  it('AE1 yellow: days=10 renders tint-yellow, ⏳ icon, ≈ 10 天', () => {
    const wrapper = mount(WishConstellationCard, {
      props: { wish, tint: 'yellow', daysEstimateValue: 10, progress: 0.5 },
      global: { plugins: [i18n] },
    })
    expect(wrapper.find('.wish-constellation-card').classes()).toContain('tint-yellow')
    expect(wrapper.find('.status-icon').text()).toBe('⏳')
    expect(wrapper.find('.days-line').text()).toBe('≈ 10 天')
  })

  it('AE1 red: days=30 renders tint-red, no positive icon, ≈ 30 天', () => {
    const wrapper = mount(WishConstellationCard, {
      props: { wish, tint: 'red', daysEstimateValue: 30, progress: 0.1 },
      global: { plugins: [i18n] },
    })
    expect(wrapper.find('.wish-constellation-card').classes()).toContain('tint-red')
    expect(wrapper.find('.status-icon').exists()).toBe(false)
    expect(wrapper.find('.days-line').text()).toBe('≈ 30 天')
  })

  it('AE4 gray: days=null renders tint-gray and placeholder copy', () => {
    const wrapper = mount(WishConstellationCard, {
      props: { wish, tint: 'gray', daysEstimateValue: null, progress: 0.2 },
      global: { plugins: [i18n] },
    })
    expect(wrapper.find('.wish-constellation-card').classes()).toContain('tint-gray')
    expect(wrapper.find('.status-icon').exists()).toBe(false)
    expect(wrapper.find('.days-line').text()).toBe('继续做家务，几天后能更准估计')
    expect(wrapper.find('.days-line').classes()).toContain('is-placeholder')
  })

  it('emits tap with wish id on click', async () => {
    const wrapper = mount(WishConstellationCard, {
      props: { wish, tint: 'yellow', daysEstimateValue: 5, progress: 0.5 },
      global: { plugins: [i18n] },
    })
    await wrapper.find('.wish-constellation-card').trigger('click')
    expect(wrapper.emitted('tap')).toEqual([['w1']])
  })

  it('emits peek-start after 350ms hold and peek-end on release; suppresses tap', async () => {
    vi.useFakeTimers()
    const wrapper = mount(WishConstellationCard, {
      props: { wish, tint: 'yellow', daysEstimateValue: 5, progress: 0.5 },
      global: { plugins: [i18n] },
    })
    const root = wrapper.find('.wish-constellation-card')
    await root.trigger('touchstart')
    vi.advanceTimersByTime(350)
    await nextTick()
    expect(wrapper.emitted('peek-start')).toEqual([['w1']])
    await root.trigger('touchend')
    expect(wrapper.emitted('peek-end')).toEqual([['w1']])
    await root.trigger('click')
    expect(wrapper.emitted('tap')).toBeUndefined()
    vi.useRealTimers()
  })

  it('does not emit peek-start if released before threshold', async () => {
    vi.useFakeTimers()
    const wrapper = mount(WishConstellationCard, {
      props: { wish, tint: 'yellow', daysEstimateValue: 5, progress: 0.5 },
      global: { plugins: [i18n] },
    })
    const root = wrapper.find('.wish-constellation-card')
    await root.trigger('touchstart')
    vi.advanceTimersByTime(200)
    await root.trigger('touchend')
    expect(wrapper.emitted('peek-start')).toBeUndefined()
    expect(wrapper.emitted('peek-end')).toBeUndefined()
    vi.useRealTimers()
  })

  it('renders +N 天 floating label when daysAdded > 0', () => {
    const wrapper = mount(WishConstellationCard, {
      props: { wish, tint: 'yellow', daysEstimateValue: 5, progress: 0.5, daysAdded: 3 },
      global: { plugins: [i18n] },
    })
    expect(wrapper.find('.days-added-label').text()).toBe('+3 天')
  })

  it('renders confirm tag when isPressed is true', () => {
    const wrapper = mount(WishConstellationCard, {
      props: { wish, tint: 'green', daysEstimateValue: null, progress: 1, isPressed: true },
      global: { plugins: [i18n] },
    })
    expect(wrapper.find('.confirm-tag').text()).toBe('这个就能拿到啦 ✨')
  })

  it('all four tints expose non-empty ARIA labels from i18n', () => {
    for (const tint of ['green', 'yellow', 'red', 'gray'] as const) {
      const wrapper = mount(WishConstellationCard, {
        props: { wish, tint, daysEstimateValue: tint === 'green' || tint === 'gray' ? null : 5, progress: 0.3 },
        global: { plugins: [i18n] },
      })
      const aria = wrapper.find('.wish-constellation-card').attributes('aria-label')
      expect(aria).toBeTruthy()
      expect(aria!.length).toBeGreaterThan(wish.name.length)
    }
  })
})
