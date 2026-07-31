import { describe, it, expect, beforeEach } from 'vitest'
import { clearLegacyOnboardingKeys, isGuideDone, markGuideDone } from '../storage'

describe('guide storage helpers', () => {
  beforeEach(() => {
    localStorage.clear()
  })

  describe('isGuideDone / markGuideDone', () => {
    it('returns false when key not set', () => {
      expect(isGuideDone('guide_test')).toBe(false)
    })

    it('returns true after markGuideDone', () => {
      markGuideDone('guide_test')
      expect(isGuideDone('guide_test')).toBe(true)
    })
  })

  describe('clearLegacyOnboardingKeys', () => {
    it('removes all guide_/gesture_/tip_ prefixed keys', () => {
      localStorage.setItem('guide_test', 'done')
      localStorage.setItem('gesture_test', 'done')
      localStorage.setItem('tip_test', 'done')
      localStorage.setItem('other_key', 'keep')
      clearLegacyOnboardingKeys()
      expect(localStorage.getItem('guide_test')).toBeNull()
      expect(localStorage.getItem('gesture_test')).toBeNull()
      expect(localStorage.getItem('tip_test')).toBeNull()
      expect(localStorage.getItem('other_key')).toBe('keep')
    })

    it('removes legacy onboarding_completed key', () => {
      localStorage.setItem('onboarding_completed', 'true')
      clearLegacyOnboardingKeys()
      expect(localStorage.getItem('onboarding_completed')).toBeNull()
    })
  })
})
