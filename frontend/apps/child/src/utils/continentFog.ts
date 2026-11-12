/**
 * Continent fog opacity mapping (shared).
 *
 * Maps a subject's mastery ratio (0..1) to a fog overlay opacity used to veil
 * unexplored subject islands on the knowledge map. The thresholds implement
 * the contract in R5: 0% mastery → heavily veiled, 80%+ → fully clear.
 *
 * Fog is a veil, never a lock: opacity is the only mastery-derived property,
 * and island silhouettes / labels are rendered above the fog layer so they
 * remain legible at every ratio (R7).
 */

export function fogOpacityForRatio(ratio: number): number {
  const clamped = Math.max(0, Math.min(1, ratio))
  if (clamped >= 0.8) return 0
  if (clamped >= 0.5) return 0.15
  if (clamped > 0) return 0.4
  return 0.7
}
