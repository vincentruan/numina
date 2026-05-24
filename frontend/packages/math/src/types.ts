export interface PrioritySimulationEntry {
  wish_id: string
  name: string
  priority: string
  star_coin_cost: number
  progress: number
  covered: boolean
}

export interface LedgerEntry {
  amount: number
  created_at: string
}

export type ReachabilityTint = 'green' | 'yellow' | 'red' | 'gray'

export interface SpendDelta {
  wish_id: string
  before_progress: number
  after_progress: number
  days_added: number
}

export interface SpendPreview {
  deltas: SpendDelta[]
}
