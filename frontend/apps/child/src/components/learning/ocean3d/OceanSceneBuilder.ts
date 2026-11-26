/**
 * Ocean scene builder — turns layout nodes into three.js island/domain objects.
 *
 * L0: low-poly floating island (cylinder top + tapered underside), a
 *     mastery ring and a semi-transparent fog disc above it.
 * L1: rounded region tiles laid out with water lanes, same fog contract.
 *
 * Motion is shader/anime-only: one child timeline bobs every island group,
 * and the shared render loop is the sole caller of `tickDriver`.
 */
import {
  CircleGeometry,
  ConeGeometry,
  CylinderGeometry,
  DoubleSide,
  Group,
  Mesh,
  MeshStandardMaterial,
  Object3D,
  RingGeometry,
  type Material,
  type Texture,
} from 'three'
import { createChildTimeline } from '@/motion/animeDriver'
import type { Timeline } from 'animejs'
import { resolveThemeColor } from '../scene3d/resolveThemeColor'
import {
  fogOpacityForMastery,
  type OceanDomainNode,
  type OceanIslandNode,
} from './oceanGeometry'

export type OceanNode = OceanIslandNode | OceanDomainNode

export interface OceanSceneOptions {
  reducedMotion?: boolean
  domainMode?: boolean
}

export interface OceanScene {
  root: Group
  islands: OceanNode[]
  pickTargets: Object3D[]
  /** Bob timelines owned by this scene; reverted exactly once on dispose. */
  timelines: Timeline[]
  dispose(): void
}

/** Bob distance and cycle length (milliseconds). */
const BOB_HEIGHT = 0.18
const BOB_DURATION = 3200
const BOB_STAGGER = 180

/** Smallest tile radius, leaving water between neighboring tiles. */
const MIN_TILE_HALF_SIZE = 0.45
/** Fraction of the node radius consumed by the tile (rest is water lane). */
const TILE_SIZE_RATIO = 0.62

/** Mastery ring gets brighter as fog fades out. */
function masteryLuminance(ratio: number): number {
  return 0.35 + 0.65 * Math.max(0, Math.min(1, ratio))
}

function buildFog(node: OceanNode, radius: number): Mesh {
  const geometry = new CircleGeometry(radius * 1.04, 24)
  const material = new MeshStandardMaterial({
    color: '#c8d8e0',
    transparent: true,
    opacity: fogOpacityForMastery(node.masteryRatio),
    depthWrite: false,
    roughness: 1,
  })
  const mesh = new Mesh(geometry, material)
  mesh.rotation.x = -Math.PI / 2
  mesh.position.y = 0.34
  mesh.userData.type = 'fog'
  return mesh
}

function buildMasteryRing(node: OceanNode, radius: number): Mesh {
  const ringRadius = radius * 1.12
  const geometry = new RingGeometry(
    ringRadius * 0.92,
    ringRadius,
    24,
    1,
    -Math.PI / 2,
    Math.PI * 2 * Math.max(0, Math.min(1, node.masteryRatio)),
  )
  const material = new MeshStandardMaterial({
    color: '#ffe6a3',
    emissive: '#ffc94d',
    emissiveIntensity: masteryLuminance(node.masteryRatio),
    transparent: true,
    depthWrite: false,
    side: DoubleSide,
  })
  const mesh = new Mesh(geometry, material)
  mesh.rotation.x = -Math.PI / 2
  mesh.position.y = 0.2
  mesh.userData.type = 'masteryRing'
  return mesh
}

/** L0 island: cylinder plateau over a tapered cone underside. */
function buildIsland(node: OceanIslandNode): Group {
  const group = new Group()
  group.position.set(node.x, 0, node.z)
  group.userData = { islandId: node.id, type: 'island' }

  const radius = node.worldRadius
  const color = resolveThemeColor(node.terrain)
  const bodyMaterial = new MeshStandardMaterial({
    color,
    roughness: 0.85,
    flatShading: true,
  })

  const centerRadius = radius * 0.9
  const top = new Mesh(
    new CylinderGeometry(radius, centerRadius, 0.36, 8),
    bodyMaterial,
  )
  top.position.y = 0.08
  top.castShadow = true
  top.receiveShadow = true
  top.userData = { islandId: node.id, type: 'island' }
  group.add(top)

  const underside = new Mesh(
    new ConeGeometry(centerRadius, radius * 0.8, 8),
    bodyMaterial,
  )
  underside.rotation.z = Math.PI
  underside.position.y = -0.3 - radius * 0.4
  underside.userData = { islandId: node.id, type: 'island' }
  group.add(underside)

  group.add(buildMasteryRing(node, radius), buildFog(node, radius))
  return group
}

/**
 * L1 region tile: an 8-sided cylinder reads as a rounded box in plan view and
 * keeps its footprint smaller than the node radius, so adjacent tiles have a
 * visible water lane even when their layout centers are close.
 */
function buildDomainTile(node: OceanDomainNode): Group {
  const group = new Group()
  group.position.set(node.x, 0, node.z)
  group.userData = { domainId: node.id, subject: node.subject, type: 'domain' }

  const radius = Math.max(
    node.worldRadius * TILE_SIZE_RATIO,
    MIN_TILE_HALF_SIZE,
  )
  const color = resolveThemeColor(node.subject)
  const material = new MeshStandardMaterial({
    color,
    roughness: 0.8,
    flatShading: true,
  })

  const tile = new Mesh(new CylinderGeometry(radius, radius, 0.3, 8), material)
  tile.rotation.y = Math.PI / 8
  tile.receiveShadow = true
  tile.userData = { domainId: node.id, subject: node.subject, type: 'domain' }
  group.add(tile)

  group.add(buildMasteryRing(node, radius), buildFog(node, radius))
  return group
}

/** Build the island/domain scene for the given layout nodes. */
export function buildOceanScene(
  nodes: OceanNode[],
  options: OceanSceneOptions = {},
): OceanScene {
  const root = new Group()
  const pickTargets: Object3D[] = []

  for (const node of nodes) {
    const pickTarget = options.domainMode
      ? buildDomainTile(node as OceanDomainNode)
      : buildIsland(node as OceanIslandNode)
    root.add(pickTarget)
    pickTargets.push(pickTarget)
  }

  let bobTimeline: Timeline | null = null
  if (!options.reducedMotion && nodes.length > 0) {
    bobTimeline = createChildTimeline()
    bobTimeline.add(
      root.children.map((group) => group.position),
      {
        y: [
          { to: BOB_HEIGHT, duration: BOB_DURATION / 4 },
          { to: 0, duration: BOB_DURATION / 4 },
          { to: -BOB_HEIGHT, duration: BOB_DURATION / 4 },
          { to: 0, duration: BOB_DURATION / 4 },
        ],
        // Staggered loop start per target; animejs accepts a function value.
        delay: (_target?: unknown, index?: number) =>
          (index ?? 0) * BOB_STAGGER,
        duration: BOB_DURATION,
        loop: true,
        ease: 'inOutSine',
      },
    )
  }

  const scene: OceanScene = {
    root,
    islands: nodes,
    pickTargets,
    timelines: bobTimeline ? [bobTimeline] : [],
    dispose: () => disposeOceanScene(scene),
  }
  return scene
}

/** Release all GPU resources, stop motion, and empty the scene graph. */
export function disposeOceanScene(scene: OceanScene): void {
  for (const timeline of scene.timelines) timeline.revert()
  scene.timelines.length = 0

  const geometries = new Set<Mesh['geometry']>()
  const materials = new Set<Material>()
  scene.root.traverse((object) => {
    if (!(object instanceof Mesh)) return
    geometries.add(object.geometry)
    const objectMaterials = Array.isArray(object.material)
      ? object.material
      : [object.material]
    for (const material of objectMaterials) materials.add(material)
  })

  for (const geometry of geometries) geometry.dispose()
  for (const material of materials) {
    for (const value of Object.values(
      material as Material & Record<string, unknown>,
    )) {
      if (value && typeof value === 'object' && 'isTexture' in value) {
        ;(value as Texture).dispose()
      }
    }
    material.dispose()
  }
  scene.root.clear()
  scene.islands = []
  scene.pickTargets.length = 0
}
