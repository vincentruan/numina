import type { Wish } from '@/types'

/**
 * Compute wish savings progress percentage (saved_amount / expected_price * 100).
 * Returns 0 when no target or target <= 0; clamps to [0, 100].
 */
export function wishProgress(wish: Pick<Wish, 'expected_price' | 'saved_amount'>): number {
  const expected = Number(wish.expected_price ?? 0) || 0
  if (expected <= 0) return 0
  const saved = Number(wish.saved_amount ?? 0) || 0
  return Math.min(100, Math.round((saved / expected) * 100))
}
