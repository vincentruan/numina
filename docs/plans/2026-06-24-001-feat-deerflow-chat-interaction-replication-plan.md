---
date: 2026-06-24
type: feat
origin: docs/brainstorms/2026-06-24-deerflow-chat-replication-requirements.md
---

# feat: DeerFlow Chat Interaction Replication — AI 对话全交互复刻

## Summary

Replicate the complete DeerFlow frontend interaction experience within Numina's `/ai/chat` page. Extend `useThreadChat.ts` to parse SSE `custom` events for real-time planning step visualization, migrate markdown rendering from `marked` to `markdown-it` + `shiki` for syntax highlighting and better streaming support, add per-message token usage display, follow-up suggestion chips, auto-scroll with user-interrupt, bouncing dots streaming indicator, table operations (copy/download), SSE retry with exponential backoff, and dark mode compliance across all new components.

---

## Problem Frame

The Numina backend has completed SSE three-track protocol alignment (messages/custom/values) per the SSE protocol plan. However, the frontend still only processes `messages-tuple` and `values` events, ignoring `custom` events for planning steps (tool calls). Users cannot see the agent's reasoning process (websearch queries, page fetches, skill invocations), token usage is only available in a header popover instead of per-message, suggestion chips are not rendered despite data being captured, markdown rendering lacks syntax highlighting, and there is no auto-scroll or SSE retry logic.

The codebase already has ~80% of the component foundation — `ChainOfThought.vue`, `MarkdownContent.vue`, `TokenUsage.vue`, `SuggestionChip.vue`, `ArtifactPreviewPopup.vue`, `CopyButton.vue`, `MessageGroup.vue`, `ModeSelector.vue` all exist. The work is primarily integration, enhancement, and filling the SSE custom event gap.

---

## Requirements Traceability

All requirements from the origin document (see origin: `docs/brainstorms/2026-06-24-deerflow-chat-replication-requirements.md`):

| Requirement | Implementation Unit |
|-------------|-------------------|
| R1 (user bubble) | U4 — already exists, wire copy |
| R2 (user bubble copy) | U4 |
| R3 (planning steps from custom events) | U1, U2 |
| R4 (collapsible panel) | U2 |
| R5 (markdown streaming + scroll) | U5, U6 |
| R6 (table copy/download) | U5 |
| R7 (bouncing dots) | U6 |
| R8 (token usage display) | U3 |
| R9 (token usage real-time) | U3 |
| R10 (suggestion chips) | U4 |
| R11 (suggestions from SSE custom) | U1, U4 |
| R12 (suggestion click sends) | U4 |
| R13 (user message copy) | U4 |
| R14 (AI message copy) | U4 |
| R15 (table copy/download) | U5 |
| R16 (artifact copy) | U7 |
| R17 (artifact entry card) | U7 |
| R18 (full-screen preview) | U7 |
| R19 (removed — mobile full-screen) | N/A |

Actors: A1 (family user), A2 (AI agent) — carried forward, no additional actor-specific decisions needed.

Key Flows: F1 (full streaming with tools), F2 (simple chat), F3 (artifact preview) — all addressed by the implementation units.

---

## Scope Boundaries

### In Scope

- SSE custom event parsing for planning steps (tool_call type) and suggestions
- Planning steps real-time panel with collapse/expand
- Token usage per-message inline display with polling
- Suggestion chips above input box
- Markdown rendering migration (`marked` → `markdown-it` + `shiki`)
- Auto-scroll with user-interrupt ("回到底部" button)
- Bouncing dots streaming indicator
- Table operations (copy as markdown, download as CSV)
- Copy functionality (user bubble, AI message, artifact)
- SSE retry (3 attempts, exponential backoff)
- Dark mode compliance for all new components
- Artifact full-screen preview popup (already exists, verify integration)

### Deferred for Later

- PDF/Word/Excel artifact generation (needs backend skill support)
- Model selector (server-configured, not user-facing)
- Session replay UI (values track supports future replay)
- Feedback events (thumbs up/down)
- Message branch navigation (1 of N)
- SubtaskCard orchestration enhancements (v1 focuses on single-step tool visualization)

### Outside This Product's Identity

- Backend SSE protocol changes (already completed in prior plan)
- Model selection UI (Numina uses server-configured models)

---

## Key Technical Decisions

### KTD1: Migrate from `marked` to `markdown-it` + `shiki`

**Decision:** Replace `marked` with `markdown-it` for markdown parsing, add `shiki` for syntax highlighting.

**Rationale:** `markdown-it` has better plugin architecture for streaming partial markdown content, more predictable handling of incomplete markdown during streaming (fewer flickering renders), and `shiki` provides VS Code-quality syntax highlighting. The current `marked` setup has no syntax highlighting at all.

**Migration steps:**
- Replace `marked` with `markdown-it` in `MarkdownContent.vue`
- Integrate `shiki` highlighter (async load to avoid blocking initial render)
- Remove the progressive rendering workaround (the `THRESHOLD` / split-render logic in current `MarkdownContent.vue`) since `markdown-it` handles streaming more naturally
- Update all `:deep()` CSS selectors if the HTML output structure changes
- Add `markdown-it` table plugin if not built-in

**Dependencies to add:** `markdown-it`, `@types/markdown-it`, `shiki`
**Dependencies to remove:** `marked`, `@types/marked` (after migration verified)

### KTD2: Token Usage via Per-Message `usage_metadata` from SSE `values` Events

**Decision:** Extract per-message token counts from SSE `values` events (each AI message carries `usage_metadata` with `input_tokens`/`output_tokens`). Store in `ChatMessage.usageMetadata`. The thread-level polling endpoint `GET /api/threads/{id}/token-usage` serves as fallback during streaming before values events arrive.

**Rationale:** The backend token-usage endpoint returns cumulative thread totals — if used directly, all AI messages in the same thread would show identical numbers, violating R8's "每个 agent 答复下方" per-message intent. LangGraph's `values` events include per-message `usage_metadata`, enabling true per-message display. Polling retained only as a real-time fallback during active streaming (before the final values event with usage data arrives).

### KTD3: SSE Retry — Exponential Backoff, 3 Attempts Max

**Decision:** On SSE stream disconnect, automatically retry up to 3 times with exponential backoff (1s, 2s, 4s). After 3 failures, show error bar.

**Rationale:** Matches the origin document requirement. Exponential backoff avoids thundering herd. 3 attempts balance resilience vs. duplicate tool call side effects.

### KTD4: Artifact Full-Screen Preview via Popup

**Decision:** Keep the existing `ArtifactPreviewPopup.vue` full-screen popup approach.

**Rationale:** Already implemented. Mobile screens cannot accommodate side panels. The popup provides good UX with conversation context preserved underneath.

### KTD5: Table Download as CSV

**Decision:** Use CSV format with comma delimiter for table downloads.

**Rationale:** Most universally compatible format. Excel opens CSV natively. Simpler to implement than TSV. UTF-8 with BOM for CJK content support.

---

## High-Level Technical Design

### SSE Event Flow

```
Backend Agent (runs.py _sse_generator)
  │
  ├── event: metadata  → run_id
  ├── event: messages  → AI text chunks, tool_calls
  ├── event: custom    → tool_call progress, suggestions
  ├── event: values    → state snapshots, artifacts, per-message usage_metadata
  ├── event: error     → error data
  └── event: end       → stream complete
          │
          ▼
Frontend (useThreadChat via LangGraph SDK)
  │
  ├── metadata         → runId ref (debugging, retry correlation)
  ├── messages-tuple   → mergeMessagesTuple() → messages[]
  ├── values           → mergeValuesMessages() → messages[]
  │                    → extract usage_metadata → ChatMessage.usageMetadata
  ├── custom           → parsePlanningStep() → planningSteps[]
  │                    → parseSuggestions() → suggestions[]
  ├── end              → markLastAiDone() + stopPolling
  └── error            → setError()
```

### Component Hierarchy (with new/enhanced components marked)

```
AIChatPage
  └── AIChatBox
        ├── ChatHeader
        │     └── TokenUsage (header popover — ENHANCED in U3)
        ├── MessageList
        │     └── MessageGroup (per group)
        │           ├── UserBubble + CopyButton
        │           ├── AssistantMessage
        │           │     ├── PlanningStepsPanel (NEW — U2)
        │           │     ├── MarkdownContent (MIGRATED — U5)
        │           │     │     └── CodeBlock (ENHANCED with shiki)
        │           │     ├── TableActionBar (NEW — U5)
        │           │     ├── StreamingIndicator (NEW — U6)
        │           │     └── CopyButton
        │           ├── ChainOfThought (existing, for history)
        │           └── ArtifactFileList
        ├── SuggestionChips (NEW container — U4)
        │     └── SuggestionChip (existing)
        ├── InputBox
        └── ArtifactPreviewPopup (existing, verify — U7)
```

### Data Flow

`useThreadChat` remains the central state holder. It exposes:

- `messages: ChatMessage[]` — existing (each ChatMessage may now carry `usageMetadata`)
- `planningSteps: PlanningStep[]` — NEW (from custom events)
- `suggestions: string[]` — NEW (from custom events, exposed at composable level)
- `runId: string | null` — NEW (from metadata event)
- `isStreaming: boolean` — NEW (alias/rename of `isLoading` for clarity)
- `streamError: string | null` — existing (`error`)

`useTokenUsage` (NEW composable in U3) handles per-message token polling independently.

Components are primarily presentational — they receive data via props and emit events upward.

---

## Implementation Units

### U1. SSE Custom Event Parsing and Retry Foundation

**Goal:** Extend `useThreadChat.ts` to parse SSE `custom` events for planning steps (tool calls) and suggestions, capture `metadata` events for `run_id`, extract per-message `usage_metadata` from `values` events, add `stream_mode` configuration, and implement SSE retry with exponential backoff.

**Requirements:** R3, R8, R9, R11, F1 steps 3/9

**Dependencies:** None

**Files:**
- `frontend/apps/main/src/composables/ai-chat/useThreadChat.ts` — extend with custom event handling, metadata handling, usage_metadata extraction, retry logic
- `frontend/apps/main/src/types/ai-chat/message-group.ts` — add `PlanningStep` interface, add `usageMetadata` field to `ChatMessage`
- `frontend/apps/main/src/types/ai-chat/session.ts` — add `StreamConfig` type if needed
- `frontend/apps/main/src/composables/ai-chat/useThreadChat.test.ts` — NEW test file

**Approach:**

1. **Add `PlanningStep` type** to `message-group.ts`:
   ```
   PlanningStep {
     id: string
     toolName: string
     displayName: string
     icon: string
     args: Record<string, unknown>
     status: 'pending' | 'running' | 'done' | 'error'
     result?: string
     timestamp: number
   }
   ```

2. **Add `UsageMetadata` field** to `ChatMessage` in `message-group.ts`:
   ```
   ChatMessage.usageMetadata?: {
     inputTokens: number
     outputTokens: number
   }
   ```

3. **Add reactive state** in `useThreadChat`:
   - `planningSteps: Ref<PlanningStep[]>` — real-time steps from custom events
   - `suggestions: Ref<string[]>` — captured suggestions (currently local variable `pendingSuggestions`, promote to ref)
   - `runId: Ref<string | null>` — captured from metadata event
   - `isStreaming: Ref<boolean>` — derived from `isLoading`
   - Clear `planningSteps` at the start of each new `sendMessage()` call

4. **Extend custom event handler** in the stream loop:
   - When `customData.type === 'tool_call'`: create a new `PlanningStep` and append to `planningSteps`
   - Map `tool_name` to icon using existing `getToolIcon()` from `utils/ai-chat/tool-icon-map.ts`
   - Map `tool_name` to display name using existing `getToolDisplayNameKey()`
   - When `customData.type === 'suggestions'`: store in `suggestions` ref (existing behavior, just promote to exposed state)

5. **Add `metadata` event handler**:
   - When `chunk.event === 'metadata'`: capture `chunk.data.run_id` into `runId` ref
   - `metadata` is the first event in the stream; store for debugging and retry correlation

6. **Extract per-message `usage_metadata`** from `values` events:
   - In `mergeValuesMessages()`, when processing an AI message that contains `usage_metadata`:
     - Extract `input_tokens` and `output_tokens`
     - Store as `usageMetadata: { inputTokens, outputTokens }` on the corresponding `ChatMessage`
   - This enables per-message token display in U3 (vs. thread-level cumulative totals from the polling endpoint)

7. **Add `stream_mode` configuration** to the `client.runs.stream()` call:
   ```
   stream_mode: ['messages-tuple', 'values', 'updates', 'custom', 'events']
   ```
   Verify the LangGraph SDK version supports `custom` and `events` modes.

8. **Add SSE retry logic** in `sendMessage()`:
   - Wrap the stream consumption loop in a retry function
   - On stream error (not user abort): retry up to 3 times with delays [1000, 2000, 4000] ms
   - Preserve `messages`, `planningSteps`, and `runId` state across retries (partial content retained)
   - After 3 failures: set `error` ref, mark user message `sendStatus: 'failed'`
   - On stream `end`: reset retry counter, mark last AI message as `done`

**Patterns to follow:**
- Existing `useThreadChat.ts` patterns for state management (refs, immutable array updates)
- Existing `mergeMessagesTuple()` and `mergeValuesMessages()` patterns for event merging
- CLAUDE.md: `<script setup lang="ts">` only, no `any` types

**Test scenarios:**
- Custom event `tool_call` is parsed into `PlanningStep` with correct `toolName`, `icon`, and `status`
- Custom event `suggestions` populates `suggestions` ref
- Multiple tool_call events append to `planningSteps` in order
- `planningSteps` is cleared at the start of each `sendMessage()` call
- `metadata` event populates `runId` ref with the run_id value
- `values` event with AI message containing `usage_metadata` stores `inputTokens`/`outputTokens` on the ChatMessage
- SSE disconnect triggers retry after 1s delay; successful retry resets counter
- 3 consecutive failures set `error` ref and `sendStatus: 'failed'`
- Partial `messages` content is preserved across retry attempts
- User abort (cancel button) does not trigger retry
- `stream_mode` includes `custom` in the SDK call

**Verification:** Unit tests pass; `planningSteps` ref populates when custom events arrive; `runId` captured from metadata; `usageMetadata` extracted from values events; retry triggers on simulated disconnect; no regressions in existing `messages-tuple` and `values` handling.

---

### U2. Planning Steps Real-Time Panel

**Goal:** Create a `PlanningStepsPanel` component that renders real-time planning steps from SSE `custom` events, with collapsible display, tool-specific icons, and a "隐藏步骤"/"查看其他 N 个步骤" toggle.

**Requirements:** R3, R4, F1 step 4

**Dependencies:** U1 (provides `planningSteps` data)

**Files:**
- `frontend/apps/main/src/components/ai-chat/PlanningStepsPanel.vue` — NEW component
- `frontend/apps/main/src/components/ai-chat/MessageGroup.vue` — integrate panel into assistant message flow
- `frontend/apps/main/src/components/ai-chat/PlanningStepsPanel.test.ts` — NEW test file

**Approach:**

1. **Create `PlanningStepsPanel.vue`**:
   - Props: `steps: PlanningStep[]`, `isStreaming: boolean`, `defaultExpanded: boolean` (default `true` per R4)
   - Emits: none (presentational)
   - Display each step with:
     - Icon (emoji per R3: 🔍 websearch, 🌐 page-fetch, 🧩 skill, 🔌 mcp, 💻 code) — use `getToolIcon()` from existing utility
     - Step summary text (websearch shows query, page-fetch shows "查看网页" + URL)
     - Status indicator (spinner for running, ✓ for done, ✗ for error)
   - Collapse behavior:
     - Default expanded (per R4, matching DeerFlow)
     - Toggle button at top: "隐藏步骤" when expanded, "查看其他 N 个步骤" when collapsed
     - When collapsed: show only the last step (DeerFlow pattern, same as existing `ChainOfThought.vue`)
   - Style: card with `var(--card-bg)` background, `var(--border-color)` border, matching existing `ChainOfThought.vue` style

2. **Integrate into `MessageGroup.vue`**:
   - Render `PlanningStepsPanel` above `MarkdownContent` when `planningSteps.length > 0` or `isStreaming` is true
   - Pass `planningSteps` from parent (AIChatBox) down to MessageGroup
   - When streaming completes, the panel remains visible with all steps (becomes historical)
   - For history loads, planning steps come from the messages' `tool_calls` — use existing `ChainOfThought.vue` for historical display

3. **Icon mapping** (R3):
   - Use existing `getToolIcon()` from `utils/ai-chat/tool-icon-map.ts` for consistency
   - Verify the icon set covers: websearch, page-fetch, skill, mcp, code
   - The requirements specify emoji icons — if existing utility returns Iconify names, either:
     (a) Map emoji in the panel component, or
     (b) Extend the utility to return emoji for these specific tools
   - Choose (a) to minimize changes to existing utility

**Patterns to follow:**
- Existing `ChainOfThought.vue` for collapsible step display pattern, card styling, step-header layout
- Existing `getToolIcon()` / `getToolDisplayNameKey()` for tool metadata
- Vant patterns: no new UI libraries, use CSS variables for theming
- Dark mode: `var(--card-bg)`, `var(--border-color)`, `var(--text-primary)`

**Test scenarios:**
- Panel renders with correct emoji icon for websearch step (🔍 + search query text)
- Panel renders with correct emoji for page-fetch step (🌐 + "查看网页" + URL)
- Panel renders with correct emoji for skill step (🧩)
- Panel defaults to expanded state showing all steps
- Collapse toggle hides steps above the last one, shows "查看其他 N 个步骤"
- Expand toggle shows all steps, button text changes to "隐藏步骤"
- Running step shows spinner animation
- Completed step shows ✓ badge
- Empty steps array renders nothing
- Dark mode: card background and text colors use CSS variables correctly

**Verification:** Panel displays real-time steps when connected to U1's `planningSteps`; collapse/expand works; emoji icons match R3 spec; dark mode renders correctly.

---

### U3. Token Usage Per-Message Display

**Goal:** Display token usage inline below each AI message in the format "Tokens 输入: X 输出: Y 总计: Z", sourced from per-message `usageMetadata` extracted from SSE `values` events (by U1). During active streaming, poll the thread-level endpoint as a fallback until per-message data arrives.

**Requirements:** R8, R9, AE4

**Dependencies:** U1 (provides `ChatMessage.usageMetadata` from `values` events)

**Files:**
- `frontend/apps/main/src/components/ai-chat/TokenUsage.vue` — add inline display mode
- `frontend/apps/main/src/composables/ai-chat/useTokenUsage.ts` — NEW composable for polling fallback during streaming
- `frontend/apps/main/src/components/ai-chat/MessageGroup.vue` — integrate inline display
- `frontend/apps/main/src/i18n/locales/zh-CN.ts` — add i18n keys
- `frontend/apps/main/src/i18n/locales/en-US.ts` — add i18n keys
- `frontend/apps/main/src/components/ai-chat/TokenUsage.test.ts` — NEW test file

**Approach:**

1. **Primary source: per-message `usageMetadata`** (from U1):
   - U1 extracts `usage_metadata` from SSE `values` events and stores `{ inputTokens, outputTokens }` on each `ChatMessage`
   - `TokenUsage.vue` receives this as a prop: `usageMetadata?: { inputTokens: number; outputTokens: number }`
   - When available, display directly — this is the accurate per-message data

2. **Fallback: polling during streaming** (via `useTokenUsage` composable):
   - Create `useTokenUsage` composable: `startPolling(threadId, intervalMs)`, `stopPolling()`, `fetchOnce()`
   - During streaming (`phase === 'answering'`), if `usageMetadata` is not yet available on the current message, poll `GET /api/threads/{id}/token-usage` every 1.5s
   - Display the polled value as a provisional count (note: this is cumulative thread total, not per-message — label it as such or hide until per-message data arrives)
   - When the final `values` event arrives with `usage_metadata`, switch to the per-message data and stop polling
   - Cleanup: `onUnmounted` stops polling

3. **Enhance `TokenUsage.vue`**:
   - Add `mode` prop: `'popover' | 'inline'` (default `'popover'` for backward compatibility)
   - Inline mode renders: `<span class="token-usage-inline">Tokens 输入: {X} 输出: {Y} 总计: {Z}</span>`
   - Format numbers with `toLocaleString()` for thousands separators (matching AE4: "200.2K", "7,424")
   - Large number formatting: >999 → "1.2K" style (existing pattern in header popover)
   - Show nothing when no usage data is available (neither `usageMetadata` prop nor polling data)

4. **Integrate in `MessageGroup.vue`**:
   - Below `AssistantMessage` content, render `<TokenUsage mode="inline" :usage-metadata="message.usageMetadata" :thread-id="threadId" :is-streaming="phase === 'answering'" />`
   - Component internally handles fallback logic: show `usageMetadata` when available, otherwise show polling data during streaming

5. **i18n keys**:
   - `aiChat.tokensInput`: "输入"
   - `aiChat.tokensOutput`: "输出"
   - `aiChat.tokensTotal`: "总计"
   - `aiChat.tokensLabel`: "Tokens"

**Patterns to follow:**
- Existing `TokenUsage.vue` polling and API call pattern (reuse `getTokenUsage()` from `api/ai-chat.ts`)
- i18n: all user-facing strings via `t()` key, no hardcoded Chinese in components
- CLAUDE.md: no `any` types

**Test scenarios:**
- Inline mode renders "Tokens 输入: 200 输出: 7,424 总计: 7,624" from per-message `usageMetadata` prop
- Large numbers (>999) display with `toLocaleString()` formatting (e.g., "200.2K")
- When `usageMetadata` is null during streaming, polling fallback activates and shows provisional count
- When `usageMetadata` arrives (from values event), polling stops and per-message data is shown
- After stream ends, final per-message count is displayed (no more polling)
- Zero tokens (no usage data) renders nothing
- Popover mode (existing header behavior) still works unchanged
- Dark mode: text uses `var(--text-secondary)` for labels, `var(--text-primary)` for values

**Verification:** Inline token display appears below AI messages with per-message accuracy; polling fallback works during streaming; final count from `usageMetadata` is correct; existing header popover unaffected.

---

### U4. Suggestion Chips and Copy Functionality

**Goal:** Render follow-up suggestion chips above the input box, wire up copy functionality for user bubbles and AI messages.

**Requirements:** R1, R2, R10, R11, R12, R13, R14, AE1, AE5

**Dependencies:** U1 (provides `suggestions` data)

**Files:**
- `frontend/apps/main/src/components/ai/SuggestionChips.vue` — EXISTING component (verify/enhance; already has `suggestions: string[]` prop, `select` emit, dark mode CSS variables, fade-in animation, mobile horizontal scroll, accessibility)
- `frontend/apps/main/src/components/ai-chat/SuggestionChip.vue` — verify existing, minor tweaks if needed
- `frontend/apps/main/src/components/ai-chat/SuggestionConfirmDialog.vue` — verify existing
- `frontend/apps/main/src/components/chat/UserBubble.vue` — add copy button
- `frontend/apps/main/src/components/chat/AssistantMessage.vue` — add copy button to action bar
- `frontend/apps/main/src/components/ai-chat/InputBox.vue` — accept suggestion fill event
- `frontend/apps/main/src/components/ai/AIChatBox.vue` — wire suggestion select to input
- `frontend/apps/main/src/i18n/locales/zh-CN.ts` — add i18n keys for new strings
- `frontend/apps/main/src/components/ai-chat/SuggestionChips.test.ts` — NEW test file

**Approach:**

1. **Verify existing `SuggestionChips.vue`** (no rewrite needed):
   - Already has: `suggestions: string[]` prop, `emit('select', text)`, CSS variables for dark mode (`--text-primary`, `--suggestion-bg`, `--suggestion-border`), fade-in animation with `prefers-reduced-motion` support, mobile horizontal scroll at `@media (max-width: 375px)`, `role="group"` + `aria-label` accessibility
   - Confirm: `--suggestion-bg` and `--suggestion-border` CSS variables are defined in `style.css` (add if missing)
   - Event name is `select` (not `click`) — this is semantically better, keep as-is
   - Visibility is handled by `v-if="suggestions.length > 0"` — no separate `visible` prop needed; parent controls display by setting/clearing the `suggestions` array

2. **Wire suggestion flow**:
   - `AIChatBox` passes `suggestions` from `useThreadChat` to `SuggestionChips`
   - On chip select: emit `select(text)` → parent fills `InputBox` and triggers send (per R12)
   - If input is non-empty, show `SuggestionConfirmDialog` (existing pattern)
   - After sending suggestion, clear `suggestions` array

3. **Copy for user bubble** (R2, R13):
   - Add a `CopyButton` next to each `UserBubble`
   - On click: `navigator.clipboard.writeText(content)` + `showSuccessToast(t('aiChat.copiedSuccess'))`
   - Use existing `CopyButton.vue` component

4. **Copy for AI message** (R14):
   - Add copy button to `AssistantMessage.vue` action bar
   - Copy full markdown text (not rendered HTML)
   - Use existing `CopyButton.vue` component

5. **i18n keys**:
   - `aiChat.copiedSuccess`: "已复制到剪贴板" (verify existing)
   - `aiChat.suggestionClick`: already handled by SuggestionConfirmDialog

**Patterns to follow:**
- Existing `SuggestionChip.vue` for chip styling and animation
- Existing `CopyButton.vue` for copy behavior
- Existing `SuggestionConfirmDialog.vue` for non-empty input handling
- Vant: `showSuccessToast()` for copy confirmation

**Test scenarios:**
- 3 suggestion chips render when `suggestions` has 3 items
- Chips hidden when `suggestions` is empty or `visible` is false
- Click on chip fills input box with suggestion text
- Click on chip with non-empty input shows confirm dialog
- After suggestion is sent, suggestions array is cleared
- User bubble copy button copies question text to clipboard
- AI message copy button copies full markdown content (not HTML)
- Copy toast shows "已复制到剪贴板"
- Chips are horizontally scrollable when >3 (edge case)
- Dark mode: chip background uses `var(--card-bg)`, border uses `var(--border-color)`

**Verification:** Chips appear after stream ends; click sends suggestion; copy works for both user and AI messages; no regressions in existing suggestion confirm dialog.

---

### U5. Markdown Rendering Migration and Table Operations

**Goal:** Migrate `MarkdownContent.vue` from `marked` to `markdown-it` + `shiki` for syntax highlighting and better streaming support. Add table action bar with "Copy table as markdown" and "Download table" (CSV) buttons.

**Requirements:** R5, R6, R15, AE3, AE6

**Dependencies:** None

**Files:**
- `frontend/apps/main/src/components/ai-chat/MarkdownContent.vue` — rewrite with markdown-it + shiki
- `frontend/apps/main/src/components/ai-chat/CodeBlock.vue` — integrate shiki for syntax highlighting
- `frontend/apps/main/src/components/ai-chat/TableActionBar.vue` — NEW component
- `frontend/apps/main/src/utils/ai-chat/tableUtils.ts` — NEW utility (HTML table → markdown, HTML table → CSV)
- `frontend/apps/main/src/components/ai-chat/MarkdownContent.test.ts` — NEW test file
- `frontend/apps/main/package.json` — add `markdown-it`, `@types/markdown-it`, `shiki`; remove `marked`

**Approach:**

1. **Install dependencies**:
   ```
   pnpm add markdown-it shiki
   pnpm add -D @types/markdown-it
   pnpm remove marked
   ```

2. **Rewrite `MarkdownContent.vue`**:
   - Replace `marked.parse()` with `markdown-it` rendering
   - Configure `markdown-it` with:
     - `html: false` (security — no raw HTML in user content)
     - `breaks: true` (match current `marked` config)
     - `linkify: true` (auto-link URLs)
   - Integrate `shiki` for code block highlighting:
     - Async load shiki highlighter on first render
     - Use shiki dual-theme mode: `getHighlighter({ themes: ['github-dark', 'github-light'], langs: ['python', 'javascript', 'typescript', 'html', 'css', 'json', 'bash', 'sql'] })`
     - Detect current theme from `van-config-provider` theme prop or CSS `prefers-color-scheme` media query
     - Apply the active theme's tokens to code blocks; switch theme when user toggles dark/light mode
     - Set `markdown-it`'s `highlight` option to use shiki with the detected theme
   - Keep `DOMPurify.sanitize()` for XSS protection
   - Remove the progressive rendering workaround (`THRESHOLD` / split-render logic) — `markdown-it` handles streaming partial markdown naturally
   - Update `:deep()` CSS selectors to match any HTML structure changes from `markdown-it`

3. **Create `TableActionBar.vue`**:
   - Props: `tableHtml: string` (the rendered table HTML)
   - Two buttons: "Copy table as markdown" and "Download table"
   - Render above each `<table>` element in markdown output
   - Implementation: use `markdown-it`'s renderer to intercept `<table>` tags and inject the action bar

4. **Create `tableUtils.ts`**:
   - `htmlTableToMarkdown(html: string): string` — parse HTML table, output markdown table
   - `htmlTableToCsv(html: string): string` — parse HTML table, output CSV with UTF-8 BOM
   - CSV formatting: comma delimiter, quote fields containing commas/quotes/newlines, double-quote escaping

5. **Download as CSV**:
   - Create `Blob` with UTF-8 BOM (`﻿`) prefix for Excel compatibility
   - MIME type: `text/csv;charset=utf-8`
   - Generate filename from first heading or default to `table.csv`
   - Use `URL.createObjectURL()` + temporary `<a>` click for download

6. **Update `CodeBlock.vue`**:
   - Accept pre-highlighted HTML from shiki (via markdown-it integration)
   - Fallback: if shiki not loaded yet, render plain `<code>` block
   - Keep existing copy button and line number features

**Patterns to follow:**
- Existing `MarkdownContent.vue` structure (props, skeleton loading, scoped styles)
- Existing `CodeBlock.vue` for code display patterns
- DOMPurify sanitization (keep existing security pattern)
- Dark mode: CSS variables for all colors

**Test scenarios:**
- Basic markdown renders correctly: headings, paragraphs, bold, links, blockquotes
- Code blocks with language tag show syntax highlighting (Python, JavaScript, SQL)
- Code blocks without language tag render as plain code
- Streaming partial markdown (incomplete code block) renders without errors
- Streaming partial markdown (incomplete table) renders partial table, not broken layout
- Table action bar appears above each table
- "Copy table as markdown" copies correct markdown format
- "Download table" produces valid CSV file with UTF-8 BOM
- CSV handles cells with commas, quotes, and newlines correctly
- CSV handles CJK characters correctly (UTF-8 BOM + Excel compatibility)
- Dark mode: code blocks, tables, and action bar render correctly
- No regression: existing markdown content (links, images, lists) renders identically

**Verification:** All existing markdown features render correctly; syntax highlighting visible in code blocks; table copy/download produce correct output; streaming partial markdown has no flickering; dark mode consistent.

---

### U6. Auto-Scroll Behavior and Streaming Indicator

**Goal:** Implement auto-scroll during streaming with user-interrupt pattern and bouncing dots streaming indicator.

**Requirements:** R5 (scroll portion), R7, F1 step 5

**Dependencies:** U1 (provides `isStreaming` state)

**Files:**
- `frontend/apps/main/src/components/ai/MessageList.vue` — add auto-scroll logic, scroll-to-bottom button
- `frontend/apps/main/src/components/ai-chat/StreamingIndicator.vue` — NEW component
- `frontend/apps/main/src/components/ai-chat/MessageGroup.vue` — integrate indicator
- `frontend/apps/main/src/i18n/locales/zh-CN.ts` — add i18n key for "回到底部"
- `frontend/apps/main/src/components/ai-chat/StreamingIndicator.test.ts` — NEW test file

**Approach:**

1. **Auto-scroll in `MessageList.vue`**:
   - Add `isAutoScrolling: Ref<boolean>` (default `true`)
   - Add `userScrolledUp: Ref<boolean>` (derived from scroll position)
   - On new content during streaming: scroll to bottom if `isAutoScrolling` is true
   - Detect user scroll-up: if `scrollTop + clientHeight < scrollHeight - threshold` (threshold ~50px), set `userScrolledUp = true`, `isAutoScrolling = false`
   - Detect user scroll-to-bottom: if within threshold of bottom, set `userScrolledUp = false`, `isAutoScrolling = true`
   - "回到底部" floating button: shown when `userScrolledUp` is true
   - Click "回到底部": scroll to bottom smoothly, restore `isAutoScrolling = true`
   - When streaming ends: keep current scroll position (don't jump)
   - Planning panel expand/collapse: maintain current reading position (use `scrollIntoView` on a preserved anchor, not scroll-to-bottom)

2. **Create `StreamingIndicator.vue`** (bouncing dots):
   - Props: `visible: boolean`
   - Renders: ⚫⚪⚫ bouncing animation (CSS keyframes)
   - **Block-level placement** (not inline): rendered as a `<div>` below the markdown content in `MessageGroup.vue`, not injected into the markdown HTML output
   - Rationale: simpler implementation (no markdown-it renderer intrusion), and combined with R5 auto-scroll the indicator is always visible at the viewport bottom — visually equivalent to inline placement on mobile screens
   - When visible: dots animate with staggered bounce
   - When not visible: hidden with `v-if` (no layout shift)
   - Animation: CSS `@keyframes bounce` with `animation-delay` stagger per dot

3. **Integrate indicator in `MessageGroup.vue`**:
   - Render `<StreamingIndicator :visible="phase === 'answering'" />` as a block element after `MarkdownContent` (not inside it)
   - The indicator appears below the last line of content, naturally moving down as text grows
   - Combined with R5 auto-scroll: indicator is always visible at the bottom of viewport during streaming

**Patterns to follow:**
- Existing scroll behavior in `MessageList.vue` (if any)
- CSS animations for bouncing dots (match existing animation patterns like `fade-in-up` in `SuggestionChip.vue`)
- Vant: `van-back-top` is NOT suitable here (custom behavior needed); use custom implementation
- i18n: `aiChat.scrollToBottom`: "回到底部"

**Test scenarios:**
- During streaming, view auto-scrolls to show latest content
- User manually scrolls up → auto-scroll pauses
- "回到底部" button appears when user has scrolled up
- Click "回到底部" → view scrolls to bottom, auto-scroll resumes
- Streaming indicator (bouncing dots) visible during `phase === 'answering'`
- Streaming indicator disappears when `phase === 'done'`
- Planning panel expand/collapse preserves current reading position (doesn't jump to top or bottom)
- After streaming ends, scroll position stays where user left it
- Auto-scroll resumes when user manually scrolls back to bottom

**Verification:** Auto-scroll works during streaming; user interrupt pattern functions correctly; bouncing dots visible at text end; "回到底部" button appears/disappears correctly; panel expand/collapse preserves position.

---

### U7. SSE Retry Polish, Artifact Integration, and Dark Mode Verification

**Goal:** End-to-end polish: verify SSE retry with full error UI, verify artifact full-screen preview integration, verify dark mode compliance across all new/modified components.

**Requirements:** R16, R17, R18, F1 step 9, F3

**Dependencies:** U1, U2, U3, U4, U5, U6

**Files:**
- `frontend/apps/main/src/components/ai-chat/ErrorMessage.vue` — NEW component (error bar with retry)
- `frontend/apps/main/src/components/ai/AIChatBox.vue` — wire error state to error bar
- `frontend/apps/main/src/components/ai-chat/ArtifactPreviewPopup.vue` — verify copy button works, verify dark mode
- `frontend/apps/main/src/components/ai-chat/ArtifactFileList.vue` — verify entry card renders correctly
- All new/modified components — dark mode audit

**Approach:**

1. **Error bar UI** (SSE retry failure):
   - Create `ErrorMessage.vue`: bottom bar showing "连接中断，点击重试"
   - On click: call `retry()` from `useThreadChat` (existing method, resends last user message)
   - Shown only after 3 retry failures (from U1 logic)
   - Style: red-tinted bar with `van-notice-bar` or custom styling

2. **Artifact integration verification**:
   - `ArtifactPreviewPopup.vue` already implements full-screen preview ✅
   - Verify: "复制到剪贴板" button in popup works (R16)
   - Verify: "返回" button closes popup correctly
   - Verify: artifact entry card in `ArtifactFileList.vue` shows filename + type icon (R17)
   - Verify: click on entry card opens full-screen popup (not side panel)

3. **Dark mode audit**:
   - Check all new components against dark mode CSS variable usage
   - Required variables: `var(--bg-primary)`, `var(--card-bg)`, `var(--text-primary)`, `var(--text-secondary)`, `var(--border-color)`
   - Verify: no hardcoded `#fff`, `#000`, or other fixed colors (CLAUDE.md red line: no inline `style="color:..."`)
   - Verify: `van-config-provider` theme propagation reaches all new components
   - Test in both light and dark themes

4. **Integration test**:
   - Run full flow: send message → see planning steps → see streaming text with bouncing dots → see token usage → see suggestion chips → click suggestion → see response → copy content → generate artifact → preview artifact
   - Verify no console errors
   - Verify `pnpm typecheck` passes
   - Verify `pnpm test:run` passes

**Patterns to follow:**
- Existing dark mode patterns in `App.vue` and `style.css`
- Existing `ErrorMessage` patterns if any
- CLAUDE.md dark mode rules: CSS variables only, no inline styles

**Test scenarios:**
- Error bar appears after 3 SSE retry failures
- Error bar "点击重试" triggers retry of last message
- Error bar disappears when new message is sent successfully
- Artifact entry card shows filename and type icon
- Click on artifact entry card opens full-screen preview popup
- "复制到剪贴板" in artifact popup copies file content
- Dark mode: all new components (PlanningStepsPanel, SuggestionChips, StreamingIndicator, TableActionBar, ErrorMessage) render correctly
- Dark mode: no hardcoded colors in any new component
- Full integration flow completes without console errors

**Verification:** Error bar works correctly; artifact preview integration verified; dark mode audit passes for all components; `pnpm typecheck` and `pnpm test:run` green.

---

## Risks & Dependencies

### Dependencies

- **Backend SSE protocol** — already completed (see origin: `docs/brainstorms/2026-06-20-deerflow-sse-protocol-alignment-requirements.md`). Backend emits `custom` events for tool_call and suggestions.
- **Token usage endpoint** — `GET /api/threads/{id}/token-usage` exists in `server/apps/agent/routers/threads.py`.
- **LangGraph SDK `custom` stream mode** — the SDK must support `stream_mode` including `'custom'`. Verify SDK version compatibility before U1 implementation.

### Risks

| Risk | Impact | Mitigation |
|------|--------|------------|
| `markdown-it` migration breaks existing rendering | Medium | Test all existing markdown features; keep DOMPurify sanitization; incremental migration if needed |
| Shiki bundle size increases initial load | Low | Lazy-load shiki on first code block render; only include needed languages |
| LangGraph SDK `custom` stream mode not supported | Medium | Verify SDK version before U1; fallback to raw SSE parsing if needed |
| Custom event format differs from expected | Low | Backend code verified (runs.py L231-236, L254); format confirmed |
| Table extraction from markdown-it HTML differs from marked | Low | Use markdown-it's renderer to intercept table tags directly |

---

## Deferred to Follow-Up Work

- **PDF/Word/Excel artifact generation** — requires backend skill support, explicitly deferred per origin scope
- **Streaming progress bar** — not in origin requirements
- **Message reactions / feedback** — out of scope per origin document
- **Session replay UI** — values track supports future replay but UI is deferred

---

## Review Decisions Log

Decisions from ce-doc-review session (2026-06-24):

| # | Finding | Decision | Affected Units |
|---|---------|----------|----------------|
| 1 | Token usage endpoint returns per-thread cumulative totals, not per-message | Extract per-message `usage_metadata` from SSE `values` events; polling as fallback only | U1, U3 |
| 2 | `SuggestionChips.vue` already exists at `src/components/ai/` | Mark as "verify/enhance existing" — no new component needed | U4 |
| 3 | `metadata` SSE event not handled (run_id not captured) | Add `metadata` event handler to capture `run_id` into ref | U1 |
| 4 | Bouncing dots: inline vs block placement ambiguous | Block-level placement below markdown content; combined with auto-scroll, visually equivalent on mobile | U6 |
| 5 | Shiki theme hardcoded to `github-dark`; dark mode adaptation deferred | Use shiki dual-theme mode (`github-dark`/`github-light`) with theme detection from `van-config-provider` | U5 |
