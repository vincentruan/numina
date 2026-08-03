import http from './index'
import type { SystemDefaultSessionResponse } from '@/types/session'

export const getSystemDefaultSession = (maxAgeHours = 6) =>
  http.get<SystemDefaultSessionResponse>('/ai/sessions/system-default', {
    params: { max_age_hours: maxAgeHours },
  })

// ── Message feedback (点赞/点踩) ────────────────────────────────────────────
// Backend: /ai/sessions/{session_id}/messages/{message_id}/feedback
// feedback: 1=点赞, -1=点踩, 0=取消 (再点同一个值时后端自动置 0)
export const submitMessageFeedback = (
  sessionId: string,
  messageId: string,
  feedback: 1 | -1 | 0,
) =>
  http.post<{ message_id: string; feedback: number }>(
    `/ai/sessions/${encodeURIComponent(sessionId)}/messages/${encodeURIComponent(messageId)}/feedback`,
    { feedback },
  )

// 批量获取某会话下当前用户的所有反馈状态 (用于历史加载时回填高亮)
export const getSessionFeedback = (sessionId: string) =>
  http.get<{ items: Record<string, number> }>(
    `/ai/sessions/${encodeURIComponent(sessionId)}/feedback`,
  )


