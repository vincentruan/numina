import { mount } from '@vue/test-utils'
import { describe, it, expect, vi } from 'vitest'
import AssetGroupHeader from '../AssetGroupHeader.vue'

vi.mock('vue-i18n', () => ({
  useI18n: () => ({
    t: (key: string, params?: Record<string, unknown>) => {
      if (key === 'asset.uncategorized') return 'Uncategorized'
      if (key === 'asset.groupSelected') return `${params?.count} selected`
      if (key === 'asset.ariaToggleGroup') return `Toggle ${params?.name} group`
      return key
    },
  }),
}))

vi.mock('@/composables/useCurrency', () => ({
  useCurrency: () => ({
    format: (amount: number | string) => `¥${Number(amount).toFixed(2)}`,
    formatPercent: (v: number) => `${v}%`,
    formatConverted: (n: number | string) => '¥' + n,
  }),
}))

const mockCategory = {
  id: 'cat-1',
  family_id: 'fam-1',
  name: '电子产品',
  icon: 'phone',
  color: '#ff6b6b',
  asset_type: 'physical' as const,
  sort_order: 1,
  is_system: false,
}

describe('AssetGroupHeader', () => {
  it('renders category name, count and subtotal', () => {
    const wrapper = mount(AssetGroupHeader, {
      props: {
        category: mockCategory,
        count: 5,
        subtotal: 12345.67,
        collapsed: false,
      },
    })

    expect(wrapper.text()).toContain('电子产品')
    expect(wrapper.text()).toContain('(5)')
    expect(wrapper.text()).toContain('¥12345.67')
  })

  it('renders uncategorized label when category is undefined', () => {
    const wrapper = mount(AssetGroupHeader, {
      props: {
        count: 2,
        subtotal: 100,
        collapsed: false,
      },
    })

    expect(wrapper.text()).toContain('Uncategorized')
    expect(wrapper.text()).toContain('(2)')
  })

  it('emits toggle on click', async () => {
    const wrapper = mount(AssetGroupHeader, {
      props: {
        category: mockCategory,
        count: 3,
        subtotal: 500,
        collapsed: false,
      },
    })

    await wrapper.trigger('click')
    expect(wrapper.emitted('toggle')).toHaveLength(1)
  })

  it('emits toggle on Enter key', async () => {
    const wrapper = mount(AssetGroupHeader, {
      props: {
        category: mockCategory,
        count: 3,
        subtotal: 500,
        collapsed: false,
      },
    })

    await wrapper.trigger('keydown.enter')
    expect(wrapper.emitted('toggle')).toHaveLength(1)
  })

  it('emits toggle on Space key', async () => {
    const wrapper = mount(AssetGroupHeader, {
      props: {
        category: mockCategory,
        count: 3,
        subtotal: 500,
        collapsed: false,
      },
    })

    await wrapper.trigger('keydown.space')
    expect(wrapper.emitted('toggle')).toHaveLength(1)
  })

  it('has correct aria-expanded attribute', async () => {
    const wrapper = mount(AssetGroupHeader, {
      props: {
        category: mockCategory,
        count: 3,
        subtotal: 500,
        collapsed: false,
      },
    })

    expect(wrapper.attributes('aria-expanded')).toBe('true')

    await wrapper.setProps({ collapsed: true })
    expect(wrapper.attributes('aria-expanded')).toBe('false')
  })

  it('applies collapsed class to arrow when collapsed', async () => {
    const wrapper = mount(AssetGroupHeader, {
      props: {
        category: mockCategory,
        count: 3,
        subtotal: 500,
        collapsed: false,
      },
    })

    const arrow = wrapper.find('.group-arrow')
    expect(arrow.classes()).not.toContain('group-arrow--collapsed')

    await wrapper.setProps({ collapsed: true })
    expect(arrow.classes()).toContain('group-arrow--collapsed')
  })

  it('shows selected count in selection mode', () => {
    const wrapper = mount(AssetGroupHeader, {
      props: {
        category: mockCategory,
        count: 5,
        subtotal: 1000,
        collapsed: false,
        selectionMode: true,
        selectedCount: 3,
      },
    })

    expect(wrapper.text()).toContain('3 selected')
  })

  it('does not show selected count when not in selection mode', () => {
    const wrapper = mount(AssetGroupHeader, {
      props: {
        category: mockCategory,
        count: 5,
        subtotal: 1000,
        collapsed: false,
        selectionMode: false,
        selectedCount: 3,
      },
    })

    expect(wrapper.text()).not.toContain('selected')
  })

  it('uses category color for icon background', () => {
    const wrapper = mount(AssetGroupHeader, {
      props: {
        category: mockCategory,
        count: 3,
        subtotal: 500,
        collapsed: false,
      },
    })

    const icon = wrapper.find('.group-icon')
    expect(icon.attributes('style')).toContain('background: #ff6b6b')
  })

  it('uses fallback color when category is undefined', () => {
    const wrapper = mount(AssetGroupHeader, {
      props: {
        count: 3,
        subtotal: 500,
        collapsed: false,
      },
    })

    const icon = wrapper.find('.group-icon')
    expect(icon.attributes('style')).toContain('background: var(--color-text-tertiary)')
  })
})
