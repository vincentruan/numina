import { describe, it, expect, beforeEach } from 'vitest'
import { clearAllGuideKeys, migrateOldOnboardingKey, isGuideDone, markGuideDone } from '../storage'

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

  describe('migrateOldOnboardingKey', () => {
    it('returns false when no old key exists', () => {
      expect(migrateOldOnboardingKey()).toBe(false)
    })

    it('migrates old key to new key and returns true', () => {
      localStorage.setItem('onboarding_completed', 'true')
      const migrated = migrateOldOnboardingKey()
      expect(migrated).toBe(true)
      expect(localStorage.getItem('guide_main-onboarding-v2')).toBe('done')
    })

    it('does not set new key if old key is not "true"', () => {
      localStorage.setItem('onboarding_completed', 'false')
      migrateOldOnboardingKey()
      expect(localStorage.getItem('guide_main-onboarding-v2')).toBeNull()
    })
  })

  describe('clearAllGuideKeys', () => {
    it('removes all guide_/gesture_/tip_ prefixed keys', () => {
      localStorage.setItem('guide_test', 'done')
      localStorage.setItem('gesture_test', 'done')
      localStorage.setItem('tip_test', 'done')
      localStorage.setItem('other_key', 'keep')
      clearAllGuideKeys()
      expect(localStorage.getItem('guide_test')).toBeNull()
      expect(localStorage.getItem('gesture_test')).toBeNull()
      expect(localStorage.getItem('tip_test')).toBeNull()
      expect(localStorage.getItem('other_key')).toBe('keep')
    })

    it('removes legacy onboarding_completed key', () => {
      localStorage.setItem('onboarding_completed', 'true')
      clearAllGuideKeys()
      expect(localStorage.getItem('onboarding_completed')).toBeNull()
    })
  })
})