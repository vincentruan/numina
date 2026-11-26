/**
 * CastleSceneBuilder — converts CastleIndex data into three.js scene objects.
 *
 * Visual mapping:
 * - Tower: CylinderGeometry (radius 1.5, height = floors * 2)
 * - Floor: RingGeometry at y = floorIndex * 2
 * - Brick: BoxGeometry(0.3, 0.2, 0.3) arranged in grid
 * - Window: SphereGeometry(0.2) emissive, on tower exterior
 */
import {
  Group,
  CylinderGeometry,
  MeshStandardMaterial,
  Mesh,
  BoxGeometry,
  SphereGeometry,
  Vector3,
  Box3,
  type Material,
} from 'three'
import type {
  CastleIndex,
  CastleTower,
  CastleFloor,
  CastleWindow,
} from '@/api/learning'
import { resolveThemeColor } from '../scene3d/resolveThemeColor'

/** Max bricks per floor to avoid rendering too many objects. */
const MAX_BRICKS_PER_FLOOR = 8

/** Tower spacing in panorama view. */
const TOWER_SPACING = 4

/** Floor height in 3D units. */
const FLOOR_HEIGHT = 2

/** Tower radius. */
const TOWER_RADIUS = 1.5

/** Brick size. */
const BRICK_SIZE = { x: 0.3, y: 0.2, z: 0.3 }

/** 3D scene build result. */
export interface CastleScene {
  /** Root group containing all towers. */
  root: Group
  /** Tower groups indexed by subject. */
  towers: Map<string, Group>
  /** Window meshes (raycaster targets). */
  windows: Mesh[]
  /** Window-to-subject mapping. */
  windowSubjects: Map<Mesh, string>
}

/**
 * Build full 3D castle scene from API data.
 */
export function buildCastleScene(castle: CastleIndex): CastleScene {
  const root = new Group()
  const towers = new Map<string, Group>()
  const windows: Mesh[] = []
  const windowSubjects = new Map<Mesh, string>()

  // Layout towers in a row
  const totalWidth = (castle.towers.length - 1) * TOWER_SPACING
  const startX = -totalWidth / 2

  castle.towers.forEach((tower, index) => {
    const x = startX + index * TOWER_SPACING
    const towerGroup = buildTower(tower, x)
    root.add(towerGroup)
    towers.set(tower.subject, towerGroup)

    // Build windows for this tower
    const towerWindows = castle.windows.filter(
      (w) => w.subject === tower.subject,
    )
    const windowMeshes = buildWindows(
      towerWindows,
      towerGroup,
      tower.floors.length,
    )
    windows.push(...windowMeshes)
    windowMeshes.forEach((mesh) => {
      windowSubjects.set(mesh, tower.subject)
    })
  })

  return { root, towers, windows, windowSubjects }
}

/**
 * Build a single tower group.
 */
export function buildTower(tower: CastleTower, xOffset: number): Group {
  const group = new Group()
  group.position.set(xOffset, 0, 0)

  const floorCount = tower.floors.length
  const height = floorCount * FLOOR_HEIGHT

  // Tower body
  const geometry = new CylinderGeometry(TOWER_RADIUS, TOWER_RADIUS, height, 16)
  const color = resolveThemeColor(tower.subject)
  const material = new MeshStandardMaterial({ color, roughness: 0.7 })
  const mesh = new Mesh(geometry, material)
  mesh.position.y = height / 2
  mesh.userData = { subject: tower.subject, type: 'tower' }
  group.add(mesh)

  // Build floors
  tower.floors.forEach((floor, index) => {
    const floorGroup = buildFloor(floor, index)
    floorGroup.position.y = index * FLOOR_HEIGHT + FLOOR_HEIGHT / 2
    group.add(floorGroup)
  })

  return group
}

/**
 * Build a floor group with bricks.
 */
export function buildFloor(floor: CastleFloor, index: number): Group {
  const group = new Group()

  const brickCount = Math.min(calcBrickCount(floor), MAX_BRICKS_PER_FLOOR)
  const bricksPerRow = Math.ceil(Math.sqrt(brickCount))
  const spacing = 0.4

  for (let i = 0; i < brickCount; i++) {
    const row = Math.floor(i / bricksPerRow)
    const col = i % bricksPerRow
    const x = (col - (bricksPerRow - 1) / 2) * spacing
    const z = (row - Math.floor((brickCount - 1) / bricksPerRow) / 2) * spacing

    const brick = buildBrick(x, z, 0)
    group.add(brick)
  }

  group.userData = { floorIndex: index, floor }
  return group
}

/**
 * Build a single brick mesh.
 */
export function buildBrick(x: number, z: number, y: number = 0): Mesh {
  const geometry = new BoxGeometry(BRICK_SIZE.x, BRICK_SIZE.y, BRICK_SIZE.z)
  const material = new MeshStandardMaterial({
    color: 0xd4a574,
    roughness: 0.8,
  }) // Warm brick color
  const mesh = new Mesh(geometry, material)
  mesh.position.set(x, y, z)
  mesh.userData = { type: 'brick' }
  return mesh
}

/**
 * Build window meshes on tower exterior.
 */
export function buildWindows(
  windowList: CastleWindow[],
  towerGroup: Group,
  floorCount: number,
): Mesh[] {
  const meshes: Mesh[] = []
  const height = floorCount * FLOOR_HEIGHT

  windowList.forEach((win, index) => {
    const geometry = new SphereGeometry(0.2, 16, 16)
    const material = new MeshStandardMaterial({
      color: 0xffd700, // Gold
      emissive: 0xffd700,
      emissiveIntensity: 0.5,
    })
    const mesh = new Mesh(geometry, material)

    // Position on tower exterior, evenly spaced
    const angle = (index / Math.max(windowList.length, 1)) * Math.PI * 2
    const y = height * 0.3 + (index % 3) * (height * 0.2) // Stagger vertically
    mesh.position.set(
      Math.cos(angle) * (TOWER_RADIUS + 0.3),
      y,
      Math.sin(angle) * (TOWER_RADIUS + 0.3),
    )
    mesh.userData = { type: 'window', window: win }
    towerGroup.add(mesh)
    meshes.push(mesh)
  })

  return meshes
}

/**
 * Calculate brick count for a floor (capped at MAX_BRICKS_PER_FLOOR).
 * Mirrors the 2D KnowledgeCastle logic.
 */
export function calcBrickCount(floor: CastleFloor): number {
  if (floor.total_count === 0) return 0
  const ratio =
    (floor.mastered_count + floor.learning_count) / floor.total_count
  return ratio === 0 ? 0 : Math.max(1, Math.round(ratio * MAX_BRICKS_PER_FLOOR))
}

/**
 * Get tower center position in 3D space.
 */
export function getTowerCenter(towerGroup: Group): Vector3 {
  return new Vector3(towerGroup.position.x, 0, towerGroup.position.z)
}

/**
 * Measure the whole castle's axis-aligned bounds.
 * Used to frame the camera so tall towers are never clipped and short castles
 * are never a speck.
 */
export function getCastleBounds(scene: CastleScene): {
  center: Vector3
  size: Vector3
} {
  const box = new Box3().setFromObject(scene.root)
  const center = box.getCenter(new Vector3())
  const size = box.getSize(new Vector3())

  // A castle with no geometry would produce an infinite box — fall back
  // to a sensible default so the camera still frames something.
  if (!Number.isFinite(size.x) || size.length() === 0) {
    return { center: new Vector3(0, 2, 0), size: new Vector3(10, 6, 10) }
  }

  return { center, size }
}

/**
 * Dispose all materials and geometries in a scene.
 */
export function disposeScene(scene: CastleScene): void {
  scene.root.traverse((obj) => {
    if (obj instanceof Mesh) {
      obj.geometry.dispose()
      if (Array.isArray(obj.material)) {
        obj.material.forEach((m: Material) => m.dispose())
      } else {
        obj.material.dispose()
      }
    }
  })
}
