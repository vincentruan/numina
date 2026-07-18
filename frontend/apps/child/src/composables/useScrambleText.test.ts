import { describe, it, expect, beforeEach, vi } from 'vitest'
import { effectScope, nextTick } from 'vue'

// useReducedMotion is mocked so scramble behavior is deterministic per test.
let reducedMotionValue = false
vi.mock('@/composables/useReducedMotion', () => ({
  useReducedMotion: () => ({ value: reducedMotionValue }),
}))

// rAF queue — tests step frames manually via flushRaf().
let rafQueue: Array<() => void> = []
beforeEach(() => {
  rafQueue = []
  reducedMotionValue = false
  vi.stubGlobal('requestAnimationFrame', (cb: () => void) => {
    rafQueue.push(cb)
    return rafQueue.length
  })
  vi.stubGlobal('cancelAnimationFrame', () => {
    /* no-op in tests */
  })
})

function flushRaf(count = 1) {
  for (let i = 0; i < count; i++) {
    const next = rafQueue.shift()
    if (next) next()
  }
}

async function decodeFully(setTarget: (s: string) => void, target: string) {
  setTarget(target)
  // Each position locks every framesPerLock(=3) frames. Need enough frames to
  // lock every char + the final settle frame.
  const framesNeeded = target.length * 3 + 5
  flushRaf(framesNeeded)
  await nextTick()
}

describe('useScrambleText', () => {
  it('scrambles then settles to the exact target (no reduced motion)', async () => {
    const { useScrambleText } = await import('./useScrambleText')
    const scope = effectScope()
    const { display, settled, setTarget } = scope.run(() =>
      useScrambleText({ framesPerLock: 3 }),
    )!
    const target = 'HI 42'
    await decodeFully(setTarget, target)
    expect(settled.value).toBe(true)
    expect(display.value).toBe(target)
    scope.stop()
  })

  it('shows glyph characters at unlocked positions during decoding', async () => {
    const { useScrambleText, __testing } = await import('./useScrambleText')
    const { DEFAULT_GLYPHS } = __testing
    const scope = effectScope()
    const { display, settled, setTarget } = scope.run(() =>
      useScrambleText({ framesPerLock: 3 }),
    )!
    const target = 'AB'
    setTarget(target)
    // Before any frame flushes, the seed frame should be all glyphs (except spaces).
    expect(display.value).not.toBe(target)
    for (const ch of display.value) {
      expect(DEFAULT_GLYPHS).toContain(ch)
    }
    expect(settled.value).toBe(false)
    scope.stop()
  })

  it('preserves spaces while scrambling', async () => {
    const { useScrambleText, __testing } = await import('./useScrambleText')
    const { DEFAULT_GLYPHS } = __testing
    const scope = effectScope()
    const { display, setTarget } = scope.run(() =>
      useScrambleText({ framesPerLock: 3 }),
    )!
    setTarget('A B')
    // Seed frame: positions 0 and 2 are glyphs, position 1 is a space.
    expect(display.value[1]).toBe(' ')
    expect(DEFAULT_GLYPHS).toContain(display.value[0])
    expect(DEFAULT_GLYPHS).toContain(display.value[2])
    scope.stop()
  })

  it('snaps to final text immediately under reduced motion', async () => {
    reducedMotionValue = true
    const { useScrambleText } = await import('./useScrambleText')
    const scope = effectScope()
    const { display, settled, setTarget } = scope.run(() =>
      useScrambleText({ framesPerLock: 3 }),
    )!
    setTarget('HELLO')
    expect(display.value).toBe('HELLO')
    expect(settled.value).toBe(true)
    // No rAF should have been scheduled.
    expect(rafQueue.length).toBe(0)
    scope.stop()
  })

  it('handles empty target gracefully', async () => {
    const { useScrambleText } = await import('./useScrambleText')
    const scope = effectScope()
    const { display, settled, setTarget } = scope.run(() =>
      useScrambleText({ framesPerLock: 3 }),
    )!
    setTarget('')
    expect(display.value).toBe('')
    expect(settled.value).toBe(true)
    scope.stop()
  })

  it('pickGlyph is deterministic and stays within the glyph pool', async () => {
    const { __testing } = await import('./useScrambleText')
    const { pickGlyph, DEFAULT_GLYPHS } = __testing
    const seen = new Set<string>()
    for (let frame = 0; frame < 50; frame++) {
      for (let pos = 0; pos < 10; pos++) {
        const ch = pickGlyph(DEFAULT_GLYPHS, frame, pos)
        expect(DEFAULT_GLYPHS).toContain(ch)
        seen.add(ch)
      }
    }
    // Should exercise more than one glyph across the input space.
    expect(seen.size).toBeGreaterThan(1)
  })
})
