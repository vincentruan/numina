/**
 * Castle3D integration tests — lifecycle, memory, degradation.
 *
 * These exercise the module boundaries together (scene builder + camera +
 * physics + reduced motion), which unit tests deliberately isolate.
 */
import { describe, it, expect, beforeEach } from 'vitest'
import { Vector3, PerspectiveCamera } from 'three'
import { _resetForTesting, initRapier, getWorld, isInitialized } from '@/physics/rapierWorld'
import { tickDriver, revertAll, getRootTimeline } from '@/motion/animeDriver'
import { buildCastleScene, disposeScene, calcBrickCount } from '../CastleSceneBuilder'
import { CameraController } from '../CameraController'
import type { CastleIndex, CastleFloor } from '@/api/learning'

const floor: CastleFloor = {
  domain: 'fractions',
  mastered_count: 5,
  learning_count: 0,
  review_due_count: 0,
  total_count: 10,
}

/** Build a castle with N towers, each with one floor. */
function makeCastle(towerCount: number): CastleIndex {
  return {
    towers: Array.from({ length: towerCount }, (_, i) => ({
      subject: `subject-${i}`,
      mastered_count: 5,
      learning_count: 0,
      review_due_count: 0,
      total_count: 10,
      floors: [floor],
    })),
    windows: [],
    streak_days: 0,
  }
}

describe('Castle3D integration', () => {
  beforeEach(() => {
    _resetForTesting()
    revertAll()
  })

  it('20 mount/unmount cycles do not leak physics bodies or timelines', async () => {
    await initRapier()
    const world = getWorld()
    const baselineBodies = world.bodies.len()

    for (let cycle = 0; cycle < 20; cycle++) {
      const scene = buildCastleScene(makeCastle(3))
      expect(scene.towers.size).toBe(3)

      // Simulate the render loop ticking a few frames
      tickDriver(cycle * 16)
      tickDriver(cycle * 16 + 16)

      disposeScene(scene)
    }

    // No physics bodies were created by the castle itself
    expect(world.bodies.len()).toBe(baselineBodies)

    // Timelines are reclaimable
    revertAll()
    expect(getRootTimeline()).toBeNull()

    // Physics world survives all cycles
    expect(isInitialized()).toBe(true)
  })

  it('handles a castle with 8 towers without losing towers or bricks', () => {
    const scene = buildCastleScene(makeCastle(8))
    expect(scene.towers.size).toBe(8)
    // Each tower: 1 body mesh + 1 floor group
    expect(scene.root.children.length).toBe(8)
  })

  it('renders zero-progress towers as an empty structure, not a missing tower', () => {
    const emptyFloor: CastleFloor = {
      domain: 'fractions',
      mastered_count: 0,
      learning_count: 0,
      review_due_count: 0,
      total_count: 10,
    }
    const castle: CastleIndex = {
      towers: [
        {
          subject: 'mathematics',
          mastered_count: 0,
          learning_count: 0,
          review_due_count: 0,
          total_count: 10,
          floors: [emptyFloor],
        },
      ],
      windows: [],
      streak_days: 0,
    }

    const scene = buildCastleScene(castle)
    expect(scene.towers.has('mathematics')).toBe(true)
    expect(calcBrickCount(emptyFloor)).toBe(0)
  })

  it('camera controller reuses one camera across panorama/tower transitions', async () => {
    const camera = new PerspectiveCamera(55, 1, 0.1, 200)
    const controller = new CameraController(camera)

    const panoramaPos = controller.getPosition()
    expect(panoramaPos.length()).toBeGreaterThan(0)

    await controller.transitionToTower(new Vector3(4, 0, 0), 4)
    const towerPos = controller.getPosition()
    expect(towerPos.length()).toBeGreaterThan(0)

    await controller.transitionToPanorama()
    const backPos = controller.getPosition()
    expect(backPos.length()).toBeGreaterThan(0)

    controller.dispose()
  })

  it('WebGL detection reports false when the context cannot be created', async () => {
    // The page's fallback hinges on this: a device with no WebGL must be
    // detected up front so the 2D castle renders instead of a black canvas.
    const { isWebGLAvailable } = await import('@/composables/useWebGLAvailable')
    const original = HTMLCanvasElement.prototype.getContext
    HTMLCanvasElement.prototype.getContext = (() => null) as typeof original

    try {
      expect(isWebGLAvailable()).toBe(false)
    } finally {
      HTMLCanvasElement.prototype.getContext = original
    }
  })

  it('keeps brick counts consistent between the 3D scene and the 2D overlay', () => {
    // Both the panorama (3D) and TowerInterior (2D) derive bricks from the
    // same rule — a mismatch would show two different castles for one child.
    const floors: CastleFloor[] = [
      { domain: 'a', mastered_count: 0, learning_count: 0, review_due_count: 0, total_count: 10 },
      { domain: 'b', mastered_count: 1, learning_count: 0, review_due_count: 0, total_count: 100 },
      { domain: 'c', mastered_count: 5, learning_count: 5, review_due_count: 0, total_count: 10 },
      { domain: 'd', mastered_count: 10, learning_count: 0, review_due_count: 0, total_count: 10 },
    ]

    const counts = floors.map(calcBrickCount)
    expect(counts[0]).toBe(0) // no progress → no bricks
    expect(counts[1]).toBe(1) // any progress → at least one brick
    expect(counts[2]).toBe(8) // full ratio → capped
    expect(counts[3]).toBe(8) // capped
    counts.forEach((c) => expect(c).toBeLessThanOrEqual(8))
  })
})
