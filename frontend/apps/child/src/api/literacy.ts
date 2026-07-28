import http from './index'

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export interface ScenarioChoice {
  text: string
  feedback: string
  dimension_signal: string
}

export interface ScenarioResponse {
  id: string
  story: string
  choices: ScenarioChoice[]
  age_group: string
  completed: boolean
}

export interface ChoiceFeedbackResponse {
  feedback_text: string
  dimension_hint: string
  badges_unlocked: string[]
}

// ---------------------------------------------------------------------------
// API
// ---------------------------------------------------------------------------

export async function getWeeklyScenario(): Promise<ScenarioResponse> {
  const res = await http.get('/child/literacy/scenario')
  return res.data
}

export async function submitChoice(choiceIndex: number): Promise<ChoiceFeedbackResponse> {
  const res = await http.post('/child/literacy/scenario/choose', { choice_index: choiceIndex })
  return res.data
}

// ---------------------------------------------------------------------------
// Badge Wall
// ---------------------------------------------------------------------------

export interface BadgeInfo {
  id: string
  name: string
  level: number
  description: string
  earned_at: string
}

export interface BadgeHistoryItem {
  id: string
  name: string
  level: number
  earned_at: string
  superseded_at: string
}

export interface BadgeDefinitionInfo {
  id: string
  name: string
  level: number
  description: string
  criteria_summary: string
}

export interface BadgeDimensionData {
  dimension: string
  current_badge: BadgeInfo | null
  history: BadgeHistoryItem[]
  next_badge: BadgeDefinitionInfo | null
}

export interface BadgeWallResponse {
  dimensions: BadgeDimensionData[]
}

export async function getBadges(): Promise<BadgeWallResponse> {
  const res = await http.get('/child/literacy/badges')
  return res.data
}
