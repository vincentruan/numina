import { describe, it, expect } from 'vitest'
import { isFirstMasteryResult, resolveSessionMode } from './usePracticeRoute'

describe('resolveSessionMode — castle review windows (KTD7)', () => {
  it('maps ?mode=review to review so the window actually re-enters review', () => {
    expect(resolveSessionMode('review')).toBe('review')
  })

  it.each([undefined, null, '', 'practice', 'challenge', 'REVIEW', ['review']])(
    'defaults %s to practice',
    (value) => {
      expect(resolveSessionMode(value)).toBe('practice')
    },
  )
})

describe('isFirstMasteryResult — castle CTA gate (U9)', () => {
  it('is true only for a mastery change to "mastered"', () => {
    expect(
      isFirstMasteryResult({ mastery_changed: true, new_mastery_level: 'mastered' }),
    ).toBe(true)
  })

  it.each([
    { mastery_changed: false, new_mastery_level: 'mastered' },
    { mastery_changed: true, new_mastery_level: 'learning' },
    { mastery_changed: true, new_mastery_level: null },
  ])('is false for %o', (result) => {
    expect(isFirstMasteryResult(result)).toBe(false)
  })

  it('is false when there is no result at all', () => {
    expect(isFirstMasteryResult(null)).toBe(false)
  })
})
