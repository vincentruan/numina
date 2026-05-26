import { describe, it, expect } from 'vitest'
import { MOTION } from './motionTokens'

describe('MOTION tokens', () => {
  it('exposes durations, easings, scales, and haptic sub-objects', () => {
    expect(MOTION.durations).toBeTypeOf('object')
    expect(MOTION.easings).toBeTypeOf('object')
    expect(MOTION.scales).toBeTypeOf('object')
    expect(MOTION.haptic).toBeTypeOf('object')
  })

  it('haptic.landing is the 5-step 3-pulse signature', () => {
    expect(MOTION.haptic.landing).toEqual([50, 30, 50, 30, 100])
  })

  it('durations.medium === 400', () => {
    expect(MOTION.durations.medium).toBe(400)
  })

  it('easings.springPop matches the spring cubic-bezier from the spec', () => {
    expect(MOTION.easings.springPop).toBe('cubic-bezier(0.175, 0.885, 0.32, 1.275)')
  })

  it('scales.pop === 1.15', () => {
    expect(MOTION.scales.pop).toBe(1.15)
  })

  it('haptic.rewardPulse is the 3-element double-pulse pattern', () => {
    expect(MOTION.haptic.rewardPulse).toEqual([50, 30, 50])
  })
})
