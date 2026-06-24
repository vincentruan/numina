import { ref, computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { getClient, createThread, deleteThread } from '@/api/ai-chat'
import type { TokenUsage } from '@/types/ai-chat/session'
import type { ChatMessage, ToolCallSummary, PlanningStep } from '@/types/ai-chat/message-group'
import { getToolIcon } from '@/utils/ai-chat/tool-icon-map'

export type { ChatMessage }

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

/** Convert DeerFlow tool_calls to ToolCallSummary[] */
function toToolCallSummaries(
  toolCalls: Array<{ id?: string; name: string; args: string | object }>,
): ToolCallSummary[] {
  return toolCalls.map((tc, i) => ({
    id: tc.id || `tc-${Date.now()}-${i}`,
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

  const msg: ChatMessage = {
    id: m.id || `msg-${Date.now()}-${Math.random().toString(36).slice(2, 6)}`,
    type,
    role,
    content: m.content || '',
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
  let createdThreadInThisCall = false

  const STREAM_TIMEOUT_MS = 120_000
  const SSE_RETRY_DELAYS = [1000, 2000, 4000] as const
  const SSE_MAX_RETRIES = SSE_RETRY_DELAYS.length

  /** Expose isStreaming as alias for isLoading */
  const isStreaming = computed(() => isLoading.value)

  function addOptimisticUserMessage(text: string): ChatMessage {
    const msg: ChatMessage = {
      id: `msg-${Date.now()}`,
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
          id: chunkId || `ai-${Date.now()}`,
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
        id: chunk.id || `tool-${Date.now()}`,
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
    const newOnes = mapped.filter(m => !existingIds.has(m.id))
    if (newOnes.length > 0) {
      messages.value = [...messages.value, ...newOnes]
    }

    // Backfill usage_metadata on existing AI messages
    for (const m of mapped) {
      if (m.usageMetadata && m.type === 'ai') {
        const idx = messages.value.findIndex(msg => msg.id === m.id)
        if (idx >= 0 && !messages.value[idx].usageMetadata) {
          messages.value = [
            ...messages.value.slice(0, idx),
            { ...messages.value[idx], usageMetadata: m.usageMetadata },
            ...messages.value.slice(idx + 1),
          ]
        }
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
      id: customData.tool_call_id || `step-${Date.now()}-${Math.random().toString(36).slice(2, 6)}`,
      toolName,
      displayName: toolName,
      icon: getToolIcon(toolName),
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
      userMsg.sendStatus = 'failed'
      error.value = e.message || t('aiChat.sendFailed')
      isLoading.value = false
      return
    }

    // Stream with retry
    let retryCount = 0
    let streamSucceeded = false

    while (!streamSucceeded && retryCount <= SSE_MAX_RETRIES) {
      if (retryCount > 0) {
        const delay = SSE_RETRY_DELAYS[retryCount - 1]
        await new Promise(resolve => setTimeout(resolve, delay))
        if (abortController?.signal.aborted) break
      }

      streamTimeoutId = setTimeout(() => {
        abortController?.abort()
      }, STREAM_TIMEOUT_MS)

      try {
        const client = getClient()
        const stream = client.runs.stream(currentThreadId as string, 'agent', {
          input: { messages: [{ role: 'user', content: text }] },
          signal: abortController.signal,
          streamMode: ['messages-tuple', 'values', 'custom', 'events'],
        })

        userMsg.sendStatus = 'sent'

        for await (const chunk of stream as AsyncIterable<StreamChunk>) {
          if (chunk.event === 'metadata' && chunk.data) {
            const metaData = chunk.data as { run_id?: string }
            if (metaData.run_id) {
              runId.value = metaData.run_id
            }
          } else if (chunk.event === 'messages-tuple' && chunk.data) {
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
              planningSteps.value = [...planningSteps.value, step]
            } else if (customData.type === 'suggestions' && customData.suggestions) {
              suggestions.value = customData.suggestions
            }
          } else if (chunk.event === 'end') {
            if (chunk.data) {
              const endData = chunk.data as { usage?: TokenUsage }
              if (endData.usage) {
                tokenUsage.value = endData.usage
              }
            }
            // Mark last AI message as done (attach suggestions if available)
            const lastIdx = messages.value.findLastIndex(m => m.type === 'ai')
            if (lastIdx >= 0) {
              const last = messages.value[lastIdx]
              const currentSuggestions = suggestions.value.length > 0 ? suggestions.value : undefined
              messages.value = [
                ...messages.value.slice(0, lastIdx),
                { ...last, phase: 'done', suggestions: currentSuggestions ?? last.suggestions },
                ...messages.value.slice(lastIdx + 1),
              ]
            }
            // Mark all planning steps as done
            planningSteps.value = planningSteps.value.map(s => ({ ...s, status: 'done' as const }))
            // Notify caller that stream ended (for title refresh)
            if (currentThreadId) {
              options.onStreamEnd?.(currentThreadId)
            }
          } else if (chunk.event === 'error' && chunk.data) {
            const errData = chunk.data as { error?: string }
            error.value = errData.error || t('aiChat.sendFailed')
          }
        }

        streamSucceeded = true
      } catch (err) {
        const e = err as Error & { name?: string }
        if (e.name === 'AbortError') {
          // User cancelled — don't retry
          userMsg.sendStatus = 'failed'
          break
        }
        retryCount++
        if (retryCount > SSE_MAX_RETRIES) {
          userMsg.sendStatus = 'failed'
          error.value = e.message || t('aiChat.sendFailed')
        }
        // Otherwise loop and retry
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
    if (abortController) {
      abortController.abort()
      abortController = null
    }
    if (streamTimeoutId !== null) {
      clearTimeout(streamTimeoutId)
      streamTimeoutId = null
    }
    // Fire-and-forget server-side cancel so the agent run is cleaned up
    if (currentThreadId) {
      const client = getClient()
      client.runs.cancel(currentThreadId, 'agent').catch(() => {})
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
