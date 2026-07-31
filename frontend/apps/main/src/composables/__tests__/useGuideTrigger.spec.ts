import { describe, it, expect, beforeEach, vi } from 'vitest'
import { shouldShowGuide, recordGuideShown } from '../useGuideTrigger'

vi.mock('@/api/config', () => ({
  updateUserConfig: vi.fn().mockResolvedValue({}),
}))

describe('shouldShowGuide', () => {
  const V = 2
  const cfg = (overrides = {}) => ({
    onboarding_guide_version: 0, onboarding_attempts: 0, onboarding_completions: 0, ...overrides,
  })

  beforeEach(() => localStorage.clear())

  it('shows on first visit', () => {
    const { shouldShow, reason } = shouldShowGuide(cfg(), V)
    expect(shouldShow).toBe(true)
    expect(reason).toBe('first_visit')
  })

  it('does NOT show when version matches', () => {
    expect(shouldShowGuide(cfg({ onboarding_guide_version: 2 }), V).shouldShow).toBe(false)
  })

  it('shows when version bumped', () => {
    const { shouldShow, reason } = shouldShowGuide(cfg({ onboarding_guide_version: 1, onboarding_attempts: 1, onboarding_completions: 1 }), V)
    expect(shouldShow).toBe(true)
    expect(reason).toBe('version_bump')
  })

  it('does NOT show when rate < 20% (attempts >= 3)', () => {
    expect(shouldShowGuide(cfg({ onboarding_attempts: 5, onboarding_completions: 0 }), V).shouldShow).toBe(false)
  })

  it('shows when rate >= 20%', () => {
    expect(shouldShowGuide(cfg({ onboarding_attempts: 5, onboarding_completions: 1 }), V).shouldShow).toBe(true)
  })

  it('does NOT show within 24h', () => {
    localStorage.setItem('guide_last_shown_ts', String(Date.now()))
    expect(shouldShowGuide(cfg(), V).shouldShow).toBe(false)
  })

  it('shows when > 24h', () => {
    localStorage.setItem('guide_last_shown_ts', String(Date.now() - 25 * 3600 * 1000))
    expect(shouldShowGuide(cfg(), V).shouldShow).toBe(true)
  })
})

describe('recordGuideShown', () => {
  beforeEach(() => localStorage.clear())
  it('sets timestamp', () => {
    recordGuideShown()
    expect(Number(localStorage.getItem('guide_last_shown_ts'))).toBeGreaterThan(0)
  })
})
