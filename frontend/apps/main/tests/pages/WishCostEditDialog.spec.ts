import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { createI18n } from 'vue-i18n'
import { ref } from 'vue'
import WishCostEditDialog from '@/components/wishes/WishCostEditDialog.vue'
import * as childWishesApi from '@/api/childWishes'
import * as familyApi from '@/api/family'
import type { ParentWish } from '@/api/childWishes'

vi.mock('@/api/childWishes')
vi.mock('@/api/family')
vi.mock('vant', async () => {
  const actual = await vi.importActual<typeof import('vant')>('vant')
  return { ...actual, showToast: vi.fn() }
})

const i18n = createI18n({
  legacy: false,
  locale: 'zh-CN',
  messages: {
    'zh-CN': {
      wishCostEdit: {
        entryBtn: '调整星币',
        title: '调整心愿星币',
        currentLabel: '当前星币',
        placeholder: '输入新的星币数量（≥1）',
        next: '下一步',
        cancel: '取消',
        warningTitle: '孩子的等待时间会变化',
        warningBodyDays: '这个心愿的预估时间会从 ≈ {before} 天变成 ≈ {after} 天，是否确认？',
        warningBodyProgress: '心愿星币会从 {beforeCost} ⭐ 调整为 {afterCost} ⭐，孩子的进度会从 {beforePct}% 变为 {afterPct}%，是否确认？',
        reconsider: '再想想',
        confirm: '确认',
        success: '✅ 已调整',
        error: '❌ 调整失败',
        errors: { invalid: '⚠️ 请输入正整数星币', unchanged: '⚠️ 星币没有变化' },
      },
    },
  },
})

const wish: ParentWish = {
  id: 'w1',
  family_id: 'f',
  child_user_id: 'c1',
  child_display_name: 'Kid',
  name: 'Lego',
  description: null,
  emoji: '🧱',
  priority: 'high',
  status: 'active',
  star_coin_cost: 100,
  star_coin_cost_history: null,
  rejection_reason: null,
  realized_asset_id: null,
  created_at: '',
  updated_at: '',
}

function mountDialog(opts: { balance?: number; ledger?: Array<{ amount: number; created_at: string }> } = {}) {
  const visible = ref(true)
  vi.mocked(familyApi.getChildBalance).mockResolvedValue({
    data: { balance: opts.balance ?? 60 },
  } as never)
  vi.mocked(familyApi.getChildLedger).mockResolvedValue({
    data: opts.ledger ?? [],
  } as never)
  const wrapper = mount(WishCostEditDialog, {
    props: {
      visible: visible.value,
      wish,
      'onUpdate:visible': (v: boolean) => (visible.value = v),
    },
    global: { plugins: [i18n] },
    attachTo: document.body,
  })
  return { wrapper, visible }
}

async function typeInCost(wrapper: ReturnType<typeof mount>, cost: string) {
  const input = wrapper.find('input.cost-input')
  await input.setValue(cost)
}

describe('WishCostEditDialog', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    document.body.innerHTML = ''
  })

  it('AE5: warning sheet renders when cost change shifts tint band (progress > 0%)', async () => {
    // Stable ledger: 3 distinct earning days, avg 5 ⭐/day.
    // balance=60, cost=100 → progress=60%, remaining=40 → days_before = ceil(40/5) = 8.
    // After cost=150 → balance still 60, remaining=90 → days_after = ceil(90/5) = 18.
    // Delta = 10 days (>=1), tint band yellow → red. Warning must fire AND render days delta.
    const NOW = Date.now()
    const daysAgo = (n: number) => new Date(NOW - n * 86400_000).toISOString()
    const stableLedger = [
      { amount: 5, created_at: daysAgo(1) },
      { amount: 5, created_at: daysAgo(2) },
      { amount: 5, created_at: daysAgo(3) },
    ]
    const { wrapper } = mountDialog({ balance: 60, ledger: stableLedger })
    await flushPromises()
    await typeInCost(wrapper, '150')
    await wrapper.find('.btn-next').trigger('click')
    await flushPromises()
    expect(wrapper.find('.dialog-title').text()).toContain('孩子的等待时间会变化')
    const body = wrapper.find('.dialog-desc').text()
    expect(body).toContain('≈ 8 天')
    expect(body).toContain('≈ 18 天')
  })

  it('AE5 fallback: warning renders progress copy when ledger is too sparse for days math', async () => {
    // Empty ledger forces daysEstimate → null on both sides. Tint stays gray either way,
    // so the warning fires only through the 5% cost-ratio proxy. Copy must fall back to
    // the progress-percent form, not the days form.
    const { wrapper } = mountDialog({ balance: 60, ledger: [] })
    await flushPromises()
    await typeInCost(wrapper, '150')
    await wrapper.find('.btn-next').trigger('click')
    await flushPromises()
    expect(wrapper.find('.dialog-title').text()).toContain('孩子的等待时间会变化')
    const body = wrapper.find('.dialog-desc').text()
    expect(body).not.toContain('≈')
    expect(body).toContain('60%')
    expect(body).toContain('40%')
  })

  it('AE6: no warning when delta is tiny (< 5% AND tint unchanged)', async () => {
    vi.mocked(childWishesApi.updateChildWishCost).mockResolvedValue({} as never)
    const { wrapper } = mountDialog({ balance: 60 })
    await flushPromises()
    await typeInCost(wrapper, '101')
    await wrapper.find('.btn-next').trigger('click')
    await flushPromises()
    expect(vi.mocked(childWishesApi.updateChildWishCost)).toHaveBeenCalledWith('w1', 101)
  })

  it('progress = 0% suppresses warning even on a big cost change', async () => {
    vi.mocked(childWishesApi.updateChildWishCost).mockResolvedValue({} as never)
    const { wrapper } = mountDialog({ balance: 0 })
    await flushPromises()
    await typeInCost(wrapper, '200')
    await wrapper.find('.btn-next').trigger('click')
    await flushPromises()
    expect(vi.mocked(childWishesApi.updateChildWishCost)).toHaveBeenCalledWith('w1', 200)
  })

  it('warning → reconsider returns to edit with entered value preserved', async () => {
    const { wrapper } = mountDialog({ balance: 60 })
    await flushPromises()
    await typeInCost(wrapper, '150')
    await wrapper.find('.btn-next').trigger('click')
    await wrapper.find('.btn-cancel').trigger('click')
    expect(wrapper.find('.dialog-title').text()).toContain('调整心愿星币')
  })

  it('warning → confirm calls updateChildWishCost once', async () => {
    vi.mocked(childWishesApi.updateChildWishCost).mockResolvedValue({} as never)
    const { wrapper } = mountDialog({ balance: 60 })
    await flushPromises()
    await typeInCost(wrapper, '150')
    await wrapper.find('.btn-next').trigger('click')
    await wrapper.find('.btn-confirm').trigger('click')
    await flushPromises()
    expect(vi.mocked(childWishesApi.updateChildWishCost)).toHaveBeenCalledTimes(1)
    expect(vi.mocked(childWishesApi.updateChildWishCost)).toHaveBeenCalledWith('w1', 150)
  })

  it('API failure shows error and keeps dialog open', async () => {
    vi.mocked(childWishesApi.updateChildWishCost).mockRejectedValue(new Error('boom'))
    const { wrapper } = mountDialog({ balance: 60 })
    await flushPromises()
    await typeInCost(wrapper, '150')
    await wrapper.find('.btn-next').trigger('click')
    await wrapper.find('.btn-confirm').trigger('click')
    await flushPromises()
    expect(wrapper.find('.error-msg').text()).toContain('调整失败')
  })
})
