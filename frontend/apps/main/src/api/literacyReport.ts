import http from './index'

export interface ReportStatus {
  status: 'none' | 'ready' | 'generating'
  thread_id: string | null
  week_start: string
  narrative: string | null
  generated_at: string | null
}

/** Get the current week's report status for a child (BabyPage entry). */
export function getReportStatus(childId: string) {
  return http.get<ReportStatus>('/literacy-reports/status', {
    params: { child_id: childId },
  })
}

/** Trigger report generation (or return cached). */
export function generateReport(childId: string, force = false) {
  return http.post<ReportStatus>('/ai/literacy-report/generate', null, {
    params: { child_id: childId, force },
  })
}
