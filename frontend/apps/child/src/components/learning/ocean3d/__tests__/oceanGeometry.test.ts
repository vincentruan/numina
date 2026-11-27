/** Ocean geometry math — pure logic, no three.js. */
import { describe, expect, it } from 'vitest'
import type {
  OceanDomain,
  OceanSubject,
} from '@/components/learning/KnowledgeOcean.vue'
import {
  ISLAND_MARGIN_RATIO,
  OCEAN_HALF_SPAN,
  fogOpacityForMastery,
  layoutOceanDomains,
  layoutOceanNodes,
  toWorldRadius,
} from '../oceanGeometry'
import { composeDomainId, parseDomainId } from '../types'
import { layoutIslands } from '@/utils/islandLayout'

function makeSubject(
  id: string,
  overrides: Partial<OceanSubject> = {},
): OceanSubject {
  return {
    id,
    terrain: 'math',
    displayName: `S${id}`,
    icon: '📐',
    topicCount: 1,
    masteryRatio: 0,
    ...overrides,
  }
}

function makeDomain(
  subject: string,
  id: string,
  masteryRatio = 0,
): OceanDomain {
  return {
    id,
    subject,
    domain: id,
    displayName: `D${id}`,
    topicCount: 1,
    masteryRatio,
  }
}

describe('layoutOceanNodes', () => {
  it('maps normalized layout to world X/Z with 15% margin and upstream separation', () => {
    const subjects = Array.from({ length: 8 }, (_, i) =>
      makeSubject(`s${i}`, { topicCount: i + 1 }),
    )
    const nodes = layoutOceanNodes(subjects)
    const bound = OCEAN_HALF_SPAN * (1 - ISLAND_MARGIN_RATIO)

    expect(nodes).toHaveLength(8)
    for (const node of nodes) {
      expect(Math.abs(node.x)).toBeLessThanOrEqual(bound)
      expect(Math.abs(node.z)).toBeLessThanOrEqual(bound)
    }

    // The upstream 2D layout enforces a minimum Euclidean separation of
    // 0.15 in normalized units. Both spacing and radius now use the same
    // margin scale, so centers stay at least 0.15 * 2 * bound apart while
    // radii stay below 0.07 * 2 * bound — islands cannot overlap.
    const raw = layoutIslands(
      subjects.map(({ id, terrain, topicCount }) => ({
        id,
        terrain,
        topicCount,
      })),
    )
    const rawById = new Map(
      raw.positions.map((position) => [position.id, position]),
    )
    for (const node of nodes) {
      const position = rawById.get(node.id)!
      expect(node.x).toBeCloseTo((position.x - 0.5) * 2 * bound)
      expect(node.z).toBeCloseTo((position.y - 0.5) * 2 * bound)
      expect(node.worldRadius).toBeCloseTo(toWorldRadius(position.radius))
    }
    for (let i = 0; i < nodes.length; i++) {
      for (let j = i + 1; j < nodes.length; j++) {
        const pi = rawById.get(nodes[i].id)!
        const pj = rawById.get(nodes[j].id)!
        expect(Math.hypot(pi.x - pj.x, pi.y - pj.y)).toBeGreaterThanOrEqual(
          0.149,
        )
        const distance = Math.hypot(
          nodes[i].x - nodes[j].x,
          nodes[i].z - nodes[j].z,
        )
        expect(distance).toBeGreaterThan(
          nodes[i].worldRadius + nodes[j].worldRadius,
        )
      }
    }
  })

  it('is deterministic for the same subject set regardless of input order', () => {
    const subjects = [
      makeSubject('math', { terrain: 'logic', topicCount: 4 }),
      makeSubject('science', {
        terrain: 'nature',
        topicCount: 7,
        masteryRatio: 0.5,
      }),
      makeSubject('art', { terrain: 'logic', topicCount: 2 }),
    ]
    expect(layoutOceanNodes(subjects)).toEqual(
      layoutOceanNodes([...subjects].reverse()),
    )
  })

  it('centers a single island and preserves its metadata', () => {
    const [node] = layoutOceanNodes([
      makeSubject('math', {
        displayName: '数学',
        icon: '➗',
        terrain: 'logic',
        masteryRatio: 0.3,
      }),
    ])
    expect(node).toEqual({
      id: 'math',
      displayName: '数学',
      icon: '➗',
      terrain: 'logic',
      x: 0,
      z: 0,
      worldRadius: toWorldRadius(0.07),
      masteryRatio: 0.3,
    })
  })

  it('returns an empty list for empty input', () => {
    expect(layoutOceanNodes([])).toEqual([])
  })
})

describe('layoutOceanDomains', () => {
  it('maps domain layout to world coordinates with subject metadata', () => {
    const domains = [
      makeDomain('math', 'algebra'),
      makeDomain('science', 'physics', 0.5),
    ]
    const nodes = layoutOceanDomains(domains)
    const bound = OCEAN_HALF_SPAN * (1 - ISLAND_MARGIN_RATIO)

    expect(nodes).toHaveLength(2)
    expect(nodes.map((node) => node.id)).toEqual(['algebra', 'physics'])
    expect(nodes.map((node) => node.subject)).toEqual(['math', 'science'])
    expect(nodes[1].masteryRatio).toBe(0.5)
    for (const node of nodes) {
      expect(Math.abs(node.x)).toBeLessThanOrEqual(bound)
      expect(Math.abs(node.z)).toBeLessThanOrEqual(bound)
      expect(node.worldRadius).toBeCloseTo(toWorldRadius(0.07))
    }
  })

  it('is deterministic for the same domain set regardless of input order', () => {
    const domains = [
      makeDomain('math', 'algebra'),
      makeDomain('math', 'geometry'),
    ]
    expect(layoutOceanDomains(domains)).toEqual(
      layoutOceanDomains([...domains].reverse()),
    )
  })
})


describe('ocean domain id helpers', () => {
  it('composes and parses composite ids without splitting unrelated subjects', () => {
    expect(composeDomainId('math', 'fractions')).toBe('math:fractions')
    expect(parseDomainId('math:fractions', 'math')).toBe('fractions')
    expect(parseDomainId('fractions', 'math')).toBe('fractions')
    expect(parseDomainId('physics:fractions', 'math')).toBe('physics:fractions')
    expect(parseDomainId('math:', 'math')).toBe('')
  })
})

describe('fogOpacityForMastery (spec T8)', () => {
  it.each([
    [0, 1],
    [0.25, 0.5],
    [0.5, 1 - Math.SQRT1_2],
    [1, 0],
  ])('maps %s to %s', (ratio, expected) => {
    expect(fogOpacityForMastery(ratio)).toBeCloseTo(expected)
  })

  it('clamps out-of-range ratios', () => {
    expect(fogOpacityForMastery(-1)).toBe(1)
    expect(fogOpacityForMastery(2)).toBe(0)
  })
})
