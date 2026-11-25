/**
 * islandBody — factory helpers for rapier rigid bodies.
 *
 * Provides ergonomic wrappers around RAPIER body/rigidBody/collider creation
 * for the two main object categories in the 3D world:
 * - Kinematic islands: moved by anime.js, not affected by gravity.
 * - Dynamic objects: affected by gravity and collisions, with CCD enabled.
 */
import RAPIER from '@dimforge/rapier3d-compat'
import type { World, RigidBody, Collider } from '@dimforge/rapier3d-compat'
import { trackBody } from './rapierWorld'

/** Parameters for creating a kinematic island body. */
export interface KinematicIslandParams {
  position: { x: number; y: number; z: number }
  /** Half-extents for the box collider. */
  halfExtents: { x: number; y: number; z: number }
}

/** Parameters for creating a dynamic object body. */
export interface DynamicObjectParams {
  position: { x: number; y: number; z: number }
  /** Radius for the ball collider. */
  radius: number
  /** Mass of the object (kg). Default 1. */
  mass?: number
  /** Enable continuous collision detection. Default true. */
  ccd?: boolean
  /** Linear damping (air friction). Default 0.5. */
  linearDamping?: number
  /** Restitution (bounciness) [0, 1]. Default 0.3. */
  restitution?: number
}

/** Result of creating a body + collider pair. */
export interface BodyResult {
  body: RigidBody
  collider: Collider
}

/**
 * Create a kinematic body for an island or platform.
 * Kinematic bodies are moved programmatically (by anime timelines),
 * not affected by gravity or forces.
 */
export function createKinematicIsland(
  world: World,
  params: KinematicIslandParams,
): BodyResult {
  const bodyDesc = new RAPIER.RigidBodyDesc(RAPIER.RigidBodyType.KinematicPositionBased)
    .setTranslation(params.position.x, params.position.y, params.position.z)
  const body = world.createRigidBody(bodyDesc)

  const colliderDesc = RAPIER.ColliderDesc.cuboid(
    params.halfExtents.x,
    params.halfExtents.y,
    params.halfExtents.z,
  )
  const collider = world.createCollider(colliderDesc, body)

  trackBody(world, body)
  return { body, collider }
}

/**
 * Create a dynamic body for a physics-interactable object.
 * CCD is enabled by default to prevent tunneling at high velocities.
 */
export function createDynamicObject(
  world: World,
  params: DynamicObjectParams,
): BodyResult {
  const bodyDesc = new RAPIER.RigidBodyDesc(RAPIER.RigidBodyType.Dynamic)
    .setTranslation(params.position.x, params.position.y, params.position.z)

  const body = world.createRigidBody(bodyDesc)

  if (params.ccd !== false) body.enableCcd(true)
  body.setLinearDamping(params.linearDamping ?? 0.5)

  // Compute density from desired mass: density = mass / volume
  // For a ball collider: volume = (4/3) * π * r³
  const mass = params.mass ?? 1
  const radius = params.radius
  const volume = (4 / 3) * Math.PI * radius ** 3
  const density = mass / volume

  const colliderDesc = RAPIER.ColliderDesc.ball(radius)
    .setRestitution(params.restitution ?? 0.3)
    .setDensity(density)

  const collider = world.createCollider(colliderDesc, body)

  trackBody(world, body)
  return { body, collider }
}

/**
 * Create a static floor/ground plane body.
 * Static bodies don't move and don't respond to forces.
 */
export function createStaticGround(
  world: World,
  y: number = 0,
  halfWidth: number = 50,
  halfDepth: number = 50,
): BodyResult {
  const bodyDesc = new RAPIER.RigidBodyDesc(RAPIER.RigidBodyType.Fixed)
    .setTranslation(0, y, 0)
  const body = world.createRigidBody(bodyDesc)

  const colliderDesc = RAPIER.ColliderDesc.cuboid(halfWidth, 0.1, halfDepth)
    .setFriction(0.8)
    .setRestitution(0.1)
  const collider = world.createCollider(colliderDesc, body)

  trackBody(world, body)
  return { body, collider }
}
