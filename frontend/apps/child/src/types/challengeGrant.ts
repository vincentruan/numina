export interface ChallengeGrant {
  id: string
  family_id: string
  child_user_id: string
  target_type: 'task_count' | 'streak_length' | 'specific_chore' | 'star_earnings'
  target_value: number
  chore_template_id: string | null
  current_progress: number
  deadline: string
  message: string | null
  status: 'active' | 'completed' | 'expired' | 'cancelled'
  completed_at: string | null
  created_at: string
  updated_at: string
}

export interface ChildChallenge {
  id: string
  target_type: 'task_count' | 'streak_length' | 'specific_chore' | 'star_earnings'
  target_value: number
  current_progress: number
  deadline: string
  message: string | null
  status: 'active' | 'completed' | 'expired' | 'cancelled'
}

export interface ChallengeCreateRequest {
  child_user_id: string
  target_type: 'task_count' | 'streak_length' | 'specific_chore' | 'star_earnings'
  target_value: number
  deadline: string
  message?: string
  chore_template_id?: string
}