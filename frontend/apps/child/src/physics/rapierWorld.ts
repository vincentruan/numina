/**
 * rapierWorld — shared physics world singleton with scoped-world escape hatch.
 *
 * Contract:
 * - `getWorld()` returns the default singleton — ocean + challenges share it.
 * - `createScopedWorld(id)` returns an isolated world for a challenge scene
 *   that needs different gravity or collision layers.
 * - Fixed timestep accumulator: 1/60s steps, max 5 catch-up steps per frame
 *   to prevent explosion on tab-return.
 * - `stepPhysics(dtFrame)` advances the world with interpolation bookkeeping.
 * - `destroyWorld()` frees WASM memory — call on full teardown.
 */
import RAPIER from '@dimforge/rapier3d-compat'
import type { World, RigidBody } from '@dimforge/rapier3d-compat'

const FIXED_DT = 1 / 60
const MAX_STEPS_PER_FRAME = 5

interface PhysicsState {
  world: World
  accumulator: number
  bodies: Set<RigidBody>
}

let defaultState: PhysicsState | null = null
let rapierInitialized = false
const scopedWorlds = new Map<string, PhysicsState>()

/** Initialize the RAPIER WASM module (idempotent). */
export async function initRapier(): Promise<void> {
  if (rapierInitialized) return
  await RAPIER.init()
  rapierInitialized = true
}

/** Create a fresh physics world with standard gravity. */
function createWorld(): World {
  const gravity = { x: 0.0, y: -9.81, z: 0.0 }
  return new RAPIER.World(gravity)
}

/** Get the default shared physics world singleton. */
export function getWorld(): World {
  if (!defaultState) {
    if (!rapierInitialized) {
      throw new Error('[rapierWorld] Call initRapier() before getWorld()')
    }
    defaultState = {
      world: createWorld(),
      accumulator: 0,
      bodies: new Set(),
    }
  }
  return defaultState.world
}

/**
 * Create an isolated physics world for a challenge scene.
 * Use when a challenge needs different gravity or collision layers.
 */
export function createScopedWorld(id: string): World {
  if (!rapierInitialized) {
    throw new Error('[rapierWorld] Call initRapier() before createScopedWorld()')
  }
  if (scopedWorlds.has(id)) {
    return scopedWorlds.get(id)!.world
  }
  const state: PhysicsState = {
    world: createWorld(),
    accumulator: 0,
    bodies: new Set(),
  }
  scopedWorlds.set(id, state)
  return state.world
}

function getStateForWorld(world: World): PhysicsState | null {
  if (defaultState?.world === world) return defaultState
  for (const state of scopedWorlds.values()) {
    if (state.world === world) return state
  }
  return null
}

/** Track a body for cleanup on world destruction. */
export function trackBody(world: World, body: RigidBody): void {
  const state = getStateForWorld(world)
  if (state) state.bodies.add(body)
  else console.warn('[rapierWorld] trackBody called with unrecognized world')
}

/** Remove a body from tracking and from the world. Call on component unmount. */
export function removeBody(world: World, body: RigidBody): void {
  const state = getStateForWorld(world)
  if (state) {
    state.bodies.delete(body)
    try {
      world.removeRigidBody(body)
    } catch {
      // Body may already be removed if world.free() was called
    }
  }
}

/**
 * Step physics with fixed timestep accumulator.
 * `dtFrame` is the real elapsed time since last frame (seconds).
 * Clamps to MAX_STEPS_PER_FRAME to prevent catch-up explosion.
 */
export function stepPhysics(dtFrame: number, world?: World): void {
  const target = world ?? defaultState?.world
  if (!target) return

  const state = getStateForWorld(target)
  if (!state) return

  state.accumulator += dtFrame
  let steps = 0
  while (state.accumulator >= FIXED_DT && steps < MAX_STEPS_PER_FRAME) {
    target.step()
    state.accumulator -= FIXED_DT
    steps++
  }
  // Drain excess to prevent unbounded growth on tab-return
  if (state.accumulator > FIXED_DT * MAX_STEPS_PER_FRAME) {
    state.accumulator = 0
  }
}

/**
 * Synchronize visual meshes from physics bodies using interpolation.
 * `alpha` is the interpolation factor [0, 1] between prev and current state.
 * Callers provide a callback that applies the interpolated transform.
 */
export function syncMeshesFromBodies(
  callback: (body: RigidBody, alpha: number) => void,
  world?: World,
): void {
  const target = world ?? defaultState?.world
  if (!target) return
  const state = getStateForWorld(target)
  if (!state) return

  const alpha = state.accumulator / FIXED_DT
  for (const body of state.bodies) {
    callback(body, alpha)
  }
}

/**
 * Destroy the default world and free WASM memory.
 * The RAPIER WASM module stays initialized; call getWorld() to recreate.
 */
export function destroyWorld(): void {
  if (defaultState) {
    // Remove all tracked bodies first
    for (const body of defaultState.bodies) {
      try { defaultState.world.removeRigidBody(body) } catch { /* ignore */ }
    }
    defaultState.bodies.clear()
    defaultState.world.free()
    defaultState = null
  }
}

/** Destroy a scoped world by id. */
export function destroyScopedWorld(id: string): void {
  const state = scopedWorlds.get(id)
  if (state) {
    state.bodies.clear()
    state.world.free()
    scopedWorlds.delete(id)
  }
}

/** Check if RAPIER WASM has been initialized. */
export function isInitialized(): boolean {
  return rapierInitialized
}

/** Reset all state — for tests only. */
export function _resetForTesting(): void {
  if (defaultState) {
    try { defaultState.world.free() } catch { /* already freed */ }
    defaultState = null
  }
  for (const state of scopedWorlds.values()) {
    try { state.world.free() } catch { /* already freed */ }
  }
  scopedWorlds.clear()
  rapierInitialized = false
}
