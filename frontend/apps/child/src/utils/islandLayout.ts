/**
 * Deterministic organic island layout for the knowledge ocean map (R3, F3).
 *
 * Places subject islands in a normalized [0,1]² coordinate space such that:
 * - Related subjects (same terrain family) cluster nearer each other.
 * - No two islands share a rigid grid or radial slot (organic jitter).
 * - Layout is stable across renders/visits (deterministic from subject set).
 */

export interface IslandSubject {
  id: string
  terrain: string
  topicCount: number
}

export interface IslandPosition {
  id: string
  x: number
  y: number
  radius: number
}

export interface IslandLayout {
  positions: IslandPosition[]
}

// Mulberry32 seeded PRNG — deterministic, fast, 32-bit state.
function mulberry32(seed: number): () => number {
  return function () {
    seed |= 0
    seed = (seed + 0x6d2b79f5) | 0
    let t = Math.imul(seed ^ (seed >>> 15), 1 | seed)
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296
  }
}

// Deterministic hash of a string → 32-bit seed.
function hashString(s: string): number {
  let hash = 0
  for (let i = 0; i < s.length; i++) {
    const char = s.charCodeAt(i)
    hash = (hash << 5) - hash + char
    hash |= 0
  }
  return hash >>> 0
}

// Golden angle in radians (≈ 137.508°) — ensures even angular distribution.
const GOLDEN_ANGLE = Math.PI * (3 - Math.sqrt(5))

/**
 * Compute island positions for a set of subjects.
 *
 * Algorithm:
 * 1. Group subjects by terrain family.
 * 2. Place each family's center on a circle (golden-angle spacing).
 * 3. Jitter each subject within its family cluster (seeded PRNG).
 * 4. Run repulsion pass to enforce minimum separation on x and y axes.
 * 5. Normalize to [0,1]².
 */
export function layoutIslands(subjects: IslandSubject[]): IslandLayout {
  if (subjects.length === 0) return { positions: [] }
  if (subjects.length === 1) {
    return {
      positions: [
        { id: subjects[0].id, x: 0.5, y: 0.5, radius: computeRadius(subjects[0].topicCount, 1) },
      ],
    }
  }

  // Deterministic seed from sorted subject IDs.
  const sortedIds = [...subjects].map((s) => s.id).sort()
  const seed = hashString(sortedIds.join(','))
  const rng = mulberry32(seed)

  // Group by terrain.
  const families = new Map<string, IslandSubject[]>()
  for (const s of subjects) {
    if (!families.has(s.terrain)) families.set(s.terrain, [])
    families.get(s.terrain)!.push(s)
  }

  // Place family centers on a circle.
  const familyCenters = new Map<string, { x: number; y: number }>()
  const familyKeys = [...families.keys()].sort()
  const familyRadius = 0.25
  familyKeys.forEach((terrain, i) => {
    const angle = i * GOLDEN_ANGLE
    familyCenters.set(terrain, {
      x: 0.5 + familyRadius * Math.cos(angle),
      y: 0.5 + familyRadius * Math.sin(angle),
    })
  })

  // Place each subject within its family cluster.
  const maxTopicCount = Math.max(...subjects.map((s) => s.topicCount), 1)
  const positions: IslandPosition[] = []
  for (const [terrain, members] of families.entries()) {
    const center = familyCenters.get(terrain)!
    for (const subject of members) {
      const angle = rng() * 2 * Math.PI
      const dist = rng() * 0.12
      positions.push({
        id: subject.id,
        x: center.x + dist * Math.cos(angle),
        y: center.y + dist * Math.sin(angle),
        radius: computeRadius(subject.topicCount, maxTopicCount),
      })
    }
  }

  // Repulsion pass — enforce minimum separation on both axes.
  const MIN_SEP = 0.02 // Minimum separation on x and y axes (organic guarantee).
  const DIST_SEP = 0.15 // Minimum Euclidean distance.
  const ITERATIONS = 20
  for (let iter = 0; iter < ITERATIONS; iter++) {
    for (let i = 0; i < positions.length; i++) {
      for (let j = i + 1; j < positions.length; j++) {
        const pi = positions[i]
        const pj = positions[j]
        const dx = pj.x - pi.x
        const dy = pj.y - pi.y
        const dist = Math.sqrt(dx * dx + dy * dy)

        // Push apart on Euclidean distance.
        if (dist < DIST_SEP && dist > 0) {
          const push = (DIST_SEP - dist) / 2
          const nx = dx / dist
          const ny = dy / dist
          pi.x -= push * nx
          pi.y -= push * ny
          pj.x += push * nx
          pj.y += push * ny
        }

        // Also ensure x and y separation (organic guarantee).
        const absDx = Math.abs(pj.x - pi.x)
        const absDy = Math.abs(pj.y - pi.y)
        if (absDx < MIN_SEP) {
          const signX = pj.x >= pi.x ? 1 : -1
          const pushX = (MIN_SEP - absDx) / 2
          pi.x -= signX * pushX
          pj.x += signX * pushX
        }
        if (absDy < MIN_SEP) {
          const signY = pj.y >= pi.y ? 1 : -1
          const pushY = (MIN_SEP - absDy) / 2
          pi.y -= signY * pushY
          pj.y += signY * pushY
        }
      }
    }
  }

  // Clamp to [0, 1].
  for (const p of positions) {
    p.x = Math.max(0, Math.min(1, p.x))
    p.y = Math.max(0, Math.min(1, p.y))
  }

  return { positions }
}

function computeRadius(topicCount: number, maxTopicCount: number): number {
  const normalized = topicCount / maxTopicCount
  return 0.03 + 0.04 * Math.sqrt(normalized)
}
