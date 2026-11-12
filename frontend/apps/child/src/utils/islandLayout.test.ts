import { describe, it, expect } from 'vitest'
import { layoutIslands, type IslandSubject, type IslandLayout } from './islandLayout'

const SAMPLE_SUBJECTS: IslandSubject[] = [
  { id: 'mathematics', terrain: 'math', topicCount: 120 },
  { id: 'physics', terrain: 'science', topicCount: 80 },
  { id: 'chemistry', terrain: 'science', topicCount: 60 },
  { id: 'biology', terrain: 'science', topicCount: 70 },
  { id: 'chinese', terrain: 'language', topicCount: 100 },
  { id: 'english', terrain: 'language', topicCount: 90 },
  { id: 'history', terrain: 'social', topicCount: 50 },
  { id: 'geography', terrain: 'social', topicCount: 40 },
  { id: 'art', terrain: 'arts', topicCount: 30 },
]

function meanPairDistance(
  layout: IslandLayout,
  predicate: (a: IslandSubject, b: IslandSubject) => boolean,
): number {
  const ids = layout.positions.map((p) => p.id)
  const subjects = new Map(layout.positions.map((p) => [p.id, p]))
  let total = 0
  let count = 0
  for (let i = 0; i < ids.length; i++) {
    for (let j = i + 1; j < ids.length; j++) {
      const a = SAMPLE_SUBJECTS.find((s) => s.id === ids[i])!
      const b = SAMPLE_SUBJECTS.find((s) => s.id === ids[j])!
      if (!predicate(a, b)) continue
      const pa = subjects.get(ids[i])!
      const pb = subjects.get(ids[j])!
      const dx = pa.x - pb.x
      const dy = pa.y - pb.y
      total += Math.sqrt(dx * dx + dy * dy)
      count++
    }
  }
  return count > 0 ? total / count : 0
}

describe('layoutIslands (R3 organic + relationship-aware)', () => {
  it('produces a position for every subject', () => {
    const layout = layoutIslands(SAMPLE_SUBJECTS)
    expect(layout.positions).toHaveLength(SAMPLE_SUBJECTS.length)
    const ids = layout.positions.map((p) => p.id)
    for (const s of SAMPLE_SUBJECTS) {
      expect(ids).toContain(s.id)
    }
  })

  it('is deterministic — same input yields identical output', () => {
    const a = layoutIslands(SAMPLE_SUBJECTS)
    const b = layoutIslands(SAMPLE_SUBJECTS)
    expect(a.positions).toEqual(b.positions)
  })

  it('produces different layouts for different subject sets', () => {
    const subset = SAMPLE_SUBJECTS.slice(0, 4)
    const a = layoutIslands(SAMPLE_SUBJECTS)
    const b = layoutIslands(subset)
    // Different counts → different layouts
    expect(a.positions).not.toEqual(b.positions)
  })

  it('is organic — no two islands share an x or y coordinate within tolerance', () => {
    const layout = layoutIslands(SAMPLE_SUBJECTS)
    const TOLERANCE = 0.01
    for (let i = 0; i < layout.positions.length; i++) {
      for (let j = i + 1; j < layout.positions.length; j++) {
        const pi = layout.positions[i]
        const pj = layout.positions[j]
        expect(Math.abs(pi.x - pj.x)).toBeGreaterThan(TOLERANCE)
        expect(Math.abs(pi.y - pj.y)).toBeGreaterThan(TOLERANCE)
      }
    }
  })

  it('keeps all positions within [0, 1] bounds', () => {
    const layout = layoutIslands(SAMPLE_SUBJECTS)
    for (const p of layout.positions) {
      expect(p.x).toBeGreaterThanOrEqual(0)
      expect(p.x).toBeLessThanOrEqual(1)
      expect(p.y).toBeGreaterThanOrEqual(0)
      expect(p.y).toBeLessThanOrEqual(1)
    }
  })

  it('related subjects (same terrain) sit nearer than unrelated ones', () => {
    const layout = layoutIslands(SAMPLE_SUBJECTS)
    const intraFamily = meanPairDistance(layout, (a, b) => a.terrain === b.terrain)
    const interFamily = meanPairDistance(layout, (a, b) => a.terrain !== b.terrain)
    expect(intraFamily).toBeLessThan(interFamily)
  })

  it('island radius scales with topic count', () => {
    const layout = layoutIslands(SAMPLE_SUBJECTS)
    const math = layout.positions.find((p) => p.id === 'mathematics')!
    const art = layout.positions.find((p) => p.id === 'art')!
    expect(math.radius).toBeGreaterThan(art.radius)
  })

  it('handles a single subject without errors', () => {
    const layout = layoutIslands([{ id: 'solo', terrain: 'math', topicCount: 10 }])
    expect(layout.positions).toHaveLength(1)
    expect(layout.positions[0].x).toBeCloseTo(0.5, 1)
    expect(layout.positions[0].y).toBeCloseTo(0.5, 1)
  })

  it('handles an empty subject list', () => {
    const layout = layoutIslands([])
    expect(layout.positions).toHaveLength(0)
  })
})
