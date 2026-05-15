import http from './index'

export interface ChoreTemplate {
  id: string
  family_id: string
  name: string
  emoji: string | null
  coin_reward: number
  frequency: 'daily' | 'weekly'
  assignment_type: 'assigned' | 'pool'
  is_active: boolean
  assignees: { id: string; display_name: string }[]
}

export interface ChoreTemplateCreate {
  name: string
  emoji?: string
  coin_reward: number
  frequency: 'daily' | 'weekly'
  assignment_type: 'assigned' | 'pool'
  assignee_ids: string[]
}

export interface ChoreTemplateUpdate {
  name?: string
  emoji?: string
  coin_reward?: number
  assignee_ids?: string[]
}

export async function listChoreTemplates(): Promise<ChoreTemplate[]> {
  const res = await http.get('/family/chore-templates')
  return res.data
}

export async function createChoreTemplate(data: ChoreTemplateCreate): Promise<ChoreTemplate> {
  const res = await http.post('/family/chore-templates', data)
  return res.data
}

export async function updateChoreTemplate(id: string, data: ChoreTemplateUpdate): Promise<ChoreTemplate> {
  const res = await http.patch(`/family/chore-templates/${id}`, data)
  return res.data
}

export async function toggleChoreTemplate(id: string, isActive: boolean): Promise<ChoreTemplate> {
  const res = await http.patch(`/family/chore-templates/${id}/toggle`, null, { params: { is_active: isActive } })
  return res.data
}

export async function deleteChoreTemplate(id: string): Promise<void> {
  await http.delete(`/family/chore-templates/${id}`)
}

export interface ChoreInstance {
  id: string
  template_id: string
  chore_name: string
  chore_emoji: string | null
  coin_reward: number
  date_bucket: string
  status: 'available' | 'pending_approval' | 'approved' | 'rejected'
  submitted_at: string | null
  approved_at: string | null
  streak_count: number
  streak_bonus: number
  milestone_triggered: string | null
  is_pool_unclaimed: boolean
  assigned_by_user_id: string | null
  claimed_at: string | null
}

/** Extends ChoreInstance with child identity fields present on pending-approval responses. */
export interface PendingApprovalInstance extends ChoreInstance {
  child_user_id: string | null
  child_display_name: string | null
  child_avatar_color: string | null
}

export async function getMyChores(date: string): Promise<ChoreInstance[]> {
  const res = await http.get('/child/chores', { params: { date } })
  return res.data
}

export async function markChoreComplete(instanceId: string): Promise<ChoreInstance> {
  const res = await http.post(`/child/chores/${instanceId}/complete`)
  return res.data
}

export async function getPendingApprovals(): Promise<PendingApprovalInstance[]> {
  const res = await http.get('/family/chore-approvals')
  return res.data
}

export async function approveChore(instanceId: string): Promise<ChoreInstance> {
  const res = await http.post(`/family/chore-approvals/${instanceId}/approve`)
  return res.data
}

export async function rejectChore(instanceId: string, returnToRedo: boolean): Promise<ChoreInstance> {
  const res = await http.post(`/family/chore-approvals/${instanceId}/reject`, { return_to_redo: returnToRedo })
  return res.data
}

export async function claimChore(instanceId: string): Promise<ChoreInstance> {
  const res = await http.post(`/child/chores/${instanceId}/claim`)
  return res.data
}

export async function abandonChore(instanceId: string): Promise<ChoreInstance> {
  const res = await http.post(`/child/chores/${instanceId}/abandon`)
  return res.data
}
