// Public API for @numina/math
//
// Pure functions backing cross-wish reachability + opportunity-cost peek.
// See docs/plans/2026-05-24-002-feat-child-cross-wish-bundle-plan.md U1
// and docs/brainstorms/2026-05-24-child-cross-wish-bundle-requirements.md
// for the trust-contract math invariants both child and parent apps depend on.

export { daysEstimate } from './daysEstimate'
export { reachabilityTint, YELLOW_BOUNDARY_DAYS } from './reachabilityTint'
export { previewSpend } from './previewSpend'

export type {
  PrioritySimulationEntry,
  LedgerEntry,
  ReachabilityTint,
  SpendDelta,
  SpendPreview,
} from './types'
