/**
 * Tests for U7: NuminaLogo component.
 *
 * The component scopes SVG def IDs via Vue 3.5 useId(), so multiple instances
 * on the same page must each have unique gradient/filter IDs to avoid SVG
 * `url(#...)` reference collisions. These tests pin that contract.
 */
import { mount } from '@vue/test-utils'
import { describe, it, expect } from 'vitest'
import NuminaLogo from '@/components/common/NuminaLogo.vue'

describe('NuminaLogo', () => {
  it('renders an SVG with aria-label "Numina"', () => {
    const wrapper = mount(NuminaLogo)
    const svg = wrapper.find('svg')
    expect(svg.exists()).toBe(true)
    expect(svg.attributes('aria-label')).toBe('Numina')
    expect(svg.attributes('role')).toBe('img')
  })

  it('uses the default width of 220px', () => {
    const wrapper = mount(NuminaLogo)
    const svg = wrapper.find('svg')
    const style = svg.attributes('style') || ''
    expect(style).toContain('width: 220px')
  })

  it('respects a custom width prop', () => {
    const wrapper = mount(NuminaLogo, { props: { width: 80 } })
    const svg = wrapper.find('svg')
    const style = svg.attributes('style') || ''
    expect(style).toContain('width: 80px')
  })

  it('declares the four expected def IDs (flourishGrad, textGrad, logoGlow, logoSoftglow)', () => {
    const wrapper = mount(NuminaLogo)
    const defs = wrapper.findAll('defs > *')
    const ids = defs.map((d) => d.attributes('id') || '')
    // Each ID is namespaced with `numina-<uid>-...` so check for the suffix.
    expect(ids.some((id) => id.endsWith('-flourishGrad'))).toBe(true)
    expect(ids.some((id) => id.endsWith('-textGrad'))).toBe(true)
    expect(ids.some((id) => id.endsWith('-logoGlow'))).toBe(true)
    expect(ids.some((id) => id.endsWith('-logoSoftglow'))).toBe(true)
  })

  it('scopes def IDs uniquely when two instances render in the same app', () => {
    // Real-world case: two NuminaLogos on the same page (e.g., agent card +
    // agent picker bottom sheet). They must get different IDs because Vue's
    // useId() is unique per-component-instance within the same app.
    // Wrapper component renders two NuminaLogo instances side by side.
    const Wrapper = {
      components: { NuminaLogo },
      template: '<div><NuminaLogo data-test="a" /><NuminaLogo data-test="b" /></div>',
    }
    const wrapper = mount(Wrapper)
    const svgs = wrapper.findAll('svg')
    expect(svgs.length).toBe(2)

    const ids1 = svgs[0].findAll('defs > *').map((d) => d.attributes('id') || '')
    const ids2 = svgs[1].findAll('defs > *').map((d) => d.attributes('id') || '')

    // The two sets must be disjoint — otherwise stacked instances would
    // share a `url(#flourishGrad)` reference and both render the same gradient.
    for (const id of ids1) {
      expect(ids2).not.toContain(id)
    }
  })

  it('every url(#...) reference points to a def ID that exists in the same instance', () => {
    const wrapper = mount(NuminaLogo)
    const html = wrapper.html()

    // Collect all url(#xxx) references.
    const urlRefs = Array.from(html.matchAll(/url\(#([^)]+)\)/g)).map((m) => m[1])
    expect(urlRefs.length).toBeGreaterThan(0)

    // Collect all defined IDs.
    const definedIds = wrapper.findAll('defs > *').map((d) => d.attributes('id') || '')

    // Each url() reference must match a defined ID in this instance.
    for (const ref of urlRefs) {
      expect(definedIds).toContain(ref)
    }
  })

  it('contains the expected SVG path elements (N + a + flourish)', () => {
    const wrapper = mount(NuminaLogo)
    // The wordmark is composed of multiple <path> elements (N, u, m, i, n, a)
    // plus decorative flourish + house-icon group + family dots. We don't
    // pin exact counts, only that the structure has many paths plus
    // recognizable accents (circles for the family dots).
    const paths = wrapper.findAll('path')
    expect(paths.length).toBeGreaterThan(10)

    const circles = wrapper.findAll('circle')
    // 3 visible family-member dots + 3 shimmer-mask flourish dots = 6
    expect(circles.length).toBe(6)
  })
})
