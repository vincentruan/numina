/**
 * CameraController — orbit camera for 3D castle with transitions.
 *
 * Provides orbit controls (touch/mouse rotate + zoom) and smooth camera
 * transitions between panorama and tower views using anime.js timelines.
 *
 * Single-clock rule: transitions use createChildTimeline() from animeDriver.
 */
import {
  PerspectiveCamera,
  Vector3,
} from 'three'
import { createChildTimeline } from '@/motion/animeDriver'
import type { Timeline } from 'animejs'

/** Orbit camera state. */
interface OrbitState {
  /** Spherical coordinates: radius from target. */
  radius: number
  /** Horizontal angle (radians). */
  theta: number
  /** Vertical angle (radians), clamped to avoid flipping. */
  phi: number
  /** Target point the camera orbits around. */
  target: Vector3
}

/** Default panorama camera position. */
const DEFAULT_PANORAMA: OrbitState = {
  radius: 20,
  theta: 0,
  phi: Math.PI / 3, // 60 degrees from top
  target: new Vector3(0, 2, 0),
}

/** Default tower close-up position. */
const DEFAULT_TOWER: OrbitState = {
  radius: 8,
  theta: 0,
  phi: Math.PI / 2.5,
  target: new Vector3(0, 3, 0),
}

/** Clamp phi to prevent camera flipping. */
const MIN_PHI = 0.1
const MAX_PHI = Math.PI - 0.1

/** Breathing room added around the castle bounds when framing. */
const FRAME_MARGIN = 1.35

export class CameraController {
  private camera: PerspectiveCamera
  private state: OrbitState
  private isDragging = false
  private previousMouse = { x: 0, y: 0 }
  private transitionTimeline: Timeline | null = null
  private enabled = false

  constructor(camera: PerspectiveCamera, initialState: OrbitState = DEFAULT_PANORAMA) {
    this.camera = camera
    this.state = { ...initialState, target: initialState.target.clone() }
    this.updateCameraFromState()
  }

  /** Enable touch/mouse orbit controls on a DOM element. */
  enable(domElement: HTMLElement): void {
    if (this.enabled) return
    this.enabled = true

    domElement.addEventListener('mousedown', this.onPointerDown)
    domElement.addEventListener('mousemove', this.onPointerMove)
    domElement.addEventListener('mouseup', this.onPointerUp)
    domElement.addEventListener('mouseleave', this.onPointerUp)
    domElement.addEventListener('touchstart', this.onTouchStart, { passive: false })
    domElement.addEventListener('touchmove', this.onTouchMove, { passive: false })
    domElement.addEventListener('touchend', this.onPointerUp)
  }

  /** Disable orbit controls. */
  disable(): void {
    this.enabled = false
    // Event listeners are cleaned up on dispose
  }

  /** Release all resources. */
  dispose(domElement?: HTMLElement): void {
    this.disable()
    if (domElement) {
      domElement.removeEventListener('mousedown', this.onPointerDown)
      domElement.removeEventListener('mousemove', this.onPointerMove)
      domElement.removeEventListener('mouseup', this.onPointerUp)
      domElement.removeEventListener('mouseleave', this.onPointerUp)
      domElement.removeEventListener('touchstart', this.onTouchStart)
      domElement.removeEventListener('touchmove', this.onTouchMove)
      domElement.removeEventListener('touchend', this.onPointerUp)
    }
    if (this.transitionTimeline) {
      this.transitionTimeline.revert()
      this.transitionTimeline = null
    }
  }

  /** Smoothly animate camera to a new position. */
  animateTo(
    target: Vector3,
    position: Vector3,
    duration: number = 800,
  ): Promise<void> {
    // Cancel any ongoing transition
    if (this.transitionTimeline) {
      this.transitionTimeline.revert()
    }

    // Calculate spherical coords from target + position
    const offset = position.clone().sub(target)
    const radius = offset.length()
    const theta = Math.atan2(offset.x, offset.z)
    const phi = Math.acos(Math.max(-1, Math.min(1, offset.y / radius)))

    return new Promise<void>((resolve) => {
      const timeline = createChildTimeline()
      this.transitionTimeline = timeline

      // Animate state properties
      const animState = {
        radius: this.state.radius,
        theta: this.state.theta,
        phi: this.state.phi,
        targetX: this.state.target.x,
        targetY: this.state.target.y,
        targetZ: this.state.target.z,
      }

      timeline.add(
        animState,
        {
          radius,
          theta,
          phi,
          targetX: target.x,
          targetY: target.y,
          targetZ: target.z,
          duration,
          ease: 'inOutCubic',
          onUpdate: () => {
            this.state.radius = animState.radius
            this.state.theta = animState.theta
            this.state.phi = animState.phi
            this.state.target.set(animState.targetX, animState.targetY, animState.targetZ)
            this.updateCameraFromState()
          },
        },
        0,
      )

      // Resolve when animation completes
      timeline.add({}, { duration: 0 }, duration)
      // Note: anime.js v4 doesn't have onComplete on timeline directly
      // We use a timeout as fallback
      setTimeout(() => {
        this.transitionTimeline = null
        resolve()
      }, duration + 50)
    })
  }

  /** Transition to panorama view. */
  async transitionToPanorama(): Promise<void> {
    const pos = this.getPositionFromState(DEFAULT_PANORAMA)
    await this.animateTo(DEFAULT_PANORAMA.target, pos, 800)
  }

  /** Transition to tower view (close-up framing the whole tower height). */
  async transitionToTower(towerCenter: Vector3, towerHeight: number): Promise<void> {
    // Frame the tower the same way the panorama is framed — a tall tower
    // needs to back off further than a short one.
    const halfHeight = (Math.max(towerHeight, 2) / 2) * FRAME_MARGIN
    const vFov = (this.camera.fov * Math.PI) / 180
    const radius = Math.max(halfHeight / Math.tan(vFov / 2), 6)

    const target = new Vector3(towerCenter.x, towerHeight / 2, towerCenter.z)
    const offset = new Vector3(towerCenter.x, towerHeight / 2, towerCenter.z + radius)
    await this.animateTo(target, offset, 800)
  }

  /** Get current camera position. */
  getPosition(): Vector3 {
    return this.camera.position.clone()
  }

  /** Get current target. */
  getTarget(): Vector3 {
    return this.state.target.clone()
  }

  // --- Private methods ---

  private updateCameraFromState(): void {
    const { radius, theta, phi, target } = this.state
    const x = radius * Math.sin(phi) * Math.sin(theta)
    const y = radius * Math.cos(phi)
    const z = radius * Math.sin(phi) * Math.cos(theta)
    this.camera.position.set(target.x + x, target.y + y, target.z + z)
    this.camera.lookAt(target)
  }

  private getPositionFromState(state: OrbitState): Vector3 {
    const { radius, theta, phi, target } = state
    const x = radius * Math.sin(phi) * Math.sin(theta)
    const y = radius * Math.cos(phi)
    const z = radius * Math.sin(phi) * Math.cos(theta)
    return new Vector3(target.x + x, target.y + y, target.z + z)
  }

  private onPointerDown = (e: MouseEvent): void => {
    this.isDragging = true
    this.previousMouse = { x: e.clientX, y: e.clientY }
  }

  private onPointerMove = (e: MouseEvent): void => {
    if (!this.isDragging) return
    const dx = e.clientX - this.previousMouse.x
    const dy = e.clientY - this.previousMouse.y
    this.rotate(dx, dy)
    this.previousMouse = { x: e.clientX, y: e.clientY }
  }

  private onPointerUp = (): void => {
    this.isDragging = false
  }

  private onTouchStart = (e: TouchEvent): void => {
    if (e.touches.length === 1) {
      e.preventDefault()
      this.isDragging = true
      this.previousMouse = { x: e.touches[0].clientX, y: e.touches[0].clientY }
    }
  }

  private onTouchMove = (e: TouchEvent): void => {
    if (!this.isDragging || e.touches.length !== 1) return
    e.preventDefault()
    const dx = e.touches[0].clientX - this.previousMouse.x
    const dy = e.touches[0].clientY - this.previousMouse.y
    this.rotate(dx, dy)
    this.previousMouse = { x: e.touches[0].clientX, y: e.touches[0].clientY }
  }

  private rotate(dx: number, dy: number): void {
    const sensitivity = 0.005
    this.state.theta -= dx * sensitivity
    this.state.phi = Math.max(MIN_PHI, Math.min(MAX_PHI, this.state.phi - dy * sensitivity))
    this.updateCameraFromState()
  }
}

/** Create a CameraController with default panorama settings. */
export function createPanoramaCamera(camera: PerspectiveCamera): CameraController {
  return new CameraController(camera, DEFAULT_PANORAMA)
}

/** Create a CameraController with default tower close-up settings. */
export function createTowerCamera(camera: PerspectiveCamera): CameraController {
  return new CameraController(camera, DEFAULT_TOWER)
}

/**
 * Frame an orbit camera around a castle of known size.
 *
 * Tower height scales with floor count (a mature subject can be ~20 units tall,
 * an untouched one ~2), so a fixed radius either clips tall towers or leaves
 * short castles as a speck. Derive the radius from the actual bounds and the
 * camera's vertical FOV.
 *
 * @param camera Perspective camera (its `fov` and `aspect` set the fit).
 * @param bounds Axis-aligned bounds of the whole castle.
 */
export function frameCastle(
  camera: PerspectiveCamera,
  bounds: { center: Vector3; size: Vector3 },
): CameraController {
  // Fit both the height and the horizontal extent; whichever needs more room wins.
  const halfHeight = (bounds.size.y / 2) * FRAME_MARGIN
  const halfWidth = (bounds.size.x / 2) * FRAME_MARGIN

  const vFov = (camera.fov * Math.PI) / 180
  const radiusForHeight = halfHeight / Math.tan(vFov / 2)

  const hFov = 2 * Math.atan(Math.tan(vFov / 2) * camera.aspect)
  const radiusForWidth = halfWidth / Math.tan(hFov / 2)

  // Keep the castle fully in frame but never closer than a readable distance.
  const radius = Math.max(radiusForHeight, radiusForWidth, 12)

  return new CameraController(camera, {
    radius,
    theta: 0,
    phi: Math.PI / 3,
    target: new Vector3(bounds.center.x, bounds.center.y, bounds.center.z),
  })
}
