import { describe, it, expect, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import { createI18n } from 'vue-i18n'
import { nextTick } from 'vue'
import WishConstellationGrid from './WishConstellationGrid.vue'
import type { ChildWish, ChildWishStats } from '@/api/childWishes'
import type { ReachabilityTint } from '@numina/math'

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
        peek: { confirmTag: '这个就能拿到啦 ✨', daysAdded: '+{n} 天' },
        constellation: {
          headline: '你今天可以拿到 {k} 个 / 共 {n} 个 心愿',
          headlineZero: '继续加油，离最近的心愿还差 {d} 天',
          headlineZeroNoEstimate: '继续做家务，慢慢攒星星',
        },
      },
    },
  },
})

const wish = (id: string, name = id, progress = 0): ChildWish => ({
  id,
  family_id: 'f',
  child_user_id: 'c',
  name,
  description: null,
  emoji: '🌟',
  priority: 'medium',
  status: 'active',
  has_cost_set: true,
  progress,
  rejection_reason: null,
  realized_asset_id: null,
  created_at: '',
  updated_at: '',
})

const baseStats: ChildWishStats = {
  balance: 25,
  active_wish_count: 3,
  realized_wish_count: 0,
  priority_simulation: [],
  shortfall_for_high_priority: 0,
}

describe('WishConstellationGrid', () => {
  it('AE1: K=1, N=3 renders headline 你今天可以拿到 1 个 / 共 3 个 心愿', () => {
    const wishes = [wish('a'), wish('b'), wish('c')]
    const tintMap = new Map<string, ReachabilityTint>([
      ['a', 'green'],
      ['b', 'yellow'],
      ['c', 'red'],
    ])
    const daysEstimateMap = new Map<string, number | null>([
      ['a', null],
      ['b', 10],
      ['c', 30],
    ])
    const wrapper = mount(WishConstellationGrid, {
      props: { wishes, stats: baseStats, daysEstimateMap, tintMap },
      global: { plugins: [i18n] },
    })
    expect(wrapper.find('.constellation-headline').text()).toBe('你今天可以拿到 1 个 / 共 3 个 心愿')
    expect(wrapper.findAll('.wish-constellation-card')).toHaveLength(3)
  })

  it('AE2: K=0, min days=5 renders 继续加油，离最近的心愿还差 5 天', () => {
    const wishes = [wish('a'), wish('b')]
    const tintMap = new Map<string, ReachabilityTint>([
      ['a', 'yellow'],
      ['b', 'red'],
    ])
    const daysEstimateMap = new Map<string, number | null>([
      ['a', 5],
      ['b', 18],
    ])
    const wrapper = mount(WishConstellationGrid, {
      props: { wishes, stats: baseStats, daysEstimateMap, tintMap },
      global: { plugins: [i18n] },
    })
    expect(wrapper.find('.constellation-headline').text()).toBe('继续加油，离最近的心愿还差 5 天')
  })

  it('all-covered: K=N, headline still uses headline form', () => {
    const wishes = [wish('a'), wish('b')]
    const tintMap = new Map<string, ReachabilityTint>([
      ['a', 'green'],
      ['b', 'green'],
    ])
    const wrapper = mount(WishConstellationGrid, {
      props: {
        wishes,
        stats: baseStats,
        daysEstimateMap: new Map(),
        tintMap,
      },
      global: { plugins: [i18n] },
    })
    expect(wrapper.find('.constellation-headline').text()).toBe('你今天可以拿到 2 个 / 共 2 个 心愿')
  })

  it('all-gray: falls back to headlineZeroNoEstimate', () => {
    const wishes = [wish('a'), wish('b')]
    const tintMap = new Map<string, ReachabilityTint>([
      ['a', 'gray'],
      ['b', 'gray'],
    ])
    const daysEstimateMap = new Map<string, number | null>([
      ['a', null],
      ['b', null],
    ])
    const wrapper = mount(WishConstellationGrid, {
      props: { wishes, stats: baseStats, daysEstimateMap, tintMap },
      global: { plugins: [i18n] },
    })
    expect(wrapper.find('.constellation-headline').text()).toBe('继续做家务，慢慢攒星星')
  })

  it('empty wishes list hides grid entirely', () => {
    const wrapper = mount(WishConstellationGrid, {
      props: {
        wishes: [],
        stats: baseStats,
        daysEstimateMap: new Map(),
        tintMap: new Map(),
      },
      global: { plugins: [i18n] },
    })
    expect(wrapper.find('.wish-constellation').exists()).toBe(false)
  })

  it('forwards tap event from card to grid emit', async () => {
    const wishes = [wish('a')]
    const tintMap = new Map<string, ReachabilityTint>([['a', 'green']])
    const wrapper = mount(WishConstellationGrid, {
      props: { wishes, stats: baseStats, daysEstimateMap: new Map(), tintMap },
      global: { plugins: [i18n] },
    })
    await wrapper.find('.wish-constellation-card').trigger('click')
    expect(wrapper.emitted('tap')).toEqual([['a']])
  })

  it('passes peek deltas to non-pressed cards as +N 天 labels', () => {
    const wishes = [wish('a'), wish('b')]
    const tintMap = new Map<string, ReachabilityTint>([
      ['a', 'green'],
      ['b', 'yellow'],
    ])
    const daysEstimateMap = new Map<string, number | null>([
      ['a', null],
      ['b', 5],
    ])
    const wrapper = mount(WishConstellationGrid, {
      props: {
        wishes,
        stats: baseStats,
        daysEstimateMap,
        tintMap,
        peekActiveWishId: 'a',
        peekDeltas: [{ wish_id: 'b', before_progress: 0.5, after_progress: 0.2, days_added: 3 }],
      },
      global: { plugins: [i18n] },
    })
    const labels = wrapper.findAll('.days-added-label')
    expect(labels).toHaveLength(1)
    expect(labels[0].text()).toBe('+3 天')
  })

  it('AE3: forwards peek-start at 350ms hold and peek-end on release from card', async () => {
    vi.useFakeTimers()
    const wishes = [wish('a'), wish('b')]
    const tintMap = new Map<string, ReachabilityTint>([
      ['a', 'yellow'],
      ['b', 'red'],
    ])
    const wrapper = mount(WishConstellationGrid, {
      props: {
        wishes,
        stats: baseStats,
        daysEstimateMap: new Map([['a', 5], ['b', 18]]),
        tintMap,
      },
      global: { plugins: [i18n] },
    })
    const cards = wrapper.findAll('.wish-constellation-card')
    await cards[0].trigger('touchstart')
    vi.advanceTimersByTime(350)
    await nextTick()
    expect(wrapper.emitted('peek-start')).toEqual([['a']])
    await cards[0].trigger('touchend')
    expect(wrapper.emitted('peek-end')).toEqual([['a']])
    vi.useRealTimers()
  })

  it('AE3: pressed card gets is-peek-affected class on others, confirm-tag on pressed', () => {
    const wishes = [wish('a'), wish('b')]
    const tintMap = new Map<string, ReachabilityTint>([
      ['a', 'green'],
      ['b', 'yellow'],
    ])
    const wrapper = mount(WishConstellationGrid, {
      props: {
        wishes,
        stats: baseStats,
        daysEstimateMap: new Map([['a', null], ['b', 5]]),
        tintMap,
        peekActiveWishId: 'a',
        peekDeltas: [{ wish_id: 'b', before_progress: 0.5, after_progress: 0.2, days_added: 3 }],
      },
      global: { plugins: [i18n] },
    })
    const cards = wrapper.findAll('.wish-constellation-card')
    expect(cards[0].classes()).toContain('is-pressed')
    expect(cards[1].classes()).toContain('is-peek-affected')
    expect(cards[0].find('.confirm-tag').exists()).toBe(true)
    expect(cards[1].find('.confirm-tag').exists()).toBe(false)
  })
})
