/**
 * useAITask — 管理单个 capability 的长任务状态和 streaming 接续。
 *
 * 功能：
 * - 页面挂载时查询任务状态，若 running 则接续 streaming
 * - 新建任务时调用 startStream()
 * - 最多保留最后 10 条 chunk（避免浏览器崩溃）
 * - 标题耗时每秒自动累加
 * - visibilitychange：切走时断开，回来时接续
 *
 * resumeStream() 不调用触发端点（避免 409 循环）。
 * 若任务已在运行，显示进度台并轮询任务状态直到完成。
 */
import { onMounted, onUnmounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { showToast } from 'vant'
import { getAITask, startAIStream, cancelAITask, type AITaskStatus } from '@/api/ai'

const MAX_CHUNKS = 10
const POLL_INTERVAL_MS = 3000

export function useAITask(
  capability: string,
  triggerEndpoint: string,
  onComplete?: () => void,
) {
  const { t } = useI18n()

  const status = ref<AITaskStatus['status']>('idle')
  const chunks = ref<string[]>([])
  const elapsedSeconds = ref(0)
  const taskId = ref<string | null>(null)
  const sessionId = ref<string | null>(null)
  const isConsoleOpen = ref(false)

  let abortController: AbortController | null = null
  let timer: ReturnType<typeof setInterval> | null = null
  let pollTimer: ReturnType<typeof setInterval> | null = null
  let startTime: number | null = null
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

  // ── Polling (used when stream cannot be re-attached) ───────────────────────

  function startPolling() {
    if (pollTimer) clearInterval(pollTimer)
    pollTimer = setInterval(async () => {
      try {
        const task = await getAITask(capability)
        if (task.status !== 'running') {
          clearInterval(pollTimer!)
          pollTimer = null
          status.value = task.status
          stopTimer()
          if (task.status === 'completed' && !completedFired) {
            isConsoleOpen.value = false
            completedFired = true
            onComplete?.()
          }
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

  // ── Chunk management ───────────────────────────────────────────────────────

  function appendChunk(text: string) {
    chunks.value.push(text)
    if (chunks.value.length > MAX_CHUNKS) {
      chunks.value.shift()
    }
  }

  // ── Streaming ──────────────────────────────────────────────────────────────

  async function consumeStream(reader: ReadableStreamDefaultReader<Uint8Array>) {
    const decoder = new TextDecoder()
    try {
      while (true) {
        const { done, value } = await reader.read()
        if (done) break
        const text = decoder.decode(value, { stream: true })
        if (text) appendChunk(text)
      }
      status.value = 'completed'
      stopTimer()
      stopPolling()
      isConsoleOpen.value = false
      if (!completedFired) {
        completedFired = true
        onComplete?.()
      }
    } catch (err: unknown) {
      const e = err as { name?: string }
      if (e?.name === 'AbortError') return // user navigated away
      status.value = 'failed'
      stopTimer()
      stopPolling()
    }
  }

  async function startStream() {
    abortController?.abort()
    abortController = new AbortController()
    chunks.value = []
    status.value = 'running'
    isConsoleOpen.value = true
    completedFired = false
    startTimer(0)

    try {
      const reader = await startAIStream(triggerEndpoint, abortController.signal)
      await consumeStream(reader)
    } catch (err: unknown) {
      const e = err as { name?: string; message?: string }
      if (e?.name === 'AbortError') return
      if (e?.message?.includes('409')) {
        // Task already running — show console with elapsed time and poll for completion.
        // Do NOT re-POST to the trigger endpoint — that would create a second task.
        showToast(t('aiTask.inProgress'))
        status.value = 'idle'
        stopTimer()
        await checkAndResume()
      } else {
        status.value = 'failed'
        stopTimer()
      }
    }
  }

  async function resumeStream(existingTask: AITaskStatus) {
    taskId.value = existingTask.task_id ?? null
    sessionId.value = existingTask.session_id ?? null
    status.value = 'running'
    isConsoleOpen.value = true

    // 计算已过去的秒数
    const elapsed = existingTask.started_at
      ? Math.floor((Date.now() - new Date(existingTask.started_at).getTime()) / 1000)
      : 0
    startTimer(elapsed)

    showToast(t('aiTask.resuming'))

    // Poll for completion instead of re-POSTing to the trigger endpoint.
    // Re-POSTing would hit the 409 guard and loop back here indefinitely.
    startPolling()
  }

  async function checkAndResume() {
    try {
      const task = await getAITask(capability)
      if (task.status === 'running') {
        await resumeStream(task)
      } else if (task.status === 'completed') {
        status.value = 'completed'
      } else {
        status.value = task.status
      }
    } catch {
      // ignore
    }
  }

  // ── Cancel task ─────────────────────────────────────────────────────────────

  async function cancelTask() {
    abortController?.abort()
    abortController = null
    stopPolling()
    stopTimer()
    try {
      const res = await cancelAITask(capability)
      if (res.ok) {
        status.value = 'idle'
        isConsoleOpen.value = false
        showToast(t('aiTask.cancelled'))
      } else {
        // Task may have completed while we were cancelling - check actual status
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
    } else if (status.value === 'running') {
      checkAndResume()
    }
  }

  // ── Lifecycle ──────────────────────────────────────────────────────────────

  onMounted(async () => {
    document.addEventListener('visibilitychange', onVisibilityChange)
    await checkAndResume()
  })

  onUnmounted(() => {
    document.removeEventListener('visibilitychange', onVisibilityChange)
    abortController?.abort()
    stopTimer()
    stopPolling()
  })

  return {
    status,
    chunks,
    elapsedSeconds,
    taskId,
    sessionId,
    isConsoleOpen,
    startStream,
    cancelTask,
    checkAndResume,
  }
}
