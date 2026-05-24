import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { createI18n } from 'vue-i18n'
import { createMemoryHistory, createRouter } from 'vue-router'
import { ref } from 'vue'
import ChildWishesPage from './ChildWishesPage.vue'
import * as wishesApi from '@/api/childWishes'
import * as coinsApi from '@/api/coins'

vi.mock('@/api/childWishes')
vi.mock('@/api/coins')
vi.mock('@/composables/useBalancePolling', () => ({
  useBalancePolling: () => ({
    balance: ref(50),
    isLoading: ref(false),
    error: ref(null),
    lastChange: ref(null),
    start: vi.fn(),
    stop: vi.fn(),
    refresh: vi.fn(),
  }),
}))

const reducedMotionRef = ref(false)
vi.mock('@/composables/useReducedMotion', () => ({
  useReducedMotion: () => reducedMotionRef,
}))

vi.mock('vant', async () => {
  const actual = await vi.importActual<typeof import('vant')>('vant')
  return { ...actual, showToast: vi.fn() }
})

const i18n = createI18n({
  legacy: false,
  locale: 'zh-CN',
  messages: {
    'zh-CN': {
      common: { loading: '加载中…', pullRefresh: { pulling: '', loosing: '', loading: '', success: '' } },
      wishes: {
        starUnit: '⭐',
        activeCount: '进行中',
        allWishes: '总共',
        sectionActive: '✨ 进行中',
        priorityLabelHigh: '高',
        priorityLabelMedium: '中',
        priorityLabelLow: '低',
        progressFull: '满了',
        timeUnitDays: '≈ {days} 天',
        timeUnitPlaceholder: '继续做家务',
        tint: {
          green: { aria: '可兑换' },
          yellow: { aria: '快了' },
          red: { aria: '还要等' },
          gray: { aria: '继续做家务' },
        },
        peek: { confirmTag: '✨', daysAdded: '+{n} 天' },
        constellation: {
          headline: '可拿 {k}/{n}',
          headlineZero: '差 {d} 天',
          headlineZeroNoEstimate: '继续做家务',
        },
      },
    },
  },
})

function makeRouter() {
  return createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/wishes', name: 'ChildWishes', component: { template: '<div />' } },
      { path: '/wishes/:id', name: 'ChildWishDetail', component: { template: '<div />' } },
    ],
  })
}

const wishA = {
  id: 'a',
  family_id: 'f',
  child_user_id: 'c',
  name: 'Lego',
  description: null,
  emoji: '🧱',
  priority: 'medium' as const,
  status: 'active' as const,
  has_cost_set: true,
  progress: 0.5,
  rejection_reason: null,
  realized_asset_id: null,
  created_at: '',
  updated_at: '',
}

const wishB = { ...wishA, id: 'b', name: 'Bike', emoji: '🚲', progress: 0.2 }

async function mountPage() {
  const router = makeRouter()
  await router.push('/wishes')
  await router.isReady()
  return mount(ChildWishesPage, {
    global: {
      plugins: [i18n, router],
      stubs: {
        VanPullRefresh: { template: '<div><slot /></div>' },
        VanIcon: { template: '<i class="van-icon" />' },
      },
    },
    attachTo: document.body,
  })
}

describe('ChildWishesPage peek timeout', () => {
  beforeEach(() => {
    reducedMotionRef.value = false
    vi.mocked(wishesApi.listChildWishes).mockResolvedValue({
      pending_review: [],
      active: [wishA, wishB],
      redemption_requested: [],
      realized: [],
      rejected: [],
    })
    vi.mocked(wishesApi.getChildWishStats).mockResolvedValue({
      balance: 50,
      active_wish_count: 2,
      realized_wish_count: 0,
      priority_simulation: [
        { wish_id: 'a', name: 'Lego', priority: 'medium', star_coin_cost: 100, progress: 0.5, covered: false },
        { wish_id: 'b', name: 'Bike', priority: 'medium', star_coin_cost: 250, progress: 0.2, covered: false },
      ],
      shortfall_for_high_priority: 0,
    })
    vi.mocked(coinsApi.getCoinLedger).mockResolvedValue([])
  })

  afterEach(() => {
    vi.useRealTimers()
    document.body.innerHTML = ''
  })

  it('peek auto-restores at 1500ms when reducedMotion=false', async () => {
    const wrapper = await mountPage()
    await flushPromises()
    vi.useFakeTimers()
    const cards = wrapper.findAll('.wish-constellation-card')
    expect(cards.length).toBeGreaterThan(0)

    await cards[0].trigger('touchstart')
    vi.advanceTimersByTime(350)
    await flushPromises()
    expect(wrapper.findAll('.wish-constellation-card')[0].classes()).toContain('is-pressed')

    vi.advanceTimersByTime(1499)
    await flushPromises()
    expect(wrapper.findAll('.wish-constellation-card')[0].classes()).toContain('is-pressed')

    vi.advanceTimersByTime(2)
    await flushPromises()
    expect(wrapper.findAll('.wish-constellation-card')[0].classes()).not.toContain('is-pressed')
  })

  it('peek auto-restores at 3000ms when reducedMotion=true', async () => {
    reducedMotionRef.value = true
    const wrapper = await mountPage()
    await flushPromises()
    vi.useFakeTimers()
    const cards = wrapper.findAll('.wish-constellation-card')

    await cards[0].trigger('touchstart')
    vi.advanceTimersByTime(350)
    await flushPromises()
    expect(wrapper.findAll('.wish-constellation-card')[0].classes()).toContain('is-pressed')

    vi.advanceTimersByTime(1500)
    await flushPromises()
    expect(wrapper.findAll('.wish-constellation-card')[0].classes()).toContain('is-pressed')

    vi.advanceTimersByTime(1501)
    await flushPromises()
    expect(wrapper.findAll('.wish-constellation-card')[0].classes()).not.toContain('is-pressed')
  })
})
