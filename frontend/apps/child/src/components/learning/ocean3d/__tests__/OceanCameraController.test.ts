/**
 * T10 level camera — L0 framing, dive/ascend transitions, instant mode,
 * and child-timeline cleanup across repeated level changes.
 */
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { PerspectiveCamera, Vector3 } from 'three'
import { getRootTimeline, revertAll, tickDriver } from '@/motion/animeDriver'
import { createOceanCameraController } from '../OceanCameraController'

const DURATION = 800

function createCamera(): PerspectiveCamera {
  return new PerspectiveCamera(55, 1, 0.1, 200)
}

function positionFrom(
  target: { x: number; z: number },
  radius: number,
  phi: number,
): Vector3 {
  return new Vector3(
    target.x,
    radius * Math.cos(phi),
    target.z + radius * Math.sin(phi),
  )
}

/** AnimeJS keeps a root timeline after a transition ends; a leak means
 *  children (synced child timelines) remain attached to the root. */
function childCount(): number {
  const root = getRootTimeline()
  if (!root) return 0
  let count = 0
  let node: unknown = (root as unknown as { _head: unknown })._head
  while (node) {
    const current = node as { _next?: unknown; _cancelled?: number }
    if (current._cancelled === 0) count++
    node = current._next
  }
  return count
}

/** AnimeJS sync() pins a child's start time to the root's current time; the
 *  root must advance inside the same window in which the child was created. */
let clock = 0
async function advance(ms: number): Promise<void> {
  tickDriver(clock + ms)
  await vi.advanceTimersByTimeAsync(ms + 50)
  clock += ms
}

beforeEach(() => {
  revertAll()
  clock = 0
  vi.useFakeTimers()
})

afterEach(() => {
  revertAll()
  vi.useRealTimers()
  vi.restoreAllMocks()
})

describe('createOceanCameraController', () => {
  it('starts at L0 with radius 22, theta 0, phi π/3 and the world center target', () => {
    const controller = createOceanCameraController(createCamera())
    const state = controller.getStateSnapshot()

    expect(state.radius).toBeCloseTo(22)
    expect(state.theta).toBeCloseTo(0)
    expect(state.phi).toBeCloseTo(Math.PI / 3)
    expect(state.target.toArray()).toEqual([0, 0, 0])
    controller.dispose()
  })

  it('diveTo animates a child timeline to the node with a low horizon and close radius', async () => {
    const controller = createOceanCameraController(createCamera())
    const node = { x: 2, z: 3, worldRadius: 2 }
    const promise = controller.diveTo(node)

    expect(getRootTimeline()).not.toBeNull()
    expect(vi.getTimerCount()).toBe(1)
    // A timeout alone cannot move the camera — only root-clock ticks do.
    expect(controller.getStateSnapshot().target.x).toBeCloseTo(0)

    await advance(DURATION)
    await promise

    const state = controller.getStateSnapshot()
    expect(state.target.x).toBeCloseTo(node.x)
    expect(state.target.z).toBeCloseTo(node.z)
    expect(state.radius).toBeCloseTo(Math.max(node.worldRadius * 3, 6))
    expect(state.phi).toBeGreaterThan(Math.PI / 3)
    controller.dispose()
  })

  it('ascend and reset return to the L0 center and radius', async () => {
    const controller = createOceanCameraController(createCamera())
    const node = { x: -4, z: 1, worldRadius: 1 }
    const dive = controller.diveTo(node)
    await advance(DURATION)
    await dive

    const ascend = controller.ascend()
    expect(getRootTimeline()).not.toBeNull()
    await advance(DURATION)
    await ascend

    let state = controller.getStateSnapshot()
    expect(state.target.toArray()).toEqual([0, 0, 0])
    expect(state.radius).toBeCloseTo(22)

    const reset = controller.reset()
    await advance(DURATION)
    await reset
    state = controller.getStateSnapshot()
    expect(state.target.toArray()).toEqual([0, 0, 0])
    expect(state.radius).toBeCloseTo(22)
    controller.dispose()
  })

  it('instant mode moves immediately without a child timeline', async () => {
    const controller = createOceanCameraController(createCamera(), {
      instant: true,
    })
    const node = { x: 2, z: 3, worldRadius: 1 }

    await controller.diveTo(node)
    expect(getRootTimeline()).toBeNull()
    expect(controller.getStateSnapshot().target.x).toBeCloseTo(node.x)
    expect(controller.getStateSnapshot().radius).toBeCloseTo(6)

    await controller.ascend()
    expect(controller.getStateSnapshot().radius).toBeCloseTo(22)
    controller.dispose()
  })

  it('20 dive/ascend cycles leave no child timelines after dispose', async () => {
    const controller = createOceanCameraController(createCamera())
    const node = { x: 2, z: 3, worldRadius: 1 }

    for (let i = 0; i < 20; i++) {
      const dive = controller.diveTo(node)
      await advance(DURATION)
      await dive
      const ascend = controller.ascend()
      await advance(DURATION)
      await ascend
    }

    controller.dispose()
    expect(childCount()).toBe(0)
  })

  it('dispose reverts an in-flight transition and stops pointer listeners', async () => {
    const camera = createCamera()
    const controller = createOceanCameraController(camera)
    const element = document.createElement('div')
    const dblClick = vi.fn()
    element.addEventListener('dblclick', dblClick)
    void controller.diveTo({ x: 2, z: 3, worldRadius: 1 })

    controller.dispose()
    expect(childCount()).toBe(0)

    element.dispatchEvent(new MouseEvent('dblclick'))
    expect(dblClick).toHaveBeenCalledTimes(1)
  })

  it('positions the camera from spherical state at all times', async () => {
    const camera = createCamera()
    const controller = createOceanCameraController(camera, { instant: true })
    const node = { x: 2, z: 3, worldRadius: 2 }
    await controller.diveTo(node)

    const state = controller.getStateSnapshot()
    const expected = positionFrom(node, state.radius, state.phi)
    expect(camera.position.x).toBeCloseTo(expected.x)
    expect(camera.position.y).toBeCloseTo(expected.y)
    expect(camera.position.z).toBeCloseTo(expected.z)
    controller.dispose()
  })
})
