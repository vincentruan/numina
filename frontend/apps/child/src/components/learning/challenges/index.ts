/**
 * Challenge component registry — maps challenge type to its Vue component.
 *
 * New interaction types register here. The dispatcher (ManipulateObserveReflect)
 * resolves the component from the config's `type` field.
 */
import type { Component } from 'vue'
import DistributeChallenge from './DistributeChallenge.vue'
import ClassifyChallenge from './ClassifyChallenge.vue'
import OrderChallenge from './OrderChallenge.vue'
import BalanceChallenge from './BalanceChallenge.vue'
import PatternChallenge from './PatternChallenge.vue'
import SpotTheMistakeChallenge from './SpotTheMistakeChallenge.vue'
import PuzzleChallenge from './PuzzleChallenge.vue'
import ConnectChallenge from './ConnectChallenge.vue'
import EstimateChallenge from './EstimateChallenge.vue'
import DrawGridChallenge from './DrawGridChallenge.vue'

/** Type → component mapping. Add entries as new interaction types are created. */
const CHALLENGE_COMPONENTS: Record<string, Component> = {
  distribute: DistributeChallenge,
  classify: ClassifyChallenge,
  order: OrderChallenge,
  balance: BalanceChallenge,
  pattern: PatternChallenge,
  'spot-the-mistake': SpotTheMistakeChallenge,
  puzzle: PuzzleChallenge,
  connect: ConnectChallenge,
  estimate: EstimateChallenge,
  'draw-grid': DrawGridChallenge,
}

/**
 * Resolve the challenge component for a given type tag.
 * Returns null when the type is not registered — the caller should skip the
 * manipulation phase and fall through to the answering flow.
 */
export function resolveChallengeComponent(type: string): Component | null {
  return CHALLENGE_COMPONENTS[type] ?? null
}
