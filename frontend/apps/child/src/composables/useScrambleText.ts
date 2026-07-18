/**
 * Scramble-decode text effect — "hacker terminal" reveal.
 *
 * A target string is revealed character-by-character: each not-yet-locked
 * position shows a pseudo-random symbol from a glyph pool, while locked
 * positions show the final character. Once every position locks, the final
 * text holds and `settled` flips true; the caller then advances to the next
 * phrase by calling `setTarget` again.
 *
 * Respects reduced-motion: when enabled, the target is shown instantly.
 */

import { onUnmounted, ref, watch, type Ref } from 'vue'
import { useReducedMotion } from '@/composables/useReducedMotion'

export interface ScrambleOptions {
  /** Glyphs cycled through while a position is unlocking. */
  glyphs?: string
  /** Frames between each position lock. Higher = slower reveal. */
  framesPerLock?: number
}

export interface UseScrambleTextReturn {
  /** Currently displayed (possibly mid-scramble) text. */
  display: Ref<string>
  /** True when the current target is fully decoded and holding. */
  settled: Ref<boolean>
  /** Set the target string to decode. */
  setTarget: (target: string) => void
}

const DEFAULT_GLYPHS = '▓▒░█▚▞◆◇»«_/\\|*+-=<>'

function pickGlyph(glyphs: string, counter: number, pos: number): string {
  // Deterministic pseudo selection driven by frame counter + position.
  // Avoids Math.random so the effect is reproducible and test-friendly,
  // while still looking noisy across positions.
  const idx = (counter * 7 + pos * 13 + (counter >> 2)) % glyphs.length
  return glyphs[idx]
}

/**
 * Decode `target` into `display`, one locked position per `framesPerLock`
 * frames, then mark `settled` once fully revealed.
 */
export function useScrambleText(options: ScrambleOptions = {}): UseScrambleTextReturn {
  const {
    glyphs = DEFAULT_GLYPHS,
    framesPerLock = 3,
  } = options

  const reducedMotion = useReducedMotion()
  const display = ref('')
  const settled = ref(false)

  let rafId: number | null = null
  let target = ''
  let frame = 0
  let lockedCount = 0

  function clearTimers() {
    if (rafId !== null) {
      cancelAnimationFrame(rafId)
      rafId = null
    }
  }

  function tick() {
    const len = target.length
    if (lockedCount >= len) {
      // Fully locked — final text shown; stop the rAF loop and signal settled.
      // Caller (component) watches `settled` and advances to the next phrase
      // after its own hold delay, then calls setTarget() to restart decoding.
      display.value = target
      settled.value = true
      rafId = null
      return
    }

    // Advance one lock every `framesPerLock` frames.
    if (frame > 0 && frame % framesPerLock === 0) {
      lockedCount = Math.min(lockedCount + 1, len)
    }

    // Build display: locked positions show real char, rest show glyphs.
    // Keep the leading locked prefix stable so it reads as "decoding left→right".
    let out = ''
    for (let i = 0; i < len; i++) {
      if (i < lockedCount) {
        out += target[i]
      } else if (target[i] === ' ') {
        out += ' ' // preserve spaces even while scrambling
      } else {
        out += pickGlyph(glyphs, frame, i)
      }
    }
    display.value = out
    frame++
    rafId = requestAnimationFrame(tick)
  }

  function setTarget(next: string) {
    clearTimers()
    target = next
    settled.value = false
    frame = 0
    lockedCount = 0

    if (reducedMotion.value || next.length === 0) {
      // No animation: show final immediately and mark settled.
      display.value = next
      settled.value = true
      return
    }

    // Seed an initial fully-scrambled frame so the first paint isn't empty.
    let out = ''
    for (let i = 0; i < next.length; i++) {
      out += next[i] === ' ' ? ' ' : pickGlyph(glyphs, 0, i)
    }
    display.value = out

    // Use setTimeout-based cadence via rAF loop. rAF pauses on tab hidden,
    // which is the desired behavior (no wasted cycles).
    rafId = requestAnimationFrame(tick)
  }

  // Re-evaluate when reduced-motion preference changes: if it turns on,
  // snap current target to its final form.
  watch(reducedMotion, (isReduced) => {
    if (isReduced) {
      clearTimers()
      display.value = target
      settled.value = true
    }
  })

  onUnmounted(clearTimers)

  return { display, settled, setTarget }
}

// Exported for tests that need the deterministic pick without reduced-motion.
export const __testing = { pickGlyph, DEFAULT_GLYPHS }
