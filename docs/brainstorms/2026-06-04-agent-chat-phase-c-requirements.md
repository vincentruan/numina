# Phase C: Artifact Registry + Session History Reconstruction — Requirements

Date: 2026-06-04
Source: `docs/ideation/2026-06-04-agent-chat-interaction-ideation.md` (#6 + #7)
Depends on: Phase B (Plan Skeleton + Subtask Card Upgrade) — completed
Status: Ready for planning

## Summary

Two parallel workstreams delivering persistent output layer and history reconstruction:

1. **Per-Session Artifact Registry** — floating badge with artifact count, bottom-sheet listing tool-derived outputs (reports, files, images, links, structured data). Activates existing `AiFinalAnswer.vue` + `AiArtifactLink.vue` components (currently unwired in AIChatPage).
2. **Session History Process Reconstruction** — frontend-only. JSONL already stores tool events. Wire normalizer into `loadSessionMessages()` to reconstruct `ProcessSteps[]` and render as expandable footnote beneath final answer.

Together they solve: ephemeral artifacts lost in scroll, opaque historical answers without process context, and two dead components (`AiFinalAnswer`, `AiArtifactLink`) that anticipated this pattern but were never integrated.

---

## 1. Per-Session Artifact Registry

### 1.1 Purpose

Collect all tool-derived outputs from the current conversation into a persistent artifact registry. Users can access artifacts via a floating badge that shows the count. Tapping opens a bottom-sheet listing all artifacts with type icons, titles, and quick actions (open/copy).

This activates two existing but unused components:
- `AiFinalAnswer.vue` — report-style answer block with artifact row support
- `AiArtifactLink.vue` — individual artifact link card

### 1.2 Artifact Definition

An **artifact** is any tool result that produces persistent output:

| Kind | Trigger | Example |
|------|---------|---------|
| `report` | Agent capability that generates structured report output | 家庭资产体检报告、负债健康报告 |
| `file` | Tool output with `path` field (local file path) | `/tmp/analysis_result.json` |
| `image` | Tool output with `url` pointing to image MIME type | Generated chart PNG |
| `link` | Tool output with `url` pointing to non-image resource | External PDF、Web page |
| `data` | Tool output with structured `data` field (JSON) | Search results, calculation output |

**Exclusions:**
- Simple text answers from chat assistant (ephemeral, not artifacts)
- Tool calls without persistent output (e.g., pure computation with inline result)
- `write_todos` internal tool (planning mechanism, not user artifact)

### 1.3 Artifact Extraction Logic

Artifacts are extracted from `ProcessStep` entries after each tool completes:

```ts
// In aiEventNormalizer or dedicated artifact extraction step
function extractArtifactFromStep(step: ProcessStep): Artifact | null {
  if (step.type !== 'tool_call' || step.status !== 'done') return null
  if (step.name === 'write_todos') return null // Internal, exclude

  // Check for report-type tool results
  if (step.toolType === 'report' && step.resultSummary) {
    return {
      id: step.id,
      kind: 'report',
      title: step.displayName || step.name,
      url: step.args?.report_url,
      generatedAt: new Date().toISOString(),
      sourceStepId: step.id,
    }
  }

  // Check for url/path in result
  const result = step.resultSummary || ''
  const urlMatch = result.match(/https?:\/\/[^\s]+/)
  const pathMatch = result.match(/(?:\/[\w.-]+)+/)

  if (urlMatch) {
    const url = urlMatch[0]
    const isImage = /\.(png|jpg|jpeg|gif|svg|webp)$/i.test(url)
    return {
      id: step.id,
      kind: isImage ? 'image' : 'link',
      title: step.displayName || step.name,
      url,
      generatedAt: new Date().toISOString(),
      sourceStepId: step.id,
    }
  }

  if (pathMatch) {
    return {
      id: step.id,
      kind: 'file',
      title: step.displayName || step.name,
      path: pathMatch[0],
      generatedAt: new Date().toISOString(),
      sourceStepId: step.id,
    }
  }

  // Check for structured data in result (JSON-like)
  if (step.args && typeof step.args === 'object' && Object.keys(step.args).length > 0) {
    return {
      id: step.id,
      kind: 'data',
      title: step.displayName || step.name,
      data: step.args,
      generatedAt: new Date().toISOString(),
      sourceStepId: step.id,
    }
  }

  return null
}
```

### 1.4 Registry State Management

Per-session artifact list lives in `AIChatPage.vue` state:

```ts
// In AIChatPage.vue
const sessionArtifacts = ref<Artifact[]>([])

// Watch processSteps changes to extract new artifacts
watch(
  () => messages.value.flatMap(m => m.processSteps || []),
  (allSteps) => {
    for (const step of allSteps) {
      if (step.type === 'tool_call' && step.status === 'done') {
        const artifact = extractArtifactFromStep(step)
        if (artifact && !sessionArtifacts.value.some(a => a.id === artifact.id)) {
          sessionArtifacts.value.push(artifact)
        }
      }
    }
  },
  { deep: true }
)

// Clear on new chat
function onNewChat() {
  sessionArtifacts.value = []
  // ... existing new chat logic
}
```

### 1.5 Floating Badge Component (`AiArtifactBadge.vue`)

```ts
interface AiArtifactBadgeProps {
  count: number
  position?: 'bottom-right' | 'bottom-left'  // Default: 'bottom-right'
}

interface AiArtifactBadgeEmits {
  'tap': []  // Opens artifact bottom-sheet
}
```

**Visual specification:**
- Badge: 44×44px circular floating button
- Background: `var(--card-bg)` with `var(--shadow-elevated)`
- Icon: 📎 (attachment emoji) at 16px
- Count badge: 12px pill overlay with `var(--van-primary-color)` background, white text
- Position: fixed at `bottom: calc(72px + env(safe-area-inset-bottom))` to float above input bar
- Hidden when `count === 0`
- Z-index: 11 (below scroll-to-bottom button which is z-index 10, but above input bar)

**Accessibility:**
- `role="button"`, `aria-label="查看 {count} 个附件"`
- Touch target: 44×44px minimum

### 1.6 Artifact Bottom-Sheet (`AiArtifactSheet.vue`)

Uses Vant `ActionSheet` or custom popup:

```ts
interface AiArtifactSheetProps {
  visible: boolean
  artifacts: Artifact[]
}

interface AiArtifactSheetEmits {
  'close': []
  'artifact-tap': [artifact: Artifact]  // Open/copy action
}
```

**Visual specification:**
- Header: "附件 ({count})" with close button
- List: scrollable, each item rendered via `AiArtifactLink.vue`
- Item layout: icon (16px) + title (truncate) + action button (open/copy)
- Empty state: "暂无附件" message when `artifacts.length === 0`
- Max height: 50vh on mobile, with scroll

### 1.7 Integration with AIChatPage

```vue
<!-- In AIChatPage.vue template -->
<AiArtifactBadge
  v-if="sessionArtifacts.length > 0"
  :count="sessionArtifacts.length"
  @tap="showArtifactSheet = true"
/>

<AiArtifactSheet
  v-model:show="showArtifactSheet"
  :artifacts="sessionArtifacts"
  @artifact-tap="onArtifactTap"
/>
```

**Artifact actions:**
- `kind: 'link'` / `kind: 'image'` → open URL in new tab
- `kind: 'file'` → copy path to clipboard
- `kind: 'report'` → navigate to report detail page (if internal URL) or open external
- `kind: 'data'` → show JSON preview in dialog

---

## 2. Session History Process Reconstruction

### 2.1 Purpose

When loading a past session from history, reconstruct the full process chain (`ProcessSteps[]`) from stored NDJSON events. Render the answer immediately visible, with process steps as an expandable footnote: "查看推理过程 (N 步)".

This restores transparency for historical answers — users can verify why the agent concluded something, especially valuable for financial recommendations.

### 2.2 Storage Verification

JSONL files already store tool events via `session_journal.py`:
- `tool.call` events with name, arguments, tool_call_id
- `tool.result` events with content, success status
- `tool.progress` events (if backend emitted during execution)

The frontend `loadSessionMessages()` currently filters to `user.message` and `assistant.message` only — tool events are parsed but discarded. The fix: pass all events through the normalizer to reconstruct steps.

### 2.3 loadSessionMessages() Extension

```ts
// In AIChatPage.vue — extend loadSessionMessages
async function loadSessionMessages(session: SessionSummary) {
  showHistory.value = false
  messages.value = []
  currentSessionId.value = session.session_id
  asking.value = true
  connecting.value = true

  // Reset session artifacts (will be re-extracted from steps)
  sessionArtifacts.value = []

  let reader: ReadableStreamDefaultReader<Uint8Array> | null = null
  try {
    reader = await streamSessionEvents(session.session_id)
    const decoder = new TextDecoder()
    let buf = ''
    const normState = createNormalizationState()

    while (true) {
      const { done, value } = await reader.read()
      if (done) break
      buf += decoder.decode(value, { stream: true })
      let nl = buf.indexOf('\n')
      while (nl >= 0) {
        const line = buf.slice(0, nl).trim()
        buf = buf.slice(nl + 1)
        if (!line) { nl = buf.indexOf('\n'); continue }

        try {
          const event = JSON.parse(line) as AgentEvent

          // Route ALL events through normalizer (not just user/assistant)
          normalizeAgentEvent(event, normState)

          // Handle user/assistant message events to build messages array
          if (event.type === 'user.message') {
            messages.value.push({
              id: event.eventId ?? Date.now().toString(),
              role: 'user',
              content: event.content ?? '',
              created_at: event.timestamp ?? new Date().toISOString(),
              displayTime: formatTime(event.timestamp ?? new Date().toISOString()),
            })
          } else if (event.type === 'assistant.message') {
            // Build assistant message with reconstructed steps
            const msg: Message = {
              id: event.eventId ?? Date.now().toString(),
              role: 'assistant',
              phase: 'done',
              content: event.content ?? '',
              renderedContent: renderMarkdown(event.content ?? ''),
              created_at: event.timestamp ?? new Date().toISOString(),
              displayTime: formatTime(event.timestamp ?? new Date().toISOString()),
              processSteps: [...normState.steps], // Reconstructed steps
              processStatus: 'done',
              // Collapse process block by default in history view
              // User can expand via "查看推理过程" footnote
            }
            messages.value.push(msg)

            // Extract artifacts from reconstructed steps
            for (const step of normState.steps) {
              const artifact = extractArtifactFromStep(step)
              if (artifact && !sessionArtifacts.value.some(a => a.id === artifact.id)) {
                sessionArtifacts.value.push(artifact)
              }
            }

            // Reset normalizer for next message
            normState.steps = []
          }
        } catch { /* skip malformed */ }
        nl = buf.indexOf('\n')
      }
    }
  } catch {
    showToast(t('aiChat.loadSessionFailed'))
  } finally {
    reader?.cancel().catch(() => {})
    asking.value = false
    connecting.value = false
    await scrollToBottom()
  }
}
```

### 2.4 Process Footnote Component (`AiProcessFootnote.vue`)

```ts
interface AiProcessFootnoteProps {
  stepCount: number
  expanded: boolean
}

interface AiProcessFootnoteEmits {
  'toggle': [expanded: boolean]
}
```

**Visual specification:**
- Collapsed state: single row `[📋] 查看推理过程 (N 步)` with chevron
- Tap expands to show full `AiProcessBlock` with all steps
- Font: 12px, color `var(--text-secondary)`
- Background: transparent when collapsed, `var(--card-bg)` when expanded
- Position: beneath answer text, before message actions

### 2.5 History Message Rendering

```vue
<!-- In AIChatPage.vue message rendering -->
<div v-if="msg.role === 'assistant'" class="bubble-text" v-html="msg.renderedContent" />

<!-- Process footnote for historical messages -->
<AiProcessFootnote
  v-if="msg.role === 'assistant' && msg.processSteps && msg.processSteps.length > 0"
  :step-count="msg.processSteps.length"
  :expanded="msg.processExpanded ?? false"
  @toggle="msg.processExpanded = !msg.processExpanded"
/>

<AiProcessBlock
  v-if="msg.role === 'assistant' && msg.processExpanded && msg.processSteps"
  :status="msg.processStatus || 'done'"
  :steps="msg.processSteps"
  :default-expanded="false"
/>
```

### 2.6 Message Interface Extension

```ts
interface Message {
  // ... existing fields ...
  processExpanded?: boolean  // NEW: toggle state for history footnote
}
```

---

## 3. Files Created

| File | Purpose |
|------|---------|
| `src/components/ai/AiArtifactBadge.vue` | Floating badge showing artifact count |
| `src/components/ai/AiArtifactSheet.vue` | Bottom-sheet listing artifacts |
| `src/components/ai/AiProcessFootnote.vue` | Collapsible "查看推理过程" footnote for history |

## 4. Files Modified

| File | Change |
|------|--------|
| `src/pages/AIChatPage.vue` | Add artifact badge + sheet; extend `loadSessionMessages()` to route all events through normalizer; add `sessionArtifacts` state; add process footnote to history messages |
| `src/utils/aiEventNormalizer.ts` | Add artifact extraction helper function (optional, can be inline) |
| `src/types/agent-stream.ts` | Extend `Artifact` interface with `sourceStepId` field; add `processExpanded` to Message type (if not already present) |
| `src/i18n/locales/zh-CN.ts` | Add artifact sheet i18n keys |
| `src/i18n/locales/en-US.ts` | Same keys in English |

---

## 5. Dependencies

- No new npm packages
- No backend changes (JSONL already stores tool events)
- Reuses existing `AiArtifactLink.vue` for artifact rendering
- Uses Vant `ActionSheet` or `Popup` for bottom-sheet
- CSS-only animations (badge pulse, footnote expand transition)

---

## 6. Acceptance Criteria

### 6.1 Artifact Registry — Functional

- [ ] Artifact badge appears when at least one artifact exists in current session
- [ ] Badge shows correct artifact count
- [ ] Badge is hidden when artifact count is 0
- [ ] Tapping badge opens artifact bottom-sheet
- [ ] Artifact sheet lists all session artifacts with correct icons
- [ ] Each artifact item shows title (truncate) and action button
- [ ] `link` artifacts open URL in new tab on tap
- [ ] `file` artifacts copy path to clipboard on tap
- [ ] `report` artifacts navigate to report page or open external URL
- [ ] `data` artifacts show JSON preview in dialog
- [ ] New chat clears the artifact registry
- [ ] Artifact registry persists within session (scrolling doesn't lose artifacts)
- [ ] Artifacts are extracted from tool results after each tool completes

### 6.2 Session History — Functional

- [ ] `loadSessionMessages()` routes all events through normalizer
- [ ] Historical assistant messages have `processSteps` populated
- [ ] Process footnote shows correct step count: "查看推理过程 (N 步)"
- [ ] Footnote collapsed by default in history view
- [ ] Tapping footnote expands to show full AiProcessBlock with all steps
- [ ] Tapping again re-collapses
- [ ] Steps in history use same AiStepBlock rendering as live stream
- [ ] Collapsed reasoning/tool_call steps show summary + duration
- [ ] Tool results display correctly in expanded steps
- [ ] Error steps show error message in history

### 6.3 Artifact Extraction — Functional

- [ ] Report-type tool outputs become `report` artifacts
- [ ] Tool results with URL become `link` or `image` artifacts (based on extension)
- [ ] Tool results with path become `file` artifacts
- [ ] Tool results with structured data become `data` artifacts
- [ ] `write_todos` tool is excluded from artifact list
- [ ] Duplicate artifacts (same step ID) are not added twice
- [ ] Artifacts are extracted from historical sessions when loaded

### 6.4 Accessibility

- [ ] Badge: `role="button"`, `aria-label` with count
- [ ] Artifact sheet: `role="dialog"`, proper focus management
- [ ] Footnote: `role="button"`, `aria-expanded`, keyboard accessible
- [ ] All touch targets ≥44×44px

### 6.5 Visual / Design System Compliance

- [ ] Badge uses `var(--card-bg)`, `var(--shadow-elevated)`
- [ ] Count pill uses `var(--van-primary-color)`
- [ ] Artifact sheet uses design tokens (no hardcoded colors)
- [ ] Footnote uses `var(--text-secondary)`, 12px
- [ ] Dark mode: badge adapts via CSS variables
- [ ] No inline `style="..."` on themable elements

### 6.6 Mobile (≤425px)

- [ ] Badge floats above input bar, doesn't interfere with scroll-to-bottom button
- [ ] Artifact sheet scrollable, max 50vh
- [ ] Footnote readable at 375px width
- [ ] Expand/collapse smooth on touch

### 6.7 Regression

- [ ] `pnpm typecheck` passes
- [ ] `pnpm test:run` passes
- [ ] Existing live streaming behavior unchanged
- [ ] Existing session list/history sidebar still works
- [ ] Phase A/B acceptance criteria remain passing

---

## 7. Non-Goals (Deferred)

- Citation chips (#5) — requires backend parser work, deferred to follow-up
- Cross-session artifact registry — per-session scope only for Phase C
- Artifact search/filter — simple list is sufficient
- Full artifact detail view (preview modal) — `data` artifacts show JSON preview only
- Export artifact collection — follow-up feature

---

## 8. Implementation Notes (for planning reference)

- **Incremental delivery**: Ship artifact badge first (visible progress marker). Then add sheet. Then history reconstruction.
- **Reuse AiFinalAnswer**: The existing `AiFinalAnswer.vue` can be used in artifact sheet for detailed artifact view if needed — it already has report header + artifact row rendering.
- **Normalizer reuse**: The `aiEventNormalizer.ts` already handles all event types — the fix is purely in `loadSessionMessages()` to route events through it rather than filtering to user/assistant only.
- **Artifact extraction timing**: Extract after `normalizeAgentEvent` completes for each tool_result event, not during streaming (to avoid partial artifacts).
- **History footprint**: Process footnote adds ~32px per assistant message when collapsed. This is acceptable on mobile — answer text is immediately visible, process is one tap away.