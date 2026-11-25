/**
 * feedback — shared warm-feedback protocol for all challenge types.
 *
 * Error feedback: gentle shake (2 oscillations, ~180ms) + guidance text + descending tone.
 * Success feedback: elastic bounce (scale 1.0→1.15→1.0, ~300ms) + chime + haptic.
 *
 * No red X, no score deduction, no page jump.
 */
import { tryVibrate } from '@/composables/useHaptic'
import { playSuccessChime, playErrorDescend } from '@/audio/sfx'

/** CSS class for the warm shake animation (injected once). */
const SHAKE_CLASS = 'challenge-feedback-shake'
const BOUNCE_CLASS = 'challenge-feedback-bounce'
let stylesInjected = false

function injectStyles(): void {
  if (stylesInjected || typeof document === 'undefined') return
  const style = document.createElement('style')
  style.textContent = `
@keyframes ${SHAKE_CLASS} {
  0%, 100% { transform: translateX(0); }
  25% { transform: translateX(-6px); }
  75% { transform: translateX(6px); }
}
@keyframes ${BOUNCE_CLASS} {
  0% { transform: scale(1); }
  40% { transform: scale(1.15); }
  100% { transform: scale(1); }
}
.${SHAKE_CLASS} {
  animation: ${SHAKE_CLASS} 180ms ease-out;
}
.${BOUNCE_CLASS} {
  animation: ${BOUNCE_CLASS} 300ms cubic-bezier(0.34, 1.56, 0.64, 1);
}
`
  document.head.appendChild(style)
  stylesInjected = true
}

/** Check prefers-reduced-motion directly — avoids calling composable outside setup. */
function prefersReducedMotion(): boolean {
  if (typeof window === 'undefined' || !window.matchMedia) return false
  return window.matchMedia('(prefers-reduced-motion: reduce)').matches
}

/**
 * Trigger warm error feedback on an element.
 * Applies a gentle shake + plays descending tone + optional haptic.
 * Respects prefers-reduced-motion: skips visual animation but still plays audio.
 */
export function triggerErrorFeedback(element: HTMLElement): void {
  injectStyles()

  // Visual shake (skipped if reduced motion)
  if (!prefersReducedMotion()) {
    element.classList.add(SHAKE_CLASS)
    element.addEventListener('animationend', () => {
      element.classList.remove(SHAKE_CLASS)
    }, { once: true })
  }

  // Audio feedback (always plays, even with reduced motion)
  playErrorDescend()

  // Light haptic
  tryVibrate(15)
}

/**
 * Trigger warm success feedback on an element.
 * Applies elastic bounce + plays success chime + haptic.
 * Respects prefers-reduced-motion: skips visual animation but still plays audio.
 */
export function triggerSuccessFeedback(element: HTMLElement): void {
  injectStyles()

  // Visual bounce (skipped if reduced motion)
  if (!prefersReducedMotion()) {
    element.classList.add(BOUNCE_CLASS)
    element.addEventListener('animationend', () => {
      element.classList.remove(BOUNCE_CLASS)
    }, { once: true })
  }

  // Audio feedback
  playSuccessChime()

  // Success haptic — slightly longer pulse
  tryVibrate([15, 30, 15])
}
