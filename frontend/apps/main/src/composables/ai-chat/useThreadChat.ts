import { ref } from 'vue'
import { getClient, createThread, deleteThread } from '@/api/ai-chat'
import type { TokenUsage } from '@/types/ai-chat/session'

export interface ChatMessage {
  id: string
  type: 'human' | 'ai' | 'tool'
  content: string
  sendStatus?: 'sending' | 'sent' | 'failed'
  phase?: 'connecting' | 'thinking' | 'answering' | 'done' | 'error' | 'interrupted'
}

/** A single chunk yielded by client.runs.stream(). */
interface StreamChunk {
  event: string
  data?: unknown
}

/** Message payload shape inside `messages` / `values` stream events. */
interface StreamMessage {
  id?: string
  type?: string
  content?: string
}

export function useThreadChat() {
  const messages = ref<ChatMessage[]>([])
  const isLoading = ref(false)
  const error = ref<string | null>(null)
  const tokenUsage = ref<TokenUsage | null>(null)
  let abortController: AbortController | null = null
  let currentThreadId: string | null = null
  let streamTimeoutId: ReturnType<typeof setTimeout> | null = null
  let createdThreadInThisCall = false

  const STREAM_TIMEOUT_MS = 120_000

  function addOptimisticUserMessage(text: string): ChatMessage {
    const msg: ChatMessage = {
      id: `msg-${Date.now()}`,
      type: 'human',
      content: text,
      sendStatus: 'sending',
    }
    messages.value = [...messages.value, msg]
    return msg
  }

  function mergeStreamingChunk(chunk: string): void {
    const last = messages.value[messages.value.length - 1]
    if (last && last.type === 'ai') {
      messages.value = [
        ...messages.value.slice(0, -1),
        { ...last, content: last.content + chunk },
      ]
    } else {
      messages.value = [...messages.value, {
        id: `ai-${Date.now()}`,
        type: 'ai',
        content: chunk,
        phase: 'answering',
      }]
    }
  }

  function mergeValuesMessages(raw: StreamMessage[]): void {
    const mapped = raw.map((m) => ({
      id: m.id || `msg-${Date.now()}`,
      type: m.type === 'human' ? 'human' as const : 'ai' as const,
      content: m.content || '',
      phase: m.type === 'ai' ? 'done' as const : undefined,
    }))
    const existingIds = new Set(messages.value.map(m => m.id))
    const newOnes = mapped.filter(m => !existingIds.has(m.id))
    if (newOnes.length > 0) {
      messages.value = [...messages.value, ...newOnes]
    }
  }

  async function sendMessage(text: string, _mode?: string, threadId?: string): Promise<void> {
    if (isLoading.value) return
    isLoading.value = true
    error.value = null
    abortController = new AbortController()
    streamTimeoutId = setTimeout(() => {
      abortController?.abort()
    }, STREAM_TIMEOUT_MS)

    const userMsg = addOptimisticUserMessage(text)

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

      const client = getClient()
      const stream = client.runs.stream(currentThreadId as string, 'agent', {
        input: { messages: [{ type: 'human', content: text }] },
        signal: abortController.signal,
      })

      userMsg.sendStatus = 'sent'

      for await (const chunk of stream as AsyncIterable<StreamChunk>) {
        if (chunk.event === 'messages' && chunk.data) {
          for (const msg of chunk.data as StreamMessage[]) {
            if (msg.content) {
              mergeStreamingChunk(msg.content)
            }
          }
        } else if (chunk.event === 'values' && chunk.data) {
          const data = chunk.data as { messages?: StreamMessage[] }
          if (data.messages) {
            mergeValuesMessages(data.messages)
          }
        } else if (chunk.event === 'metadata' && chunk.data) {
          tokenUsage.value = chunk.data as TokenUsage
        }
      }
    } catch (err) {
      const e = err as Error & { name?: string }
      if (e.name === 'AbortError') {
        userMsg.sendStatus = 'failed'
      } else {
        userMsg.sendStatus = 'failed'
        error.value = e.message || '发送失败'
      }
      // Clean up orphan thread created during this call
      if (createdThreadInThisCall && currentThreadId) {
        deleteThread(currentThreadId).catch(() => {})
        currentThreadId = null
      }
    } finally {
      createdThreadInThisCall = false
      isLoading.value = false
      abortController = null
      if (streamTimeoutId !== null) {
        clearTimeout(streamTimeoutId)
        streamTimeoutId = null
      }
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
    isLoading.value = false
  }

  async function loadHistory(threadId: string): Promise<void> {
    isLoading.value = true
    error.value = null
    currentThreadId = threadId

    try {
      const client = getClient()
      const state = await client.threads.getState(threadId)
      const values = state.values as { messages?: StreamMessage[] } | undefined
      if (values?.messages) {
        mergeValuesMessages(values.messages)
      }
    } catch (err) {
      const e = err as Error
      error.value = e.message || '加载历史记录失败'
    } finally {
      isLoading.value = false
    }
  }

  async function retry(threadId?: string): Promise<void> {
    const lastHuman = [...messages.value].reverse().find(m => m.type === 'human')
    if (lastHuman) {
      const lastIdx = messages.value.lastIndexOf(lastHuman)
      messages.value = messages.value.slice(0, lastIdx + 1)
      await sendMessage(lastHuman.content, undefined, threadId || currentThreadId || undefined)
    }
  }

  return {
    messages, isLoading, error, tokenUsage,
    sendMessage, cancelStream, loadHistory, retry,
  }
}
