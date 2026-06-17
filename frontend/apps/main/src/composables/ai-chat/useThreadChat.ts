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
  toolTimeline?: any[]
  // Process block
  processStatus?: 'running' | 'done' | 'error' | 'interrupted'
  processElapsedMs?: number
  processSteps?: any[]
  planSteps?: any[]
  planSource?: 'explicit' | 'inferred' | null
  processExpanded?: boolean
  suggestions?: string[]
}

export function useThreadChat(messages: Ref<Message[]>) {
  // Use current origin + /api as the base URL for LangGraph endpoints
  const apiUrl = typeof window !== 'undefined' ? `${window.location.origin}/api` : '/api'
  const client = new Client({ apiUrl })

  const asking = ref(false)
  const connecting = ref(false)
  const connectingSeconds = ref(0)
  
  let abortController: AbortController | null = null

  const getThreadHistory = async (threadId: string) => {
    try {
      const state = await client.threads.getState(threadId)
      const stateMessages = state.values?.messages || []
      
      messages.value = stateMessages.map((m: any, i: number) => {
        let role: 'user' | 'assistant' = 'user'
        if (m.type === 'ai' || m.type === 'assistant') role = 'assistant'
        else if (m.type === 'human' || m.type === 'user') role = 'user'
        
        return {
          id: m.id || `msg-${i}`,
          role,
          content: m.content || '',
          phase: 'done',
          sendStatus: 'sent',
          created_at: new Date().toISOString(),
          displayTime: new Date().toLocaleTimeString(),
          // Parse kwargs if needed for thinking or tools
          thinkContent: m.additional_kwargs?.reasoning_content,
        } as Message
      })
    } catch (e) {
      console.error("Failed to fetch thread history:", e)
    }
  }

  const submitRun = async (
    threadId: string, 
    input: any, 
    agentId?: string, 
    aiMsgId?: string,
    onMetadata?: (meta: any) => void,
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
    
    try {
      const configurable: Record<string, any> = {}
      if (options?.deerflow_plan_mode !== undefined) configurable.deerflow_plan_mode = options.deerflow_plan_mode
      if (options?.deerflow_subagent_enabled !== undefined) configurable.deerflow_subagent_enabled = options.deerflow_subagent_enabled
      if (options?.reasoning_effort !== undefined) configurable.reasoning_effort = options.reasoning_effort
      if (options?.deep_think !== undefined) configurable.deep_think = options.deep_think

      const stream = client.runs.stream(
        threadId,
        agentId || 'chat',
        {
          input: { messages: [input] },
          streamMode: ["messages", "values", "updates"],
          config: { configurable }
        },
        { signal: abortController.signal }
      )
      
      connecting.value = false
      let currentAiMsgId: string | null = null
      
      for await (const chunk of stream) {
        if (chunk.event === 'metadata') {
          if (onMetadata) onMetadata(chunk.data)
        } else if (chunk.event === 'messages/partial') {
          const partials = chunk.data as any[]
          
          for (const p of partials) {
            if (p.type === 'ai' || p.type === 'assistant') {
              if (!currentAiMsgId) {
                currentAiMsgId = aiMsgId || p.id || `ai-${Date.now()}`
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
                if (p.content) {
                  messages.value[msgIndex].content += p.content
                }
                // Update thinking content
                if (p.additional_kwargs?.reasoning_content) {
                  messages.value[msgIndex].phase = 'thinking'
                  messages.value[msgIndex].thinkContent = 
                    (messages.value[msgIndex].thinkContent || '') + p.additional_kwargs.reasoning_content
                } else if (messages.value[msgIndex].phase === 'thinking' && p.content) {
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
      
    } catch (e: any) {
      if (e.name === 'AbortError') {
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
