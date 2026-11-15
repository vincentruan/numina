/**
 * Seeded PRNG + deterministic string hash, shared between the layout modules.
 *
 * #6 fix: `mulberry32` and `hashString` were byte-identical copies in
 * `islandLayout.ts` and `constellationLayout.ts` (and a third ad-hoc hash
 * lived inside `KnowledgeOcean.vue`'s `islandSilhouette`). Changing the seed
 * algorithm in one place left the others producing a different organic layout
 * from the same seed, which breaks the F3 "layout stable on return" promise.
 * Single source of truth here.
 */

/** Mulberry32 — fast, deterministic, 32-bit state. */
export function mulberry32(seed: number): () => number {
  return function () {
    seed |= 0
    seed = (seed + 0x6d2b79f5) | 0
    let t = Math.imul(seed ^ (seed >>> 15), 1 | seed)
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296
  }
}

/** Deterministic hash of a string -> 32-bit seed. */
export function hashString(s: string): number {
  let hash = 0
  for (let i = 0; i < s.length; i++) {
    const char = s.charCodeAt(i)
    hash = (hash << 5) - hash + char
    hash |= 0
  }
  return hash >>> 0
}
