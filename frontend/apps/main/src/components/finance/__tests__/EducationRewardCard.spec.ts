import { mount, flushPromises } from '@vue/test-utils'
import { ref } from 'vue'
import { describe, it, expect, vi, beforeEach } from 'vitest'

vi.mock('vue-i18n', () => ({
  useI18n: () => ({
    t: (key: string, params?: Record<string, unknown>) => {
      if (!params) return key
      return key.replace(/\{(\w+)\}/g, (_m, p) => String(params[p] ?? ''))
    },
    locale: { value: 'zh-CN' },
  }),
  createI18n: () => ({ global: { t: (k: string) => k, te: () => true } }),
}))

vi.mock('vue-router', () => ({
  useRouter: () => ({ push: vi.fn() }),
  useRoute: () => ({ query: {}, path: '/finance' }),
  createRouter: () => ({ beforeEach: () => {}, afterEach: () => {}, push: () => Promise.resolve() }),
  createWebHistory: () => ({}),
}))

// --- dashboard store mock: educationRewardSummary drives render/collapse ---
const educationRewardSummaryRef = ref<null | { total: number; month_total: number; count: number }>(null)
vi.mock('@/stores/dashboard', () => ({
  useDashboardStore: () => ({
    get educationRewardSummary() { return educationRewardSummaryRef.value },
  }),
}))

// getRecentActivities is called on drill-down open; stub to return filtered list.
const getRecentActivitiesMock = vi.fn((_limit?: number) => Promise.resolve({ data: [] as Array<{ id: string; type: string; title: string; amount: number | null; created_at: string | null }> }))
vi.mock('@/api/dashboard', () => ({
  getRecentActivities: (limit?: number) => getRecentActivitiesMock(limit),
}))

import EducationRewardCard from '../EducationRewardCard.vue'

const stubs = [
  'van-popup',
  'van-loading',
  'van-icon',
  'MoneyDisplay',
]

function resetState() {
  educationRewardSummaryRef.value = null
  getRecentActivitiesMock.mockReset()
  getRecentActivitiesMock.mockResolvedValue({ data: [] })
}

describe('EducationRewardCard', () => {
  beforeEach(() => {
    resetState()
  })

  it('renders summary (total/month/count) when count > 0', async () => {
    educationRewardSummaryRef.value = { total: 50, month_total: 20, count: 3 }

    const wrapper = mount(EducationRewardCard, { global: { stubs } })
    await flushPromises()

    const card = wrapper.find('.education-reward-card')
    expect(card.exists()).toBe(true)
    expect(card.text()).toContain('financeHub.educationReward')
    expect(card.text()).toContain('financeHub.educationRewardTotal')
    expect(card.text()).toContain('financeHub.educationRewardMonth')
    // count interpolated into the count cell
    expect(wrapper.find('.er-cell-count').text()).toContain('financeHub.educationRewardCount')
  })

  it('collapses (does not render) when count is 0 — empty-state noise eliminated', async () => {
    educationRewardSummaryRef.value = { total: 0, month_total: 0, count: 0 }

    const wrapper = mount(EducationRewardCard, { global: { stubs } })
    await flushPromises()

    expect(wrapper.find('.education-reward-card').exists()).toBe(false)
  })

  it('collapses (does not render) when summary not yet loaded (null)', async () => {
    educationRewardSummaryRef.value = null

    const wrapper = mount(EducationRewardCard, { global: { stubs } })
    await flushPromises()

    expect(wrapper.find('.education-reward-card').exists()).toBe(false)
  })

  it('drills down: clicking fetches recent activities and filters education_reward', async () => {
    educationRewardSummaryRef.value = { total: 50, month_total: 20, count: 2 }
    getRecentActivitiesMock.mockResolvedValue({
      data: [
        { id: '1', type: 'education_reward', title: '家务奖励 - 小宝', amount: 10, created_at: '2026-07-23T10:00:00' },
        { id: '2', type: 'payment', title: '还款', amount: 500, created_at: '2026-07-23T09:00:00' },
        { id: '3', type: 'education_reward', title: '家务奖励 - 大宝', amount: 15, created_at: '2026-07-22T10:00:00' },
      ],
    })

    const wrapper = mount(EducationRewardCard, { global: { stubs } })
    await flushPromises()

    // Card is clickable (role=button)
    const card = wrapper.find('.education-reward-card')
    expect(card.exists()).toBe(true)
    await card.trigger('click')
    await flushPromises()

    // getRecentActivities called with limit 50
    expect(getRecentActivitiesMock).toHaveBeenCalledWith(50)
    // Popup opened
    expect(wrapper.find('.er-detail').exists()).toBe(true)
    // Only education_reward items rendered (2 of 3); payment item filtered out.
    expect(wrapper.findAll('.er-detail-item')).toHaveLength(2)
    expect(wrapper.find('.er-detail-item-title').text()).toContain('家务奖励 - 小宝')
  })

  it('drill-down shows empty text when no education_reward records returned', async () => {
    educationRewardSummaryRef.value = { total: 50, month_total: 20, count: 1 }
    getRecentActivitiesMock.mockResolvedValue({
      data: [
        { id: '1', type: 'payment', title: '还款', amount: 500, created_at: '2026-07-23T09:00:00' },
      ],
    })

    const wrapper = mount(EducationRewardCard, { global: { stubs } })
    await flushPromises()

    await wrapper.find('.education-reward-card').trigger('click')
    await flushPromises()

    expect(wrapper.find('.er-detail-empty').exists()).toBe(true)
    expect(wrapper.find('.er-detail-empty').text()).toContain('financeHub.educationRewardDetailEmpty')
  })
})
