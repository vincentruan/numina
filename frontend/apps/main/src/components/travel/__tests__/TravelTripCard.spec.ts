import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount } from '@vue/test-utils'
import { createI18n } from 'vue-i18n'
import { createPinia, setActivePinia } from 'pinia'
import TravelTripCard from '../TravelTripCard.vue'
import type { Trip } from '@/types/travel'

vi.mock('vue-i18n', async () => {
  const actual = await vi.importActual('vue-i18n')
  return {
    ...actual,
    useI18n: () => ({
      t: (key: string) => key,
      locale: { value: 'zh-CN' },
    }),
  }
})

function makeTrip(overrides: Partial<Trip> = {}): Trip {
  return {
    id: '1',
    family_id: '1',
    user_id: '1',
    name: '东京之旅',
    destination: '东京',
    departure_date: '2026-10-01',
    return_date: '2026-10-07',
    status: 'planning',
    planned_budget: '15000.00',
    initial_funding: null,
    actual_spend: '5000.00',
    currency: 'CNY',
    wish_id: null,
    timezone: null,
    is_active: true,
    created_at: '2026-09-01T00:00:00',
    updated_at: '2026-09-01T00:00:00',
    ...overrides,
  }
}

const i18n = createI18n({
  legacy: false,
  locale: 'zh-CN',
  messages: { 'zh-CN': {} },
})

function mountCard(trip?: Trip) {
  return mount(TravelTripCard, {
    props: {
      trip: trip || makeTrip(),
    },
    global: {
      plugins: [i18n],
      stubs: {
        // Use pass-through stubs that render slot content
        VanCell: {
          template: '<div class="van-cell-stub"><slot name="title" /><slot name="label" /><slot /></div>',
        },
        VanTag: {
          props: ['type', 'size'],
          template: '<span class="van-tag-stub" :data-type="type"><slot /></span>',
        },
        VanIcon: {
          props: ['name'],
          template: '<i class="van-icon-stub" />',
        },
        VanProgress: {
          props: ['percentage', 'color', 'strokeWidth', 'showPivot'],
          template: '<div class="van-progress-stub" :data-pct="percentage" />',
        },
      },
    },
  })
}

describe('TravelTripCard', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  it('renders trip name', () => {
    const wrapper = mountCard()
    expect(wrapper.find('.trip-name').text()).toBe('东京之旅')
  })

  it('renders destination with icon', () => {
    const wrapper = mountCard()
    expect(wrapper.find('.trip-destination').exists()).toBe(true)
    expect(wrapper.find('.trip-destination span').text()).toBe('东京')
  })

  it('renders date range', () => {
    const wrapper = mountCard()
    expect(wrapper.find('.trip-dates').exists()).toBe(true)
  })

  it('renders status tag with correct type for active', () => {
    const wrapper = mountCard(makeTrip({ status: 'active' }))
    const tag = wrapper.find('.van-tag-stub')
    expect(tag.exists()).toBe(true)
    expect(tag.attributes('data-type')).toBe('success')
  })

  it('renders planning status tag', () => {
    const wrapper = mountCard(makeTrip({ status: 'planning' }))
    const tag = wrapper.find('.van-tag-stub')
    expect(tag.attributes('data-type')).toBe('primary')
  })

  it('renders budget progress bar when budget exists', () => {
    const wrapper = mountCard(makeTrip({
      planned_budget: '10000.00',
      actual_spend: '3000.00',
    }))
    expect(wrapper.find('.trip-budget').exists()).toBe(true)
    expect(wrapper.find('.van-progress-stub').exists()).toBe(true)
  })

  it('hides budget section when no planned budget', () => {
    const wrapper = mountCard(makeTrip({ planned_budget: null }))
    expect(wrapper.find('.trip-budget').exists()).toBe(false)
  })

  it('hides budget section when budget is zero', () => {
    const wrapper = mountCard(makeTrip({ planned_budget: '0.00', actual_spend: '0.00' }))
    expect(wrapper.find('.trip-budget').exists()).toBe(false)
  })

  it('emits click event', async () => {
    const wrapper = mountCard()
    await wrapper.find('.trip-card').trigger('click')
    expect(wrapper.emitted('click')).toHaveLength(1)
  })

  it('displays formatted amounts in budget info', () => {
    const wrapper = mountCard(makeTrip({
      planned_budget: '15000.00',
      actual_spend: '5000.00',
    }))
    const budgetInfo = wrapper.find('.budget-info')
    expect(budgetInfo.exists()).toBe(true)
    expect(budgetInfo.text()).toContain('5')
    expect(budgetInfo.text()).toContain('15')
  })

  it('renders cancelled status with danger tag', () => {
    const wrapper = mountCard(makeTrip({ status: 'cancelled' }))
    const tag = wrapper.find('.van-tag-stub')
    expect(tag.exists()).toBe(true)
    expect(tag.attributes('data-type')).toBe('danger')
  })

  it('renders settled status with warning tag', () => {
    const wrapper = mountCard(makeTrip({ status: 'settled' }))
    const tag = wrapper.find('.van-tag-stub')
    expect(tag.exists()).toBe(true)
    expect(tag.attributes('data-type')).toBe('warning')
  })
})
