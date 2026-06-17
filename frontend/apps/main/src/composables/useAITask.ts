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
 * - 支持后台执行（background）：任务开始后立即返回，不阻塞 UI
 * - visibilitychange：切走时断开，回来时接续
 * - 弹性输出：Phase 1 成功时记录 markdown_file_path，Phase 2 失败时可回退
 *
 * resumeStream() 不调用触发端点（避免 409 循环）。
 */
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { showToast, showFailToast } from 'vant'
import { useAIStore } from '@/stores/ai'
import { refreshTokenIfNeeded } from '@/api'
import {
  getAITask,
  startAIEventStream,
  cancelAITask,
  type AITaskStatus,
} from '@/api/ai'
import { createAgentEventParser } from '@/composables/useAgentEventStream'
import type { AgentEvent, PlanStep } from '@/types/agent-stream'

const POLL_INTERVAL_MS = 3000
const COOKIE_REFRESH_INTERVAL_MS = 10 * 60 * 1000 // 10 minutes (< 15 min token TTL)

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

export interface StartStreamOptions {
  /** Background mode: start task and return immediately without blocking UI */
  background?: boolean
  /** Callback when Phase 1 succeeds with markdown file path (for elastic fallback) */
  onMarkdownGenerated?: (path: string) => void
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
  const planSteps = ref<PlanStep[]>([])
  const markdownFilePath = ref<string | null>(null)  // Phase 1 success marker for elastic fallback
  const isBackground = ref(false)  // Track if running in background mode

  const currentStepIndex = computed(() => {
    const activeIdx = planSteps.value.findIndex((s) => s.status === 'active')
    if (activeIdx >= 0) return activeIdx
    const pendingIdx = planSteps.value.findIndex((s) => s.status === 'pending')
    if (pendingIdx >= 0) return pendingIdx
    const doneCount = planSteps.value.filter((s) => s.status === 'done').length
    if (doneCount === planSteps.value.length && doneCount > 0) return doneCount - 1
    return 0
  })

  const totalSteps = computed(() => planSteps.value.length)

  let abortController: AbortController | null = null
  let timer: ReturnType<typeof setInterval> | null = null
  let pollTimer: ReturnType<typeof setInterval> | null = null
  let thinkTimer: ReturnType<typeof setInterval> | null = null
  let cookieRefreshTimer: ReturnType<typeof setInterval> | null = null
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

  // ── Proactive cookie refresh during long SSE ────────────────────────────────
  // Access tokens expire in 15 minutes. Long-running SSE operations may exceed this.
  // Proactive refresh every 10 minutes keeps cookies fresh for post-stream API calls.

  function startCookieRefresh() {
    if (cookieRefreshTimer) clearInterval(cookieRefreshTimer)
    cookieRefreshTimer = setInterval(async () => {
      try {
        await refreshTokenIfNeeded()
      } catch {
        // Silently ignore - next API call will handle 401 if truly expired
      }
    }, COOKIE_REFRESH_INTERVAL_MS)
  }

  function stopCookieRefresh() {
    if (cookieRefreshTimer) {
      clearInterval(cookieRefreshTimer)
      cookieRefreshTimer = null
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

  function handleEvent(event: AgentEvent, options?: StartStreamOptions) {
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
          const rawName = event.tool.name || ''
          const rawDisplay = event.tool.display_name || ''
          const rawIcon = event.tool.icon || ''
          const displayKey = event.tool.display_key || ''
          const hasSpecificLabel = !!(rawDisplay || rawName)
          // Use i18n key if available, otherwise fall back to display_name
          const resolvedDisplay = displayKey
            ? t(`toolName.${displayKey.replace('toolName.', '')}`)
            : rawDisplay || rawName || t('aiTask.toolProcessing')
          const step: ToolStep = {
            id: event.tool.id,
            name: rawName,
            displayName: resolvedDisplay,
            icon: rawIcon === 'tool' || !rawIcon ? '⚙️' : rawIcon,
            toolType: event.tool.tool_type,
            status: 'running',
          }
          toolSteps.value = [...toolSteps.value, step]
          // Only update header label for tools with a specific name
          currentToolLabel.value = hasSpecificLabel ? step.displayName : null
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
      case 'capability.end': {
        // Capture markdown file path from result (for elastic fallback)
        // result.data may contain path info, cast as Record<string, unknown>
        const resultData = event.result?.data as Record<string, unknown> | undefined
        const resultPath = resultData?.path as string | undefined
        if (resultPath) {
          markdownFilePath.value = resultPath
          // Update background task registry
          if (isBackground.value && taskId.value) {
            aiStore.updateBackgroundTask(capability, { markdownFilePath: resultPath })
          }
          // Notify callback for immediate use
          if (options?.onMarkdownGenerated) {
            options.onMarkdownGenerated(resultPath)
          }
        }
        if (event.result?.suggestions?.length) {
          suggestions.value = event.result.suggestions
        }
        // Mark all plan steps done on completion
        if (planSteps.value.length) {
          planSteps.value = planSteps.value.map((s) =>
            s.status !== 'done' ? { ...s, status: 'done' as const } : s,
          )
        }
        break
      }
      case 'state.snapshot': {
        // Backend may emit state.snapshot when transitioning from Phase 1 to Phase 2
        // Captures markdown_file_path for elastic fallback
        const metadata = event.metadata as Record<string, unknown> | undefined
        if (metadata?.markdown_file_path) {
          markdownFilePath.value = metadata.markdown_file_path as string
          if (isBackground.value && taskId.value) {
            aiStore.updateBackgroundTask(capability, {
              markdownFilePath: metadata.markdown_file_path as string,
            })
          }
          if (options?.onMarkdownGenerated) {
            options.onMarkdownGenerated(metadata.markdown_file_path as string)
          }
        }
        break
      }
      case 'plan.update':
        if (event.todos?.length) {
          planSteps.value = event.todos.map((todo) => ({
            id: todo.id,
            label: todo.content,
            status: (todo.status === 'in_progress' ? 'active' : todo.status === 'done' || todo.status === 'completed' ? 'done' : 'pending') as PlanStep['status'],
          }))
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
        // Clear running state so UI shows failure cleanly (no stale "处理中" badges)
        toolSteps.value = toolSteps.value.map((s) =>
          s.status === 'running' ? { ...s, status: 'error' as const } : s,
        )
        currentToolLabel.value = null
        // Mark all pending/active plan steps as done so progress bar stops
        if (planSteps.value.length) {
          planSteps.value = planSteps.value.map((s) =>
            s.status === 'active' || s.status === 'pending' ? { ...s, status: 'done' as const } : s,
          )
        }
        // Update background task registry
        if (isBackground.value && taskId.value) {
          aiStore.updateBackgroundTask(capability, { status: 'failed' })
        }
        // do NOT call onComplete() — task did not actually finish
        break
    }
  }

  // ── Stream consumption ─────────────────────────────────────────────────────

  async function consumeEventStream(
    reader: ReadableStreamDefaultReader<Uint8Array>,
    options?: StartStreamOptions,
  ) {
    const decoder = new TextDecoder()
    const parser = createAgentEventParser((event) => handleEvent(event, options))
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
      stopCookieRefresh()
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
      stopCookieRefresh()
      // Update background task registry
      if (isBackground.value && taskId.value) {
        aiStore.updateBackgroundTask(capability, { status: 'failed' })
      }
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
          // Update background task registry
          if (isBackground.value && taskId.value) {
            aiStore.updateBackgroundTask(capability, { status: 'completed' })
          }
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
          stopThinkTimer()
          // Clear running state so UI shows failure cleanly
          currentToolLabel.value = null
          toolSteps.value = toolSteps.value.map((s) =>
            s.status === 'running' || s.status === 'pending' ? { ...s, status: 'error' as const } : s,
          )
          // Update background task registry
          if (isBackground.value && taskId.value) {
            aiStore.updateBackgroundTask(capability, { status: task.status })
          }
          return
        }
        // running / post_processing → keep polling
        // Update background task registry with current status
        if (isBackground.value && taskId.value) {
          aiStore.updateBackgroundTask(capability, { status: task.status })
        }
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
    // Clear running state so UI shows failure cleanly
    currentToolLabel.value = null
    toolSteps.value = toolSteps.value.map((s) =>
      s.status === 'running' || s.status === 'pending' ? { ...s, status: 'error' as const } : s,
    )
    // Update background task registry
    if (isBackground.value && taskId.value) {
      aiStore.updateBackgroundTask(capability, { status: 'failed' })
    }
  }

  // ── Start stream ───────────────────────────────────────────────────────────

  async function startStream(options?: StartStreamOptions) {
    if (abortController) abortController.abort()
    abortController = new AbortController()

    const backgroundMode = options?.background ?? false
    isBackground.value = backgroundMode

    // Reset state
    thinkContent.value = ''
    answerContent.value = ''
    thinkDone.value = false
    thinkSeconds.value = 0
    elapsedSeconds.value = 0 // Explicit reset before startTimer
    errorCode.value = null
    phase.value = 'connecting'
    status.value = 'running'
    markdownFilePath.value = null
    completedFired = false
    toolSteps.value = []
    currentToolLabel.value = null
    suggestions.value = []
    planSteps.value = []
    startTimer(0)
    startCookieRefresh() // Keep auth fresh during long SSE operations

    // Background mode: don't force console open, let user navigate away
    if (!backgroundMode) {
      isConsoleOpen.value = true
    }

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
        // Register background task
        aiStore.registerBackgroundTask({
          capability,
          taskId: result.taskId,
          sessionId: '', // Will be updated when task starts
          startedAt: new Date().toISOString(),
          status: 'queued',
        })
        if (backgroundMode) {
          showToast(t('aiReport.taskQueued'))
        }
        return
      }

      // Register background task immediately after stream starts
      // Note: taskId is only available when queued=true; for non-queued streams, taskId remains null
      // and will be populated by backend events if needed
      if (backgroundMode) {
        // taskId.value is set earlier from queued case; for non-queued, use sessionId as fallback identifier
        const effectiveId = taskId.value || sessionId.value || ''
        aiStore.registerBackgroundTask({
          capability,
          taskId: effectiveId,
          sessionId: sessionId.value ?? '',
          startedAt: new Date().toISOString(),
          status: 'running',
        })
        showToast(t('aiReport.taskStarted'))
        // In background mode, we still consume the stream but allow navigation
        // The stream will be aborted on visibilitychange or unmount
      }

      await consumeEventStream(result.reader, options)
    } catch (err: unknown) {
      if (err instanceof Error && err.name === 'AbortError') return
      const errorMsg = err instanceof Error ? err.message : ''
      if (errorMsg.includes('409')) {
        // User explicitly triggered start — cancel stale task first, then retry fresh
        try {
          await cancelAITask(capability)
        } catch (cancelErr) {
          // Log but don't block retry — the stale task may already be completed/cancelled
          console.warn('[useAITask] cancelAITask failed on 409:', cancelErr)
        }
        // Retry starting stream (non-recursive via flag)
        retryAfterCancel = true
      } else {
        status.value = 'failed'
        phase.value = null
        stopTimer()
        stopThinkTimer()
        stopPolling()
        stopCookieRefresh()
        if (isBackground.value && taskId.value) {
          aiStore.updateBackgroundTask(capability, { status: 'failed' })
        }
      }
    }
  }

  // Retry flag for 409 handling — avoids recursive call stack
  let retryAfterCancel = false

  async function startStreamWrapper(options?: StartStreamOptions) {
    retryAfterCancel = false
    await startStream(options)
    // Handle 409 retry with bounded attempts (max 2 retries to avoid infinite loops)
    let retryCount = 0
    while (retryAfterCancel && retryCount < 2) {
      retryAfterCancel = false // Reset flag before retry
      await startStream(options)
      retryCount++
    }
    // If still flagged after max retries, set failed status
    if (retryAfterCancel) {
      status.value = 'failed'
      phase.value = null
      stopTimer()
      stopThinkTimer()
      stopPolling()
      stopCookieRefresh()
      if (isBackground.value && taskId.value) {
        aiStore.updateBackgroundTask(capability, { status: 'failed' })
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
    planSteps.value = []

    const elapsed = existingTask.started_at
      ? Math.floor((Date.now() - new Date(existingTask.started_at).getTime()) / 1000)
      : 0
    startTimer(elapsed)
    startCookieRefresh() // Keep auth fresh during resumed SSE operations

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
        stopCookieRefresh()
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
    stopCookieRefresh()
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
      showFailToast(t('toast.operationFailed'))
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
      stopCookieRefresh()
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
    stopCookieRefresh()
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
    planSteps,
    currentStepIndex,
    totalSteps,
    markdownFilePath,
    isBackground,
    startStream: startStreamWrapper,
    cancelTask,
  }
}
