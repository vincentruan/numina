/**
 * useReportStream — U4 asset-report SSE consumer (LangGraph SDK protocol).
 *
 * Replaces the legacy NDJSON useAIReportStream. Calls the backend trigger
 * endpoint POST /api/v1/ai/report/generate/events and consumes the LangGraph
 * SSE stream that the backend transparently forwards from the agent worker
 * (_run_asset_report_pipeline emits metadata/messages/values/custom/end frames).
 *
 * Two response shapes (plan step 6 8h cache):
 * - Cache hit (Content-Type: application/json): {status:"cached", generated_at,
 *   report} → short-circuits to a completed state with the cached report.
 * - Cache miss / force (text/event-stream): stream the 3-step pipeline.
 *
 * Three-step state machine (plan step 9 阶段×status mapping):
 * - step1 (markdown 落盘): write_file tool_call → process, tool_result → finish
 * - step2 (JSON 输出): report.step2_json custom event → finish
 * - step3 (json-repair 落库): end frame status=complete → finish
 *
 * Replicates useThreadChat's SSE reader/decoder pattern (currentEvent + data
 * accumulation) and useAIReportStream's 401-refresh + cookie-refresh auth.
 */
import { ref, computed, type Ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { refreshTokenIfNeeded } from '@/api'

export type ReportStreamStatus = 'idle' | 'connecting' | 'streaming' | 'completed' | 'error'
export type StepStatus = 'waiting' | 'process' | 'finish' | 'error'

export interface ToolCallInfo {
  id: string
  name: string
  args: Record<string, unknown>
  display_name?: string
  icon?: string
}

export interface ToolResultInfo {
  tool_call_id: string
  tool_name: string
  content: unknown
}

export interface UseReportStreamReturn {
  status: Ref<ReportStreamStatus>
  progressMessage: Ref<string>
  report: Ref<Record<string, unknown> | null>
  generatedAt: Ref<string | null>
  cached: Ref<boolean>
  errorMessage: Ref<string>
  // Three-step timeline state
  step1Status: Ref<StepStatus>
  step2Status: Ref<StepStatus>
  step3Status: Ref<StepStatus>
  step1Thinking: Ref<string>
  toolCalls: Ref<ToolCallInfo[]>
  toolResults: Ref<ToolResultInfo[]>
  step2Json: Ref<Record<string, unknown> | null>
  abort: () => void
  connect: (force?: boolean) => Promise<void>
  reset: () => void
}

export function useReportStream(): UseReportStreamReturn {
  const { t } = useI18n()

  const status = ref<ReportStreamStatus>('idle')
  const progressMessage = ref('')
  const report = ref<Record<string, unknown> | null>(null)
  const generatedAt = ref<string | null>(null)
  const cached = ref(false)
  const errorMessage = ref('')

  const step1Status = ref<StepStatus>('waiting')
  const step2Status = ref<StepStatus>('waiting')
  const step3Status = ref<StepStatus>('waiting')
  const step1Thinking = ref('')
  const toolCalls = ref<ToolCallInfo[]>([])
  const toolResults = ref<ToolResultInfo[]>([])
  const step2Json = ref<Record<string, unknown> | null>(null)

  let abortController: AbortController | null = null
  let cookieRefreshTimer: ReturnType<typeof setInterval> | null = null

  function startCookieRefresh(): void {
    if (cookieRefreshTimer) clearInterval(cookieRefreshTimer)
    cookieRefreshTimer = setInterval(async () => {
      try {
        await refreshTokenIfNeeded()
      } catch {
        // best-effort; stream continues
      }
    }, 10 * 60 * 1000)
  }

  function stopCookieRefresh(): void {
    if (cookieRefreshTimer) {
      clearInterval(cookieRefreshTimer)
      cookieRefreshTimer = null
    }
  }

  function reset(): void {
    status.value = 'idle'
    progressMessage.value = ''
    report.value = null
    generatedAt.value = null
    cached.value = false
    errorMessage.value = ''
    step1Status.value = 'waiting'
    step2Status.value = 'waiting'
    step3Status.value = 'waiting'
    step1Thinking.value = ''
    toolCalls.value = []
    toolResults.value = []
    step2Json.value = null
  }

  function abort(): void {
    abortController?.abort()
    stopCookieRefresh()
    if (status.value === 'streaming' || status.value === 'connecting') {
      status.value = 'idle'
    }
  }

  async function doFetch(force: boolean, signal: AbortSignal): Promise<Response> {
    const url = force
      ? '/api/v1/ai/report/generate/events?force=true'
      : '/api/v1/ai/report/generate/events'
    const headers: Record<string, string> = {
      'Content-Type': 'application/json',
      Accept: 'text/event-stream',
    }
    let res = await fetch(url, {
      method: 'POST',
      headers,
      credentials: 'include',
      signal,
    })
    if (res.status === 401) {
      try {
        await refreshTokenIfNeeded()
      } catch {
        status.value = 'error'
        errorMessage.value = t('wsErrors.authFailed')
        throw new Error('401')
      }
      res = await fetch(url, {
        method: 'POST',
        headers,
        credentials: 'include',
        signal,
      })
    }
    return res
  }

  /** Handle a cache-hit JSON response (plan step 6): short-circuit to completed. */
  function handleCacheHit(data: {
    status?: string
    generated_at?: string
    report?: Record<string, unknown>
  }): void {
    cached.value = true
    report.value = data.report ?? null
    generatedAt.value = data.generated_at ?? null
    // A cached report means all three steps finished previously.
    step1Status.value = 'finish'
    step2Status.value = 'finish'
    step3Status.value = 'finish'
    status.value = 'completed'
    progressMessage.value = t('aiReport.cacheFresh')
  }

  /** Merge a messages-tuple AI message chunk into step1 thinking / tool calls. */
  function handleAiMessage(data: {
    content?: string
    tool_calls?: Array<{ id?: string; name?: string; args?: Record<string, unknown> }>
  }): void {
    if (data.content) {
      step1Thinking.value += data.content
      // step1 goes to 'process' as soon as the LLM starts emitting / calling tools.
      if (step1Status.value === 'waiting') step1Status.value = 'process'
    }
    if (data.tool_calls && data.tool_calls.length > 0) {
      for (const tc of data.tool_calls) {
        const name = tc.name || ''
        toolCalls.value.push({
          id: tc.id || '',
          name,
          args: tc.args || {},
        })
        // write_file (step1 markdown 落盘) → step1 process; read_file → still step1.
        if (name.includes('write_file') && step1Status.value !== 'finish') {
          step1Status.value = 'process'
        }
      }
    }
  }

  /** Tool result message → mark the matching tool_call done. */
  function handleToolMessage(data: {
    tool_call_id?: string
    name?: string
    content?: unknown
  }): void {
    const result: ToolResultInfo = {
      tool_call_id: String(data.tool_call_id || ''),
      tool_name: data.name || '',
      content: data.content,
    }
    toolResults.value.push(result)
    // write_file tool_result → step1 finish (markdown 落盘 done).
    if (result.tool_name.includes('write_file')) {
      step1Status.value = 'finish'
      // step2 begins (read_file + JSON output in flight).
      step2Status.value = 'process'
    }
  }

  /** custom event: report.step2_json → step2 finish; tool_call/tool_result
   * synthesized events also arrive here (worker mirrors them from messages). */
  function handleCustom(data: { type?: string; payload?: unknown }): void {
    if (data.type === 'report.step2_json' && data.payload) {
      step2Json.value = data.payload as Record<string, unknown>
      step2Status.value = 'finish'
      // step3 (json-repair 落库) begins.
      step3Status.value = 'process'
    }
  }

  /** end frame → step3 finish (ai_reports written) on complete status. */
  function handleEnd(data: { status?: string } | null): void {
    // Plan U4 step 9 design-lens Finding 7: if step2 never received
    // report.step2_json (step2Status still 'process' at stream end), the
    // indicators JSON parse failed → mark step2 error so the "指标 JSON 解析失败"
    // panel renders and step3 stays waiting (not silently stuck 'process').
    if (step2Status.value === 'process') {
      step2Status.value = 'error'
    }
    if (data?.status === 'complete') {
      if (step3Status.value !== 'error') step3Status.value = 'finish'
      status.value = 'completed'
    } else if (data?.status === 'error') {
      status.value = 'error'
      errorMessage.value = errorMessage.value || t('toast.aiGenerateFailed')
    } else {
      status.value = 'completed'
    }
  }

  async function connect(force = false): Promise<void> {
    if (status.value === 'streaming' || status.value === 'connecting') return
    abortController = new AbortController()
    const signal = abortController.signal

    status.value = 'connecting'
    progressMessage.value = t('wsErrors.connecting')
    errorMessage.value = ''

    let res: Response
    try {
      res = await doFetch(force, signal)
    } catch (err) {
      status.value = 'error'
      errorMessage.value = err instanceof Error && err.message === '401'
        ? t('wsErrors.authFailed')
        : t('wsErrors.connectionFailed')
      throw err
    }

    if (!res.ok) {
      status.value = 'error'
      const detail = res.headers.get('Content-Type')?.includes('application/json')
        ? (await res.json()).detail
        : res.statusText
      errorMessage.value = detail || t('wsErrors.connectionFailed')
      throw new Error(`${res.status}`)
    }

    // Cache hit: JSON response (non-stream) → short-circuit.
    const contentType = res.headers.get('Content-Type') || ''
    if (contentType.includes('application/json')) {
      const data = await res.json()
      handleCacheHit(data)
      return
    }

    if (!res.body) {
      status.value = 'error'
      errorMessage.value = t('wsErrors.connectionFailed')
      throw new Error('streaming_not_supported')
    }

    status.value = 'streaming'
    progressMessage.value = t('aiHub.reportGenerating')
    startCookieRefresh()

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
            // 'end' frame carries data: null (sentinel) — handle it.
            if (currentEvent === 'end') handleEnd(null)
            currentEvent = ''
            continue
          }

          try {
            const parsed = JSON.parse(dataStr)
            const event = currentEvent || parsed.event || 'message'
            const data = parsed.data ?? parsed
            currentEvent = ''

            if (event === 'metadata') {
              progressMessage.value = t('aiHub.reportGenerating')
            } else if (event === 'messages' && data) {
              const msg = data as { type?: string }
              if (msg.type === 'ai') handleAiMessage(data as Parameters<typeof handleAiMessage>[0])
              else if (msg.type === 'tool') handleToolMessage(data as Parameters<typeof handleToolMessage>[0])
            } else if (event === 'values' && data) {
              // values frames carry the full message list; we rely on messages
              // frames for incremental updates, so values is a no-op here.
            } else if (event === 'custom' && data) {
              handleCustom(data as Parameters<typeof handleCustom>[0])
            } else if (event === 'error' && data) {
              const errData = data as { message?: string }
              status.value = 'error'
              errorMessage.value = errData.message || t('toast.aiGenerateFailed')
            } else if (event === 'end') {
              handleEnd(data as { status?: string })
            }
          } catch {
            // Non-JSON data line; skip (best-effort, mirrors useThreadChat)
          }
          currentEvent = ''
        }
      }
    } catch (err) {
      if ((err as Error).name === 'AbortError') {
        status.value = 'idle'
      } else {
        status.value = 'error'
        errorMessage.value = (err instanceof Error && err.message)
          ? t('wsErrors.connectionInterrupted')
          : t('toast.aiGenerateFailed')
      }
    } finally {
      stopCookieRefresh()
      // If the stream ended without an explicit end frame, mark step3 from
      // process → finish when status is already completed via a custom event.
      if (status.value === 'streaming') status.value = 'completed'
    }
  }

  return {
    status,
    progressMessage,
    report,
    generatedAt,
    cached,
    errorMessage,
    step1Status,
    step2Status,
    step3Status,
    step1Thinking,
    toolCalls,
    toolResults,
    step2Json,
    abort,
    connect,
    reset,
  }
}
