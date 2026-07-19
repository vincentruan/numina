import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { createI18n } from 'vue-i18n'
import { createMemoryHistory, createRouter } from 'vue-router'
import ChildWishDetailPage from './ChildWishDetailPage.vue'
import * as wishesApi from '@/api/childWishes'
import * as coinsApi from '@/api/coins'

vi.mock('@/api/childWishes')
vi.mock('@/api/coins')

const i18n = createI18n({
  legacy: false,
  locale: 'zh-CN',
  messages: {
    'zh-CN': {
      common: { loading: '加载中...', back: '返回' },
      wishes: {
        sectionActive: '✨ 进行中',
        priorityLabelHigh: '最想要 🔥',
        priorityLabelMedium: '比较想 ⭐',
        priorityLabelLow: '以后再说 💤',
        progressFull: '积分已够',
        waitingGoal: '等待爸妈',
        waitingRedemption: '等待兑现',
        waitingReview: '等待审核',
        realized: '已实现',
        rejected: '未通过',
        redeemBtn: '让爸妈实现',
        timeUnitDays: '≈ {days} 天',
        timeUnitPlaceholder: '继续做家务',
        constellation: { detailUnknown: '没找到这个心愿' },
      },
      toast: { submitFailed: '❌ 提交失败' },
    },
  },
})

function makeRouter() {
  const r = createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/wishes/:id', name: 'ChildWishDetail', component: { template: '<div />' } },
      { path: '/wishes', name: 'ChildWishes', component: { template: '<div />' } },
    ],
  })
  return r
}

async function mountAt(id: string) {
  const router = makeRouter()
  await router.push({ name: 'ChildWishDetail', params: { id } })
  await router.isReady()
  return mount(ChildWishDetailPage, {
    global: {
      plugins: [i18n, router],
      stubs: { PageHeader: { template: '<div class="page-header-stub" />' } },
    },
  })
}

const wish = {
  id: 'w1',
  family_id: 'f',
  child_user_id: 'c',
  name: 'Lego Set',
  description: '酷炫积木',
  emoji: '🧱',
  priority: 'high' as const,
  status: 'active' as const,
  has_cost_set: true,
  star_coin_cost: null,
  progress: 0.5,
  rejection_reason: null,
  realized_asset_id: null,
  fulfilled_at: null,
  created_at: '',
  updated_at: '',
}

describe('ChildWishDetailPage', () => {
  beforeEach(() => {
    vi.mocked(wishesApi.listChildWishes).mockResolvedValue({
      pending_review: [],
      active: [wish],
      redemption_requested: [],
      realized: [],
      rejected: [],
    })
    vi.mocked(wishesApi.getChildWishStats).mockResolvedValue({
      balance: 50,
      active_wish_count: 1,
      realized_wish_count: 0,
      priority_simulation: [{ wish_id: 'w1', name: 'Lego Set', priority: 'high', star_coin_cost: 100, progress: 0.5, covered: false }],
      shortfall_for_high_priority: 0,
    })
    vi.mocked(coinsApi.getCoinLedger).mockResolvedValue([])
  })

  it('renders active wish detail with name, emoji, progress, and time placeholder when ledger empty', async () => {
    const wrapper = await mountAt('w1')
    await flushPromises()
    expect(wrapper.find('.wish-name').text()).toBe('Lego Set')
    expect(wrapper.find('.wish-emoji').text()).toBe('🧱')
    expect(wrapper.find('.progress-pct').text()).toBe('50%')
    expect(wrapper.find('.hint-placeholder').exists()).toBe(true)
  })

  it('renders ≈ N 天 line when ledger is stable', async () => {
    vi.mocked(coinsApi.getCoinLedger).mockResolvedValue([
      { id: '1', amount: 5, transaction_type: 'chore', narrative: null, narrative_emoji: null, created_at: new Date(Date.now() - 1 * 86400_000).toISOString(), relative_time: '1d' },
      { id: '2', amount: 5, transaction_type: 'chore', narrative: null, narrative_emoji: null, created_at: new Date(Date.now() - 2 * 86400_000).toISOString(), relative_time: '2d' },
      { id: '3', amount: 5, transaction_type: 'chore', narrative: null, narrative_emoji: null, created_at: new Date(Date.now() - 3 * 86400_000).toISOString(), relative_time: '3d' },
    ])
    const wrapper = await mountAt('w1')
    await flushPromises()
    expect(wrapper.find('.hint-days').text()).toBe('≈ 10 天')
  })

  it('renders "已实现" status line for realized wish; no redeem button', async () => {
    vi.mocked(wishesApi.listChildWishes).mockResolvedValue({
      pending_review: [],
      active: [],
      redemption_requested: [],
      realized: [{ ...wish, status: 'realized' }],
      rejected: [],
    })
    const wrapper = await mountAt('w1')
    await flushPromises()
    expect(wrapper.find('.btn-redeem').exists()).toBe(false)
    expect(wrapper.find('.status-line').text()).toBe('已实现')
  })

  it('renders friendly empty state for unknown id; no toast', async () => {
    const wrapper = await mountAt('w-unknown')
    await flushPromises()
    expect(wrapper.find('.empty-text').text()).toBe('没找到这个心愿')
    expect(wrapper.find('.btn-back').exists()).toBe(true)
  })
})
