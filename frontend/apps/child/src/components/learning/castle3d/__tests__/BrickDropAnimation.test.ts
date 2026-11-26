/**
 * BrickDropAnimation tests — reduced motion, physics body lifecycle.
 */
import { describe, it, expect, beforeEach } from 'vitest'
import { Vector3, Mesh, BoxGeometry, MeshStandardMaterial } from 'three'
import { animateBrickDrop, animateBrickBounce } from '../BrickDropAnimation'
import { _resetForTesting, initRapier, getWorld } from '@/physics/rapierWorld'

function makeBrick(): Mesh {
  return new Mesh(new BoxGeometry(0.3, 0.2, 0.3), new MeshStandardMaterial())
}

describe('animateBrickDrop', () => {
  beforeEach(async () => {
    _resetForTesting()
    await initRapier()
  })

  it('places the brick at the target instantly under reduced motion', async () => {
    const brick = makeBrick()
    const target = new Vector3(1, 2, 3)
    const world = getWorld()

    const before = world.bodies.len()
    await animateBrickDrop(brick, target, world, { reducedMotion: true })

    expect(brick.position.x).toBe(1)
    expect(brick.position.y).toBe(2)
    expect(brick.position.z).toBe(3)
    // No physics body should be created for reduced motion
    expect(world.bodies.len()).toBe(before)
  })

  it('starts the brick above the target when animating', () => {
    const brick = makeBrick()
    const target = new Vector3(0, 1, 0)
    const world = getWorld()

    void animateBrickDrop(brick, target, world)

    // Synchronously, the brick has been lifted to the drop height
    expect(brick.position.y).toBeGreaterThan(target.y)
  })

  it('creates the brick body plus a temporary landing plane', () => {
    const brick = makeBrick()
    const world = getWorld()
    const before = world.bodies.len()

    void animateBrickDrop(brick, new Vector3(0, 1, 0), world)

    // Brick (dynamic) + landing plane (static). The plane stops the brick
    // from free-falling past the floor.
    expect(world.bodies.len()).toBe(before + 2)
  })

  it('brick settles onto the floor instead of falling through', async () => {
    const brick = makeBrick()
    const world = getWorld()
    const target = new Vector3(0, 1, 0)
    const controller = new AbortController()

    const promise = animateBrickDrop(brick, target, world, { signal: controller.signal })

    // Step physics for ~2 seconds of simulated fall
    for (let i = 0; i < 120; i++) {
      world.step()
    }

    controller.abort()
    await promise

    // The brick must not have fallen below the landing plane
    expect(brick.position.y).toBeGreaterThanOrEqual(target.y - 0.5)
  })

  it('returns a promise', () => {
    const brick = makeBrick()
    const promise = animateBrickDrop(brick, new Vector3(0, 1, 0), getWorld())
    expect(promise).toBeInstanceOf(Promise)
  })

  it('aborts cleanly and frees both bodies on unmount signal', async () => {
    const brick = makeBrick()
    const world = getWorld()
    const before = world.bodies.len()
    const controller = new AbortController()

    const promise = animateBrickDrop(brick, new Vector3(0, 1, 0), world, {
      signal: controller.signal,
    })
    expect(world.bodies.len()).toBe(before + 2)

    controller.abort()
    await expect(promise).resolves.toBeUndefined()

    // Both bodies freed — no leak after unmount
    expect(world.bodies.len()).toBe(before)
  })

  it('resolves immediately when the signal is already aborted', async () => {
    const brick = makeBrick()
    const world = getWorld()
    const before = world.bodies.len()
    const controller = new AbortController()
    controller.abort()

    await expect(
      animateBrickDrop(brick, new Vector3(0, 1, 0), world, { signal: controller.signal }),
    ).resolves.toBeUndefined()
    expect(world.bodies.len()).toBe(before)
  })
})

describe('animateBrickBounce', () => {
  it('resolves immediately under reduced motion without scaling', async () => {
    const brick = makeBrick()
    const scaleBefore = brick.scale.y
    await animateBrickBounce(brick, true)
    expect(brick.scale.y).toBe(scaleBefore)
  })

  it('returns a promise when animating', () => {
    const brick = makeBrick()
    const promise = animateBrickBounce(brick)
    expect(promise).toBeInstanceOf(Promise)
  })
})
