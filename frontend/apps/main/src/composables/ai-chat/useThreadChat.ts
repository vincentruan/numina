import { ref, type Ref } from 'vue'
import { Client } from '@langchain/langgraph-sdk'

// ── Types ──────────────────────────────────────────────────────────────────
export interface Message {
  id: string
  role: 'user' | 'assistant'
  content: string
  // Additional fields for Numina UI
  phase?: 'connecting' | 'thinking' | 'answering' | 'done' | 'error' | 'interrupted'
  sendStatus?: 'sending' | 'sent' | 'failed'
  created_at: string
  displayTime: string
  feedback?: 1 | -1 | 0
  // Deep thinking state
  thinkContent?: string
  thinkOpen?: boolean
  thinkDone?: boolean
  thinkSeconds?: number
  reasoningStartTime?: number | null
  thinkManuallyToggled?: boolean
  // Tools
  toolTimeline?: unknown[]
  // Process block
  processStatus?: 'running' | 'done' | 'error' | 'interrupted'
  processElapsedMs?: number
  processSteps?: unknown[]
  planSteps?: unknown[]
  planSource?: 'explicit' | 'inferred' | null
  processExpanded?: boolean
  suggestions?: string[]
}

// LangGraph state values type (partial for our use)
interface LangGraphStateValues {
  messages?: unknown[]
}

interface LangGraphState {
  values?: LangGraphStateValues
}

export function useThreadChat(messages: Ref<Message[]>) {
  // Use current origin + /api as the base URL for LangGraph endpoints
  const apiUrl = typeof window !== 'undefined' ? `${window.location.origin}/api` : '/api'
  const client = new Client({ apiUrl })

  const asking = ref(false)
  const connecting = ref(false)
  const connectingSeconds = ref(0)

  let abortController: AbortController | null = null
  // Track current AI message ID across try/catch boundaries
  let currentAiMsgId: string | null = null

  const getThreadHistory = async (threadId: string) => {
    try {
      const state = await client.threads.getState(threadId) as LangGraphState
      const stateMessages = state.values?.messages || []

      messages.value = stateMessages.map((m: unknown, i: number) => {
        const msg = m as Record<string, unknown>
        let role: 'user' | 'assistant' = 'user'
        if (msg.type === 'ai' || msg.type === 'assistant') role = 'assistant'
        else if (msg.type === 'human' || msg.type === 'user') role = 'user'

        return {
          id: (msg.id as string) || `msg-${i}`,
          role,
          content: (msg.content as string) || '',
          phase: 'done',
          sendStatus: 'sent',
          created_at: new Date().toISOString(),
          displayTime: new Date().toLocaleTimeString(),
          // Parse kwargs if needed for thinking or tools
          thinkContent: (msg.additional_kwargs as Record<string, unknown>)?.reasoning_content as string | undefined,
        } as Message
      })
    } catch (e) {
      console.error("Failed to fetch thread history:", e)
    }
  }

  const submitRun = async (
    threadId: string,
    input: unknown,
    agentId?: string,
    aiMsgId?: string,
    onMetadata?: (meta: unknown) => void,
    options?: {
      deerflow_plan_mode?: boolean,
      deerflow_subagent_enabled?: boolean,
      reasoning_effort?: string,
      deep_think?: boolean
    }
  ) => {
    asking.value = true
    connecting.value = true

    abortController = new AbortController()
    currentAiMsgId = null

    try {
      const configurable: Record<string, unknown> = {}
      if (options?.deerflow_plan_mode !== undefined) configurable.deerflow_plan_mode = options.deerflow_plan_mode
      if (options?.deerflow_subagent_enabled !== undefined) configurable.deerflow_subagent_enabled = options.deerflow_subagent_enabled
      if (options?.reasoning_effort !== undefined) configurable.reasoning_effort = options.reasoning_effort
      if (options?.deep_think !== undefined) configurable.deep_think = options.deep_think

      // LangGraph SDK stream: (threadId, assistantId, options) - 3 args
      // Pass signal at top level for abort handling
      const stream = client.runs.stream(
        threadId,
        agentId || 'chat',
        {
          input: { messages: [input] },
          streamMode: ['messages', 'values', 'updates'],
          config: { configurable },
          signal: abortController.signal
        }
      )

      connecting.value = false

      for await (const chunk of stream) {
        if (chunk.event === 'metadata') {
          if (onMetadata) onMetadata(chunk.data)
        } else if (chunk.event === 'messages/partial') {
          const partials = chunk.data as unknown[]

          for (const p of partials) {
            const partial = p as Record<string, unknown>
            if (partial.type === 'ai' || partial.type === 'assistant') {
              if (!currentAiMsgId) {
                currentAiMsgId = aiMsgId || (partial.id as string) || `ai-${Date.now()}`
                // If it doesn't exist in the array, push it
                if (!messages.value.some(m => m.id === currentAiMsgId)) {
                  messages.value.push({
                    id: currentAiMsgId,
                    role: 'assistant',
                    content: '',
                    phase: 'answering',
                    created_at: new Date().toISOString(),
                    displayTime: new Date().toLocaleTimeString()
                  })
                }
              }

              const msgIndex = messages.value.findIndex(m => m.id === currentAiMsgId)
              if (msgIndex !== -1) {
                // Update content
                if (partial.content) {
                  messages.value[msgIndex].content += partial.content as string
                }
                // Update thinking content
                const additionalKwargs = partial.additional_kwargs as Record<string, unknown> | undefined
                if (additionalKwargs?.reasoning_content) {
                  messages.value[msgIndex].phase = 'thinking'
                  messages.value[msgIndex].thinkContent =
                    (messages.value[msgIndex].thinkContent || '') + (additionalKwargs.reasoning_content as string)
                } else if (messages.value[msgIndex].phase === 'thinking' && partial.content) {
                  messages.value[msgIndex].phase = 'answering'
                  messages.value[msgIndex].thinkDone = true
                }
              }
            }
          }
        } else if (chunk.event === 'error') {
          console.error("Stream error:", chunk.data)
        }
      }

      if (currentAiMsgId) {
        const msgIndex = messages.value.findIndex(m => m.id === currentAiMsgId)
        if (msgIndex !== -1) {
          messages.value[msgIndex].phase = 'done'
          if (messages.value[msgIndex].thinkContent) {
            messages.value[msgIndex].thinkDone = true
          }
        }
      }

    } catch (e: unknown) {
      const error = e as Error & { name?: string }
      if (error.name === 'AbortError') {
        console.log('Stream aborted')
        if (currentAiMsgId) {
          const msgIndex = messages.value.findIndex(m => m.id === currentAiMsgId)
          if (msgIndex !== -1) {
            messages.value[msgIndex].phase = 'interrupted'
          }
        }
      } else {
        console.error('Stream failed:', e)
        if (currentAiMsgId) {
          const msgIndex = messages.value.findIndex(m => m.id === currentAiMsgId)
          if (msgIndex !== -1) {
            messages.value[msgIndex].phase = 'error'
          }
        }
        throw e // Rethrow so AIChatPage can handle it
      }
    } finally {
      asking.value = false
      connecting.value = false
      abortController = null
      currentAiMsgId = null
    }
  }

  const abortStream = () => {
    if (abortController) {
      abortController.abort()
      abortController = null
    }
  }

  return {
    client,
    messages,
    asking,
    connecting,
    connectingSeconds,
    getThreadHistory,
    submitRun,
    abortStream
  }
}
