/** Shared orbit camera controller tests. */
import { afterEach, describe, expect, it, vi } from 'vitest'
import { PerspectiveCamera, Vector3 } from 'three'
import { getRootTimeline, revertAll, tickDriver } from '@/motion/animeDriver'
import {
  CameraController,
  DEFAULT_PANORAMA,
  DEFAULT_TOWER,
  createPanoramaCamera,
  createTowerCamera,
  frameCastle,
} from '../OrbitCameraController'

/** Build a minimal TouchEvent; happy-dom lacks a Touch constructor. */
function touchEvent(
  type: string,
  touches: Array<{ clientX: number; clientY: number }>,
): TouchEvent {
  const event = new Event(type, { cancelable: true, bubbles: true })
  Object.defineProperty(event, 'touches', { value: touches })
  Object.defineProperty(event, 'changedTouches', { value: touches })
  return event as TouchEvent
}

afterEach(() => {
  revertAll()
  vi.useRealTimers()
})

describe('OrbitCameraController', () => {
  it('animateTo resolves a Promise and writes spherical state', async () => {
    const camera = new PerspectiveCamera(60, 1, 0.1, 100)
    const controller = new CameraController(camera)
    const target = new Vector3(0, 0, 0)
    const position = new Vector3(0, 0, 10)
    vi.useFakeTimers()

    const promise = controller.animateTo(target, position, 20)
    expect(promise).toBeInstanceOf(Promise)

    tickDriver(20)
    await vi.advanceTimersByTimeAsync(70)
    await promise

    expect(controller.getRadius()).toBeCloseTo(10)
    expect(controller.getTarget().x).toBeCloseTo(0)
    expect(controller.getTarget().y).toBeCloseTo(0)
    expect(controller.getTarget().z).toBeCloseTo(0)
    expect(controller.getPosition().z).toBeCloseTo(10)
  })

  it('animateTo uses a child timeline driven by the root clock', async () => {
    const camera = new PerspectiveCamera(60, 1, 0.1, 100)
    const controller = new CameraController(camera)
    vi.useFakeTimers()

    const promise = controller.animateTo(new Vector3(0, 0, 0), new Vector3(0, 0, 10), 40)
    const root = getRootTimeline()
    expect(root).not.toBeNull()
    expect(root?._head).toBeTruthy()
    // The single root clock owns the transition; the timeout only settles the Promise.
    expect(vi.getTimerCount()).toBe(1)
    expect(controller.getRadius()).toBe(DEFAULT_PANORAMA.radius)

    tickDriver(20)
    await vi.advanceTimersByTimeAsync(90)
    await promise
    expect(controller.getRadius()).toBeCloseTo(10)
  })

  it('pinch zoom changes radius without changing theta/phi', () => {
    const camera = new PerspectiveCamera(60, 1, 0.1, 100)
    const controller = new CameraController(camera, undefined, {
      pinchZoom: true,
    })
    const element = document.createElement('div')
    controller.enable(element)

    const before = controller.getStateSnapshot()
    const startRadius = before.radius

    element.dispatchEvent(
      touchEvent('touchstart', [
        { clientX: 90, clientY: 0 },
        { clientX: 110, clientY: 0 },
      ]),
    )
    element.dispatchEvent(
      touchEvent('touchmove', [
        { clientX: 80, clientY: 0 },
        { clientX: 120, clientY: 0 },
      ]),
    )

    const after = controller.getStateSnapshot()
    expect(after.radius).toBeCloseTo(startRadius * (20 / 40))
    expect(after.theta).toBeCloseTo(before.theta)
    expect(after.phi).toBeCloseTo(before.phi)
    expect(controller.getPosition().distanceTo(controller.getTarget())).toBeCloseTo(after.radius)

    controller.dispose(element)
  })

  it('dispose removes listeners, stops rotation, and reverts transition timeline', async () => {
    const camera = new PerspectiveCamera(60, 1, 0.1, 100)
    const controller = new CameraController(camera)
    const element = document.createElement('div')
    controller.enable(element)

    const beforeRotation = controller.getStateSnapshot()
    element.dispatchEvent(touchEvent('touchstart', [{ clientX: 100, clientY: 100 }]))
    element.dispatchEvent(touchEvent('touchmove', [{ clientX: 140, clientY: 100 }]))
    expect(controller.getStateSnapshot().theta).not.toBeCloseTo(beforeRotation.theta)

    const promise = controller.animateTo(new Vector3(0, 0, 0), new Vector3(0, 0, 6), 30)
    const root = getRootTimeline()
    expect(root?._head).toBeTruthy()
    const radiusBeforeDispose = controller.getRadius()
    const headBeforeDispose = root?._head

    controller.dispose(element)
    expect(root?._head).toBe(headBeforeDispose)
    expect(controller.getRadius()).toBeCloseTo(radiusBeforeDispose)

    const afterDispose = controller.getStateSnapshot()
    element.dispatchEvent(touchEvent('touchstart', [{ clientX: 100, clientY: 100 }]))
    element.dispatchEvent(touchEvent('touchmove', [{ clientX: 300, clientY: 300 }]))
    expect(controller.getStateSnapshot().theta).toBeCloseTo(afterDispose.theta)
    expect(controller.getStateSnapshot().phi).toBeCloseTo(afterDispose.phi)

    tickDriver(100)
    await promise
    expect(controller.getRadius()).toBeCloseTo(radiusBeforeDispose)
  })

  it('instant mode positions the camera immediately and resolves without a timeline', async () => {
    const camera = new PerspectiveCamera(60, 1, 0.1, 100)
    const controller = new CameraController(camera, undefined, {
      instant: true,
    })
    const target = new Vector3(1, 2, 3)
    const position = new Vector3(1, 2, 13)

    const promise = controller.animateTo(target, position, 800)
    expect(promise).toBeInstanceOf(Promise)
    await promise

    expect(getRootTimeline()).toBeNull()
    expect(controller.getRadius()).toBeCloseTo(10)
    expect(controller.getTarget().equals(target)).toBe(true)
    expect(controller.getPosition().distanceTo(position)).toBeLessThan(1e-6)

    await controller.transitionToPanorama()
    expect(getRootTimeline()).toBeNull()
    expect(controller.getRadius()).toBeCloseTo(DEFAULT_PANORAMA.radius)
    expect(controller.getTarget().equals(DEFAULT_PANORAMA.target)).toBe(true)
  })

  it('setPinchZoom toggles pinch handling without affecting rotation', () => {
    const camera = new PerspectiveCamera(60, 1, 0.1, 100)
    const controller = new CameraController(camera)
    const element = document.createElement('div')
    controller.enable(element)
    controller.setPinchZoom(true)

    const before = controller.getStateSnapshot()
    element.dispatchEvent(
      touchEvent('touchstart', [
        { clientX: 90, clientY: 0 },
        { clientX: 110, clientY: 0 },
      ]),
    )
    element.dispatchEvent(
      touchEvent('touchmove', [
        { clientX: 80, clientY: 0 },
        { clientX: 120, clientY: 0 },
      ]),
    )
    expect(controller.getRadius()).toBeCloseTo(before.radius / 2)

    controller.setPinchZoom(false)
    const radius = controller.getRadius()
    element.dispatchEvent(
      touchEvent('touchstart', [
        { clientX: 90, clientY: 0 },
        { clientX: 110, clientY: 0 },
      ]),
    )
    element.dispatchEvent(
      touchEvent('touchmove', [
        { clientX: 80, clientY: 0 },
        { clientX: 120, clientY: 0 },
      ]),
    )
    expect(controller.getRadius()).toBe(radius)

    controller.dispose(element)
  })

  it('keeps castle defaults, export factories, and framing behavior', () => {
    const camera = new PerspectiveCamera(60, 1, 0.1, 100)

    expect(DEFAULT_PANORAMA.radius).toBe(20)
    expect(DEFAULT_PANORAMA.phi).toBeCloseTo(Math.PI / 3)
    expect(DEFAULT_PANORAMA.target.equals(new Vector3(0, 2, 0))).toBe(true)
    expect(DEFAULT_TOWER.radius).toBe(8)
    expect(DEFAULT_TOWER.phi).toBeCloseTo(Math.PI / 2.5)
    expect(DEFAULT_TOWER.target.equals(new Vector3(0, 3, 0))).toBe(true)

    const panorama = createPanoramaCamera(camera)
    expect(panorama.getRadius()).toBe(20)
    const tower = createTowerCamera(camera)
    expect(tower.getRadius()).toBe(8)

    const framed = frameCastle(new PerspectiveCamera(60, 1, 0.1, 100), {
      center: new Vector3(1, 2, 3),
      size: new Vector3(2, 4, 0),
    })
    expect(framed.getRadius()).toBeGreaterThanOrEqual(12)
    expect(framed.getTarget().equals(new Vector3(1, 2, 3))).toBe(true)

    const tiny = frameCastle(new PerspectiveCamera(60, 1, 0.1, 100), {
      center: new Vector3(0, 0, 0),
      size: new Vector3(0, 0, 0),
    })
    expect(tiny.getRadius()).toBe(12)
  })

  it('clamps phi and pinch radius to their supported ranges', () => {
    const camera = new PerspectiveCamera(60, 1, 0.1, 100)
    const controller = new CameraController(camera, undefined, {
      pinchZoom: true,
    })
    const element = document.createElement('div')
    controller.enable(element)

    const ctrl = controller as unknown as {
      rotate: (dx: number, dy: number) => void
    }
    ctrl.rotate(0, -10000)
    expect(controller.getStateSnapshot().phi).toBeCloseTo(Math.PI - 0.1)
    ctrl.rotate(0, 20000)
    expect(controller.getStateSnapshot().phi).toBeCloseTo(0.1)

    element.dispatchEvent(
      touchEvent('touchstart', [
        { clientX: 90, clientY: 0 },
        { clientX: 110, clientY: 0 },
      ]),
    )
    element.dispatchEvent(
      touchEvent('touchmove', [
        { clientX: 99.9, clientY: 0 },
        { clientX: 100.1, clientY: 0 },
      ]),
    )
    expect(controller.getRadius()).toBe(80)

    controller.dispose(element)
  })
})
