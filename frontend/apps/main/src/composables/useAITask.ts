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

export function useAITask(
  capability: string,
  triggerEndpoint: string,
  onComplete?: () => void,
) {
  const { t } = useI18n()

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

  let abortController: AbortController | null = null
  let timer: ReturnType<typeof setInterval> | null = null
  let pollTimer: ReturnType<typeof setInterval> | null = null
  let thinkTimer: ReturnType<typeof setInterval> | null = null
  let startTime: number | null = null
  let thinkStartTime: number | null = null
  let completedFired = false

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
    if (pollTimer) clearInterval(pollTimer)
    pollTimer = setInterval(async () => {
      try {
        const task = await getAITask(capability)
        if (task.status === 'queued') {
          queuePosition.value = task.queue_position ?? null
          return
        }
        if (task.status === 'running') {
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
      clearInterval(pollTimer)
      pollTimer = null
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
      case 'capability.end':
        // summary may be in result.summary — already accumulated via token.stream
        break
      case 'capability.error':
        status.value = 'failed'
        phase.value = null
        stopTimer()
        stopThinkTimer()
        break
    }
  }

  // ── Stream consumption ─────────────────────────────────────────────────────

  async function consumeEventStream(reader: ReadableStreamDefaultReader<Uint8Array>) {
    const decoder = new TextDecoder()
    const parser = createAgentEventParser(handleEvent)
    try {
      while (true) {
        const { done, value } = await reader.read()
        if (done) break
        const text = decoder.decode(value, { stream: true })
        if (text) parser.push(text)
      }
      parser.flush()
      status.value = 'completed'
      phase.value = null
      thinkDone.value = true
      stopTimer()
      stopThinkTimer()
      stopPolling()
      isConsoleOpen.value = false
      if (!completedFired) {
        completedFired = true
        onComplete?.()
      }
    } catch (err: unknown) {
      const e = err as { name?: string }
      if (e?.name === 'AbortError') return
      status.value = 'failed'
      phase.value = null
      stopTimer()
      stopThinkTimer()
    }
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
    chunks.value = []
    phase.value = 'connecting'
    status.value = 'running'
    isConsoleOpen.value = true
    completedFired = false
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
      const e = err as { name?: string; message?: string }
      if (e?.name === 'AbortError') return
      if (e?.message?.includes('409')) {
        showToast(t('aiTask.inProgress'))
        status.value = 'idle'
        phase.value = null
        stopTimer()
        await checkAndResume()
      } else {
        status.value = 'failed'
        phase.value = null
        stopTimer()
        stopThinkTimer()
      }
    }
  }

  async function resumeStream(existingTask: AITaskStatus) {
    taskId.value = existingTask.task_id ?? null
    sessionId.value = existingTask.session_id ?? null
    status.value = 'running'
    phase.value = 'connecting'
    isConsoleOpen.value = true

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
      const e = err as { name?: string; message?: string }
      if (e?.name === 'AbortError') return
      // 409 means task is running but we can't attach — fall back to polling
      if (e?.message?.includes('409')) {
        showToast(t('aiTask.resuming'))
        startPolling()
      } else {
        status.value = 'failed'
        phase.value = null
        stopTimer()
        stopThinkTimer()
      }
    }
  }

  async function checkAndResume() {
    try {
      const task = await getAITask(capability)
      if (task.status === 'running') {
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
    }
  }

  // ── Visibility change ──────────────────────────────────────────────────────

  function onVisibilityChange() {
    if (document.hidden) {
      abortController?.abort()
      abortController = null
      stopPolling()
    } else if (status.value === 'running' || status.value === 'queued') {
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
    startStream,
    cancelTask,
  }
}
