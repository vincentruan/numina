import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import ContinentFog from './ContinentFog.vue'

describe('ContinentFog (U4)', () => {
  it('renders with opacity 0.7 when masteryRatio is 0', () => {
    const wrapper = mount(ContinentFog, { props: { masteryRatio: 0 } })
    const fog = wrapper.find('.continent-fog')
    expect(fog.exists()).toBe(true)
    expect(fog.attributes('style')).toContain('opacity: 0.7')
  })

  it('renders with opacity 0.4 when masteryRatio is 0.25', () => {
    const wrapper = mount(ContinentFog, { props: { masteryRatio: 0.25 } })
    expect(wrapper.find('.continent-fog').attributes('style')).toContain('opacity: 0.4')
  })

  it('renders with opacity 0.15 when masteryRatio is 0.5', () => {
    const wrapper = mount(ContinentFog, { props: { masteryRatio: 0.5 } })
    expect(wrapper.find('.continent-fog').attributes('style')).toContain('opacity: 0.15')
  })

  it('renders with opacity 0 when masteryRatio is 0.8 or above', () => {
    const wrapper = mount(ContinentFog, { props: { masteryRatio: 0.8 } })
    expect(wrapper.find('.continent-fog').attributes('style')).toContain('opacity: 0')
  })

  it('renders with opacity 0 when masteryRatio is 1.0 (fully mastered)', () => {
    const wrapper = mount(ContinentFog, { props: { masteryRatio: 1.0 } })
    expect(wrapper.find('.continent-fog').attributes('style')).toContain('opacity: 0')
  })

  it('has pointer-events: none so territory nodes remain tappable', () => {
    const wrapper = mount(ContinentFog, { props: { masteryRatio: 0.3 } })
    expect(wrapper.find('.continent-fog').attributes('style')).toContain('pointer-events: none')
  })

  it('has aria-hidden for accessibility', () => {
    const wrapper = mount(ContinentFog, { props: { masteryRatio: 0.5 } })
    expect(wrapper.find('.continent-fog').attributes('aria-hidden')).toBe('true')
  })

  it('clamps ratio below 0 to 0.7 opacity', () => {
    const wrapper = mount(ContinentFog, { props: { masteryRatio: -0.5 } })
    expect(wrapper.find('.continent-fog').attributes('style')).toContain('opacity: 0.7')
  })

  it('clamps ratio above 1 to 0 opacity', () => {
    const wrapper = mount(ContinentFog, { props: { masteryRatio: 1.5 } })
    expect(wrapper.find('.continent-fog').attributes('style')).toContain('opacity: 0')
  })
})
