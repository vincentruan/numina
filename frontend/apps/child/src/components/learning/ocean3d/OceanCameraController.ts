/**
 * T10 level camera — L0 ocean overview and L1 island/domain close-ups.
 *
 * All transitions go through the shared `CameraController.animateTo`, so
 * their anime.js child timelines stay on the single render-loop clock.
 */
import { PerspectiveCamera, Vector3 } from 'three'
import { CameraController } from '../scene3d/OrbitCameraController'

/** Structural shape needed to frame a level node. */
export interface OceanCameraNode {
  x: number
  z: number
  worldRadius: number
}

export interface OceanCameraController {
  diveTo(node: OceanCameraNode): Promise<void>
  ascend(): Promise<void>
  reset(): Promise<void>
  dispose(): void
}

export interface OceanCameraState {
  radius: number
  theta: number
  phi: number
  target: Vector3
}

/** L0 camera: whole-ocean overview above the water. */
const L0_RADIUS = 22
const L0_THETA = 0
const L0_PHI = Math.PI / 3
/** L1 camera: lower, closer to the horizon for a sense of scale. */
const L1_PHI = Math.PI * 0.41
/** Smallest framing radius for a tiny island/region tile. */
const MIN_L1_RADIUS = 6
/** Camera transition duration (ms) — shared with castle level changes. */
const TRANSITION_MS = 800

/** L0 view position derived from the spherical state. */
function l0Position(): Vector3 {
  return new Vector3(
    0,
    L0_RADIUS * Math.cos(L0_PHI),
    L0_RADIUS * Math.sin(L0_PHI),
  )
}

/** L1 view position derived from the node and spherical framing constants. */
function l1Position(node: OceanCameraNode, radius: number): Vector3 {
  return new Vector3(
    node.x,
    radius * Math.cos(L1_PHI),
    node.z + radius * Math.sin(L1_PHI),
  )
}

/**
 * Create a level camera controller around `camera`.
 *
 * `instant: true` writes endpoints synchronously (reduced-motion path) and
 * creates no anime timeline. Otherwise every level change is one child
 * timeline driven by the scene's render loop.
 */
export function createOceanCameraController(
  camera: PerspectiveCamera,
  options: { instant?: boolean } = {},
): OceanCameraController & { getStateSnapshot(): OceanCameraState } {
  const controller = new CameraController(
    camera,
    {
      radius: L0_RADIUS,
      theta: L0_THETA,
      phi: L0_PHI,
      target: new Vector3(0, 0, 0),
    },
    { instant: options.instant ?? false },
  )

  return {
    diveTo(node: OceanCameraNode): Promise<void> {
      const radius = Math.max(node.worldRadius * 3, MIN_L1_RADIUS)
      return controller.animateTo(
        new Vector3(node.x, 0, node.z),
        l1Position(node, radius),
        TRANSITION_MS,
      )
    },
    ascend(): Promise<void> {
      return controller.animateTo(
        new Vector3(0, 0, 0),
        l0Position(),
        TRANSITION_MS,
      )
    },
    reset(): Promise<void> {
      return controller.animateTo(
        new Vector3(0, 0, 0),
        l0Position(),
        TRANSITION_MS,
      )
    },
    dispose(): void {
      controller.dispose()
    },
    getStateSnapshot(): OceanCameraState {
      return controller.getStateSnapshot()
    },
  }
}
