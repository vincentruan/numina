import http from './index'

// --- Interfaces (IDs as string — Snowflake serialization) ---

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

export interface SessionResponse {
  id: string
  assignment_id: string | null
  child_id: string
  topic_id: string
  thread_id: string | null
  session_type: string
  score: number | null
  duration_seconds: number | null
  started_at: string
  ended_at: string | null
}

export interface SessionCreate {
  topic_id: string
  assignment_id?: string
  session_type?: string
}

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

// Composite type: progress with topic detail for the map view
export interface ProgressWithTopic extends ProgressResponse {
  topic: TopicResponse
}

// --- API Functions ---

export async function getMyLearningMap(): Promise<ProgressResponse[]> {
  const res = await http.get('/child/learning/map')
  return res.data
}

export async function getMyAssignments(status?: string): Promise<AssignmentResponse[]> {
  const res = await http.get('/child/learning/assignments', {
    params: status ? { status } : {},
  })
  return res.data
}

export async function getTopicDetail(topicId: string): Promise<TopicResponse> {
  const res = await http.get(`/child/learning/topics/${topicId}`)
  return res.data
}

export async function createSession(req: SessionCreate): Promise<SessionResponse> {
  const res = await http.post('/child/learning/sessions', req)
  return res.data
}

export async function getSession(sessionId: string): Promise<SessionResponse> {
  const res = await http.get(`/child/learning/sessions/${sessionId}`)
  return res.data
}

export async function startAssessment(sessionId: string): Promise<ProgressResponse> {
  const res = await http.post(`/child/learning/sessions/${sessionId}/start-assessment`)
  return res.data
}

export async function submitAssignment(assignmentId: string): Promise<ProgressResponse> {
  const res = await http.post(`/child/learning/assignments/${assignmentId}/submit`)
  return res.data
}

export async function getMyProgress(): Promise<ProgressResponse> {
  const res = await http.get('/child/learning/progress')
  return res.data
}
