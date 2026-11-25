import { describe, it, expect, afterEach } from 'vitest'
import { resumeAudio, toggleMute, isMuted, setMuted, playClickPop, playSuccessChime, playErrorDescend, playDropThunk, _resetForTesting } from './sfx'

describe('sfx', () => {
  afterEach(() => {
    _resetForTesting()
  })

  it('is not muted by default on non-iOS', () => {
    // happy-dom doesn't match iOS UA pattern
    expect(isMuted()).toBe(false)
  })

  it('toggleMute flips mute state', () => {
    expect(isMuted()).toBe(false)
    const result = toggleMute()
    expect(result).toBe(true)
    expect(isMuted()).toBe(true)
    toggleMute()
    expect(isMuted()).toBe(false)
  })

  it('setMuted sets mute state directly', () => {
    setMuted(true)
    expect(isMuted()).toBe(true)
    setMuted(false)
    expect(isMuted()).toBe(false)
  })

  it('play functions do not throw when muted', () => {
    setMuted(true)
    expect(() => playClickPop()).not.toThrow()
    expect(() => playSuccessChime()).not.toThrow()
    expect(() => playErrorDescend()).not.toThrow()
    expect(() => playDropThunk()).not.toThrow()
  })

  it('play functions do not throw when unmuted (no AudioContext in test env)', () => {
    // In happy-dom, AudioContext may not exist — play functions should handle gracefully
    expect(() => playClickPop()).not.toThrow()
    expect(() => playSuccessChime()).not.toThrow()
    expect(() => playErrorDescend()).not.toThrow()
    expect(() => playDropThunk()).not.toThrow()
  })

  it('resumeAudio does not throw', () => {
    expect(() => resumeAudio()).not.toThrow()
  })
})
