import type { PrioritySimulationEntry, ReachabilityTint } from './types'

export const YELLOW_BOUNDARY_DAYS = 14

export function reachabilityTint(
  sim: PrioritySimulationEntry,
  daysEst: number | null,
): ReachabilityTint {
  if (sim.covered) return 'green'
  if (daysEst === null) return 'gray'
  if (daysEst <= YELLOW_BOUNDARY_DAYS) return 'yellow'
  return 'red'
}
