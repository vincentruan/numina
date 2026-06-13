/**
 * useChatInteraction — Shared chat interaction composable
 *
 * DeerFlow-aligned interaction logic shared between AIChatPage and AIReportPage.
 * Handles:
 * - Session management (create, load, history)
 * - Event streaming with normalization
 * - Message rendering with filtering
 * - Process visualization state
 */
import { ref, type Ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { marked } from 'marked'
import DOMPurify from 'dompurify'
import type { AgentEvent, ProcessStep, PlanStep, Artifact, NormalizationState } from '@/types/agent-stream'
import { normalizeAgentEvent } from '@/utils/aiEventNormalizer'
import { filterAIContent } from '@/utils/contentFilter'

// Configure marked for markdown rendering
marked.use({ breaks: true })

export interface ChatMessage {
  id: string
  role: 'user' | 'assistant'
  content: string
  renderedContent?: string
  phase?: 'connecting' | 'thinking' | 'answering' | 'done' | 'error' | 'interrupted'
  displayTime: string
  created_at: string
  // Process visualization
  processSteps?: ProcessStep[]
  processStatus?: 'running' | 'done' | 'error' | 'interrupted'
  processElapsedMs?: number
  reasoningStartTime?: number | null
  // Plan progress
  planSteps?: PlanStep[]
  planSource?: 'explicit' | 'inferred' | null
  // Feedback and suggestions
  feedback?: 1 | -1 | 0
  suggestions?: string[]
  // Artifacts
  artifacts?: Artifact[]
}

export interface UseChatInteractionOptions {
  familyId: string
  userId?: string
  agentId?: string
  deepThink?: Ref<boolean>
  webSearch?: Ref<boolean>
  reasoningEffort?: Ref<'low' | 'high'>
}

export function useChatInteraction(_options: UseChatInteractionOptions) {
  const { t, locale } = useI18n()

  // Core state
  const messages: Ref<ChatMessage[]> = ref([])
  const inputText = ref('')
  const asking = ref(false)
  const connecting = ref(false)
  const connectingSeconds = ref(0)
  const currentSessionId = ref<string | null>(null)
  const abortController: Ref<AbortController | null> = ref(null)

  // Artifact registry
  const sessionArtifacts: Ref<Artifact[]> = ref([])

  // Helper functions
  function formatTime(iso: string): string {
    return new Date(iso).toLocaleTimeString(locale.value, { hour: '2-digit', minute: '2-digit' })
  }

  function renderMarkdown(text: string): string {
    return DOMPurify.sanitize(marked.parse(text) as string)
  }

  function generateMessageId(): string {
    return `msg-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`
  }

  // Create user message
  function createUserMessage(content: string): ChatMessage {
    const now = new Date().toISOString()
    return {
      id: generateMessageId(),
      role: 'user',
      content,
      displayTime: formatTime(now),
      created_at: now,
    }
  }

  // Create assistant message placeholder
  function createAssistantPlaceholder(): ChatMessage {
    const now = new Date().toISOString()
    return {
      id: generateMessageId(),
      role: 'assistant',
      content: '',
      phase: 'connecting',
      displayTime: formatTime(now),
      created_at: now,
      processSteps: [],
      processStatus: 'running',
    }
  }

  // Apply content filter to assistant content
  function applyContentFilter(rawContent: string, userQuestion?: string): string {
    return filterAIContent(rawContent, userQuestion)
  }

  // Get user question from last user message
  function getLastUserQuestion(): string {
    const lastUserMsg = messages.value.filter(m => m.role === 'user').pop()
    return lastUserMsg?.content ?? ''
  }

  // Process streaming event
  function processEvent(
    event: AgentEvent,
    normState: NormalizationState,
    assistantMsg: ChatMessage,
    userQuestion: string
  ): void {
    // Normalize event
    normalizeAgentEvent(event, normState)

    // Sync state to message
    assistantMsg.phase = normState.phase
    assistantMsg.processSteps = [...normState.steps]
    assistantMsg.planSteps = normState.planSteps.length > 0 ? [...normState.planSteps] : undefined
    assistantMsg.planSource = normState.planSource
    assistantMsg.artifacts = [...normState.artifacts]

    // Handle token events
    if (event.type === 'token.stream') {
      const token = event.token ?? ''
      if (event.is_thinking) {
        // Thinking content is in processSteps, no direct content update
      } else {
        // Apply filter to streaming content
        const currentRaw = assistantMsg.content + token
        assistantMsg.content = applyContentFilter(currentRaw, userQuestion)
        assistantMsg.renderedContent = renderMarkdown(assistantMsg.content)
      }
    }

    // Handle phase changes
    if (event.type === 'phase.thinking') {
      if (assistantMsg.reasoningStartTime == null) {
        assistantMsg.reasoningStartTime = Date.now()
      }
    }

    if (event.type === 'phase.answering') {
      assistantMsg.processStatus = 'running'
    }

    // Handle completion
    if (event.type === 'capability.end') {
      assistantMsg.phase = 'done'
      assistantMsg.processStatus = 'done'
      if (event.result?.suggestions?.length) {
        assistantMsg.suggestions = event.result.suggestions
      }
    }

    // Handle error
    if (event.type === 'capability.error') {
      assistantMsg.phase = 'error'
      assistantMsg.content = event.error?.message ?? t('toast.aiChatError')
      assistantMsg.processStatus = 'error'
    }

    // Update artifacts registry
    if (normState.artifacts.length > 0) {
      sessionArtifacts.value = [...normState.artifacts]
    }
  }

  // Abort current stream
  function abortStream(): void {
    if (abortController.value) {
      abortController.value.abort()
      abortController.value = null
    }
    asking.value = false
    connecting.value = false

    // Mark current assistant message as interrupted
    const lastAssistant = messages.value.filter(m => m.role === 'assistant').pop()
    if (lastAssistant && lastAssistant.phase !== 'done' && lastAssistant.phase !== 'error') {
      lastAssistant.phase = 'interrupted'
      lastAssistant.processStatus = 'interrupted'
    }
  }

  // Clear session
  function clearSession(): void {
    messages.value = []
    sessionArtifacts.value = []
    currentSessionId.value = null
    inputText.value = ''
  }

  // Calculate duration from reasoning start
  function calculateReasoningDuration(msg: ChatMessage): number {
    if (msg.reasoningStartTime) {
      return Math.round((Date.now() - msg.reasoningStartTime) / 1000) * 1000
    }
    return msg.processElapsedMs ?? 0
  }

  return {
    // State
    messages,
    inputText,
    asking,
    connecting,
    connectingSeconds,
    currentSessionId,
    sessionArtifacts,
    abortController,

    // Helpers
    formatTime,
    renderMarkdown,
    generateMessageId,
    createUserMessage,
    createAssistantPlaceholder,
    applyContentFilter,
    getLastUserQuestion,
    processEvent,
    abortStream,
    clearSession,
    calculateReasoningDuration,
  }
}