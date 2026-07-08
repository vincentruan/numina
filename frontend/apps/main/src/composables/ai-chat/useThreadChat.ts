import { ref, computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { nanoid } from 'nanoid'
import { getClient, createThread, deleteThread } from '@/api/ai-chat'
import type { TokenUsage } from '@/types/ai-chat/session'
import type { ChatMessage, ToolCallSummary, PlanningStep, UsageMetadata } from '@/types/ai-chat/message-group'
import { explainToolCallKey } from '@/utils/ai-chat/tool-icon-map'

export type { ChatMessage }

/**
 * Generate a unique id for an optimistic/temporary chat message.
 *
 * `crypto.randomUUID()` is only available in secure contexts (HTTPS or
 * localhost). The Vite dev server is commonly reached over plain HTTP on a
 * LAN IP (e.g. http://100.72.41.99:5173), where `crypto.randomUUID` is
 * `undefined` — and calling it throws `TypeError: crypto.randomUUID is not
 * a function`. That throw aborts `sendMessage` before the stream starts,
 * leaving the /ai/chat page blank. Fall back to nanoid on non-secure
 * contexts so the dev flow works identically to production (HTTPS).
 */
function genId(prefix: string): string {
  const uuid = typeof crypto !== 'undefined' && typeof crypto.randomUUID === 'function'
    ? crypto.randomUUID()
    : nanoid()
  return `${prefix}-${uuid}`
}

/** A single chunk yielded by client.runs.stream() in legacy SSE mode. */
interface StreamChunk {
  event: string
  data?: unknown
}

/** DeerFlow messages-tuple event data shape (AI text chunk). */
interface AiTextData {
  type: 'ai'
  content: string
  id?: string
  tool_calls?: Array<{ id?: string; name: string; args: string | object }>
  usage_metadata?: Record<string, unknown>
  additional_kwargs?: Record<string, unknown>
}

/** DeerFlow messages-tuple event data shape (Tool result). */
interface ToolResultData {
  type: 'tool'
  content: string
  id?: string
  tool_call_id?: string
  name?: string
}

type MessagesTupleData = AiTextData | ToolResultData

/** Serialized message from DeerFlow values event. */
interface SerializedMessage {
  type?: string
  content?: string
  id?: string
  name?: string
  tool_calls?: Array<{ id?: string; name: string; args: string | object }>
  tool_call_id?: string
  additional_kwargs?: Record<string, unknown>
  usage_metadata?: {
    input_tokens?: number
    output_tokens?: number
    total_tokens?: number
  }
}

/** DeerFlow values event data shape. */
interface ValuesData {
  title?: string
  messages?: SerializedMessage[]
  artifacts?: Array<Record<string, unknown>>
}

/** Format current time as HH:MM */
function formatDisplayTime(): string {
  const now = new Date()
  return `${String(now.getHours()).padStart(2, '0')}:${String(now.getMinutes()).padStart(2, '0')}`
}

/** Parse tool call args to Record<string, unknown> */
function parseArgs(args: string | object): Record<string, unknown> {
  if (typeof args === 'string') {
    try { return JSON.parse(args) } catch { return { _raw: args } }
  }
  return args
}

/**
 * Recover the user's original input text from a backend-stored human message.
 *
 * The agent adapter (server/apps/agent/services/deerflow_adapter/adapter.py
 * `_build_prompt`) wraps the user message as ``[SKILL:chat]\n{json}`` so the
 * DeerFlow harness knows which skill to dispatch. That wrapper is an internal
 * prompt string — it must never be shown to the user. LangGraph persists it as
 * the human message content and replays it via ``values`` events and thread
 * history, so strip the wrapper here and recover ``free_text`` (the user's
 * original text, PII-redacted) for display. If ``free_text`` is empty/missing
 * (e.g. the wrapper arrived without user text), return an empty string rather
 * than leaking the raw JSON to the UI.
 */
function unwrapSkillPrompt(content: string): string {
  const match = content.match(/^\[SKILL:[^\]]+\]\s*\n?([\s\S]*)$/)
  if (!match) return content
  try {
    const ctx = JSON.parse(match[1]) as { free_text?: unknown }
    if (typeof ctx.free_text === 'string' && ctx.free_text.length > 0) {
      return ctx.free_text
    }
  } catch { /* not valid JSON — fall through to empty */ }
  return ''
}

/** Convert DeerFlow tool_calls to ToolCallSummary[] */
function toToolCallSummaries(
  toolCalls: Array<{ id?: string; name: string; args: string | object }>,
): ToolCallSummary[] {
  return toolCalls.map((tc, i) => ({
    id: tc.id || genId('tc'),
    name: tc.name,
    displayName: tc.name,
    args: parseArgs(tc.args),
    status: 'pending' as const,
  }))
}

/** Map a serialized backend message to rich ChatMessage */
function serializedToChatMessage(m: SerializedMessage): ChatMessage {
  const type = m.type === 'human' ? 'human' as const
    : m.type === 'tool' ? 'tool' as const
    : 'ai' as const
  const role = type === 'human' ? 'user' as const : 'assistant' as const

  const rawContent = m.content || ''
  const content = type === 'human' ? unwrapSkillPrompt(rawContent) : rawContent

  const msg: ChatMessage = {
    id: m.id || genId('msg'),
    type,
    role,
    content,
    displayTime: formatDisplayTime(),
    phase: type !== 'human' ? 'done' as const : undefined,
    name: m.name,
    tool_call_id: m.tool_call_id,
    tool_calls: m.tool_calls ? toToolCallSummaries(m.tool_calls) : undefined,
    additional_kwargs: m.additional_kwargs,
  }

  // Extract per-message usage_metadata from values events
  if (m.usage_metadata && (m.usage_metadata.input_tokens != null || m.usage_metadata.output_tokens != null)) {
    msg.usageMetadata = {
      inputTokens: m.usage_metadata.input_tokens ?? 0,
      outputTokens: m.usage_metadata.output_tokens ?? 0,
    }
  }

  return msg
}

export interface UseThreadChatOptions {
  /** Called after stream ends — caller can schedule title refresh */
  onStreamEnd?: (threadId: string) => void
}

export function useThreadChat(options: UseThreadChatOptions = {}) {
  const { t } = useI18n()
  const messages = ref<ChatMessage[]>([])
  const isLoading = ref(false)
  const error = ref<string | null>(null)
  const tokenUsage = ref<TokenUsage | null>(null)
  const planningSteps = ref<PlanningStep[]>([])
  const suggestions = ref<string[]>([])
  const runId = ref<string | null>(null)
  let abortController: AbortController | null = null
  let currentThreadId: string | null = null
  let streamTimeoutId: ReturnType<typeof setTimeout> | null = null
  let retryDelayId: ReturnType<typeof setTimeout> | null = null
  let createdThreadInThisCall = false
  // Distinguishes a user-initiated cancel from a stream timeout/error abort.
  // Timeout and stream errors must be retryable; a user cancel must not be.
  let userCancelled = false

  const STREAM_TIMEOUT_MS = 120_000
  const SSE_RETRY_DELAYS = [1000, 2000, 4000] as const
  const SSE_MAX_RETRIES = SSE_RETRY_DELAYS.length

  /** Expose isStreaming as alias for isLoading */
  const isStreaming = computed(() => isLoading.value)

  function addOptimisticUserMessage(text: string): ChatMessage {
    const msg: ChatMessage = {
      id: genId('msg'),
      type: 'human',
      role: 'user',
      content: text,
      displayTime: formatDisplayTime(),
      sendStatus: 'sending',
    }
    messages.value = [...messages.value, msg]
    return msg
  }

  /**
   * Reactively update an optimistic user message's send status.
   *
   * ``addOptimisticUserMessage`` returns the raw message object, but
   * ``messages.value`` exposes a reactive proxy of it. Mutating the raw object
   * (``userMsg.sendStatus = 'sent'``) updates the underlying data but does NOT
   * call Vue's ``trigger()``, so the "发送中" indicator stays stuck until some
   * unrelated reassignment happens to re-run the computed. Replace the message
   * through the reactive array so watchers/computeds re-run immediately.
   */
  function setUserMsgStatus(id: string, status: 'sending' | 'sent' | 'failed'): void {
    const idx = messages.value.findIndex(m => m.id === id)
    if (idx === -1) return
    messages.value = [
      ...messages.value.slice(0, idx),
      { ...messages.value[idx], sendStatus: status },
      ...messages.value.slice(idx + 1),
    ]
  }

  /**
   * Merge a DeerFlow messages-tuple event.
   *
   * AI text chunks: append to existing AI message with same id, or create new.
   * AI tool calls: attach tool_calls to existing AI message with same id.
   * Tool results: add as separate tool message.
   */
  function mergeMessagesTuple(chunk: MessagesTupleData): void {
    if (chunk.type === 'ai') {
      const last = messages.value[messages.value.length - 1]
      const chunkId = chunk.id

      // If last message is AI with matching id (or both have no id), append text
      if (last && last.type === 'ai' && (!chunkId || chunkId === last.id || !last.id)) {
        const updated: ChatMessage = { ...last }
        updated.content = last.content + chunk.content
        updated.phase = 'answering'
        if (chunkId) updated.id = chunkId
        if (chunk.tool_calls) {
          const newCalls = toToolCallSummaries(chunk.tool_calls)
          updated.tool_calls = [...(last.tool_calls || []), ...newCalls]
        }
        if (chunk.additional_kwargs) {
          updated.additional_kwargs = { ...(last.additional_kwargs || {}), ...chunk.additional_kwargs }
        }
        messages.value = [...messages.value.slice(0, -1), updated]
      } else {
        // New AI message
        const msg: ChatMessage = {
          id: chunkId || genId('ai'),
          type: 'ai',
          role: 'assistant',
          content: chunk.content,
          displayTime: formatDisplayTime(),
          phase: 'answering',
        }
        if (chunk.tool_calls) {
          msg.tool_calls = toToolCallSummaries(chunk.tool_calls)
        }
        if (chunk.additional_kwargs) {
          msg.additional_kwargs = chunk.additional_kwargs
        }
        messages.value = [...messages.value, msg]
      }
    } else if (chunk.type === 'tool') {
      // Tool result message
      const msg: ChatMessage = {
        id: chunk.id || genId('tool'),
        type: 'tool',
        role: 'assistant',
        content: chunk.content,
        displayTime: formatDisplayTime(),
        name: chunk.name,
        tool_call_id: chunk.tool_call_id,
      }
      messages.value = [...messages.value, msg]

      // Update matching tool_call status to 'done' in the previous AI message
      if (chunk.tool_call_id) {
        const aiMsgIdx = messages.value.findLastIndex(
          (m, i) => m.type === 'ai' && i < messages.value.length - 1
            && m.tool_calls?.some(tc => tc.id === chunk.tool_call_id),
        )
        if (aiMsgIdx >= 0) {
          const aiMsg = messages.value[aiMsgIdx]
          const updatedCalls = (aiMsg.tool_calls || []).map(tc =>
            tc.id === chunk.tool_call_id
              ? { ...tc, status: 'success' as const, result: chunk.content }
              : tc,
          )
          messages.value = [
            ...messages.value.slice(0, aiMsgIdx),
            { ...aiMsg, tool_calls: updatedCalls },
            ...messages.value.slice(aiMsgIdx + 1),
          ]
        }
      }
    }
  }

  /**
   * Merge messages from a DeerFlow values event.
   * Values events contain full state snapshots — we deduplicate by id.
   * Also backfills usage_metadata on existing AI messages.
   */
  function mergeValuesMessages(raw: SerializedMessage[]): void {
    if (!raw || raw.length === 0) return
    const mapped = raw.map(serializedToChatMessage)
    const existingIds = new Set(messages.value.map(m => m.id))
    // Skip human messages from values events. sendMessage always creates an
    // optimistic human message with the user's original text before streaming,
    // and that optimistic message is the authoritative display text. The
    // backend persists the human message as a `[SKILL:chat]\n{json}` prompt
    // wrapper (adapter._build_prompt) — an internal prompt string that must
    // never be shown. Including it here would render a duplicate human bubble
    // with the raw JSON. Prior turns' human messages are already in
    // messages.value (from earlier optimistic messages or loadHistory), so
    // skipping human messages only drops the current turn's prompt wrapper.
    const newOnes = mapped.filter(m => !existingIds.has(m.id) && m.type !== 'human')
    if (newOnes.length > 0) {
      messages.value = [...messages.value, ...newOnes]
    }

    // Backfill/refresh usage_metadata on existing AI messages. Values events are
    // authoritative full-state snapshots emitted multiple times per run; a later
    // values event may carry the COMPLETE usage after an earlier one carried
    // partial. Always overwrite with the latest incoming usage (#16) and do it
    // in a single array rebuild instead of one slice per match (#18).
    const usageById = new Map<string, UsageMetadata>()
    for (const m of mapped) {
      if (m.usageMetadata && m.type === 'ai') {
        usageById.set(m.id, m.usageMetadata)
      }
    }
    if (usageById.size > 0) {
      let changed = false
      const next = messages.value.map(msg => {
        const incoming = usageById.get(msg.id)
        if (incoming && msg.type === 'ai' && msg.usageMetadata !== incoming) {
          // Overwrite with the authoritative latest counts (input+output tokens
          // grow as the run progresses; the final values event has the totals).
          const prev = msg.usageMetadata
          if (
            !prev
            || incoming.inputTokens >= prev.inputTokens
            || incoming.outputTokens >= prev.outputTokens
          ) {
            changed = true
            return { ...msg, usageMetadata: incoming }
          }
        }
        return msg
      })
      if (changed) {
        messages.value = next
      }
    }
  }

  /** Create a PlanningStep from a custom tool_call event. */
  function createPlanningStep(customData: {
    tool_call_id?: string
    tool_name?: string
    args?: Record<string, unknown>
  }): PlanningStep {
    const toolName = customData.tool_name || 'unknown'
    return {
      id: customData.tool_call_id || genId('step'),
      toolName,
      args: customData.args || {},
      status: 'running',
      timestamp: Date.now(),
    }
  }

  async function sendMessage(text: string, _mode?: string, threadId?: string): Promise<void> {
    if (isLoading.value) return
    isLoading.value = true
    error.value = null
    planningSteps.value = []
    suggestions.value = []
    runId.value = null
    userCancelled = false
    abortController = new AbortController()

    const userMsg = addOptimisticUserMessage(text)

    // Resolve thread before streaming
    try {
      if (!threadId && !currentThreadId) {
        const thread = await createThread()
        currentThreadId = thread.thread_id
        createdThreadInThisCall = true
      } else if (threadId) {
        currentThreadId = threadId
        createdThreadInThisCall = false
      } else {
        createdThreadInThisCall = false
      }
    } catch (err) {
      const e = err as Error
      setUserMsgStatus(userMsg.id, 'failed')
      error.value = e.message || t('aiChat.sendFailed')
      isLoading.value = false
      return
    }

    // Stream with retry
    let retryCount = 0
    let streamSucceeded = false
    // True once an `end` chunk arrives in the current attempt. Distinguishes a
    // clean stream-end (decide success/failure by content) from a mid-stream
    // drop (decide success by whether we got substantial content). Reset to
    // false at the top of each attempt so a prior iteration's `end` doesn't leak.
    let streamEnded: boolean

    while (!streamSucceeded && retryCount <= SSE_MAX_RETRIES) {
      streamEnded = false
      if (retryCount > 0) {
        // Exponential backoff with jitter to avoid thundering herd on backend
        // recovery (#24). Jitter is bounded to [85%, 100%] of the base delay so
        // the timer always fires no later than the base delay — this keeps retry
        // behavior deterministic enough for tests that advance the exact base
        // delay values (1s/2s/4s) while still desynchronizing concurrent clients.
        const baseDelay = SSE_RETRY_DELAYS[retryCount - 1]
        const jitteredDelay = Math.floor(baseDelay * (0.85 + Math.random() * 0.15))
        await new Promise(resolve => {
          retryDelayId = setTimeout(resolve, jitteredDelay)
        })
        retryDelayId = null
        // If the user cancelled during the delay (or nulled the controller via
        // cancelStream), exit cleanly instead of dereferencing a null controller.
        if (userCancelled || !abortController || abortController.signal.aborted) break
      }

      streamTimeoutId = setTimeout(() => {
        // A timeout abort is NOT a user cancel — the catch block still retries.
        abortController?.abort()
      }, STREAM_TIMEOUT_MS)

      try {
        const client = getClient()

        // Idempotent retry (#2): if we have already streamed content in a prior
        // attempt (partial progress observed server-side), do NOT re-send the
        // user message — that would append a duplicate and re-execute tools.
        // Resume the run instead by passing `input: null`.
        const hasPriorProgress = planningSteps.value.length > 0
          || messages.value.some(m => m.type === 'ai' && m.phase === 'answering')
        const stream = client.runs.stream(currentThreadId as string, 'agent', {
          input: hasPriorProgress ? null : { messages: [{ role: 'user', content: text }] },
          signal: abortController.signal,
          // #17: drop 'events' — the active backend never emits an 'events' frame
          // and there is no handler branch for it; requesting it advertises an
          // unfulfilled contract.
          streamMode: ['messages-tuple', 'values', 'custom'],
        })

        if (!hasPriorProgress) {
          setUserMsgStatus(userMsg.id, 'sent')
        }

        // Clear any error carried over from a prior attempt (#20): an error chunk
        // in attempt N must not persist if attempt N+1 succeeds.
        error.value = null
        // Reset planning steps on retry (#21) so the backend's re-emitted tool_call
        // events don't append duplicates.
        if (retryCount > 0) {
          planningSteps.value = []
        }

        for await (const chunk of stream as AsyncIterable<StreamChunk>) {
          if (chunk.event === 'metadata' && chunk.data) {
            const metaData = chunk.data as { run_id?: string }
            if (metaData.run_id) {
              runId.value = metaData.run_id
            }
          } else if (
            // #1 (P0): the active backend (runs.py:221) emits `event: messages`,
            // while LangGraph Platform wire convention is `messages-tuple`. The
            // SDK's SSEDecoder passes the event name through verbatim, so listen
            // for both to stay correct whichever router serves the request.
            (chunk.event === 'messages-tuple' || chunk.event === 'messages')
            && chunk.data
          ) {
            mergeMessagesTuple(chunk.data as MessagesTupleData)
          } else if (chunk.event === 'values' && chunk.data) {
            const data = chunk.data as ValuesData
            if (data.messages) {
              mergeValuesMessages(data.messages)
            }
          } else if (chunk.event === 'custom' && chunk.data) {
            const customData = chunk.data as {
              type?: string
              tool_call_id?: string
              tool_name?: string
              args?: Record<string, unknown>
              suggestions?: string[]
            }
            if (customData.type === 'tool_call') {
              const step = createPlanningStep(customData)
              // Dedup by tool_call_id across retries (#21): if the backend re-emits
              // the same step, don't append a duplicate.
              const exists = step.id && planningSteps.value.some(s => s.id === step.id)
              if (!exists) {
                planningSteps.value = [...planningSteps.value, step]
              }
            } else if (customData.type === 'suggestions' && customData.suggestions) {
              suggestions.value = customData.suggestions
            }
          } else if (chunk.event === 'end') {
            streamEnded = true
            // worker.py publishes an `end` data frame `{"status": ...}` before
            // the END_SENTINEL. "error" means the agent run threw (LLM failure,
            // API-key decrypt, etc.) — treat as a retryable failure instead of
            // the silent success below, which left the page blank with no AI
            // reply and no error UI (B-end-status).
            let endStatus: string | undefined
            if (chunk.data) {
              const endData = chunk.data as { usage?: TokenUsage; status?: string }
              endStatus = endData.status
              if (endData.usage) {
                tokenUsage.value = endData.usage
              }
            }
            if (endStatus === 'error') {
              throw new Error(t('aiChat.sendFailed'))
            }
            // Mark last AI message as done (attach suggestions if available).
            // #19: an `end` chunk is the backend's completion signal — treat it
            // as success. Truncated-content detection is unreliable from `end`
            // alone (a tool-only turn legitimately ends with no AI text), and
            // duplicate-execution risk on retry is already mitigated by #2
            // (idempotent resume via input:null). Marking the last AI message
            // 'done' only when one exists; absent AI message (tool-only turn
            // with no text yet) is still a clean success.
            const lastIdx = messages.value.findLastIndex(m => m.type === 'ai')
            if (lastIdx >= 0) {
              const last = messages.value[lastIdx]
              const currentSuggestions = suggestions.value.length > 0 ? suggestions.value : undefined
              messages.value = [
                ...messages.value.slice(0, lastIdx),
                {
                  ...last,
                  phase: 'done' as const,
                  suggestions: currentSuggestions ?? last.suggestions,
                },
                ...messages.value.slice(lastIdx + 1),
              ]
            }
            // Mark all planning steps as done
            planningSteps.value = planningSteps.value.map(s => ({ ...s, status: 'done' as const }))
            streamSucceeded = true
            // Notify caller that stream ended (for title refresh)
            if (currentThreadId) {
              options.onStreamEnd?.(currentThreadId)
            }
          } else if (chunk.event === 'error' && chunk.data) {
            // worker.py publishes `{"message": str(exc), "name": error_type}`;
            // accept both `message` and `error` so the toast carries the real
            // backend reason instead of falling back to the generic string.
            const errData = chunk.data as { error?: string; message?: string; name?: string }
            // #20: an `error` chunk is terminal for this attempt. Set the error
            // and throw so the catch block classifies and retries; do NOT let
            // the loop fall through to streamSucceeded=true with a stale error.
            const errMsg = errData.error || errData.message || t('aiChat.sendFailed')
            throw new Error(errMsg)
          }
        }

        // If the stream closed WITHOUT an explicit `end` chunk (network drop
        // mid-stream) but we DID receive substantial AI content, treat it as a
        // completed answer rather than retrying and duplicating it. A clean `end`
        // sets streamSucceeded directly above; this only covers the dropped-
        // connection-after-content case. Truncated/empty content falls through
        // to retry.
        if (!streamSucceeded && streamEnded === false) {
          const lastAi = [...messages.value].reverse().find(m => m.type === 'ai')
          if (lastAi && lastAi.content.trim().length > 0) {
            streamSucceeded = true
          }
        }
      } catch (err) {
        const e = err as Error & { name?: string }
        // #9: distinguish a user-initiated cancel (break, no retry, mark failed)
        // from a timeout/stream error abort (retryable transient failure).
        if (e.name === 'AbortError') {
          if (userCancelled) {
            setUserMsgStatus(userMsg.id, 'failed')
            break
          }
          // Timeout abort — retry like any transient failure.
          retryCount++
          if (retryCount > SSE_MAX_RETRIES) {
            setUserMsgStatus(userMsg.id, 'failed')
            error.value = e.message || t('aiChat.sendFailed')
          }
        } else {
          retryCount++
          if (retryCount > SSE_MAX_RETRIES) {
            setUserMsgStatus(userMsg.id, 'failed')
            error.value = e.message || t('aiChat.sendFailed')
          }
          // Otherwise loop and retry
        }
      } finally {
        if (streamTimeoutId !== null) {
          clearTimeout(streamTimeoutId)
          streamTimeoutId = null
        }
      }
    }

    createdThreadInThisCall = false
    isLoading.value = false
    abortController = null

    // Clean up orphan thread created during this call (only on total failure)
    if (!streamSucceeded && createdThreadInThisCall && currentThreadId) {
      deleteThread(currentThreadId).catch(() => {})
      currentThreadId = null
    }
  }

  function cancelStream() {
    // Mark this as a user-initiated cancel so the retry loop (#9) treats the
    // resulting AbortError as terminal rather than a retryable timeout.
    userCancelled = true
    if (abortController) {
      abortController.abort()
      abortController = null
    }
    if (streamTimeoutId !== null) {
      clearTimeout(streamTimeoutId)
      streamTimeoutId = null
    }
    // Cancel the pending retry-delay timer (#3): otherwise a setTimeout that
    // resolves mid-cancel leaves the loop to dereference a nulled controller.
    if (retryDelayId !== null) {
      clearTimeout(retryDelayId)
      retryDelayId = null
    }
    // Fire-and-forget server-side cancel so the agent run is cleaned up.
    // Pass the real run_id captured from the metadata SSE event; if metadata
    // hasn't arrived yet, skip — the server's SSE disconnect watcher still
    // cancels the run when abortController fires.
    if (currentThreadId && runId.value) {
      const client = getClient()
      client.runs.cancel(currentThreadId, runId.value).catch(() => {})
    }
    isLoading.value = false
    // Mark in-progress planning steps as interrupted
    planningSteps.value = planningSteps.value.map(s =>
      s.status === 'running' ? { ...s, status: 'error' as const } : s,
    )
  }

  async function loadHistory(threadId: string, retries = 1): Promise<void> {
    // Cancel any ongoing stream before loading new history
    cancelStream()

    isLoading.value = true
    error.value = null
    planningSteps.value = []
    suggestions.value = []
    runId.value = null
    currentThreadId = threadId

    for (let attempt = 0; attempt <= retries; attempt++) {
      try {
        const client = getClient()
        const state = await client.threads.getState(threadId)
        const values = state.values as { messages?: SerializedMessage[] } | undefined
        if (values?.messages) {
          // Replace messages entirely for history load
          messages.value = values.messages.map(serializedToChatMessage)
        }
        isLoading.value = false
        return
      } catch (err) {
        const e = err as Error
        if (attempt < retries) continue
        error.value = e.message || t('aiChat.loadSessionFailed')
        isLoading.value = false
      }
    }
  }

  async function retry(threadId?: string): Promise<void> {
    if (isLoading.value) return
    const lastHuman = [...messages.value].reverse().find(m => m.type === 'human')
    if (lastHuman) {
      const lastIdx = messages.value.lastIndexOf(lastHuman)
      messages.value = messages.value.slice(0, lastIdx + 1)
      await sendMessage(lastHuman.content, undefined, threadId || currentThreadId || undefined)
    }
  }

  return {
    messages, isLoading, isStreaming, error, tokenUsage,
    planningSteps, suggestions, runId,
    sendMessage, cancelStream, loadHistory, retry,
  }
}
