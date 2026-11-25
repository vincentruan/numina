/**
 * sfx — Web Audio API procedural synthesis for challenge feedback.
 *
 * No audio files — all sounds are generated via OscillatorNode + GainNode envelopes.
 * AudioContext is created lazily on first user gesture (iOS Safari requirement).
 * Mute toggle defaults to system silent state.
 */

let audioCtx: AudioContext | null = null
let muted = false

/** Check if the system is in silent mode (iOS mute switch). */
function detectSystemSilent(): boolean {
  // On iOS, the mute switch state is not directly queryable.
  // Default to muted on iOS until first user gesture confirms audio works.
  if (typeof navigator !== 'undefined' && /iP(hone|ad|od)/.test(navigator.userAgent)) {
    return true
  }
  return false
}

// Initialize mute state from system
muted = detectSystemSilent()

/** Get or create the AudioContext (lazy, on first user gesture). */
function getContext(): AudioContext | null {
  if (typeof window === 'undefined') return null
  if (!audioCtx) {
    try {
      // webkitAudioContext: Safari ≤14 prefixed fallback
      const Ctor = window.AudioContext || (window as unknown as { webkitAudioContext: typeof AudioContext }).webkitAudioContext
      audioCtx = new Ctor()
    } catch {
      return null
    }
  }
  // Resume if suspended (iOS Safari blocks until user gesture)
  if (audioCtx.state === 'suspended') {
    audioCtx.resume().catch(() => { /* silently ignore */ })
  }
  return audioCtx
}

/** Resume audio context — call from first user gesture handler. */
export function resumeAudio(): void {
  getContext()
}

/** Toggle mute state. Returns new muted value. */
export function toggleMute(): boolean {
  muted = !muted
  return muted
}

/** Check current mute state. */
export function isMuted(): boolean {
  return muted
}

/** Set mute state directly. */
export function setMuted(value: boolean): void {
  muted = value
}

/**
 * Play a short percussive pop — button clicks, object placement.
 * Frequency: 600Hz → 200Hz sweep, 80ms duration.
 */
export function playClickPop(): void {
  if (muted) return
  const ctx = getContext()
  if (!ctx) return

  const osc = ctx.createOscillator()
  const gain = ctx.createGain()
  osc.connect(gain)
  gain.connect(ctx.destination)

  const now = ctx.currentTime
  osc.frequency.setValueAtTime(600, now)
  osc.frequency.exponentialRampToValueAtTime(200, now + 0.08)
  gain.gain.setValueAtTime(0.3, now)
  gain.gain.exponentialRampToValueAtTime(0.001, now + 0.08)

  osc.start(now)
  osc.stop(now + 0.08)
}

/**
 * Play a success chime — ascending major triad.
 * Notes: C5 → E5 → G5, 120ms each, total ~360ms.
 */
export function playSuccessChime(): void {
  if (muted) return
  const ctx = getContext()
  if (!ctx) return

  const notes = [523.25, 659.25, 783.99] // C5, E5, G5
  const noteDur = 0.12

  notes.forEach((freq, i) => {
    const osc = ctx.createOscillator()
    const gain = ctx.createGain()
    osc.connect(gain)
    gain.connect(ctx.destination)

    const start = ctx.currentTime + i * noteDur
    osc.frequency.setValueAtTime(freq, start)
    osc.type = 'sine'
    gain.gain.setValueAtTime(0.25, start)
    gain.gain.exponentialRampToValueAtTime(0.001, start + noteDur)

    osc.start(start)
    osc.stop(start + noteDur)
  })
}

/**
 * Play an error descent — gentle descending tone, not alarming.
 * Frequency: 400Hz → 250Hz, 200ms, sine wave.
 */
export function playErrorDescend(): void {
  if (muted) return
  const ctx = getContext()
  if (!ctx) return

  const osc = ctx.createOscillator()
  const gain = ctx.createGain()
  osc.connect(gain)
  gain.connect(ctx.destination)

  const now = ctx.currentTime
  osc.frequency.setValueAtTime(400, now)
  osc.frequency.exponentialRampToValueAtTime(250, now + 0.2)
  osc.type = 'sine'
  gain.gain.setValueAtTime(0.2, now)
  gain.gain.exponentialRampToValueAtTime(0.001, now + 0.2)

  osc.start(now)
  osc.stop(now + 0.2)
}

/**
 * Play a drop thunk — object landing on surface.
 * Low frequency bump: 150Hz → 60Hz, 100ms.
 */
export function playDropThunk(): void {
  if (muted) return
  const ctx = getContext()
  if (!ctx) return

  const osc = ctx.createOscillator()
  const gain = ctx.createGain()
  osc.connect(gain)
  gain.connect(ctx.destination)

  const now = ctx.currentTime
  osc.frequency.setValueAtTime(150, now)
  osc.frequency.exponentialRampToValueAtTime(60, now + 0.1)
  osc.type = 'triangle'
  gain.gain.setValueAtTime(0.35, now)
  gain.gain.exponentialRampToValueAtTime(0.001, now + 0.1)

  osc.start(now)
  osc.stop(now + 0.1)
}

/** Reset audio state — for tests only. */
export function _resetForTesting(): void {
  if (audioCtx) {
    audioCtx.close().catch(() => { /* ignore */ })
    audioCtx = null
  }
  muted = false
}
