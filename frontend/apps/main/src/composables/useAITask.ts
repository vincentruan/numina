/**
 * useAITask — 管理单个 capability 的长任务状态和 streaming 接续。
 *
 * 功能：
 * - 页面挂载时查询任务状态，若 running 则接续 streaming
 * - 新建任务时调用 startStream()
 * - 解析 NDJSON 事件流：phase.connecting / phase.thinking / phase.answering / token.stream / capability.end / capability.error
 * - 思考内容单独累积，答案内容单独累积
 * - 任务完成后自动折叠思考内容
 * - 支持排队状态（queued）：轮询直到前置任务完成后自动启动
 * - visibilitychange：切走时断开，回来时接续
 *
 * resumeStream() 不调用触发端点（避免 409 循环）。
 */
import { onMounted, onUnmounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { showToast } from 'vant'
import { useAIStore } from '@/stores/ai'
import {
  getAITask,
  startAIEventStream,
  cancelAITask,
  type AITaskStatus,
} from '@/api/ai'
import { createAgentEventParser } from '@/composables/useAgentEventStream'
import type { AgentEvent } from '@/types/agent-stream'

const POLL_INTERVAL_MS = 3000

export type AITaskPhase = 'connecting' | 'thinking' | 'answering' | null

export interface ToolStep {
  id: string
  name: string
  displayName: string
  icon: string
  toolType?: string
  status: 'pending' | 'running' | 'done' | 'error'
  progressMessage?: string
  resultSummary?: string
}

export function useAITask(
  capability: string,
  triggerEndpoint: string,
  onComplete?: () => void,
) {
  const { t } = useI18n()
  const aiStore = useAIStore()

  const status = ref<AITaskStatus['status']>('idle')
  const phase = ref<AITaskPhase>(null)
  const thinkContent = ref('')
  const thinkDone = ref(false)
  const thinkSeconds = ref(0)
  const answerContent = ref('')
  const elapsedSeconds = ref(0)
  const taskId = ref<string | null>(null)
  const sessionId = ref<string | null>(null)
  const isConsoleOpen = ref(false)
  const queuePosition = ref<number | null>(null)
  const errorCode = ref<string | null>(null)
  const toolSteps = ref<ToolStep[]>([])
  const currentToolLabel = ref<string | null>(null)
  const suggestions = ref<string[]>([])

  let abortController: AbortController | null = null
  let timer: ReturnType<typeof setInterval> | null = null
  let pollTimer: ReturnType<typeof setInterval> | null = null
  let thinkTimer: ReturnType<typeof setInterval> | null = null
  let startTime: number | null = null
  let thinkStartTime: number | null = null
  let completedFired = false
  let postProcessingPollTimer: ReturnType<typeof setTimeout> | null = null

  // ── Elapsed timer ──────────────────────────────────────────────────────────

  function startTimer(fromSeconds = 0) {
    elapsedSeconds.value = fromSeconds
    startTime = Date.now() - fromSeconds * 1000
    if (timer) clearInterval(timer)
    timer = setInterval(() => {
      elapsedSeconds.value = Math.floor((Date.now() - startTime!) / 1000)
    }, 1000)
  }

  function stopTimer() {
    if (timer) {
      clearInterval(timer)
      timer = null
    }
  }

  function startThinkTimer() {
    thinkStartTime = Date.now()
    thinkSeconds.value = 0
    if (thinkTimer) clearInterval(thinkTimer)
    thinkTimer = setInterval(() => {
      thinkSeconds.value = Math.floor((Date.now() - thinkStartTime!) / 1000)
    }, 1000)
  }

  function stopThinkTimer() {
    if (thinkTimer) {
      clearInterval(thinkTimer)
      thinkTimer = null
    }
  }

  // ── Polling ────────────────────────────────────────────────────────────────

  function startPolling() {
    if (pollTimer) {
      clearInterval(pollTimer)
      pollTimer = null
    }
    pollTimer = setInterval(async () => {
      try {
        const task = await getAITask(capability)
        if (task.status === 'queued') {
          queuePosition.value = task.queue_position ?? null
          return
        }
        if (task.status === 'running' || task.status === 'post_processing') {
          // Queued task was promoted — stop polling and reconnect to the stream
          stopPolling()
          await resumeStream(task)
          return
        }
        clearInterval(pollTimer!)
        pollTimer = null
        status.value = task.status
        phase.value = null
        stopTimer()
        stopThinkTimer()
        if (task.status === 'completed' && !completedFired) {
          isConsoleOpen.value = false
          completedFired = true
          onComplete?.()
        }
      } catch {
        // ignore transient errors
      }
    }, POLL_INTERVAL_MS)
  }

  function stopPolling() {
    if (pollTimer) {
      const t = pollTimer
      pollTimer = null
      clearInterval(t)
    }
  }

  // ── NDJSON event handling ──────────────────────────────────────────────────

  function handleEvent(event: AgentEvent) {
    switch (event.type) {
      case 'phase.connecting':
        phase.value = 'connecting'
        break
      case 'phase.thinking':
        phase.value = 'thinking'
        thinkDone.value = false
        startThinkTimer()
        break
      case 'phase.answering':
        phase.value = 'answering'
        thinkDone.value = true
        stopThinkTimer()
        break
      case 'token.stream':
        if (event.is_thinking) {
          thinkContent.value += event.token ?? ''
        } else {
          answerContent.value += event.token ?? ''
        }
        break
      case 'tool.call':
        if (event.tool) {
          const step: ToolStep = {
            id: event.tool.id,
            name: event.tool.name,
            displayName: event.tool.display_name || event.tool.name,
            icon: event.tool.icon || '⚙️',
            toolType: event.tool.tool_type,
            status: 'running',
          }
          toolSteps.value = [...toolSteps.value, step]
          currentToolLabel.value = step.displayName
        }
        break
      case 'tool.result':
        if (event.tool_id) {
          toolSteps.value = toolSteps.value.map((s) =>
            s.id === event.tool_id
              ? {
                  ...s,
                  status: (event.result?.success ?? true) ? 'done' : 'error',
                  resultSummary: event.result?.summary,
                }
              : s,
          )
          // Update currentToolLabel to next running tool, or keep last
          const running = toolSteps.value.find((s) => s.status === 'running')
          if (running) {
            currentToolLabel.value = running.displayName
          }
        }
        break
      case 'tool.progress':
        if (event.tool_id) {
          toolSteps.value = toolSteps.value.map((s) =>
            s.id === event.tool_id && s.status === 'running'
              ? { ...s, progressMessage: event.progress_message }
              : s,
          )
          if (event.progress_message) {
            currentToolLabel.value = event.progress_message
          }
        }
        break
      case 'capability.end':
        // summary may be in result.summary — already accumulated via token.stream
        if (event.result?.suggestions?.length) {
          suggestions.value = event.result.suggestions
        }
        break
      case 'capability.error':
        // R6.1: 不清空 thinkContent / answerContent — 保留对话文本以便用户阅读
        status.value = 'failed'
        phase.value = null
        // Backend emits flat shape: { type, code, message }; legacy nested: { error: { code, message } }
        {
          const rawCode = event.code ?? event.error?.code ?? 'extraction_failed'
          const normalized = rawCode.startsWith('circuit_blocked:')
            ? rawCode.slice('circuit_blocked:'.length)
            : rawCode
          errorCode.value = normalized
        }
        stopTimer()
        stopThinkTimer()
        // R6.4: do not collapse the console on failure
        // do NOT call onComplete() — task did not actually finish
        break
    }
  }

  // ── Stream consumption ─────────────────────────────────────────────────────

  async function consumeEventStream(reader: ReadableStreamDefaultReader<Uint8Array>) {
    const decoder = new TextDecoder()
    const parser = createAgentEventParser(handleEvent)
    const TIMEOUT_MS = 300000 // 5 minutes max wait for next chunk

    try {
      while (true) {
        let timeoutId: ReturnType<typeof setTimeout> | null = null
        const timeoutPromise = new Promise<never>((_, reject) => {
          timeoutId = setTimeout(() => reject(new Error('Stream timeout')), TIMEOUT_MS)
        })

        let result: { done: boolean; value: Uint8Array | undefined }
        try {
          result = await Promise.race([reader.read(), timeoutPromise])
        } finally {
          if (timeoutId !== null) clearTimeout(timeoutId)
        }

        if (result.done) break
        const text = decoder.decode(result.value, { stream: true })
        if (text) parser.push(text)
      }
      parser.flush()
      // Stream ended — but task may still be in post_processing on backend.
      // R1.3: Don't claim 'completed' until backend confirms via getAITask.
      // If a capability.error event already set status='failed', skip the post-processing wait.
      if (status.value !== 'failed') {
        await waitForTerminalStatus()
      }
      stopTimer()
      stopThinkTimer()
      stopPolling()
    } catch (err: unknown) {
      // Cancel reader on abort to signal backend
      if (err instanceof Error && err.name === 'AbortError') {
        try {
          await reader.cancel()
        } catch {
          // Ignore reader.cancel errors
        }
        return
      }
      // Cleanup on other errors
      try {
        await reader.cancel()
      } catch {
        // Ignore
      }
      status.value = 'failed'
      errorCode.value = errorCode.value ?? 'stream_error'
      phase.value = null
      stopTimer()
      stopThinkTimer()
      stopPolling()
    }
  }

  // ── Post-stream terminal-status wait ───────────────────────────────────────
  // After the agent NDJSON stream ends, the backend transitions through
  // post_processing → completed/failed. Poll briefly until we see a terminal
  // state, with a hard ceiling of POST_PROCESSING_MAX_MS to avoid hanging UI.

  // Post-processing timeout: based on provider's timeout_seconds × 3 (stream + fallback + write),
  // with a floor of 120s. A report may involve multiple LLM calls (stream + structured extraction
  // fallback), so the ceiling must be at least 2× the normal completion time.
  // Evaluated lazily at call time so aiStore.config is populated after fetchConfig().
  function getPostProcessingMaxMs(): number {
    const providerTimeout = aiStore.config?.ai_timeout_seconds ?? 60
    return Math.max(providerTimeout * 3, 120) * 1000
  }
  const POST_PROCESSING_POLL_INTERVAL_MS = 500

  async function waitForTerminalStatus() {
    const deadline = Date.now() + getPostProcessingMaxMs()
    while (Date.now() < deadline) {
      try {
        const task = await getAITask(capability)
        if (task.status === 'completed') {
          status.value = 'completed'
          phase.value = null
          thinkDone.value = true
          isConsoleOpen.value = false
          if (!completedFired) {
            completedFired = true
            onComplete?.()
          }
          return
        }
        if (task.status === 'failed' || task.status === 'timeout' || task.status === 'cancelled') {
          status.value = task.status
          if (status.value === 'failed' && !errorCode.value) {
            errorCode.value = 'extraction_failed'
          }
          phase.value = null
          return
        }
        // running / post_processing → keep polling
      } catch {
        // transient — keep polling
      }
      await new Promise((resolve) => {
        postProcessingPollTimer = setTimeout(resolve, POST_PROCESSING_POLL_INTERVAL_MS)
      })
    }
    // Hit the ceiling without a terminal state — surface as failed
    status.value = 'failed'
    errorCode.value = errorCode.value ?? 'post_processing_timeout'
    phase.value = null
  }

  // ── Start stream ───────────────────────────────────────────────────────────

  async function startStream() {
    if (abortController) abortController.abort()
    abortController = new AbortController()

    // Reset state
    thinkContent.value = ''
    answerContent.value = ''
    thinkDone.value = false
    thinkSeconds.value = 0
    errorCode.value = null
    phase.value = 'connecting'
    status.value = 'running'
    isConsoleOpen.value = true
    completedFired = false
    toolSteps.value = []
    currentToolLabel.value = null
    suggestions.value = []
    startTimer(0)

    try {
      const result = await startAIEventStream(triggerEndpoint, abortController.signal)

      if (result.queued) {
        // Task is queued — show queued state and poll until it starts
        status.value = 'queued'
        phase.value = null
        taskId.value = result.taskId
        queuePosition.value = result.queuePosition
        stopTimer()
        startPolling()
        return
      }

      await consumeEventStream(result.reader)
    } catch (err: unknown) {
      if (err instanceof Error && err.name === 'AbortError') return
      const errorMsg = err instanceof Error ? err.message : ''
      if (errorMsg.includes('409')) {
        showToast(t('aiTask.inProgress'))
        status.value = 'idle'
        phase.value = null
        stopTimer()
        stopThinkTimer()
        stopPolling()
        await checkAndResume()
      } else {
        status.value = 'failed'
        phase.value = null
        stopTimer()
        stopThinkTimer()
        stopPolling()
      }
    }
  }

  async function resumeStream(existingTask: AITaskStatus) {
    taskId.value = existingTask.task_id ?? null
    sessionId.value = existingTask.session_id ?? null
    status.value = 'running'
    phase.value = 'connecting'
    isConsoleOpen.value = true
    // Reset content state so resumed stream doesn't append to stale content
    thinkContent.value = ''
    answerContent.value = ''
    thinkDone.value = false
    thinkSeconds.value = 0
    errorCode.value = null
    completedFired = false
    toolSteps.value = []
    currentToolLabel.value = null
    suggestions.value = []

    const elapsed = existingTask.started_at
      ? Math.floor((Date.now() - new Date(existingTask.started_at).getTime()) / 1000)
      : 0
    startTimer(elapsed)

    if (abortController) abortController.abort()
    abortController = new AbortController()

    try {
      const result = await startAIEventStream(triggerEndpoint, abortController.signal)
      if (result.queued) {
        // Still queued (shouldn't happen here, but handle gracefully)
        status.value = 'queued'
        phase.value = null
        queuePosition.value = result.queuePosition
        stopTimer()
        startPolling()
        return
      }
      await consumeEventStream(result.reader)
    } catch (err: unknown) {
      if (err instanceof Error && err.name === 'AbortError') return
      const errorMsg = err instanceof Error ? err.message : ''
      // 409 means task is running but we can't attach — fall back to polling
      if (errorMsg.includes('409')) {
        showToast(t('aiTask.resuming'))
        startPolling()
      } else {
        status.value = 'failed'
        phase.value = null
        stopTimer()
        stopThinkTimer()
        stopPolling()
      }
    }
  }

  async function checkAndResume() {
    try {
      const task = await getAITask(capability)
      if (task.status === 'running' || task.status === 'post_processing') {
        await resumeStream(task)
      } else if (task.status === 'queued') {
        status.value = 'queued'
        queuePosition.value = task.queue_position ?? null
        taskId.value = task.task_id ?? null
        isConsoleOpen.value = true
        startPolling()
      } else if (task.status === 'completed') {
        status.value = 'completed'
      } else {
        status.value = task.status as AITaskStatus['status']
      }
    } catch {
      // ignore
    }
  }

  async function cancelTask() {
    abortController?.abort()
    abortController = null
    stopTimer()
    stopThinkTimer()
    stopPolling()
    try {
      const res = await cancelAITask(capability)
      if (res.ok) {
        status.value = 'idle'
        phase.value = null
        isConsoleOpen.value = false
        showToast(t('aiTask.cancelled'))
      } else {
        // Task may have completed while we were cancelling — sync actual state
        const task = await getAITask(capability)
        status.value = task.status
        if (task.status === 'completed' && !completedFired) {
          isConsoleOpen.value = false
          completedFired = true
          onComplete?.()
        }
      }
    } catch {
      showToast(t('toast.operationFailed'))
      status.value = 'idle'
      phase.value = null
      stopTimer()
      stopThinkTimer()
      stopPolling()
    }
  }

  // ── Visibility change ──────────────────────────────────────────────────────

  function onVisibilityChange() {
    if (document.hidden) {
      // Disconnect stream on tab hidden
      if (abortController) {
        abortController.abort()
        abortController = null
      }
      stopPolling()
      stopTimer()
      stopThinkTimer()
    } else if (status.value === 'running' || status.value === 'queued' || status.value === 'post_processing') {
      // Resume when tab becomes visible again
      checkAndResume()
    }
  }

  onMounted(async () => {
    await checkAndResume()
    document.addEventListener('visibilitychange', onVisibilityChange)
  })

  onUnmounted(() => {
    abortController?.abort()
    stopTimer()
    stopThinkTimer()
    stopPolling()
    if (postProcessingPollTimer) {
      clearTimeout(postProcessingPollTimer)
      postProcessingPollTimer = null
    }
    document.removeEventListener('visibilitychange', onVisibilityChange)
  })

  return {
    status,
    phase,
    thinkContent,
    thinkDone,
    thinkSeconds,
    answerContent,
    elapsedSeconds,
    taskId,
    sessionId,
    isConsoleOpen,
    queuePosition,
    errorCode,
    toolSteps,
    currentToolLabel,
    suggestions,
    startStream,
    cancelTask,
  }
}
