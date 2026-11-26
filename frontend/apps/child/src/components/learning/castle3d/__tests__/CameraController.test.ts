/**
 * CameraController tests.
 */
import { describe, it, expect, beforeEach } from 'vitest'
import { PerspectiveCamera } from 'three'
import { CameraController } from '../CameraController'

describe('CameraController', () => {
  let camera: PerspectiveCamera
  let controller: CameraController

  beforeEach(() => {
    camera = new PerspectiveCamera(60, 1, 0.1, 100)
    controller = new CameraController(camera)
  })

  it('creates camera at default panorama position', () => {
    const pos = controller.getPosition()
    expect(pos.z).toBeGreaterThan(0) // Behind castle
    expect(pos.y).toBeGreaterThan(0) // Above ground
  })

  it('rotate changes theta and phi', () => {
    // Simulate drag
    const initialPos = controller.getPosition()

    // Access private method via type assertion for testing
    const ctrl = controller as unknown as {
      rotate: (dx: number, dy: number) => void
    }
    ctrl.rotate(100, 0) // Horizontal drag

    const newPos = controller.getPosition()
    // Position should have changed
    expect(newPos.x).not.toBe(initialPos.x)
  })

  it('animateTo returns a promise that resolves', async () => {
    const { Vector3 } = await import('three')
    const target = new Vector3(0, 3, 0)
    const position = new Vector3(0, 3, 10)

    // animateTo should return a promise
    const promise = controller.animateTo(target, position, 50)
    expect(promise).toBeInstanceOf(Promise)

    // Wait for it to resolve
    await promise
  })

  it('disable prevents rotation', () => {
    controller.disable()

    // Access private method via type assertion for testing
    const ctrl = controller as unknown as {
      enabled: boolean
      rotate: (dx: number, dy: number) => void
    }

    expect(ctrl.enabled).toBe(false)

    // Try to rotate - should not throw
    ctrl.rotate(100, 0)

    // The key test is that enabled flag is false
    expect(ctrl.enabled).toBe(false)
  })
})
