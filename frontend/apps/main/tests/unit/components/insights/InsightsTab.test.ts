/**
 * Regression guards for the Smart Discovery card dark-mode fix.
 *
 * Background: in dark mode, primary text on cards rendered invisible because
 * each card carried inline `style="background:..."` with specificity (1,0,0,0)
 * that silently outranked every `[data-theme='dark']` rule. Fix moved per-card
 * backgrounds to semantic modifier classes (.isc-card--{yoy,high,low,long,top}).
 *
 * These tests guard the structural invariants of that fix — happy-dom does not
 * apply <style scoped> rules to getComputedStyle, so we assert on the markup
 * that the CSS rules depend on:
 *   1. Each card carries the expected modifier class (no :nth-child coupling)
 *   2. No card or icon carries an inline `style="background:..."` attribute
 *   3. The previously-fragile inline `style="color: #ccc"` is replaced with
 *      a CSS class (.isc-sub-meta)
 *   4. Card structure is identical across light/dark theme attribute toggle
 */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { createI18n } from 'vue-i18n'
import { setActivePinia, createPinia } from 'pinia'

import InsightsTab from '@/components/insights/InsightsTab.vue'
import type { InsightsResponse } from '@/api/dashboard'

vi.mock('@/api/dashboard', async () => {
  const actual = await vi.importActual<typeof import('@/api/dashboard')>('@/api/dashboard')
  return {
    ...actual,
    getInsights: vi.fn(),
  }
})

vi.mock('@/stores/auth', () => ({
  useAuthStore: () => ({
    user: { default_currency: 'CNY' },
  }),
}))

import { getInsights } from '@/api/dashboard'

const i18n = createI18n({
  legacy: false,
  locale: 'zh-CN',
  messages: {
    'zh-CN': {
      insights: {
        smartDiscovery: {
          title: '智能发现',
          purchaseYoY: '购入同比上月',
          highestDailyCost: '最高日均成本',
          lowestDailyCost: '最低日均成本',
          longestHeld: '持有最久',
          topCategoryByValue: '占比最高分类',
          byValue: '按价值',
          vsLastMonth: '相比上月',
          daysUnit: '天',
        },
      },
      analyticsPage: { perDay: '/天' },
    },
  },
})

const fixture: InsightsResponse = {
  smart_discovery: {
    purchase_yoy: 12.5,
    highest_daily_cost: { name: '上海浦东新区住宅', cost: 234.5, icon: '🏠' },
    lowest_daily_cost: { name: '咖啡机', cost: 0.8, icon: '☕' },
    longest_held: { name: '百达翡丽手表', days: 4382, icon: '⌚' },
    top_category: { name: '不动产', percentage: 67, icon: '🏠', color: '#FF6B9D' },
  },
  daily_cost_ranking: [],
  goal_progress: {
    summary: { healthy: 0, near_end: 0, overdue: 0 },
    items: [],
  },
  type_distribution: { total_value: 0, total_count: 0, categories: [] },
  duration_distribution: { avg_days: 0, max_days: 0, buckets: [] },
  retention_rate: {
    total_bought: 0,
    total_sold: 0,
    avg_rate: 0,
    total_profit_loss: 0,
    top_items: [],
  },
}

const stubs = {
  VanLoading: { template: '<div class="van-loading" />' },
  VanPopup: { template: '<div class="van-popup"><slot /></div>' },
}

async function mountTab() {
  vi.mocked(getInsights).mockResolvedValueOnce({ data: fixture } as never)
  const wrapper = mount(InsightsTab, {
    global: { plugins: [i18n], stubs },
  })
  await flushPromises()
  return wrapper
}

describe('InsightsTab — Smart Discovery dark-mode regression guards', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    document.documentElement.removeAttribute('data-theme')
  })

  afterEach(() => {
    document.documentElement.removeAttribute('data-theme')
    vi.clearAllMocks()
  })

  it('renders all 5 cards with semantic modifier classes (no :nth-child coupling)', async () => {
    const wrapper = await mountTab()

    const cards = wrapper.findAll('.insight-stat-card')
    expect(cards).toHaveLength(5)

    expect(cards[0].classes()).toContain('isc-card--yoy')
    expect(cards[1].classes()).toContain('isc-card--high')
    expect(cards[2].classes()).toContain('isc-card--low')
    expect(cards[3].classes()).toContain('isc-card--long')
    expect(cards[4].classes()).toContain('isc-card--top')
  })

  it('renders the original-bug primary text on structural classes', async () => {
    const wrapper = await mountTab()

    const names = wrapper.findAll('.isc-name').map((n) => n.text())
    expect(names).toContain('上海浦东新区住宅')
    expect(names).toContain('咖啡机')
    expect(names).toContain('百达翡丽手表')

    expect(wrapper.find('.isc-category-name').text()).toBe('不动产')
  })

  it('has zero inline style="background:..." on cards or icons (F1 regression guard)', async () => {
    const wrapper = await mountTab()

    const cards = wrapper.findAll('.insight-stat-card')
    for (const card of cards) {
      const style = card.attributes('style') ?? ''
      expect(style).not.toContain('background')
    }

    const icons = wrapper.findAll('.insight-stat-card .isc-icon')
    for (const icon of icons) {
      const style = icon.attributes('style') ?? ''
      expect(style).not.toContain('background')
    }
  })

  it('replaces inline style="color:..." with .isc-sub-meta class (fragile-selector guard)', async () => {
    const wrapper = await mountTab()

    const meta = wrapper.find('.isc-sub-meta')
    expect(meta.exists()).toBe(true)
    expect(meta.attributes('style') ?? '').not.toContain('color')
  })

  it('preserves identical card class structure when [data-theme="dark"] is set', async () => {
    document.documentElement.setAttribute('data-theme', 'dark')
    const wrapper = await mountTab()

    const cards = wrapper.findAll('.insight-stat-card')
    expect(cards).toHaveLength(5)

    expect(cards[0].classes()).toEqual(
      expect.arrayContaining(['insight-stat-card', 'isc-card--yoy']),
    )
    expect(cards[4].classes()).toEqual(
      expect.arrayContaining(['insight-stat-card', 'isc-card--top']),
    )

    for (const card of cards) {
      const style = card.attributes('style') ?? ''
      expect(style).not.toContain('background')
    }
  })
})
