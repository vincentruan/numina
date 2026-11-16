import { describe, it, expect } from 'vitest'
import { fogOpacityForRatio } from './continentFog'

describe('fogOpacityForRatio (R5 thresholds)', () => {
  it('returns 0.7 (heavily veiled) when mastery is 0', () => {
    expect(fogOpacityForRatio(0)).toBe(0.7)
  })

  it('returns 0.4 (dimmed) for mastery between 0 and 0.5 exclusive', () => {
    expect(fogOpacityForRatio(0.1)).toBe(0.4)
    expect(fogOpacityForRatio(0.25)).toBe(0.4)
    expect(fogOpacityForRatio(0.49)).toBe(0.4)
  })

  it('returns 0.15 (lightly veiled) for mastery between 0.5 and 0.8 exclusive', () => {
    expect(fogOpacityForRatio(0.5)).toBe(0.15)
    expect(fogOpacityForRatio(0.6)).toBe(0.15)
    expect(fogOpacityForRatio(0.79)).toBe(0.15)
  })

  it('returns 0 (fully clear) at 80% mastery and above', () => {
    expect(fogOpacityForRatio(0.8)).toBe(0)
    expect(fogOpacityForRatio(1)).toBe(0)
  })

  it('clamps negative ratios to 0.7', () => {
    expect(fogOpacityForRatio(-0.5)).toBe(0.7)
  })

  it('clamps ratios above 1 to 0', () => {
    expect(fogOpacityForRatio(1.5)).toBe(0)
  })

  it('monotonically non-increasing with mastery', () => {
    const samples = [0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1]
    for (let i = 1; i < samples.length; i++) {
      expect(fogOpacityForRatio(samples[i])).toBeLessThanOrEqual(fogOpacityForRatio(samples[i - 1]))
    }
  })
})
