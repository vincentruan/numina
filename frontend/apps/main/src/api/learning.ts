// Shared learning API types and functions for the parent (main) app.
// NOTE: Type definitions (TopicResponse, ProgressResponse, etc.) are duplicated
// in apps/child/src/api/learning.ts — extract to @numina/types when drift becomes painful.
import http from './index'

// --- Interfaces (IDs as string — Snowflake serialization) ---

export interface ChildLearningOverview {
  child_id: string
  child_name: string
  mastered_count: number
  learning_count: number
  available_count: number
  locked_count: number
  review_count: number
  total_study_minutes: number
}

export interface TopicResponse {
  id: string
  topic_key: string
  topic_type: string
  subject: string
  domain: string | null
  name: string | null
  name_zh: string | null
  description: string
  description_zh: string | null
  age_range_start: number | null
  age_range_end: number | null
  age_group: string
  centrality: number | null
  evidence: string[]
  evidence_zh: string[] | null
  assessment_prompt: string | null
  assessment_prompt_zh: string | null
  standards: string[]
  ability_dimensions: string[] | null
  deprecated: boolean
}

export interface ProgressResponse {
  id: string
  child_id: string
  topic_id: string
  mastery_level: string
  mastery_score: number | null
  completed_via: string | null
  attempts: number
  xp_earned: number
  last_practice_at: string | null
  first_mastered_at: string | null
  stability: number | null
  next_review_at: string | null
  ability_dimensions_score: Record<string, number> | null
}

export interface AssignmentResponse {
  id: string
  family_id: string
  child_id: string
  topic_id: string
  path_id: string | null
  created_by: string
  assignment_type: string
  status: string
  priority: number
  due_date: string | null
  created_at: string
  completed_at: string | null
  topic?: TopicResponse | null
}

export interface ReviewItem {
  progress_id: string
  child_id: string
  child_name: string
  topic_id: string
  topic_name: string
  topic_description: string
  evidence: string[]
  evidence_zh: string[] | null
  attempts: number
  study_duration_seconds: number
  submitted_at: string
}

// Composite type: progress with topic detail for the map view
export interface ProgressWithTopic extends ProgressResponse {
  topic: TopicResponse
}

// --- API Functions ---

export async function getLearningChildren(): Promise<ChildLearningOverview[]> {
  const res = await http.get('/family/learning/children')
  return res.data
}

export async function getChildMap(childId: string): Promise<ProgressResponse[]> {
  const res = await http.get(`/family/learning/children/${childId}/map`)
  return res.data
}

export async function getChildProgress(childId: string): Promise<ProgressResponse[]> {
  const res = await http.get(`/family/learning/children/${childId}/progress`)
  return res.data
}

export async function createAssignment(req: {
  child_id: string
  topic_id: string
  due_date?: string
  priority?: number
}): Promise<AssignmentResponse> {
  const res = await http.post('/family/learning/assignments', req)
  return res.data
}

export async function getAssignments(childId?: string): Promise<AssignmentResponse[]> {
  const res = await http.get('/family/learning/assignments', {
    params: childId ? { child_id: childId } : {},
  })
  return res.data
}

export async function getReviews(): Promise<ReviewItem[]> {
  const res = await http.get('/family/learning/reviews')
  return res.data
}

export async function approveReview(progressId: string): Promise<ProgressResponse> {
  const res = await http.post(`/family/learning/reviews/${progressId}/approve`)
  return res.data
}

export async function rejectReview(progressId: string): Promise<ProgressResponse> {
  const res = await http.post(`/family/learning/reviews/${progressId}/reject`)
  return res.data
}

export async function getTopicDetail(topicId: string): Promise<TopicResponse> {
  const res = await http.get(`/family/learning/topics/${topicId}`)
  return res.data
}

export async function getTopicsBatch(ids: string[]): Promise<TopicResponse[]> {
  const res = await http.get(`/learning/topics/batch?ids=${ids.join(',')}`)
  return res.data
}

export async function searchTopics(query: string): Promise<TopicResponse[]> {
  const res = await http.get('/learning/topics', { params: { search: query } })
  return res.data
}

/** Translate a topic's content to Chinese. Returns translated fields. */
export async function translateTopic(topicId: string): Promise<{
  name_zh: string | null
  description_zh: string | null
  evidence_zh: string[] | null
  assessment_prompt_zh: string | null
}> {
  const res = await http.post(`/learning/topics/${topicId}/translate`)
  return res.data
}
