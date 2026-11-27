/**
 * Ocean geometry math (T6, T8) — pure logic, deliberately free of three.js
 * imports so layout/fog tests stay fast.
 *
 * `layoutIslands()` produces normalized [0,1]² positions with a radius scaled
 * to that unit width; world space scales both through OCEAN_HALF_SPAN.
 */
import { layoutIslands } from '@/utils/islandLayout'
import type {
  OceanDomain,
  OceanSubject,
} from '@/components/learning/KnowledgeOcean.vue'
import type { OceanCameraNode } from './types'

/** Half-width (and half-depth) of the ocean plane in world units. */
export const OCEAN_HALF_SPAN = 10

/** Fraction of the ocean reserved as open water around the islands. */
export const ISLAND_MARGIN_RATIO = 0.15

export interface OceanIslandNode extends OceanCameraNode {
  displayName: string
  icon: string
  terrain: string
  masteryRatio: number
}

export interface OceanDomainNode extends OceanCameraNode {
  subject: string
  displayName: string
  masteryRatio: number
}

/** Normalized coordinate → world coordinate, mirroring the 15% margin. */
function toWorld(value: number): number {
  return (value - 0.5) * 2 * OCEAN_HALF_SPAN * (1 - ISLAND_MARGIN_RATIO)
}

/** Normalized layout radius → world radius, using the same margin as the centers. */
export function toWorldRadius(radius: number): number {
  return radius * 2 * OCEAN_HALF_SPAN * (1 - ISLAND_MARGIN_RATIO)
}

/** Deterministic subject layout with metadata retained for picking/rendering. */
export function layoutOceanNodes(subjects: OceanSubject[]): OceanIslandNode[] {
  const positions = layoutIslands(
    subjects.map(({ id, terrain, topicCount }) => ({
      id,
      terrain,
      topicCount,
    })),
  ).positions
  const byId = new Map(subjects.map((subject) => [subject.id, subject]))

  return positions.map((position) => {
    const subject = byId.get(position.id)!
    return {
      id: subject.id,
      displayName: subject.displayName,
      icon: subject.icon,
      terrain: subject.terrain,
      x: toWorld(position.x),
      z: toWorld(position.y),
      worldRadius: toWorldRadius(position.radius),
      masteryRatio: subject.masteryRatio,
    }
  })
}

/** Domain layout uses a single terrain family so all regions share a cluster. */
export function layoutOceanDomains(domains: OceanDomain[]): OceanDomainNode[] {
  const positions = layoutIslands(
    domains.map(({ id, topicCount }) => ({
      id,
      terrain: 'region',
      topicCount,
    })),
  ).positions
  const byId = new Map(domains.map((domain) => [domain.id, domain]))

  return positions.map((position) => {
    const domain = byId.get(position.id)!
    return {
      id: domain.id,
      subject: domain.subject,
      displayName: domain.displayName,
      x: toWorld(position.x),
      z: toWorld(position.y),
      worldRadius: toWorldRadius(position.radius),
      masteryRatio: domain.masteryRatio,
    }
  })
}

/** Spec T8: fog opacity is exactly `1 - sqrt(clamp(ratio, 0, 1))`. */
export function fogOpacityForMastery(ratio: number): number {
  return 1 - Math.sqrt(Math.max(0, Math.min(1, ratio)))
}
