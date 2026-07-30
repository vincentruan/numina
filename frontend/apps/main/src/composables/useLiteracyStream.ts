/**
 * useLiteracyStream — SSE consumer for literacy weekly report generation.
 *
 * Calls POST /api/v1/ai/literacy-report/generate/events and consumes the
 * LangGraph SSE stream. The agent emits incremental AI messages (the report
 * text) and a final `literacy_weekly_report.result` custom event.
 *
 * Two response shapes:
 * - Cache hit (application/json): {status:"ready", ...} → completed immediately.
 * - Cache miss / force (text/event-stream): stream the report generation.
 */
import { ref, type Ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { refreshTokenIfNeeded } from '@/api'

export type LiteracyStreamStatus = 'idle' | 'connecting' | 'streaming' | 'completed' | 'error'

export interface UseLiteracyStreamReturn {
  status: Ref<LiteracyStreamStatus>
  narrative: Ref<string>
  thinking: Ref<string>
  errorMessage: Ref<string>
  completedAt: Ref<string | null>
  abort: () => void
  connect: (childId: string, force?: boolean) => Promise<void>
  reset: () => void
}

export function useLiteracyStream(): UseLiteracyStreamReturn {
  const { t } = useI18n()

  const status = ref<LiteracyStreamStatus>('idle')
  const narrative = ref('')
  const thinking = ref('')
  const errorMessage = ref('')
  const completedAt = ref<string | null>(null)

  let abortController: AbortController | null = null

  function reset(): void {
    status.value = 'idle'
    narrative.value = ''
    thinking.value = ''
    errorMessage.value = ''
    completedAt.value = null
  }

  function abort(): void {
    abortController?.abort()
    if (status.value === 'streaming' || status.value === 'connecting') {
      status.value = 'idle'
    }
  }

  async function connect(childId: string, force = false): Promise<void> {
    if (status.value === 'streaming' || status.value === 'connecting') return
    abortController = new AbortController()
    const signal = abortController.signal

    reset()
    status.value = 'connecting'

    const params = new URLSearchParams({ child_id: childId })
    if (force) params.set('force', 'true')
    const url = `/api/v1/ai/literacy-report/generate/events?${params}`

    const headers: Record<string, string> = {
      'Content-Type': 'application/json',
      Accept: 'text/event-stream',
    }

    let res: Response
    try {
      res = await fetch(url, {
        method: 'POST',
        headers,
        credentials: 'include',
        signal,
      })
      if (res.status === 401) {
        await refreshTokenIfNeeded()
        res = await fetch(url, { method: 'POST', headers, credentials: 'include', signal })
      }
    } catch {
      status.value = 'error'
      errorMessage.value = t('literacyReport.streamError')
      return
    }

    if (!res.ok) {
      status.value = 'error'
      errorMessage.value = t('literacyReport.generateFailed')
      return
    }

    // JSON response: cache hit
    const contentType = res.headers.get('Content-Type') || ''
    if (contentType.includes('application/json')) {
      const data = await res.json()
      if (data.status === 'ready') {
        narrative.value = data.narrative || ''
        completedAt.value = data.generated_at || new Date().toISOString()
        status.value = 'completed'
      }
      return
    }

    if (!res.body) {
      status.value = 'error'
      errorMessage.value = t('literacyReport.streamError')
      return
    }

    // SSE stream
    status.value = 'streaming'

    const reader = res.body.getReader()
    const decoder = new TextDecoder()
    let buffer = ''
    let currentEvent = ''

    try {
      while (true) {
        const { done, value } = await reader.read()
        if (done) break

        buffer += decoder.decode(value, { stream: true })
        const lines = buffer.split('\n')
        buffer = lines.pop() || ''

        for (const line of lines) {
          if (line.startsWith('event:')) {
            currentEvent = line.slice(6).trim()
            continue
          }
          if (!line.startsWith('data:')) continue
          const dataStr = line.slice(5).trim()
          if (!dataStr || dataStr === '[DONE]' || dataStr === 'null') {
            if (currentEvent === 'end') {
              status.value = 'completed'
              if (!completedAt.value) completedAt.value = new Date().toISOString()
            }
            currentEvent = ''
            continue
          }

          try {
            const parsed = JSON.parse(dataStr)
            const event = currentEvent || parsed.event || 'message'
            const data = parsed.data ?? parsed
            currentEvent = ''

            if (event === 'messages' && data) {
              const msg = data as { type?: string; content?: string }
              if (msg.type === 'ai' && msg.content) {
                narrative.value += msg.content
              }
            } else if (event === 'custom' && data) {
              const custom = data as { type?: string; content?: string; payload?: Record<string, unknown> }
              if (custom.type === 'reasoning_delta' && custom.content) {
                thinking.value += custom.content
              } else if (custom.type === 'literacy_weekly_report.result' && custom.payload) {
                // Final result — use the authoritative text from the payload
                const payload = custom.payload
                if (payload.report) narrative.value = String(payload.report)
                if (payload.thinking) thinking.value = String(payload.thinking)
              }
            } else if (event === 'error' && data) {
              status.value = 'error'
              errorMessage.value = (data as { message?: string }).message || t('literacyReport.generateFailed')
            } else if (event === 'end') {
              const endData = data as { status?: string }
              if (endData?.status === 'complete' || endData?.status === 'completed') {
                status.value = 'completed'
              } else if (endData?.status === 'error') {
                status.value = 'error'
                errorMessage.value = errorMessage.value || t('literacyReport.generateFailed')
              } else {
                status.value = 'completed'
              }
              if (!completedAt.value) completedAt.value = new Date().toISOString()
            }
          } catch {
            // Non-JSON data line; skip
          }
          currentEvent = ''
        }
      }
    } catch (err) {
      if ((err as Error).name === 'AbortError') {
        status.value = 'idle'
      } else {
        status.value = 'error'
        errorMessage.value = t('literacyReport.streamError')
      }
    } finally {
      if (status.value === 'streaming') status.value = 'completed'
    }
  }

  return {
    status,
    narrative,
    thinking,
    errorMessage,
    completedAt,
    abort,
    connect,
    reset,
  }
}
