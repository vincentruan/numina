import http from './index'

export interface TreasureItem {
  id: string
  name: string
  image_url: string | null
  purchase_date: string | null
  coins_spent: number | null
}

export interface ChildAsset {
  id: string
  name: string
  image_url: string | null
  purchase_date: string | null
  purchase_price: number | null
  current_value: number | null
  status: string
  created_at: string
}

export async function listTreasures(): Promise<TreasureItem[]> {
  const res = await http.get('/child/treasures')
  return res.data
}

export async function getChildAsset(assetId: string): Promise<ChildAsset> {
  const res = await http.get(`/child/assets/${assetId}`)
  return res.data
}
