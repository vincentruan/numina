import http from './index'

export interface TreasureItem {
  id: string
  name: string
  image_url: string | null
  purchase_date: string | null
  coins_spent: number | null
}

export async function listTreasures(): Promise<TreasureItem[]> {
  const res = await http.get('/child/treasures')
  return res.data
}
