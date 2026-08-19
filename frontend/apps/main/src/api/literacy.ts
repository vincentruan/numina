import http from './index'

export interface BadgeSummary {
  new_unlocks: string[]
  progress: string[]
}

export interface ScenarioAnalysis {
  choice: string
  interpretation: string
}

export interface ReportJson {
  badge_summary: BadgeSummary
  behavioral_highlights: string[]
  scenario_analysis: ScenarioAnalysis
  family_activity: string
}

export interface WeeklyReportResponse {
  id: string
  child_id: string
  week_start: string
  report_json: ReportJson
  narrative: string
  generated_at: string
}

export interface ReportChild {
  child_id: string
  display_name: string
  avatar_url: string | null
  avatar_color: string
  latest_week_start: string | null
}

export interface ReportChildListResponse {
  children: ReportChild[]
}

export interface ReportHistoryWeek {
  week_start: string
  has_report: boolean
}

export interface ReportHistoryResponse {
  weeks: ReportHistoryWeek[]
}

export async function getReport(childId: string, weekStart?: string): Promise<WeeklyReportResponse> {
  const params: Record<string, string> = { child_id: childId }
  if (weekStart) params.week_start = weekStart
  const res = await http.get<WeeklyReportResponse>('/literacy-reports', { params })
  return res.data
}

export async function getReportChildren(): Promise<ReportChildListResponse> {
  const res = await http.get<ReportChildListResponse>('/literacy-reports/children')
  return res.data
}

export async function getReportHistory(childId: string): Promise<ReportHistoryResponse> {
  const res = await http.get<ReportHistoryResponse>('/literacy-reports/history', { params: { child_id: childId } })
  return res.data
}
