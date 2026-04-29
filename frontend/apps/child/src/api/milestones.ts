import http from './index'

export type MilestoneType =
  | 'first_chore'
  | 'first_wish_realized'
  | 'coins_50'
  | 'coins_200'
  | 'streak_7'
  | 'streak_14'
  | 'streak_30'

export interface Milestone {
  id: string
  milestone_type: MilestoneType
  triggered_at: string
  ref_id: string | null
  ref_type: string | null
}

export async function getMyMilestones(): Promise<Milestone[]> {
  const res = await http.get<{ data: Milestone[] }>('/child/milestones')
  return res.data.data ?? []
}
