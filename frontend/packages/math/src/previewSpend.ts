import { daysEstimate } from './daysEstimate'
import type {
  LedgerEntry,
  PrioritySimulationEntry,
  SpendDelta,
  SpendPreview,
} from './types'

export function previewSpend(
  spendWishId: string,
  balance: number,
  simulation: PrioritySimulationEntry[],
  ledger: LedgerEntry[],
  now: number = Date.now(),
): SpendPreview {
  const spendWish = simulation.find(s => s.wish_id === spendWishId)
  const spendCost = spendWish?.star_coin_cost ?? 0
  const balanceAfter = Math.max(0, balance - spendCost)

  const deltas: SpendDelta[] = []

  for (const sim of simulation) {
    if (sim.wish_id === spendWishId) continue
    if (sim.star_coin_cost == null || sim.star_coin_cost <= 0) continue

    const beforeProgress = Math.max(0, Math.min(1, balance / sim.star_coin_cost))
    const afterProgress = Math.max(0, Math.min(1, balanceAfter / sim.star_coin_cost))

    const stillCoveredAfter = balanceAfter >= sim.star_coin_cost
    let daysAdded = 0
    if (!stillCoveredAfter) {
      const daysBefore = daysEstimate(balance, sim, ledger, now)
      const daysAfter = daysEstimate(balanceAfter, sim, ledger, now)
      if (daysBefore !== null && daysAfter !== null) {
        daysAdded = daysAfter - daysBefore
      }
    }

    deltas.push({
      wish_id: sim.wish_id,
      before_progress: beforeProgress,
      after_progress: afterProgress,
      days_added: daysAdded,
    })
  }

  return { deltas }
}
