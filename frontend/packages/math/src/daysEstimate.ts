import type { LedgerEntry, PrioritySimulationEntry } from './types'

const SEVEN_DAYS_MS = 7 * 24 * 60 * 60 * 1000
const MIN_DISTINCT_EARNING_DAYS = 3

export function daysEstimate(
  balance: number,
  sim: PrioritySimulationEntry,
  ledger: LedgerEntry[],
  now: number = Date.now(),
): number | null {
  if (sim.star_coin_cost == null) return null

  const remaining = sim.star_coin_cost - balance
  if (remaining <= 0) return null

  const cutoff = now - SEVEN_DAYS_MS
  const earnDays = new Set<string>()
  let earnSum = 0
  for (const tx of ledger) {
    if (tx.amount <= 0) continue
    const ts = new Date(tx.created_at).getTime()
    if (ts < cutoff) continue
    earnDays.add(new Date(tx.created_at).toDateString())
    earnSum += tx.amount
  }

  if (earnDays.size < MIN_DISTINCT_EARNING_DAYS) return null

  const dailyAvg = earnSum / earnDays.size
  if (dailyAvg <= 0) return null

  return Math.ceil(remaining / dailyAvg)
}
