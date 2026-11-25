/**
 * Unified easing vocabulary for all 3D and 2D animation modules.
 *
 * Components import from here — never define their own easing curves.
 * Values are compatible with anime.js v4 easing parameters.
 */

/** Elastic overshoot — success feedback, weight landing bounce. */
export const easeOutElastic = 'outElastic(1, 0.5)'

/** Gentle deceleration — UI transitions, position snaps. */
export const easeOutQuad = 'outQuad'

/** Smooth acceleration + deceleration — camera moves, scene transitions. */
export const easeInOutCubic = 'inOutCubic'

/** Soft bounce — object snap-to-zone, puzzle piece placement. */
export const easeOutBack = 'outBack(2)'

/** Linear — physics sync, constant-velocity slides. */
export const easeLinear = 'linear'

/** Quick snap — error shake, immediate feedback. */
export const easeOutCubic = 'outCubic'

/** Bounce settle — coin drop, reward reveal. */
export const easeOutBounce = 'outBounce'
