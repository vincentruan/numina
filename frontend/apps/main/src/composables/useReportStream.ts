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
import { ref, type Ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { refreshTokenIfNeeded } from '@/api'
import { getAITask } from '@/api/ai'
import { readSSEStream } from '@/utils/sseReader'

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
  // U6: SSE reconnection state
  runId: Ref<string | null>
  abort: (keepRunning?: boolean) => void
  connect: (force?: boolean) => Promise<boolean>
  reset: () => void
  pollTaskUntilComplete: () => Promise<void>
  startPolling: () => Promise<void>
  /**
   * P1-5 fix: ingest an external SSE event (from useTaskResume reconnect)
   * and route it through the same internal handlers as connect().
   */
  ingestEvent: (eventName: string, data: unknown) => void
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

  // U6: SSE reconnection state
  const runId = ref<string | null>(null)

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
    // U6: Reset reconnection state
    runId.value = null
  }

  function abort(keepRunning = false): void {
    abortController?.abort()
    stopCookieRefresh()
    if (!keepRunning && (status.value === 'streaming' || status.value === 'connecting')) {
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
      // The SSE end frame does not carry generated_at (end_payload only has
      // status + usage). Set it now so the caller sees a fresh timestamp
      // instead of null — without this the "暂无报告" empty state shows.
      if (!generatedAt.value) {
        generatedAt.value = new Date().toISOString()
      }
    } else if (data?.status === 'error') {
      status.value = 'error'
      errorMessage.value = errorMessage.value || t('toast.aiGenerateFailed')
    } else if (status.value !== 'error') {
      // Only transition to 'completed' if not already in error state.
      // An error event may have been received before this end frame.
      status.value = 'completed'
      if (!generatedAt.value) {
        generatedAt.value = new Date().toISOString()
      }
    }
  }

  /** Poll task status until completed/failed (for 202 queued responses). */
  async function pollTaskUntilComplete(): Promise<void> {
    const MAX_POLL_DURATION = 10 * 60 * 1000 // 10 minutes max
    const POLL_INTERVAL = 30_000 // 30 seconds — long polling to reduce request load
    const startTime = Date.now()

    while (Date.now() - startTime < MAX_POLL_DURATION) {
      await new Promise(resolve => setTimeout(resolve, POLL_INTERVAL))

      try {
        const taskStatus = await getAITask('report')
        if (taskStatus.status === 'completed' || taskStatus.status === 'idle') {
          // Task completed — caller will reload report from API
          status.value = 'completed'
          if (!generatedAt.value) {
            generatedAt.value = new Date().toISOString()
          }
          return
        } else if (taskStatus.status === 'failed' || taskStatus.status === 'cancelled' || taskStatus.status === 'timeout') {
          status.value = 'error'
          errorMessage.value = t('toast.aiGenerateFailed')
          throw new Error(`task_${taskStatus.status}`)
        }
        // Still running/queued — continue polling
      } catch (err) {
        // Network error during polling — continue unless it's a task failure
        if (err instanceof Error && err.message.startsWith('task_')) {
          throw err
        }
        // Otherwise continue polling
      }
    }

    // Timeout — polling exceeded max duration
    status.value = 'error'
    errorMessage.value = t('toast.reportTimeout')
    throw new Error('poll_timeout')
  }

  /** Start polling an already-running background task (used when the user
   * returns to the page after leaving while generation was in progress). */
  async function startPolling(): Promise<void> {
    reset()
    status.value = 'streaming'
    progressMessage.value = t('aiHub.reportGenerating')
    await pollTaskUntilComplete()
  }

  async function connect(force = false): Promise<boolean> {
    if (status.value === 'streaming' || status.value === 'connecting') return false
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

    // JSON response: either cache hit (200) or queued task (202).
    const contentType = res.headers.get('Content-Type') || ''
    if (contentType.includes('application/json')) {
      const data = await res.json()
      // 202 = task queued/running — poll until complete instead of returning immediately.
      if (res.status === 202 && data.status === 'queued') {
        status.value = 'streaming'
        progressMessage.value = t('aiHub.reportQueued')
        await pollTaskUntilComplete()
        return true
      }
      // 200 = cache hit — short-circuit with cached report.
      handleCacheHit(data)
      return true
    }

    if (!res.body) {
      status.value = 'error'
      errorMessage.value = t('wsErrors.connectionFailed')
      throw new Error('streaming_not_supported')
    }

    status.value = 'streaming'
    progressMessage.value = t('aiHub.reportGenerating')
    startCookieRefresh()

    try {
      await readSSEStream(res, {
        onMetadata: (data) => {
          progressMessage.value = t('aiHub.reportGenerating')
          if (data && typeof data === 'object' && 'run_id' in data) {
            runId.value = (data as Record<string, unknown>).run_id as string
          }
        },
        onMessage: (event, data) => {
          if (event === 'messages' && data) {
            const msg = data as { type?: string }
            if (msg.type === 'ai') handleAiMessage(data as Parameters<typeof handleAiMessage>[0])
            else if (msg.type === 'tool') handleToolMessage(data as Parameters<typeof handleToolMessage>[0])
          }
          // values frames: no-op (we rely on messages for incremental updates).
        },
        onCustom: (data) => {
          handleCustom(data as Parameters<typeof handleCustom>[0])
        },
        onError: (data) => {
          const errData = data as { error?: string; message?: string }
          status.value = 'error'
          errorMessage.value = errData.error || errData.message || t('toast.aiGenerateFailed')
        },
        onGap: () => {
          console.warn('[useReportStream] Stream gap detected, reloading state from DB')
          status.value = 'error'
          errorMessage.value = '事件流中断，请刷新页面重新连接'
        },
        onEnd: (data) => {
          handleEnd(data as { status?: string } | null)
        },
      })
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
      if (status.value === 'streaming') status.value = 'completed'
    }
    return true
  }

  /**
   * P1-5 fix: ingest an external SSE event (e.g. from useTaskResume
   * reconnect via subscribeTaskStream) and route it through the same
   * internal handlers as connect()'s SSE reader loop.
   */
  function ingestEvent(eventName: string, data: unknown): void {
    if (status.value === 'completed' || status.value === 'error') return
    status.value = 'streaming'

    const d = (data ?? {}) as Record<string, unknown>

    switch (eventName) {
      case 'metadata':
        if (typeof d.run_id === 'string') runId.value = d.run_id
        if (typeof d.progress_message === 'string') progressMessage.value = d.progress_message
        break
      case 'messages': {
        const msgType = d.type as string | undefined
        if (msgType === 'ai') {
          handleAiMessage(d as Parameters<typeof handleAiMessage>[0])
        } else if (msgType === 'tool') {
          handleToolMessage(d as Parameters<typeof handleToolMessage>[0])
        }
        break
      }
      case 'custom':
        handleCustom(d as Parameters<typeof handleCustom>[0])
        break
      case 'end':
        handleEnd(d as Parameters<typeof handleEnd>[0])
        break
      case 'error':
        status.value = 'error'
        errorMessage.value = (d.error as string) || (d.message as string) || t('toast.aiGenerateFailed')
        break
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
    // U6: SSE reconnection state
    runId,
    abort,
    connect,
    reset,
    pollTaskUntilComplete,
    startPolling,
    ingestEvent,
  }
}
