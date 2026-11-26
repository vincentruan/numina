/**
 * easing.test.ts — validates the easing vocabulary constants.
 *
 * These are string constants compatible with anime.js v4 easing parameters.
 * The test ensures they remain stable strings (not accidentally changed).
 */
import { describe, it, expect } from 'vitest'
import {
  easeOutElastic,
  easeOutQuad,
  easeInOutCubic,
  easeOutBack,
  easeLinear,
  easeOutCubic,
  easeOutBounce,
} from './easing'

describe('easing vocabulary', () => {
  it('exports all expected easing constants', () => {
    expect(easeOutElastic).toBeDefined()
    expect(easeOutQuad).toBeDefined()
    expect(easeInOutCubic).toBeDefined()
    expect(easeOutBack).toBeDefined()
    expect(easeLinear).toBeDefined()
    expect(easeOutCubic).toBeDefined()
    expect(easeOutBounce).toBeDefined()
  })

  it('all easings are strings compatible with anime.js', () => {
    // anime.js v4 accepts string easing names
    expect(typeof easeOutElastic).toBe('string')
    expect(typeof easeOutQuad).toBe('string')
    expect(typeof easeInOutCubic).toBe('string')
    expect(typeof easeOutBack).toBe('string')
    expect(typeof easeLinear).toBe('string')
    expect(typeof easeOutCubic).toBe('string')
    expect(typeof easeOutBounce).toBe('string')
  })

  it('easing values contain expected anime.js easing names', () => {
    // Verify the easing names match anime.js conventions
    expect(easeOutElastic).toContain('outElastic')
    expect(easeOutQuad).toContain('outQuad')
    expect(easeInOutCubic).toContain('inOutCubic')
    expect(easeOutBack).toContain('outBack')
    expect(easeLinear).toContain('linear')
    expect(easeOutCubic).toContain('outCubic')
    expect(easeOutBounce).toContain('outBounce')
  })

  it('elastic and back easings have parameter syntax', () => {
    // These easings take parameters: outElastic(1, 0.5), outBack(2)
    expect(easeOutElastic).toMatch(/outElastic\(.+\)/)
    expect(easeOutBack).toMatch(/outBack\(.+\)/)
  })

  it('linear easing has no parameters', () => {
    expect(easeLinear).toBe('linear')
  })
})
