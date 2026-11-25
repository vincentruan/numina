/**
 * Challenge Router — data-driven dispatch to three rendering backends.
 *
 * Classification is declarative (CHALLENGE_CLASSIFICATION map), so a challenge
 * can be upgraded from native-2d to physics-3d without changing routing logic.
 */
import type { Component } from 'vue'
import type { ChallengeType } from '@/types/learning-challenge'
import { resolveChallengeComponent } from './index'

/** Rendering backend classification for each challenge type. */
export type ChallengeRenderingBackend = 'physics-3d' | 'enhanced-2d' | 'native-2d'

/**
 * Data-driven classification map.
 * To upgrade a challenge from native-2d to physics-3d, change its entry here.
 */
export const CHALLENGE_CLASSIFICATION: Record<ChallengeType, ChallengeRenderingBackend> = {
  balance: 'physics-3d',
  distribute: 'physics-3d',
  puzzle: 'physics-3d',
  classify: 'enhanced-2d',
  order: 'enhanced-2d',
  connect: 'enhanced-2d',
  estimate: 'native-2d',
  pattern: 'native-2d',
  'spot-the-mistake': 'native-2d',
  'draw-grid': 'native-2d',
}

/** Resolve the rendering backend for a challenge type. */
export function resolveChallengeBackend(type: ChallengeType): ChallengeRenderingBackend {
  return CHALLENGE_CLASSIFICATION[type] ?? 'native-2d'
}

/**
 * Lazy-load the 3D component for a physics challenge.
 * Uses dynamic import() so three.js + rapier are only loaded when needed.
 */
async function loadPhysics3DComponent(type: string): Promise<Component> {
  switch (type) {
    case 'balance': {
      const mod = await import('./BalanceChallenge3D.vue')
      return mod.default
    }
    case 'distribute': {
      const mod = await import('./DistributeChallenge3D.vue')
      return mod.default
    }
    case 'puzzle': {
      const mod = await import('./PuzzleChallenge3D.vue')
      return mod.default
    }
    default:
      throw new Error(`No 3D component registered for challenge type: ${type}`)
  }
}

/**
 * Load the challenge component for a given type.
 * - physics-3d: dynamically imports the 3D component (lazy loads three.js + rapier)
 * - enhanced-2d / native-2d: returns the existing 2D component synchronously
 *
 * Returns null if the type is not registered (same as resolveChallengeComponent).
 */
export async function loadChallengeComponent(type: string): Promise<Component | null> {
  const backend = resolveChallengeBackend(type as ChallengeType)

  if (backend === 'physics-3d') {
    try {
      return await loadPhysics3DComponent(type)
    } catch {
      // Dynamic import failed — fall back to 2D implementation
      console.warn(`[challengeRouter] 3D load failed for "${type}", falling back to 2D`)
      return resolveChallengeComponent(type)
    }
  }

  // enhanced-2d and native-2d use the existing synchronous registry
  return resolveChallengeComponent(type)
}

/** Check if a challenge type uses the physics-3d backend. */
export function isPhysics3D(type: ChallengeType): boolean {
  return CHALLENGE_CLASSIFICATION[type] === 'physics-3d'
}
