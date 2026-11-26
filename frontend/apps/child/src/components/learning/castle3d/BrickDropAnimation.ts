/**
 * BrickDropAnimation — rapier physics brick drop on first mastery.
 *
 * New bricks fall from above, land on the floor plate, and settle with
 * an elastic bounce. Respects prefers-reduced-motion by skipping the visual
 * drop while keeping the brick in its final position.
 */
import { Mesh, Vector3 } from 'three'
import type { World } from '@dimforge/rapier3d-compat'
import { removeBody } from '@/physics/rapierWorld'
import { createDynamicObject, createStaticGround } from '@/physics/islandBody'
import { createChildTimeline } from '@/motion/animeDriver'
import type { Timeline } from 'animejs'

/** Drop height above target. */
const DROP_HEIGHT = 3

/** Settle threshold in 3D units. */
const SETTLE_THRESHOLD = 0.05

/** Max frames to wait for settle before forcing final position. */
const MAX_SETTLE_FRAMES = 120

/**
 * Animate a brick dropping onto its floor target position.
 *
 * Creates a temporary dynamic rapier body, lets gravity pull it down, then
 * snaps to the target position with an elastic settle. The body is removed
 * from the world when done — no residual bodies remain.
 *
 * @param brickMesh Visual brick mesh (already added to the scene).
 * @param targetPosition Final resting position.
 * @param world Physics world (shared singleton or scoped).
 * @param options.reducedMotion Skip the drop animation, place at target instantly.
 * @param options.signal Abort on component unmount — stops polling and frees the body.
 * @returns Resolves when the brick has settled (or the drop was aborted).
 */
export function animateBrickDrop(
  brickMesh: Mesh,
  targetPosition: Vector3,
  world: World,
  options: { reducedMotion?: boolean; signal?: AbortSignal } = {},
): Promise<void> {
  // Reduced motion: instant placement, no physics simulation
  if (options.reducedMotion) {
    brickMesh.position.copy(targetPosition)
    return Promise.resolve()
  }

  // Start above the target
  const startPosition = targetPosition.clone()
  startPosition.y += DROP_HEIGHT
  brickMesh.position.copy(startPosition)

  // Create dynamic body at start position
  const { body } = createDynamicObject(world, {
    position: { x: startPosition.x, y: startPosition.y, z: startPosition.z },
    radius: 0.15,
    mass: 1,
    restitution: 0.2,
    linearDamping: 0.8,
  })

  // Temporary landing plane at the target height — without it the brick
  // free-falls straight through the floor. Removed with the body on settle.
  const landing = createStaticGround(world, targetPosition.y - 0.1, 40, 40)

  return new Promise<void>((resolve) => {
    let frames = 0
    let settled = false
    let rafId = 0
    let timeline: Timeline | null = null

    /** Free both physics bodies. Safe to call after world teardown. */
    const releaseBodies = (): void => {
      try {
        removeBody(world, body)
      } catch {
        // World may already be freed on teardown
      }
      try {
        removeBody(world, landing.body)
      } catch {
        // World may already be freed on teardown
      }
    }

    const abort = (): void => {
      if (settled) return
      settled = true
      cancelAnimationFrame(rafId)
      releaseBodies()
      if (timeline) {
        timeline.revert()
        timeline = null
      }
      resolve()
    }

    const cleanup = (): void => {
      if (settled) return
      settled = true
      releaseBodies()
      if (timeline) {
        timeline.revert()
        timeline = null
      }
      // Final resting position
      brickMesh.position.copy(targetPosition)
      resolve()
    }

    // Stop the drop if the host component unmounts mid-flight
    if (options.signal) {
      if (options.signal.aborted) {
        abort()
        return
      }
      options.signal.addEventListener('abort', abort, { once: true })
    }

    // Poll each frame for settle (driven by the host render loop calling stepPhysics)
    const checkSettle = (): void => {
      if (settled) return
      frames++

      let pos: { x: number; y: number; z: number }
      let isSlow: boolean
      try {
        pos = body.translation()
        isSlow = body.isSleeping() || Math.abs(body.linvel().y) < 0.05
      } catch {
        // Body or world was freed underneath us — nothing left to animate
        abort()
        return
      }

      brickMesh.position.set(pos.x, pos.y, pos.z)

      const distanceToTarget = Math.abs(pos.y - targetPosition.y)

      if ((distanceToTarget < SETTLE_THRESHOLD && isSlow) || frames > MAX_SETTLE_FRAMES) {
        // Elastic settle to exact target — visual only, body already removed
        timeline = createChildTimeline()
        timeline.add(
          brickMesh.position,
          {
            x: targetPosition.x,
            y: targetPosition.y,
            z: targetPosition.z,
            duration: 220,
            ease: 'outElastic(1, 0.6)',
          },
          0,
        )
        // Remove physics body immediately; the visual keeps animating
        try {
          removeBody(world, body)
        } catch {
          // World may already be freed on teardown
        }
        setTimeout(cleanup, 280)
        return
      }

      rafId = requestAnimationFrame(checkSettle)
    }

    rafId = requestAnimationFrame(checkSettle)
  })
}

/**
 * Apply a landing bounce to an already-placed brick (no physics).
 * Used when a brick was placed statically but should still feel alive.
 */
export function animateBrickBounce(mesh: Mesh, reducedMotion = false): Promise<void> {
  if (reducedMotion) return Promise.resolve()

  const baseScale = mesh.scale.clone()

  return new Promise<void>((resolve) => {
    const timeline = createChildTimeline()
    timeline.add(
      mesh.scale,
      {
        y: baseScale.y * 1.25,
        duration: 150,
        ease: 'outQuad',
      },
      0,
    )
    timeline.add(
      mesh.scale,
      {
        y: baseScale.y,
        duration: 200,
        ease: 'outBounce',
      },
      150,
    )
    setTimeout(() => {
      timeline.revert()
      mesh.scale.copy(baseScale)
      resolve()
    }, 380)
  })
}
