import http from './index'

export interface CoinTransaction {
  id: string
  amount: number
  transaction_type: string
  narrative: string | null
  narrative_emoji: string | null
  created_at: string
  relative_time: string
}

export async function getCoinBalance(): Promise<number> {
  const res = await http.get('/child/coins/balance')
  return res.data.balance
}

export async function getCoinLedger(): Promise<CoinTransaction[]> {
  const res = await http.get('/child/coins/ledger')
  return res.data
}

// TODO: wire up to a parent UI for manual coin grants (no consumer yet)
export async function grantCoins(childUserId: string, amount: number, reason: string): Promise<void> {
  await http.post('/family/coins/grant', { child_user_id: childUserId, amount, reason })
}
