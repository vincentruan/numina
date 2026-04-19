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

export interface Sibling {
  id: string
  display_name: string
  avatar_color: string | null
}

export async function getCoinBalance(): Promise<number> {
  const res = await http.get('/child/coins/balance')
  return res.data.balance
}

export async function getCoinLedger(): Promise<CoinTransaction[]> {
  const res = await http.get('/child/coins/ledger')
  return res.data
}

export async function getSiblings(): Promise<Sibling[]> {
  const res = await http.get('/child/coins/siblings')
  return res.data
}

export async function giftCoins(
  toChildId: string,
  amount: number,
  emojiReason?: string,
): Promise<{ sent_amount: number; to_display_name: string }> {
  const res = await http.post('/child/coins/gift', {
    to_child_id: toChildId,
    amount,
    emoji_reason: emojiReason,
  })
  return res.data
}

export async function grantCoins(childUserId: string, amount: number, reason: string): Promise<void> {
  await http.post('/family/coins/grant', { child_user_id: childUserId, amount, reason })
}
