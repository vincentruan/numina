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
  if (!audioCtx || audioCtx.state === 'closed') {
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
  // First user gesture confirms audio is allowed — clear any iOS default mute
  muted = false
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

/** Shared tone player — reduces boilerplate across play functions. */
function playTone(opts: {
  freqStart: number
  freqEnd: number
  type: OscillatorType
  duration: number
  peakGain: number
  delay?: number
}): void {
  if (muted) return
  const ctx = getContext()
  if (!ctx) return

  const osc = ctx.createOscillator()
  const gain = ctx.createGain()
  osc.connect(gain)
  gain.connect(ctx.destination)

  const start = ctx.currentTime + (opts.delay ?? 0)
  const end = start + opts.duration

  osc.frequency.setValueAtTime(opts.freqStart, start)
  osc.frequency.exponentialRampToValueAtTime(opts.freqEnd, end)
  osc.type = opts.type
  gain.gain.setValueAtTime(opts.peakGain, start)
  gain.gain.exponentialRampToValueAtTime(0.001, end)

  osc.start(start)
  osc.stop(end)
}

/**
 * Play a short percussive pop — button clicks, object placement.
 * Frequency: 600Hz → 200Hz sweep, 80ms duration.
 */
export function playClickPop(): void {
  playTone({ freqStart: 600, freqEnd: 200, type: 'sine', duration: 0.08, peakGain: 0.3 })
}

/**
 * Play a success chime — ascending major triad.
 * Notes: C5 → E5 → G5, 120ms each, total ~360ms.
 */
export function playSuccessChime(): void {
  const notes = [523.25, 659.25, 783.99] // C5, E5, G5
  const noteDur = 0.12
  notes.forEach((freq, i) => {
    playTone({ freqStart: freq, freqEnd: freq, type: 'sine', duration: noteDur, peakGain: 0.25, delay: i * noteDur })
  })
}

/**
 * Play an error descent — gentle descending tone, not alarming.
 * Frequency: 400Hz → 250Hz, 200ms, sine wave.
 */
export function playErrorDescend(): void {
  playTone({ freqStart: 400, freqEnd: 250, type: 'sine', duration: 0.2, peakGain: 0.2 })
}

/**
 * Play a drop thunk — object landing on surface.
 * Low frequency bump: 150Hz → 60Hz, 100ms.
 */
export function playDropThunk(): void {
  playTone({ freqStart: 150, freqEnd: 60, type: 'triangle', duration: 0.1, peakGain: 0.35 })
}

/** Reset audio state — for tests only. */
export function _resetForTesting(): void {
  if (audioCtx) {
    audioCtx.close().catch(() => { /* ignore */ })
    audioCtx = null
  }
  muted = false
}
