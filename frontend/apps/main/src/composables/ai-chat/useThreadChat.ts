import { ref, computed, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { showFailToast, showSuccessToast, showToast } from 'vant'
import { nanoid } from 'nanoid'
import {
  getClient,
  createThread,
  deleteThread,
  compactThread,
  getThreadGoal,
  setThreadGoal,
  clearThreadGoal,
} from '@/api/ai-chat'
import type { GoalState } from '@/api/ai-chat'
import { submitMessageFeedback, getSessionFeedback } from '@/api/sessions'
import type { TokenUsage } from '@/types/ai-chat/session'
import type { ChatMessage, ToolCallSummary, PlanningStep, UsageMetadata } from '@/types/ai-chat/message-group'
import { useUpdateSubtask } from '@/composables/ai-chat/useSubtasks'
import { useChatSessionStore } from '@/stores/chatSession'

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
  /** DeerFlow ClarificationMiddleware attaches ``artifact.human_input``. */
  artifact?: Record<string, unknown>
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
  /** DeerFlow ClarificationMiddleware attaches ``artifact.human_input``. */
  artifact?: Record<string, unknown>
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
  // U7 (D5 TodoList): todos channel from TodoMiddleware's write_todos tool.
  // Items are {content, status} (no id) — keyed by index+content in the UI.
  todos?: Array<{ content: string; status: string }>
  // U5 (D1 /goal): goal channel from the checkpoint's channel_values["goal"].
  // `undefined` when a values chunk omits the goal field (do NOT treat as
  // clear — see useActiveGoal); `null` when the server explicitly reports no
  // goal; a GoalState otherwise. U4's auto-continuation loop bumps
  // continuation_count / updated_at here.
  goal?: GoalState | null
}

// ---------------------------------------------------------------------------
// U5 (D1 /goal) — parseGoalCommand, ported from DeerFlow
// input-box-helpers.ts:171-186. Module-level pure function so it can be unit
// tested in isolation. Three-state branch: set / status / clear.
// ---------------------------------------------------------------------------

export type GoalCommand =
  | { kind: 'status' }
  | { kind: 'clear' }
  | { kind: 'set'; objective: string }

/**
 * Parse a `/goal ...` slash command into a three-state branch. Returns `null`
 * when the input is not a `/goal` command. Ported from DeerFlow
 * `parseGoalCommand` (input-box-helpers.ts:171-186).
 *
 * - `/goal` (no args) → `{ kind: 'status' }` (GET + toast)
 * - `/goal clear` | `/goal reset` | `/goal off` → `{ kind: 'clear' }` (DELETE)
 * - `/goal <condition>` → `{ kind: 'set', objective }` (PUT + submit)
 */
export function parseGoalCommand(value: string): GoalCommand | null {
  const trimmed = value.trim()
  const match = /^\/goal(?:\s+|$)/i.exec(trimmed)
  if (!match) {
    return null
  }

  const args = trimmed.slice(match[0].length).trim()
  if (!args) {
    return { kind: 'status' }
  }
  if (['clear', 'reset', 'off'].includes(args.toLowerCase())) {
    return { kind: 'clear' }
  }
  return { kind: 'set', objective: args }
}

/**
 * Clarification request payload from DeerFlow's ``ClarificationMiddleware``.
 *
 * DeerFlow's ``ask_clarification`` tool is intercepted by
 * ``ClarificationMiddleware`` (always last in ``build_middlewares()``) which
 * returns ``Command(goto=END)`` with a ``ToolMessage(artifact={"human_input":
 * payload})``. The adapter preserves the ``artifact`` field (see
 * ``sync_tool_patch._apply_clarification_artifact_patch``) so the frontend can
 * extract the structured request and render an interactive clarification card.
 * The user's answer is sent back as a NEW ``HumanMessage`` carrying
 * ``additional_kwargs.human_input_response`` (DeerFlow pattern) - not via a
 * resume endpoint.
 *
 * Mirrors DeerFlow's ``HumanInputRequest`` (core/messages/human-input.ts).
 */
export interface InterruptData {
  question: string
  options?: Array<{ id: string; label: string; value: string }>
  context?: string
  /** Derived from ``input_mode === 'choice_with_other'``. */
  choiceWithOther?: boolean
  input_mode?: 'free_text' | 'single_choice' | 'choice_with_other'
  /** DeerFlow ``request_id`` - used to match ``human_input_response``. */
  interrupt_id: string
  source?: string
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
  return args as Record<string, unknown>
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

// ---------------------------------------------------------------------------
// U6 transient bridge — ported from DeerFlow hooks.ts:441-545,1277-1322.
//
// When the backend summarizes context (RemoveMessage(ALL) + summary_text +
// preserved tail), a subsequent `values` event carries a SHORTER messages
// list. Until canonical history (loadHistory / next values) confirms the
// summarized state, the UI would otherwise still show the soon-to-be-dropped
// turns — or flicker if we naively replaced `messages`. The transient bridge
// rescues those turns so `visibleMessages` keeps the full conversation until
// canonical history catches up, then prunes confirmed entries.
// ---------------------------------------------------------------------------

/**
 * Stable identity for a chat message, mirroring DeerFlow `messageIdentity`.
 * Tool messages key off `tool_call_id` (one result per call); everything else
 * keys off `id`. Returns undefined for identity-less messages so callers can
 * skip them (overlaying those would risk permanent duplicates).
 */
function messageIdentity(message: ChatMessage): string | undefined {
  if (typeof message.tool_call_id === 'string' && message.tool_call_id.length > 0) {
    return `tool:${message.tool_call_id}`
  }
  if (typeof message.id === 'string' && message.id.length > 0) {
    return `message:${message.id}`
  }
  return undefined
}

function isNonEmptyString(value: string | undefined): value is string {
  return typeof value === 'string' && value.length > 0
}

/**
 * Whether a message should be hidden from the UI (control / summary messages).
 * Mirrors DeerFlow `isHiddenFromUIMessage`. numina marks hidden continuation
 * messages via `additional_kwargs.hide_from_ui` (U4 goal-continuation) and
 * names summary control messages `summary`.
 */
function isHiddenFromUiMessage(message: ChatMessage): boolean {
  if (message.additional_kwargs?.hide_from_ui === true) return true
  if (typeof message.name === 'string' && message.name === 'summary') return true
  return false
}

/**
 * Derive the live turns that context summarization is about to drop and that
 * therefore need a short-lived visual bridge until canonical history catches
 * up. Ported from DeerFlow `computeSummarizationTransientMessages`.
 *
 * Summarization emits RemoveMessage(ALL) + a hidden summary + the retained
 * tail. Everything in the current live thread before the first retained
 * visible message is being removed; we keep those (minus ids already
 * summarized in a prior pass) so the UI can still show the full conversation.
 */
function computeSummarizationTransientMessages(
  currentMessages: ChatMessage[],
  summarizationMessages: ChatMessage[],
  summarizedIds: ReadonlySet<string>,
): ChatMessage[] {
  const firstRetainedVisibleIdentity = summarizationMessages
    .filter(m => !isHiddenFromUiMessage(m))
    .map(messageIdentity)
    .find(isNonEmptyString)

  const moved: ChatMessage[] = []
  for (const message of currentMessages) {
    if (
      firstRetainedVisibleIdentity
      && messageIdentity(message) === firstRetainedVisibleIdentity
    ) {
      break
    }
    if (!summarizedIds.has(message.id)) {
      moved.push(message)
    }
  }
  return moved
}

/**
 * Overlay messages rescued from context summarization on top of the (possibly
 * stale) visible history so the merged view never drops them. Ported from
 * DeerFlow `resolveTransientHistoryBridge`. Canonical history copies always
 * win; identity-less rescued turns are skipped (no stable anchor → dedupe risk).
 */
function resolveTransientHistoryBridge(
  visibleHistory: ChatMessage[],
  transientMessages: ChatMessage[],
  bridgeOrder: readonly string[] = transientMessages
    .map(messageIdentity)
    .filter(isNonEmptyString),
): ChatMessage[] {
  if (transientMessages.length === 0) {
    return visibleHistory
  }
  const presentIdentities = new Set(
    visibleHistory.map(messageIdentity).filter(isNonEmptyString),
  )
  const missing = transientMessages.filter(m => {
    const identity = messageIdentity(m)
    return identity !== undefined && !presentIdentities.has(identity)
  })
  if (missing.length === 0) {
    return visibleHistory
  }

  const missingByIdentity = new Map<string, ChatMessage>()
  for (const m of missing) {
    const identity = messageIdentity(m)
    if (identity) missingByIdentity.set(identity, m)
  }

  const beforeAnchor = new Map<string, ChatMessage[]>()
  const emittedMissingIdentities = new Set<string>()
  let pending: ChatMessage[] = []
  let lastAnchorIdentity: string | undefined
  let hasCanonicalAnchor = false

  for (const identity of bridgeOrder) {
    if (presentIdentities.has(identity)) {
      if (pending.length > 0 && hasCanonicalAnchor) {
        beforeAnchor.set(identity, [
          ...(beforeAnchor.get(identity) ?? []),
          ...pending,
        ])
      }
      pending = []
      hasCanonicalAnchor = true
      lastAnchorIdentity = identity
      continue
    }
    const message = missingByIdentity.get(identity)
    if (message && !emittedMissingIdentities.has(identity)) {
      pending.push(message)
      emittedMissingIdentities.add(identity)
    }
  }

  // No bridge identity overlaps canonical history — the rescued live turns
  // belong after the currently-loaded (older) history.
  if (!lastAnchorIdentity) {
    return [...visibleHistory, ...missing]
  }

  // Trailing candidates with no anchor keep their capture order at the tail.
  for (const m of missing) {
    const identity = messageIdentity(m)
    if (identity && !emittedMissingIdentities.has(identity)) {
      pending.push(m)
      emittedMissingIdentities.add(identity)
    }
  }

  const resolved: ChatMessage[] = []
  for (const message of visibleHistory) {
    const identity = messageIdentity(message)
    if (identity) {
      resolved.push(...(beforeAnchor.get(identity) ?? []))
    }
    resolved.push(message)
    if (identity === lastAnchorIdentity) {
      resolved.push(...pending)
    }
  }
  return resolved
}

/**
 * Drop bridge entries once canonical history confirms their stable identities.
 * Ported from DeerFlow `pruneConfirmedTransientMessages`. Identity-less
 * entries are retained (cannot be matched → cannot be safely drained here).
 */
function pruneConfirmedTransientMessages(
  transientMessages: ChatMessage[],
  visibleHistory: ChatMessage[],
): ChatMessage[] {
  if (transientMessages.length === 0) {
    return transientMessages
  }
  const confirmedIdentities = new Set(
    visibleHistory.map(messageIdentity).filter(isNonEmptyString),
  )
  return transientMessages.filter(m => {
    const identity = messageIdentity(m)
    return !identity || !confirmedIdentities.has(identity)
  })
}

/** Convert DeerFlow tool_calls to ToolCallSummary[] */
function toToolCallSummaries(
  toolCalls: Array<{ id?: string; name: string; args: string | object }>,
): ToolCallSummary[] {
  return toolCalls.map((tc, _i) => ({
    id: tc.id || genId('tc'),
    name: tc.name,
    displayName: tc.name,
    args: parseArgs(tc.args),
    status: 'pending' as const,
  }))
}

/**
 * Extract a clarification request from a ``ToolMessage.artifact.human_input``.
 *
 * DeerFlow's ``ClarificationMiddleware`` intercepts ``ask_clarification`` and
 * returns a ``ToolMessage`` whose ``artifact`` carries the structured
 * ``human_input`` payload (version/kind/source/request_id/question/input_mode/
 * options). This helper parses that payload into the frontend's ``InterruptData``
 * shape so ``MessageGroup`` can render a ``HumanInputCard`` and
 * ``submitClarification`` can build a matching ``human_input_response``.
 *
 * Returns ``null`` when the artifact is absent or malformed (non-clarification
 * tool messages, or older backends without the artifact-preservation patch).
 */
function extractHumanInputFromArtifact(artifact: unknown): InterruptData | null {
  if (typeof artifact !== 'object' || artifact === null) return null
  const humanInput = (artifact as Record<string, unknown>).human_input
  if (typeof humanInput !== 'object' || humanInput === null) return null
  const h = humanInput as Record<string, unknown>
  if (h.kind !== 'human_input_request') return null
  if (typeof h.question !== 'string' || typeof h.request_id !== 'string') return null

  const inputMode = h.input_mode as InterruptData['input_mode']
  const options = Array.isArray(h.options)
    ? h.options
        .map((o): { id: string; label: string; value: string } | null => {
          if (typeof o !== 'object' || o === null) return null
          const rec = o as Record<string, unknown>
          if (typeof rec.id !== 'string' || typeof rec.label !== 'string' || typeof rec.value !== 'string') return null
          return { id: rec.id, label: rec.label, value: rec.value }
        })
        .filter((o): o is { id: string; label: string; value: string } => o !== null)
    : undefined

  return {
    question: h.question,
    options: options && options.length > 0 ? options : undefined,
    context: typeof h.context === 'string' ? h.context : undefined,
    choiceWithOther: inputMode === 'choice_with_other',
    input_mode: inputMode,
    interrupt_id: h.request_id,
    source: typeof h.source === 'string' ? h.source : undefined,
  }
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

  // DeerFlow ClarificationMiddleware: extract human_input from ToolMessage.artifact
  // so MessageGroup can render a HumanInputCard. The artifact is preserved by the
  // adapter's sync_tool_patch (_apply_clarification_artifact_patch).
  if (type === 'tool' && m.name === 'ask_clarification') {
    const interruptData = extractHumanInputFromArtifact(m.artifact)
    if (interruptData) {
      msg.additional_kwargs = { ...(msg.additional_kwargs || {}), interruptData }
    }
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
  const { handleTaskEvent } = useUpdateSubtask()
  const messages = ref<ChatMessage[]>([])
  const isLoading = ref(false)
  const error = ref<string | null>(null)
  const tokenUsage = ref<TokenUsage | null>(null)
  const planningSteps = ref<PlanningStep[]>([])
  const suggestions = ref<string[]>([])
  // U7 (D5 TodoList): todos written by the agent via write_todos. Single source
  // of truth; useThreadTodos derives hasTodos/todos from this. Cleared on
  // thread switch / history reload; hydrated from values events (stream + load).
  const todos = ref<Array<{ content: string; status: string }>>([])
  // U5 (D1 /goal): server goal streamed from the checkpoint's
  // channel_values["goal"] (U4 writes continuation_count/updated_at here).
  // `undefined` = no values chunk has carried the goal field yet (useActiveGoal
  // must NOT treat this as a clear); `null` = server explicitly reports no goal;
  // a GoalState otherwise. Cleared on thread switch / history reload and
  // re-hydrated from state.values.goal (loadHistory) + values events (stream).
  const serverGoal = ref<GoalState | null | undefined>(undefined)
  /**
   * Clarification request IDs that have been answered by the user.
   *
   * Derived from the message history (DeerFlow ``deriveHumanInputThreadState``
   * pattern): a human message carrying ``additional_kwargs.human_input_response``
   * with a ``request_id`` marks that request as answered. This survives page
   * refresh (``loadHistory`` replays the hidden response message) and doesn't
   * require manual bookkeeping in ``submitClarification``.
   *
   * Used by MessageGroup to transition HumanInputCard from 'pending' to
   * 'answered'. getMessageGroups doesn't set phase/answer on clarification
   * groups, so we derive it here.
   */
  const answeredInterruptIds = computed<Set<string>>(() => {
    const answered = new Set<string>()
    for (const m of messages.value) {
      if (m.type !== 'human') continue
      const response = m.additional_kwargs?.human_input_response as { request_id?: string } | undefined
      if (response?.request_id) {
        answered.add(response.request_id)
      }
    }
    return answered
  })
  const runId = ref<string | null>(null)
  /**
   * U6 transient bridge buffer. Holds live turns that a summarization `values`
   * event is about to drop, so `visibleMessages` can keep showing the full
   * conversation until canonical history (loadHistory / next values) confirms
   * the summarized state. Never persisted; drained on history reload / clear.
   */
  const transientBridge = ref<ChatMessage[]>([])
  /**
   * Ids of messages already captured by a prior summarization pass. Prevents
   * re-capturing the same turn if summarization emits multiple values events.
   * Mirrors DeerFlow `summarizedRef`.
   */
  const summarizedIds = ref<Set<string>>(new Set())
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

  /**
   * U6: messages with the transient bridge overlaid. The UI binds to this so
   * soon-to-be-dropped turns (rescued during summarization) stay visible until
   * canonical history confirms the summarized state — no flicker. Non-display
   * logic (feedback, suggestions, retry) keeps reading `messages`.
   */
  const visibleMessages = computed(() =>
    resolveTransientHistoryBridge(messages.value, transientBridge.value),
  )

  /**
   * U6: release bridge entries once canonical history (messages) confirms their
   * identities. Mirrors DeerFlow hooks.ts:1313-1322 `useEffect([visibleHistory])`.
   * When the bridge drains to empty, also clear the summarized-id set so a later
   * run can capture fresh summarizations cleanly.
   */
  watch(messages, (live) => {
    if (transientBridge.value.length === 0) return
    const next = pruneConfirmedTransientMessages(transientBridge.value, live)
    if (next.length !== transientBridge.value.length) {
      transientBridge.value = next
    }
    if (transientBridge.value.length === 0) {
      summarizedIds.value = new Set()
    }
  })

  function addOptimisticUserMessage(text: string, additionalKwargs?: Record<string, unknown>): ChatMessage {
    const msg: ChatMessage = {
      id: genId('msg'),
      type: 'human',
      role: 'user',
      content: text,
      displayTime: formatDisplayTime(),
      sendStatus: 'sending',
      ...(additionalKwargs ? { additional_kwargs: additionalKwargs } : {}),
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
      console.log('[useThreadChat] AI message chunk received:', {
        id: chunk.id,
        contentLength: chunk.content?.length || 0,
        contentPreview: chunk.content?.slice(0, 50),
        hasToolCalls: !!chunk.tool_calls,
      })
      const last = messages.value[messages.value.length - 1]
      const chunkId = chunk.id

      // If last message is AI with matching id (or both have no id), append text
      if (last && last.type === 'ai' && (!chunkId || chunkId === last.id || !last.id)) {
        const updated: ChatMessage = { ...last }
        updated.content = last.content + chunk.content
        // Preserve 'done' phase: once an AI message is marked done (by the `end`
        // event's mark-all-done logic), a late messages-tuple chunk arriving
        // after `end` must not regress it back to 'answering' - otherwise the
        // StreamingIndicator (three-dot animation) reappears after completion.
        if (last.phase !== 'done') {
          updated.phase = 'answering'
        }
        if (chunkId) updated.id = chunkId
        if (chunk.tool_calls) {
          const newCalls = toToolCallSummaries(chunk.tool_calls)
          updated.tool_calls = [...(last.tool_calls || []), ...newCalls]
        }
        if (chunk.additional_kwargs) {
          updated.additional_kwargs = { ...(last.additional_kwargs || {}), ...chunk.additional_kwargs }
        }
        messages.value = [...messages.value.slice(0, -1), enrichToolCallMetadata(updated)]
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
        messages.value = [...messages.value, enrichToolCallMetadata(msg)]
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
      // DeerFlow ClarificationMiddleware: extract human_input from the
      // ToolMessage artifact so MessageGroup can render a HumanInputCard.
      if (chunk.name === 'ask_clarification') {
        const interruptData = extractHumanInputFromArtifact(chunk.artifact)
        if (interruptData) {
          msg.additional_kwargs = { interruptData }
        }
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

    // U6 transient bridge: detect a summarization values event. Summarization
    // emits RemoveMessage(ALL) + preserved tail, so the incoming list is
    // SHORTER than the current live messages but still contains the last
    // visible live identity (the tail). When that happens, the live turns
    // before the retained tail are about to be dropped — rescue them into the
    // bridge so visibleMessages keeps the full conversation until canonical
    // history confirms the summarized state (no flicker). Ported from DeerFlow
    // hooks.ts:1093-1118 (onUpdateEvent summarization detection).
    if (messages.value.length > 0 && mapped.length < messages.value.length) {
      const transientMessages = computeSummarizationTransientMessages(
        messages.value,
        mapped,
        summarizedIds.value,
      )
      if (transientMessages.length > 0) {
        // Mark the captured ids as summarized so a follow-up values event in
        // the same run doesn't re-capture them.
        summarizedIds.value = new Set([
          ...summarizedIds.value,
          ...transientMessages.map(m => m.id),
        ])
        // Merge without duplicating identities already in the bridge.
        const existingBridgeIds = new Set(transientBridge.value.map(messageIdentity))
        const fresh = transientMessages.filter(m => {
          const identity = messageIdentity(m)
          return !identity || !existingBridgeIds.has(identity)
        })
        if (fresh.length > 0) {
          transientBridge.value = [...transientBridge.value, ...fresh]
        }
      }
    }

    const existingIds = new Set(messages.value.map(m => m.id))
    // During active streaming, skip human messages from values events because
    // sendMessage already created an optimistic human message with the user's
    // original text. The backend persists the human message as a
    // `[SKILL:chat]\n{json}` prompt wrapper (adapter._build_prompt) — an
    // internal prompt string that must never be shown as a duplicate.
    //
    // On page refresh (initial load), however, there is no optimistic human
    // message — the values event is the ONLY source of user messages. Include
    // human messages only when messages.value is empty (initial hydration).
    const isInitialLoad = messages.value.length === 0
    const newOnes = mapped.filter(m => {
      if (existingIds.has(m.id)) return false
      if (m.type === 'human' && !isInitialLoad) return false
      return true
    })
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
    display_name?: string
    display_key?: string
    icon?: string
    tool_type?: string
  }): PlanningStep {
    const toolName = customData.tool_name || 'unknown'
    return {
      id: customData.tool_call_id || genId('step'),
      toolName,
      args: customData.args || {},
      status: 'running',
      timestamp: Date.now(),
      displayName: customData.display_name,
      displayKey: customData.display_key,
      icon: customData.icon,
      toolType: customData.tool_type,
    }
  }

  /**
   * Enrich a ChatMessage's tool_calls with display metadata (displayName /
   * displayKey / icon / toolType) resolved by the backend and stored on the
   * matching planning step.
   *
   * The AI `messages-tuple` chunk only carries the raw tool name (e.g.
   * "Numina Backend MCP_get_assets"); the readable Chinese label and i18n key
   * arrive on the separate custom `tool_call` event (held in planningSteps).
   * ChainOfThought reads from the AI message's tool_calls, so without this
   * join it would only ever see the raw name. We backfill displayName /
   * displayKey here so ChainOfThought.getName() can show "查询资产数据" etc.
   */
  function enrichToolCallMetadata(msg: ChatMessage): ChatMessage {
    if (msg.type !== 'ai' || !msg.tool_calls?.length) return msg
    const stepById = new Map(planningSteps.value.map(s => [s.id, s]))
    let changed = false
    const updatedCalls = msg.tool_calls.map(tc => {
      const step = stepById.get(tc.id)
      if (!step || (!step.displayName && !step.displayKey)) return tc
      changed = true
      return {
        ...tc,
        displayName: step.displayName || tc.displayName,
        displayKey: step.displayKey || tc.displayKey,
      }
    })
    return changed ? { ...msg, tool_calls: updatedCalls } : msg
  }

  /**
   * Attach a tool result (raw content) to the matching tool_call on the most
   * recent AI message that carries it.
   *
   * This is a fallback for the custom `tool_result` event: the messages-tuple
   * `tool` chunk (handled in mergeMessagesTupleChunk) normally sets
   * `tc.result`. But when that chunk is absent (certain LangGraph configs), the
   * ChainOfThought search-result / artifact renderers would have no `result`
   * to parse. The custom event's `content` (raw tool return value) bridges
   * that gap so web_search URLs etc. still render.
   *
   * No-op if `content` is undefined or no matching AI message exists, or if the
   * tool_call already has a result (mergeMessagesTupleChunk won the race).
   */
  function attachToolResultToAiMessage(toolCallId: string, content: unknown): void {
    if (content === undefined || content === null) return
    const aiMsgIdx = messages.value.findLastIndex(
      m => m.type === 'ai' && m.tool_calls?.some(tc => tc.id === toolCallId),
    )
    if (aiMsgIdx < 0) return
    const aiMsg = messages.value[aiMsgIdx]
    const updatedCalls = (aiMsg.tool_calls || []).map(tc =>
      tc.id === toolCallId && tc.result === undefined
        ? { ...tc, status: 'success' as const, result: content }
        : tc,
    )
    messages.value = [
      ...messages.value.slice(0, aiMsgIdx),
      { ...aiMsg, tool_calls: updatedCalls },
      ...messages.value.slice(aiMsgIdx + 1),
    ]
  }

  /**
   * Finalize all in-progress AI messages and planning steps.
   *
   * Marks every AI message with phase='answering' → phase='done', stops all
   * planning steps, and ensures the user message is not stuck at 'sending'.
   *
   * Called in error/cleanup paths where the stream terminates abnormally
   * (error event, retries exhausted, stream drop without content) — without
   * this, AI messages stay at phase='answering' forever, causing:
   * - StreamingIndicator (three-dot animation) never stops
   * - User bubble stuck at "发送中"
   * - No retry button visible (AssistantMessage only shows retry at phase='error')
   */
  function finalizeAllInProgress(): void {
    // Mark all AI messages as done
    const hasAnswering = messages.value.some(m => m.type === 'ai' && m.phase === 'answering')
    if (hasAnswering) {
      messages.value = messages.value.map(msg =>
        msg.type === 'ai' && msg.phase === 'answering'
          ? { ...msg, phase: 'done' as const }
          : msg,
      )
    }
    // Mark all planning steps as done
    planningSteps.value = planningSteps.value.map(s =>
      s.status === 'running' ? { ...s, status: 'done' as const } : s,
    )
  }

  /**
   * Mark the last AI message as error phase so the retry button appears.
   *
   * When the stream fails with an error (LLM failure, MCP error, etc.), the
   * AI message content may contain the error text. Setting phase='error' on
   * the last AI message triggers AssistantMessage's error-state UI, which
   * includes a retry button — so the user is not left staring at an error
   * message with no way to recover.
   */
  function markLastAiAsError(): void {
    const lastIdx = messages.value.findLastIndex(m => m.type === 'ai')
    if (lastIdx >= 0) {
      messages.value = [
        ...messages.value.slice(0, lastIdx),
        { ...messages.value[lastIdx], phase: 'error' as const },
        ...messages.value.slice(lastIdx + 1),
      ]
    }
  }

  /**
   * Finalize stream completion: mark all AI messages as done, attach suggestions
   * to the last message, mark planning steps done, and set user message status.
   *
   * Extracted from the `end` event handler to avoid duplication across multiple
   * success paths (end event, dropped-connection with content).
   */
  function finalizeStreamSuccess(userMsgId: string): void {
    // Mark ALL AI messages as done (fixes multi-AI-message stuck bug)
    const lastIdx = messages.value.findLastIndex(m => m.type === 'ai')
    if (lastIdx >= 0) {
      const currentSuggestions = suggestions.value.length > 0 ? suggestions.value : undefined
      let changed = false
      const next = messages.value.map((msg, i) => {
        if (msg.type !== 'ai' || msg.phase === 'done') return msg
        changed = true
        const isLast = i === lastIdx
        return {
          ...msg,
          phase: 'done' as const,
          suggestions: isLast ? (currentSuggestions ?? msg.suggestions) : msg.suggestions,
        }
      })
      if (changed) {
        messages.value = next
      }
    }
    // Mark all planning steps as done
    planningSteps.value = planningSteps.value.map(s => ({ ...s, status: 'done' as const }))
    // Ensure user message status is 'sent'
    setUserMsgStatus(userMsgId, 'sent')
    // Clear standalone suggestions (now attached inline)
    suggestions.value = []
  }

  async function sendMessage(
    text: string,
    mode?: string,
    threadId?: string,
    modeConfig?: {
      thinking_enabled?: boolean
      is_plan_mode?: boolean
      subagent_enabled?: boolean
      reasoning_effort?: 'minimal' | 'low' | 'medium' | 'high'
      websearch_enabled?: boolean
    },
    source?: string,
    /**
     * ``additional_kwargs`` attached to the outgoing HumanMessage. Used by
     * ``submitClarification`` to carry ``hide_from_ui`` + ``human_input_response``
     * (DeerFlow pattern: the clarification answer is a new message, not a resume).
     */
    additionalKwargs?: Record<string, unknown>,
    /** Uploaded file attachments (images/documents) to include in the message. */
    files?: Array<{ path: string; filename: string; mime_type?: string }>,
  ): Promise<void> {
    // If a previous stream is still marked as loading (e.g. dropped connection
    // that hasn't fully cleaned up, or user clicked retry mid-stream), cancel
    // it first instead of silently dropping the new message. Previously
    // `if (isLoading.value) return` caused the retry button to appear
    // clickable but do nothing.
    if (isLoading.value) {
      cancelStream()
      // Wait one tick for Vue reactivity to settle after cancel
      await new Promise(resolve => setTimeout(resolve, 0))
    }
    isLoading.value = true
    error.value = null
    planningSteps.value = []
    suggestions.value = []
    runId.value = null
    userCancelled = false
    abortController = new AbortController()

    const userMsg = addOptimisticUserMessage(text, additionalKwargs)

    // Resolve thread before streaming
    try {
      if (!threadId && !currentThreadId) {
        const thread = await createThread(source)
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
        //
        // The progress check must key off the CURRENT turn's user message — not
        // just `phase === 'answering'`. The error path calls finalizeAllInProgress()
        // which flips in-progress AI messages to `phase='done'` before throwing,
        // so by the time a retry re-enters this block those messages are no longer
        // 'answering'. Checking only 'answering' would then return false, re-send
        // the user message, and the backend would re-execute the LLM with a NEW
        // message id — mergeValuesMessages dedups by id, so the new AI reply
        // (a duplicate greeting) was appended instead of merged. That produced
        // "greeting output, then repeated twice, third attempt failed" because
        // each of the 3 retries generated a fresh duplicate until SSE_MAX_RETRIES
        // exhausted and markLastAiAsError flagged the last one.
        const turnUserMsgId = userMsg.id
        const hasPriorProgress = planningSteps.value.length > 0
          || messages.value.some(m => {
            if (m.type !== 'ai') return false
            // Any AI message that arrived AFTER this turn's user message counts
            // as progress (find its index relative to the user message).
            const userIdx = messages.value.findIndex(mm => mm.id === turnUserMsgId)
            const aiIdx = messages.value.indexOf(m)
            return userIdx >= 0 && aiIdx > userIdx
          })
        // Pass execution-mode overrides (flash/thinking/pro/ultra) to the backend
        // via config.configurable. The worker (run_family_agent) reads these and
        // forwards them to DeerFlowClient.stream() as per-call kwargs, which
        // control tool loading (subagent_enabled -> task tool for ultra mode)
        // and planning middleware (is_plan_mode -> TodoList for pro/ultra).
        // Mirrors the reference frontend (hooks.ts:781-796).
        const configurable: Record<string, unknown> = {}
        if (modeConfig) {
          if (modeConfig.thinking_enabled !== undefined) configurable.thinking_enabled = modeConfig.thinking_enabled
          if (modeConfig.is_plan_mode !== undefined) configurable.is_plan_mode = modeConfig.is_plan_mode
          if (modeConfig.subagent_enabled !== undefined) configurable.subagent_enabled = modeConfig.subagent_enabled
          if (modeConfig.reasoning_effort !== undefined) configurable.reasoning_effort = modeConfig.reasoning_effort
          if (modeConfig.websearch_enabled !== undefined) configurable.websearch_enabled = modeConfig.websearch_enabled
        }
        const inputMessage: Record<string, unknown> = {
          role: 'user',
          content: text,
        }
        const mergedKwargs: Record<string, unknown> = { ...additionalKwargs }
        if (files && files.length > 0) {
          mergedKwargs.files = files
        }
        if (Object.keys(mergedKwargs).length > 0) {
          inputMessage.additional_kwargs = mergedKwargs
        }
        const stream = client.runs.stream(currentThreadId as string, 'agent', {
          input: hasPriorProgress ? null : { messages: [inputMessage] },
          signal: abortController.signal,
          // #17: drop 'events' — the active backend never emits an 'events' frame
          // and there is no handler branch for it; requesting it advertises an
          // unfulfilled contract.
          streamMode: ['messages-tuple', 'values', 'custom'],
          ...(Object.keys(configurable).length > 0 ? { config: { configurable } } : {}),
        })

        // Always mark the current turn's user message as 'sent' once the stream
        // connection succeeds. The previous guard (`if (!hasPriorProgress)`)
        // incorrectly skipped this on follow-up turns after history load, where
        // replayed AI messages still had phase='answering', causing the user
        // bubble to stay stuck at "发送中" forever.
        setUserMsgStatus(userMsg.id, 'sent')

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
            // Title channel (DeerFlow pattern): TitleMiddleware writes title to
            // the checkpoint, LangGraph streams it as a values event. The
            // adapter cleans the sync fallback (JSON wrapper → user text) before
            // yielding, so any non-empty title here is display-safe.
            // Updates the session store in-place so the sidebar reflects the
            // title without HTTP polling.
            if (data.title && currentThreadId) {
              // Lazy store access — avoids requiring Pinia at composable
              // creation time (tests create useThreadChat without Pinia).
              const sessionStore = useChatSessionStore()
              const idx = sessionStore.sessions.findIndex(s => s.thread_id === currentThreadId)
              if (idx !== -1) {
                sessionStore.sessions[idx] = { ...sessionStore.sessions[idx], title: data.title }
              }
            }
            // U7 (D5 TodoList): todos channel — replace wholesale (merge_todos
            // reducer semantics: new non-None wins over existing).
            if (data.todos !== undefined) {
              todos.value = Array.isArray(data.todos) ? data.todos : []
            }
            // U5 (D1 /goal): goal channel. Only overwrite when the values chunk
            // explicitly carries the goal field (undefined → omit, NOT clear).
            // The backend U4 writes continuation_count/updated_at bumps here;
            // useActiveGoal reconciles the optimistic override against this.
            if (data.goal !== undefined) {
              serverGoal.value = data.goal
            }
          } else if (chunk.event === 'custom' && chunk.data) {
            const customData = chunk.data as {
              type?: string
              tool_call_id?: string
              tool_name?: string
              args?: Record<string, unknown>
              display_name?: string
              display_key?: string
              icon?: string
              tool_type?: string
              content?: unknown
              suggestions?: string[]
              task_id?: string
              description?: string
              prompt?: string
              result?: string
              error?: string
              usage?: { input_tokens: number; output_tokens: number; total_tokens: number }
            }
            if (customData.type === 'tool_call') {
              const step = createPlanningStep(customData)
              // Dedup by tool_call_id across retries (#21): if the backend re-emits
              // the same step, don't append a duplicate.
              const exists = step.id && planningSteps.value.some(s => s.id === step.id)
              if (!exists) {
                planningSteps.value = [...planningSteps.value, step]
              }
              // Backfill display metadata onto any pre-existing AI message that
              // already carries this tool_call (tool_call custom event may arrive
              // after the messages-tuple AI chunk that created it).
              if (step.id && (step.displayName || step.displayKey)) {
                const idx = messages.value.findLastIndex(
                  m => m.type === 'ai' && m.tool_calls?.some(tc => tc.id === step.id),
                )
                if (idx >= 0) {
                  const enriched = enrichToolCallMetadata(messages.value[idx])
                  if (enriched !== messages.value[idx]) {
                    messages.value = [
                      ...messages.value.slice(0, idx),
                      enriched,
                      ...messages.value.slice(idx + 1),
                    ]
                  }
                }
              }
            } else if (customData.type === 'tool_result') {
              // Tool result from backend — update the corresponding tool_call
              // step status from 'running' to 'done' and attach the result.
              // This is needed for ChainOfThought to display artifact links
              // (which require status === 'done').
              const toolCallId = customData.tool_call_id
              if (toolCallId) {
                planningSteps.value = planningSteps.value.map(s =>
                  s.id === toolCallId
                    ? { ...s, status: 'done' as const }
                    : s
                )
                // Fallback: attach the result content to the matching AI message's
                // tool_call. The messages-tuple `tool` chunk normally carries the
                // content (set via mergeMessagesTupleChunk), but if that chunk is
                // absent for some LangGraph configurations, the ChainOfThought
                // search-result / artifact rendering would have no `result` to
                // parse. The custom tool_result event's `content` (the raw tool
                // return value) covers that gap so web_search URLs etc. still show.
                attachToolResultToAiMessage(toolCallId, customData.content)
              }
            } else if (customData.type === 'suggestions' && customData.suggestions) {
              suggestions.value = customData.suggestions
              // If the stream already ended (end arrived before suggestions),
              // retroactively attach suggestions to the last AI message so
              // they appear without requiring a new message.
              const lastAiIdx = messages.value.findLastIndex(m => m.type === 'ai')
              if (lastAiIdx >= 0 && messages.value[lastAiIdx].phase === 'done') {
                const msg = messages.value[lastAiIdx]
                messages.value = [
                  ...messages.value.slice(0, lastAiIdx),
                  { ...msg, suggestions: customData.suggestions },
                  ...messages.value.slice(lastAiIdx + 1),
                ]
              }
            } else if (
              customData.type === 'task_started'
              || customData.type === 'task_running'
              || customData.type === 'task_completed'
              || customData.type === 'task_failed'
              || customData.type === 'task_timed_out'
              || customData.type === 'task_cancelled'
            ) {
              // DeerFlow task_tool emits these events for subagent progress
              handleTaskEvent({ ...customData, type: customData.type })
            }
          } else if (chunk.event === 'end') {
            streamEnded = true
            // worker.py publishes an `end` data frame `{"status": ...}` before
            // the END_SENTINEL. "error" means the agent run threw (LLM failure,
            // API-key decrypt, etc.) — treat as a retryable failure instead of
            // the silent success below, which left the page blank with no AI
            // reply and no error UI (B-end-status).
            let endStatus: string | undefined
            let endError: string | undefined
            if (chunk.data) {
              const endData = chunk.data as {
                usage?: TokenUsage | { input_tokens?: number; output_tokens?: number; total_tokens?: number }
                status?: string
                error?: string
                message?: string
              }
              endStatus = endData.status
              endError = endData.error || endData.message
              if (endData.usage) {
                // Normalize: backend may send DeerFlow format (input_tokens/output_tokens)
                // or legacy format (prompt_tokens/completion_tokens)
                const raw = endData.usage as Record<string, number>
                tokenUsage.value = {
                  prompt_tokens: raw.prompt_tokens ?? raw.input_tokens ?? 0,
                  completion_tokens: raw.completion_tokens ?? raw.output_tokens ?? 0,
                  total_tokens: raw.total_tokens ?? 0,
                }
              }
            }

            // CRITICAL: Mark ALL AI messages as done BEFORE checking for error status.
            // Previously, the throw for `status: 'error'` happened BEFORE this cleanup,
            // leaving AI messages stuck at phase='answering' forever — the three-dot
            // StreamingIndicator never stopped, and the user message stayed at "发送中".
            // #19: an `end` chunk is the backend's completion signal — treat it
            // as success. Truncated-content detection is unreliable from `end`
            // alone (a tool-only turn legitimately ends with no AI text), and
            // duplicate-execution risk on retry is already mitigated by #2
            // (idempotent resume via input:null).
            //
            // A single turn can produce multiple AI messages (e.g. a tool-call
            // message followed by a text-reply message, or a summarization-leak
            // message followed by the real reply). Previously only the LAST AI
            // message was marked 'done', leaving earlier ones stuck at
            // phase='answering' — their StreamingIndicator stayed visible forever
            // (three-dot animation never stops), and the next turn's
            // hasPriorProgress check saw an 'answering' message and skipped
            // setUserMsgStatus, leaving the follow-up user bubble on "发送中".
            //
            // Extracted to finalizeStreamSuccess() to avoid duplication across
            // multiple success paths (end event, dropped-connection with content).

            // Check if any AI message has actual visible content (not just tool_calls or thinking).
            // If all AI messages are empty/tool-only, show a fallback so the user doesn't see a blank page.
            const hasVisibleContent = messages.value.some(m => {
              if (m.type !== 'ai') return false
              const content = (m.content || '').trim()
              const withoutThinking = content.replace(/<think>[\s\S]*?<\/think>/g, '').trim()
              return withoutThinking.length > 0
            })

            if (!hasVisibleContent) {
              console.warn('[useThreadChat] Stream completed but no visible AI content')
              const fallbackMsg: ChatMessage = {
                id: genId('fallback'),
                type: 'ai',
                role: 'assistant',
                content: t('aiChat.noResponseFallback'),
                displayTime: formatDisplayTime(),
                phase: 'done',
              }
              messages.value = [...messages.value, fallbackMsg]
            }

            // Finalize: mark all AI messages done, attach suggestions, mark planning steps done
            finalizeStreamSuccess(userMsg.id)

            // Notify caller that stream ended
            if (currentThreadId) {
              options.onStreamEnd?.(currentThreadId)
            }

            // NOW check for error status AFTER cleanup. This ensures AI messages are
            // marked as 'done' and user message status is finalized before throwing.
            // Set streamSucceeded=true before throwing to prevent the catch block from
            // retrying on terminal backend errors (LLM API key failure, provider outage).
            // Without this, the same failing request is retried SSE_MAX_RETRIES times,
            // each producing the same error — wasted round-trips for a known-terminal failure.
            if (endStatus === 'error') {
              streamSucceeded = true
              throw new Error(endError || t('aiChat.sendFailed'))
            }

            streamSucceeded = true
          } else if (chunk.event === 'error' && chunk.data) {
            // worker.py publishes `{"message": str(exc), "name": error_type}`;
            // accept both `message` and `error` so the toast carries the real
            // backend reason instead of falling back to the generic string.
            const errData = chunk.data as { error?: string; message?: string; name?: string }
            // #20: an `error` chunk is terminal for this attempt. Set the error
            // and throw so the catch block classifies and retries; do NOT let
            // the loop fall through to streamSucceeded=true with a stale error.
            //
            // IMPORTANT: Finalize in-progress messages BEFORE throwing. Without
            // this, AI messages stay at phase='answering' (three-dot indicator
            // never stops) and the user message stays at 'sending'. The throw
            // goes to the catch block which handles retry logic.
            const errMsg = errData.error || errData.message || t('aiChat.sendFailed')
            finalizeAllInProgress()
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
            // Use the same finalization helper as the `end` event path to avoid
            // duplication and ensure consistent behavior.
            finalizeStreamSuccess(userMsg.id)
            streamSucceeded = true
          }
        }
      } catch (err) {
        const e = err as Error & { name?: string }
        // Mark the user message as failed for THIS attempt so it doesn't stay
        // stuck at 'sending' while we retry or after all retries are exhausted.
        // A successful retry will set it back to 'sent' via setUserMsgStatus
        // after the stream connection succeeds.
        setUserMsgStatus(userMsg.id, 'failed')
        // #9: distinguish a user-initiated cancel (break, no retry)
        // from a timeout/stream error abort (retryable transient failure).
        if (e.name === 'AbortError') {
          if (userCancelled) {
            // User cancelled — finalize messages so they don't stay in-progress
            finalizeAllInProgress()
            break
          }
          // Timeout abort — retry like any transient failure.
          retryCount++
          if (retryCount <= SSE_MAX_RETRIES) {
            // Optimistic: set back to 'sending' while we retry, so the UI
            // reflects that we're still trying. If this retry also fails,
            // the top of this catch block will set it to 'failed' again.
            setUserMsgStatus(userMsg.id, 'sending')
          }
        } else {
          retryCount++
          if (retryCount <= SSE_MAX_RETRIES) {
            setUserMsgStatus(userMsg.id, 'sending')
          }
        }
        if (retryCount > SSE_MAX_RETRIES) {
          // All retries exhausted — finalize messages and mark last AI as error
          // so the retry button appears in the UI.
          finalizeAllInProgress()
          markLastAiAsError()
          error.value = e.message || t('aiChat.sendFailed')
        }
      } finally {
        if (streamTimeoutId !== null) {
          clearTimeout(streamTimeoutId)
          streamTimeoutId = null
        }
      }
    }

    // Post-loop finalization: if the stream never succeeded (e.g. all retries
    // exhausted, or the loop broke without reaching streamSucceeded=true),
    // ensure no messages are stuck in-progress. This is a safety net for edge
    // cases where the catch block's finalization didn't run (e.g. unexpected
    // exceptions, or the stream ended without an `end` event and without
    // substantial content to trigger the dropped-connection path above).
    if (!streamSucceeded) {
      finalizeAllInProgress()
      // Ensure user message status is finalized even when stream didn't complete.
      // Without this, the user bubble stays stuck at "发送中" forever when:
      // - Stream connection succeeded but `end` event never arrived (network drop)
      // - User cancelled the stream mid-flight (cancelStream)
      // - All retries exhausted before receiving `end`
      // For user cancel, mark as 'sent' (message was sent, user just stopped the response).
      // For errors, mark as 'failed' so the retry button appears.
      if (userCancelled) {
        setUserMsgStatus(userMsg.id, 'sent')
      } else if (error.value) {
        setUserMsgStatus(userMsg.id, 'failed')
      } else {
        // No error but stream didn't succeed — mark as 'sent' to avoid stuck "发送中"
        setUserMsgStatus(userMsg.id, 'sent')
      }
      // Only mark as error if there's an actual error to show (avoid marking
      // as error when the user cancelled — that's a clean exit, not a failure).
      if (!userCancelled && error.value) {
        markLastAiAsError()
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

    // U6: history reload is authoritative — drain the transient bridge so
    // summarized-away turns (which will never reappear in canonical history)
    // don't linger. Also clears summarizedIds so a fresh run can recapture.
    transientBridge.value = []
    summarizedIds.value = new Set()

    isLoading.value = true
    error.value = null
    planningSteps.value = []
    suggestions.value = []
    runId.value = null
    // U7 (D5 TodoList): reset todos on thread switch; re-hydrated from
    // state.values.todos below (if present in the checkpoint).
    todos.value = []
    // U5 (D1 /goal): reset to `undefined` (not `null`) on thread switch so
    // useActiveGoal's optimistic override from the previous thread is dropped
    // (threadChanged) and the new thread's server goal hydrates cleanly below.
    serverGoal.value = undefined
    currentThreadId = threadId

    for (let attempt = 0; attempt <= retries; attempt++) {
      try {
        const client = getClient()
        const state = await client.threads.getState(threadId)
        const values = state.values as { messages?: SerializedMessage[]; todos?: Array<{ content: string; status: string }>; goal?: GoalState | null } | undefined
        if (values?.messages) {
          // Replace messages entirely for history load
          messages.value = values.messages.map(serializedToChatMessage)
          // Hydrate per-user feedback state (点赞/点踩) from backend so the
          // thumbs-up/down highlight persists across reloads.
          await hydrateFeedback(threadId)
        }
        // U7 (D5 TodoList): hydrate todos from checkpoint channel_values.
        if (Array.isArray(values?.todos)) {
          todos.value = values!.todos!
        }
        // U5 (D1 /goal): hydrate server goal from checkpoint channel_values.
        // The backend persists goal as channel_values["goal"] (U2); a missing
        // key (older checkpoints) hydrates as `null` (explicitly no goal) only
        // when the key is present, else stays `undefined` (omit, not clear).
        if (values && Object.prototype.hasOwnProperty.call(values, 'goal')) {
          serverGoal.value = values.goal ?? null
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

  /**
   * Hydrate per-user message feedback (点赞/点踩) from backend into the
   * currently-loaded messages so the thumbs-up/down highlight is restored.
   * Safe to call after loadHistory; failures are non-fatal (silent).
   */
  async function hydrateFeedback(threadId: string): Promise<void> {
    try {
      const res = await getSessionFeedback(threadId)
      const items = res.data?.items
      if (!items || Object.keys(items).length === 0) return
      const idToFeedback = new Map<string, 1 | -1>(Object.entries(items) as [string, 1 | -1][])
      let changed = false
      const next = messages.value.map(msg => {
        const fb = idToFeedback.get(msg.id)
        if (fb !== undefined && msg.feedback !== fb) {
          changed = true
          return { ...msg, feedback: fb }
        }
        return msg
      })
      if (changed) messages.value = next
    } catch {
      // Feedback hydration is best-effort; don't surface errors to the user.
    }
  }

  /**
   * Submit 点赞/点踩 for a message.
   * Optimistically updates the local message.feedback so the highlight is
   * immediate; rolls back + toasts on backend failure.
   * Toggle semantics: clicking the same value again cancels (→ 0). The
   * backend also enforces this, but we mirror it locally for instant UX.
   */
  async function submitFeedback(
    threadId: string,
    messageId: string,
    value: 1 | -1,
  ): Promise<void> {
    const idx = messages.value.findIndex(m => m.id === messageId)
    if (idx === -1) return
    const current = messages.value[idx].feedback ?? 0
    const optimistic = current === value ? 0 : value
    const prev = messages.value[idx]
    messages.value = [
      ...messages.value.slice(0, idx),
      { ...prev, feedback: optimistic },
      ...messages.value.slice(idx + 1),
    ]
    try {
      const res = await submitMessageFeedback(threadId, messageId, value)
      // Reconcile with authoritative server value (backend may have toggled to 0).
      // Backend contract: feedback is only ever 1 (点赞) / -1 (点踩) / 0 (取消).
      const serverFeedback = (res.data?.feedback as 1 | -1 | 0 | undefined) ?? optimistic
      if (serverFeedback !== optimistic && messages.value[idx]?.id === messageId) {
        messages.value = [
          ...messages.value.slice(0, idx),
          { ...messages.value[idx], feedback: serverFeedback },
          ...messages.value.slice(idx + 1),
        ]
      }
      if (serverFeedback !== 0) {
        showSuccessToast(t('aiChat.feedbackSubmitted'))
      }
    } catch {
      // Rollback on failure.
      messages.value = [
        ...messages.value.slice(0, idx),
        { ...prev, feedback: current },
        ...messages.value.slice(idx + 1),
      ]
      showFailToast(t('aiChat.feedbackFailed'))
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

  /**
   * U6: handle the `/compact` slash command. Calls POST /api/threads/{id}/compact
   * to summarize old history (RemoveMessage(ALL) + summary_text + preserved
   * tail). On success reloads history so the canonical summarized state lands
   * (the transient bridge covers any mid-flight flicker during the prior run).
   * Skips with compactSkipped when there is no active thread (welcome mode) or
   * the backend reports the thread was not compacted (reason present, e.g.
   * not_enough_messages / empty thread).
   */
  async function handleCompact(threadId: string | null): Promise<void> {
    if (!threadId) {
      showToast(t('aiChat.compactSkipped'))
      return
    }
    try {
      const result = await compactThread(threadId)
      if (!result.compacted) {
        // reason present (not_enough_messages, empty thread, etc.) → skip.
        showToast(t('aiChat.compactSkipped'))
        return
      }
      showSuccessToast(t('aiChat.compactSuccess'))
      // Reload canonical history so the summarized state (preserved tail +
      // summary_text) replaces the live messages. loadHistory drains the
      // transient bridge as the authoritative reset.
      await loadHistory(threadId)
    } catch {
      showFailToast(t('aiChat.compactFailed'))
    }
  }

  /**
   * U5 (D1 /goal): handle a parsed `/goal` command (set / status / clear).
   * Ported from DeerFlow input-box.tsx:667-770 (handleGoalCommand). Returns
   * `true` only on success; the caller starts a run ONLY when
   * `command.kind === 'set'` and this returned `true` (input-box.tsx:953-961).
   *
   * - `set`: PUT /goal + onGoalChange(goal) so useActiveGoal can apply the
   *   optimistic override immediately. (The run is started by the caller via
   *   submitThreadMessage with the objective as text.)
   * - `status`: GET /goal + toast goalActive (objective) or goalNone (none).
   *   onGoalChange(goal) syncs server state. Never starts a run.
   * - `clear`: DELETE /goal + goalCleared toast + onGoalChange(null). Never
   *   starts a run.
   *
   * Welcome-mode (no active thread) is guarded by the caller — this function
   * requires a real threadId because goal lives in the checkpoint.
   */
  async function handleGoalCommand(
    threadId: string,
    command: GoalCommand,
    onGoalChange?: (goal: GoalState | null) => void,
  ): Promise<boolean> {
    try {
      if (command.kind === 'status') {
        const res = await getThreadGoal(threadId)
        const goal = res.goal ?? null
        onGoalChange?.(goal)
        const objective = goal?.objective
        showToast(
          objective !== undefined
            ? t('aiChat.goalActive').replace('{goal}', objective)
            : t('aiChat.goalNone'),
        )
        return true
      }
      if (command.kind === 'clear') {
        await clearThreadGoal(threadId)
        onGoalChange?.(null)
        showSuccessToast(t('aiChat.goalCleared'))
        return true
      }
      // set
      const res = await setThreadGoal(threadId, { objective: command.objective })
      const goal = res.goal ?? null
      onGoalChange?.(goal)
      showSuccessToast(t('aiChat.goalSet'))
      return true
    } catch (err) {
      const message = err instanceof Error ? err.message : t('aiChat.goalFailed')
      showFailToast(message)
      return false
    }
  }

  function clearMessages() {
    cancelStream()
    messages.value = []
    tokenUsage.value = null
    planningSteps.value = []
    suggestions.value = []
    runId.value = null
    error.value = null
    isLoading.value = false
    // U7 (D5 TodoList): clear todos on full clear (new chat / thread switch).
    todos.value = []
    // U5 (D1 /goal): reset to `undefined` (omit, not clear) on full clear so
    // useActiveGoal drops any optimistic override and the new chat has no goal.
    serverGoal.value = undefined
    // U6: drain the transient bridge + summarized ids on full clear (new chat /
    // thread switch) so rescued turns never leak across chat views.
    transientBridge.value = []
    summarizedIds.value = new Set()
  }

  /**
   * Submit a clarification answer as a NEW HumanMessage (DeerFlow pattern).
   *
   * DeerFlow's ClarificationMiddleware intercepts ``ask_clarification`` and
   * ends the run (``Command(goto=END)``) with a
   * ``ToolMessage(artifact={human_input})``. The user's answer is NOT sent via
   * a resume endpoint - it's a new ``HumanMessage`` carrying
   * ``additional_kwargs.human_input_response`` (structured) + ``hide_from_ui``
   * (so it doesn't render as a duplicate chat bubble). The message text follows
   * DeerFlow's ``buildHumanInputResponseText`` format so the LLM sees a
   * natural-language answer.
   *
   * ``answeredInterruptIds`` (computed from message history) automatically
   * marks the clarification card as 'answered' once the response message lands.
   */
  async function submitClarification(
    threadId: string,
    interruptId: string,
    answer: string,
  ): Promise<void> {
    if (isLoading.value) return

    // Locate the InterruptData for this request to build a structured response.
    const clarificationMsg = messages.value.find(
      m => m.type === 'tool' && m.name === 'ask_clarification'
        && (m.additional_kwargs?.interruptData as InterruptData | undefined)?.interrupt_id === interruptId,
    )
    const request = clarificationMsg?.additional_kwargs?.interruptData as InterruptData | undefined
    const source = request?.source || 'ask_clarification'
    const question = request?.question || ''

    // Build HumanInputResponse (DeerFlow core/messages/human-input.ts). If the
    // answer matches an option value, it's an option response; otherwise text.
    const matchedOption = request?.options?.find(o => o.value === answer)
    const response: Record<string, unknown> = matchedOption
      ? { version: 1, kind: 'human_input_response', source, request_id: interruptId, response_kind: 'option', option_id: matchedOption.id, value: matchedOption.value }
      : { version: 1, kind: 'human_input_response', source, request_id: interruptId, response_kind: 'text', value: answer }

    // DeerFlow buildHumanInputResponseText: natural-language wrapper so the LLM
    // sees a readable answer, not just a raw value.
    const text = `For your clarification "${question}", my answer is: ${answer}`

    await sendMessage(text, undefined, threadId, undefined, undefined, {
      hide_from_ui: true,
      human_input_response: response,
    })
  }

  return {
    messages, visibleMessages, isLoading, isStreaming, error, tokenUsage,
    planningSteps, suggestions, answeredInterruptIds, runId,
    todos, serverGoal,
    sendMessage, cancelStream, loadHistory, retry, clearMessages, submitClarification,
    submitFeedback, handleCompact, handleGoalCommand,
  }
}
