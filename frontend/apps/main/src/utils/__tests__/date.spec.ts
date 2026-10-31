import { describe, it, expect } from 'vitest'
import { normalizeDigestTime } from '../date'

// normalizeDigestTime is the read-side repair for legacy digest_time rows:
// the backend pattern requires "HH:MM", but older API writes can leave the
// stored value unpadded ("8:00") or otherwise malformed. The helper pads what
// it can and falls back to a safe default for everything else so the channel
// stays editable via the UI.
describe('normalizeDigestTime', () => {
  it('passes through already-padded values unchanged', () => {
    expect(normalizeDigestTime('21:00')).toBe('21:00')
    expect(normalizeDigestTime('08:30')).toBe('08:30')
    expect(normalizeDigestTime('00:00')).toBe('00:00')
    expect(normalizeDigestTime('23:59')).toBe('23:59')
  })

  it('zero-pads single-digit hours and minutes', () => {
    expect(normalizeDigestTime('8:00')).toBe('08:00')
    expect(normalizeDigestTime('08:5')).toBe('08:05')
    expect(normalizeDigestTime('8:5')).toBe('08:05')
    expect(normalizeDigestTime(' 8:30 ')).toBe('08:30')
  })

  it('falls back to the default for out-of-range digits', () => {
    expect(normalizeDigestTime('25:00')).toBe('21:00')
    expect(normalizeDigestTime('21:60')).toBe('21:00')
    expect(normalizeDigestTime('99:99')).toBe('21:00')
  })

  it('falls back for anything non-time shaped', () => {
    expect(normalizeDigestTime('')).toBe('21:00')
    expect(normalizeDigestTime(null)).toBe('21:00')
    expect(normalizeDigestTime(undefined)).toBe('21:00')
    expect(normalizeDigestTime('abc')).toBe('21:00')
    expect(normalizeDigestTime('21-00')).toBe('21:00')
    expect(normalizeDigestTime('2100')).toBe('21:00')
  })

  it('honours an explicit fallback', () => {
    expect(normalizeDigestTime('bad', '09:00')).toBe('09:00')
  })
})
