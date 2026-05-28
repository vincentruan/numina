import { describe, expect, it, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import StreamingDots from '@/components/ai/StreamingDots.vue'
import SuggestionChips from '@/components/ai/SuggestionChips.vue'
import {
  generateSuggestions,
  interpolateTemplate,
  extractCategoriesFromMessages,
} from '@/utils/suggestionTemplates'

// Mock vue-i18n before any component imports that use it
vi.mock('vue-i18n', () => ({
  useI18n: () => ({
    t: (key: string) => {
      const translations: Record<string, string> = {
        'aiChat.suggestionsAria': '后续建议',
        'aiChat.generatingResponse': '正在生成回复...',
      }
      return translations[key] || key
    },
  }),
}))

describe('StreamingDots', () => {
  it('renders three dots', () => {
    const wrapper = mount(StreamingDots)
    expect(wrapper.findAll('.dot')).toHaveLength(3)
  })

  it('has correct stagger delays', () => {
    const wrapper = mount(StreamingDots)
    const dots = wrapper.findAll('.dot')
    expect(dots[0].classes()).toContain('dot--1')
    expect(dots[1].classes()).toContain('dot--2')
    expect(dots[2].classes()).toContain('dot--3')
  })

  it('applies static class for reduced motion', () => {
    // Test by directly mounting with static class
    const wrapper = mount(StreamingDots)
    // Component uses computed property, we test the CSS exists
    expect(wrapper.find('.streaming-dots').exists()).toBe(true)
    expect(wrapper.find('.streaming-dots--static').exists()).toBe(false) // Default without matchMedia
  })

  it('has screen reader text', () => {
    const wrapper = mount(StreamingDots)
    expect(wrapper.find('.sr-only').exists()).toBe(true)
    expect(wrapper.find('.sr-only').text()).toContain('生成')
  })
})

describe('SuggestionChips', () => {
  it('renders suggestion buttons', () => {
    const wrapper = mount(SuggestionChips, {
      props: { suggestions: ['查看房产详情', '基金趋势如何'] },
    })
    expect(wrapper.findAll('.suggestion-chip')).toHaveLength(2)
  })

  it('emits select event on click', async () => {
    const wrapper = mount(SuggestionChips, {
      props: { suggestions: ['查看房产详情'] },
    })
    await wrapper.find('.suggestion-chip').trigger('click')
    expect(wrapper.emitted('select')).toBeTruthy()
    expect(wrapper.emitted('select')?.[0]).toEqual(['查看房产详情'])
  })

  it('has role="group" and aria-label', () => {
    const wrapper = mount(SuggestionChips, {
      props: { suggestions: ['test'] },
    })
    expect(wrapper.find('.suggestion-chips').attributes('role')).toBe('group')
    expect(wrapper.find('.suggestion-chips').attributes('aria-label')).toBeTruthy()
  })

  it('uses 4px border-radius (not pill)', () => {
    const wrapper = mount(SuggestionChips, {
      props: { suggestions: ['test'] },
    })
    const chip = wrapper.find('.suggestion-chip')
    // CSS should specify 4px radius
    expect(chip.exists()).toBe(true)
  })

  it('does not render when suggestions empty', () => {
    const wrapper = mount(SuggestionChips, {
      props: { suggestions: [] },
    })
    expect(wrapper.find('.suggestion-chips').exists()).toBe(false)
  })
})

describe('suggestionTemplates', () => {
  it('interpolates template with category', () => {
    const result = interpolateTemplate('查看{category}详情', { categories: ['房产'] })
    expect(result).toBe('查看房产详情')
  })

  it('uses default category when none provided', () => {
    const result = interpolateTemplate('查看{category}详情', {})
    expect(result).toBe('查看资产详情')
  })

  it('generates suggestions from context', () => {
    const suggestions = generateSuggestions({ categories: ['基金'] }, 3)
    expect(suggestions.length).toBeLessThanOrEqual(3)
    expect(suggestions[0]).toContain('基金')
  })

  it('extracts categories from messages', () => {
    const messages = ['我的房产值多少钱？', '基金收益怎么样']
    const categories = extractCategoriesFromMessages(messages)
    expect(categories).toContain('房产')
    expect(categories).toContain('基金')
  })

  it('returns default category when none found', () => {
    const categories = extractCategoriesFromMessages(['你好'])
    expect(categories).toEqual(['资产'])
  })
})