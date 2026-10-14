// Practice API — question bank + adaptive practice system
import http from './index'

// --- Interfaces (IDs as string — Snowflake serialization) ---

export interface QuestionOption {
  key: string
  text: string
  text_zh?: string | null
}

export interface QuestionResponse {
  id: string
  topic_id: string
  question_type: 'multiple_choice' | 'true_false' | 'fill_blank' | 'calculation' | 'application'
  stem: string
  stem_zh: string | null
  options: QuestionOption[] | null
  answer: Record<string, unknown>
  solution: { steps?: string[] } | null
  difficulty: number
  bloom_level: string
  source: string
  review_status: string
  age_group: string
  parameters: Record<string, unknown> | null
  times_used: number
  correct_count: number
}

export interface PracticeSessionResponse {
  id: string
  child_id: string
  topic_id: string
  session_mode: string
  question_ids: string[]
  started_at: string
  ended_at: string | null
  total_score: number | null
  completed_count: number
  source: string
  learning_progress_id: string | null
}

export interface PracticeAttemptResponse {
  id: string
  session_id: string
  question_id: string
  child_id: string
  topic_id: string
  is_correct: boolean
  time_spent_seconds: number | null
  attempt_number: number
  created_at: string
}

export interface PracticeResultResponse {
  session_id: string
  total_score: number
  correct_count: number
  total_count: number
  xp_earned: number
  coins_earned: number
  mastery_changed: boolean
  new_mastery_level: string | null
}

export interface PracticeSessionCreate {
  topic_id: string
  session_mode?: 'practice' | 'review' | 'challenge'
  count?: number
}

export interface PracticeAnswerSubmit {
  question_id: string
  user_answer: Record<string, unknown>
  time_spent_seconds?: number
}

// --- API functions ---

export async function listPracticeQuestions(
  topicId: string,
): Promise<QuestionResponse[]> {
  const resp = await http.get('/practice/questions', { params: { topic_id: topicId } })
  return resp.data
}

export async function batchGetQuestions(
  questionIds: string[],
): Promise<QuestionResponse[]> {
  const resp = await http.post('/practice/questions/batch', {
    question_ids: questionIds,
  })
  return resp.data
}

export async function createPracticeSession(
  req: PracticeSessionCreate,
): Promise<PracticeSessionResponse> {
  const resp = await http.post('/practice/sessions', req)
  return resp.data
}

export async function submitPracticeAnswer(
  sessionId: string,
  req: PracticeAnswerSubmit,
): Promise<PracticeAttemptResponse> {
  const resp = await http.post(`/practice/sessions/${sessionId}/answer`, req)
  return resp.data
}

export async function finishPracticeSession(
  sessionId: string,
): Promise<PracticeResultResponse> {
  const resp = await http.post(`/practice/sessions/${sessionId}/finish`)
  return resp.data
}

// --- Phase 5: Weak points + history + recommend ---

export interface WeakTopicResponse {
  topic_id: string
  topic_name: string
  topic_name_zh: string | null
  total_attempts: number
  correct_attempts: number
  accuracy: number
  last_practice_at: string | null
  mastery_level: string
}

export interface SessionListItem {
  id: string
  topic_id: string
  topic_name: string
  topic_name_zh: string | null
  session_mode: string
  total_score: number | null
  completed_count: number
  total_count: number
  started_at: string
  ended_at: string | null
}

export interface SessionDetailResponse {
  id: string
  topic_id: string
  topic_name: string
  topic_name_zh: string | null
  session_mode: string
  total_score: number | null
  completed_count: number
  total_count: number
  started_at: string
  ended_at: string | null
  attempts: Array<{
    id: string
    question_id: string
    question_stem: string
    question_type: string
    user_answer: Record<string, unknown>
    is_correct: boolean
    time_spent_seconds: number | null
    attempt_number: number
    created_at: string
  }>
}

export interface RecommendResponse {
  topic_id: string
  topic_name: string
  topic_name_zh: string | null
  mastery_level: string
  accuracy: number
  is_prerequisite: boolean
  prerequisite_of_topic_id: string | null
}

export async function getWeakTopics(
  limit = 10,
  minAttempts = 3,
): Promise<WeakTopicResponse[]> {
  const resp = await http.get('/practice/weak-topics', {
    params: { limit, min_attempts: minAttempts },
  })
  return resp.data
}

export async function listPracticeSessions(
  limit = 20,
  offset = 0,
): Promise<SessionListItem[]> {
  const resp = await http.get('/practice/sessions', {
    params: { limit, offset },
  })
  return resp.data
}

export async function getPracticeSessionDetail(
  sessionId: string,
): Promise<SessionDetailResponse> {
  const resp = await http.get(`/practice/sessions/${sessionId}`)
  return resp.data
}

export async function getPracticeRecommendations(
  topicId?: string,
): Promise<RecommendResponse[]> {
  const params = topicId ? { topic_id: topicId } : {}
  const resp = await http.get('/practice/recommend', { params })
  return resp.data
}
