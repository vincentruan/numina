---
type: feat
origin: docs/brainstorms/2026-06-04-agent-chat-phase-c-requirements.md
created: 2026-06-04
status: completed
depends_on:
  - docs/plans/2026-06-04-002-feat-agent-chat-phase-b-plan.md (completed)
---

# Phase C: Artifact Registry + Session History Reconstruction

## Summary

Two parallel frontend workstreams delivering persistent output layer and history reconstruction:

1. **Per-Session Artifact Registry** — floating badge showing artifact count, bottom-sheet listing tool-derived outputs (reports, files, images, links, data). Activates existing `AiFinalAnswer.vue` + `AiArtifactLink.vue` components.
2. **Session History Process Reconstruction** — frontend-only. JSONL already stores tool events. Wire normalizer into `loadSessionMessages()` to reconstruct `ProcessSteps[]` and render as expandable footnote.

Together they solve: ephemeral artifacts lost in scroll, opaque historical answers without process context, and two dead components (`AiFinalAnswer`, `AiArtifactLink`) that anticipated this pattern but were never integrated.

---

## Problem Frame

**Current state:**
- Tool outputs (reports, generated files, URLs) appear inline during streaming but have no persistent access point after scroll
- Historical sessions load only user/assistant message text — process steps (reasoning, tool calls) are discarded
- `AiFinalAnswer.vue` and `AiArtifactLink.vue` exist but are not wired into AIChatPage

**Target state:**
- Floating badge always visible showing artifact count; tap opens bottom-sheet with all session artifacts
- Historical messages show "查看推理过程 (N 步)" footnote; expand to see full process chain
- Artifacts extracted from tool results and persisted in per-session registry

**Why now:** Phase A/B established unified step rendering. Phase C completes the output layer with persistent artifact access and history transparency.

---

## Scope Boundaries

### In Scope

- Artifact extraction from ProcessStep tool results
- Per-session artifact registry (state in AIChatPage, clears on new chat)
- Floating badge + bottom-sheet UI (Vant Popup pattern)
- Process footnote for historical messages
- loadSessionMessages() extension to route all events through normalizer
- i18n keys for new UI strings

### Deferred for Later

- Citation chips (#5) — requires backend parser work
- Cross-session artifact persistence — per-session scope only
- Artifact search/filter in sheet — simple list sufficient
- Artifact preview modal for `data` kind — JSON preview in dialog only
- Export artifact collection — follow-up feature

### Outside this Product's Identity

- Artifact sharing between family members — privacy boundary
- Artifact versioning/diffing — not a document management product

### Deferred to Follow-Up Work

- Performance optimization for sessions with 100+ artifacts (pagination, virtual scroll)
- Artifact deduplication across tool calls (same URL produced twice)

---

## Requirements Trace

| ID | Requirement | Unit |
|----|-------------|------|
| R1 | Artifact badge appears when count > 0 | U2, U5 |
| R2 | Badge shows correct artifact count | U2, U5 |
| R3 | Badge hidden when count = 0 | U2, U5 |
| R4 | Tapping badge opens artifact bottom-sheet | U3, U5 |
| R5 | Sheet lists all artifacts with icons/titles | U3 |
| R6 | Link artifacts open URL in new tab | U3, U5 |
| R7 | File artifacts copy path to clipboard | U3, U5 |
| R8 | Report artifacts navigate to report page | U3, U5 |
| R9 | Data artifacts show JSON preview | U3, U5 |
| R10 | New chat clears artifact registry | U5 |
| R11 | loadSessionMessages routes all events through normalizer | U6 |
| R12 | Historical messages have processSteps populated | U6 |
| R13 | Footnote shows "查看推理过程 (N 步)" | U4, U6 |
| R14 | Footnote collapsed by default in history | U4, U6 |
| R15 | Tap footnote expands to show AiProcessBlock | U4, U6 |

---

## Key Technical Decisions

### K1: Artifact extraction in normalizer (not separate service)

**Decision:** Artifact extraction happens in `aiEventNormalizer.ts` as a helper function, called after each `tool.result` event.

**Rationale:** Normalizer already has access to full step state; avoids separate extraction pass. Extraction is pure function — no side effects.

**Alternative rejected:** Separate artifact service tracking tool results — adds complexity, duplicates state watching.

### K2: Badge position — independent floating button

**Decision:** Badge floats at `bottom: calc(72px + env(safe-area-inset-bottom)); right: 16px; z-index: 11` — independent of scroll-to-bottom button row.

**Rationale:** Future flexibility — badge may grow actions, needs independent positioning. Avoids collision with centered scroll button.

### K3: Bottom-sheet uses van-popup (not van-action-sheet)

**Decision:** Use `<van-popup position="bottom" round>` with custom inner layout, following CapabilityPickerSheet.vue pattern.

**Rationale:** ActionSheet is action-oriented (pick one option). Artifact sheet needs list + per-item actions (open/copy) — custom layout required.

### K4: Process footnote component separate from AiProcessBlock

**Decision:** Create `AiProcessFootnote.vue` as thin wrapper that toggles visibility of existing `AiProcessBlock`.

**Rationale:** Separation of concerns — footnote handles collapsed state + toggle; ProcessBlock handles step rendering. Reuses existing component.

---

## System-Wide Impact

| Surface | Impact |
|---------|--------|
| AIChatPage.vue | New state (sessionArtifacts, showArtifactSheet), new components, loadSessionMessages refactor |
| aiEventNormalizer.ts | New extraction helper function |
| agent-stream.ts | Artifact interface may need `sourceStepId` field |
| i18n locales | New keys for artifact sheet, badge, footnote |
| Dark mode | New components must use CSS variables, no inline styles |

---

## Risks & Dependencies

| Risk | Severity | Mitigation |
|------|----------|------------|
| Badge/sheet z-index conflicts with existing modals | Medium | Test with van-popup overlays; adjust z-index hierarchy |
| JSONL parsing errors for malformed events | Medium | Graceful skip with console.warn, same as current |
| Artifact extraction false positives (matching URLs in text) | Low | Only extract from `step.resultSummary`, not raw content |
| Performance with 50+ artifacts in sheet | Low | Sheet scrollable; defer pagination to follow-up |

**Dependencies:**
- Phase B (AiProcessBlock) — completed
- Vant 4 Popup component — available
- existing AiArtifactLink.vue — available, needs wiring

---

## Implementation Units

### U1. Extend Artifact Interface + Add Extraction Helper

**Goal:** Add `sourceStepId` to Artifact interface; implement extraction helper that maps ProcessStep tool results to Artifact objects.

**Requirements:** none (foundation type/helper consumed by U3, U5, U6)

**Dependencies:** none

**Files:**
- Create: none
- Modify: `frontend/apps/main/src/types/agent-stream.ts`
- Modify: `frontend/apps/main/src/utils/aiEventNormalizer.ts`
- Test: `frontend/apps/main/src/utils/aiEventNormalizer.test.ts`

**Approach:**
1. Extend `Artifact` interface in agent-stream.ts with optional `sourceStepId?: string` and `generatedAt?: string` fields
2. Add `extractArtifactFromStep(step: ProcessStep): Artifact | null` helper in aiEventNormalizer.ts
3. Helper checks step type/status, excludes `write_todos`, extracts url/path/data from result
4. Returns null for non-artifact steps

**Patterns to follow:**
- Existing ProcessStep type handling in aiEventNormalizer.ts
- Artifact interface structure in agent-stream.ts

**Test scenarios:**
- `tool.result` with URL in resultSummary → `link` artifact
- `tool.result` with image URL → `image` artifact
- `tool.result` with path → `file` artifact
- `write_todos` tool → excluded (returns null)
- `reasoning` step → excluded (returns null)
- Step not done → excluded (returns null)
- Duplicate sourceStepId → not added twice

**Verification:** `pnpm typecheck` passes; extraction helper tests pass.

---

### U2. Create AiArtifactBadge Component

**Goal:** Floating badge showing artifact count, positioned above input bar on right side.

**Requirements:** R1, R2, R3

**Dependencies:** U1 (Artifact type extended)

**Files:**
- Create: `frontend/apps/main/src/components/ai/AiArtifactBadge.vue`
- Test: `frontend/apps/main/src/components/ai/AiArtifactBadge.test.ts`

**Approach:**
1. Props: `count: number` (required)
2. Emits: `tap` event when clicked
3. Visibility: `v-if="count > 0"` (hidden when zero)
4. Layout: 44×44px circular button, attachment icon (📎), count pill overlay
5. Position: fixed at `bottom: calc(72px + env(safe-area-inset-bottom)); right: 16px; z-index: 11`
6. Use CSS variables for colors, no inline styles (dark mode compatibility)
7. `<transition>` for smooth enter/leave
8. Accessibility: `role="button"`, `aria-label` with count

**Patterns to follow:**
- Scroll-to-bottom button in AIChatPage.vue (position, transition, z-index)
- CSS variable usage per DESIGN.md
- Badge counter styling from history filter tabs

**Test scenarios:**
- Covers R1. count > 0 → badge visible
- Covers R3. count = 0 → badge hidden
- Covers R2. count = 5 → shows "5" in pill
- Click triggers `tap` emit
- Touch target ≥44×44px
- aria-label includes count

**Verification:** `pnpm typecheck` passes; component tests pass.

---

### U3. Create AiArtifactSheet Component

**Goal:** Bottom-sheet listing all session artifacts with type icons, titles, and action buttons.

**Requirements:** R4, R5, R6, R7, R8, R9

**Dependencies:** U1 (Artifact type), U2 (badge triggers it)

**Files:**
- Create: `frontend/apps/main/src/components/ai/AiArtifactSheet.vue`
- Test: `frontend/apps/main/src/components/ai/AiArtifactSheet.test.ts`

**Approach:**
1. Props: `visible: boolean`, `artifacts: Artifact[]`
2. Emits: `close`, `artifact-tap` (artifact: Artifact)
3. Use `<van-popup position="bottom" round>` with `v-model:show="visible"`
4. Header: "附件 ({count})" + close icon
5. List: scrollable (max 50vh), each item uses existing `AiArtifactLink.vue`
6. Empty state: "暂无附件" when empty
7. CSS variables for colors; `paddingBottom: 'env(safe-area-inset-bottom)'`
8. Item actions: link/image → open URL; file → copy path; report → navigate; data → show JSON dialog

**Patterns to follow:**
- CapabilityPickerSheet.vue (van-popup structure, header, list)
- AiArtifactLink.vue (per-item rendering, action buttons)
- CSS variable usage for dark mode

**Test scenarios:**
- Covers R4. visible=true → popup shown
- Covers R5. artifacts=[...] → renders list with icons
- Covers R6. tap link artifact → `artifact-tap` emit with artifact
- Covers R7. tap file artifact → `artifact-tap` emit with artifact
- Covers R8. tap report artifact → `artifact-tap` emit with artifact
- Covers R9. tap data artifact → `artifact-tap` emit with artifact
- Empty artifacts → shows "暂无附件"
- Close icon → `close` emit
- Scrollable when many artifacts

**Verification:** `pnpm typecheck` passes; component tests pass.

---

### U4. Create AiProcessFootnote Component

**Goal:** Collapsible footnote beneath historical assistant messages showing "查看推理过程 (N 步)".

**Requirements:** R13, R14, R15

**Dependencies:** none (uses existing AiProcessBlock)

**Files:**
- Create: `frontend/apps/main/src/components/ai/AiProcessFootnote.vue`
- Test: `frontend/apps/main/src/components/ai/AiProcessFootnote.test.ts`

**Approach:**
1. Props: `stepCount: number`, `expanded: boolean`
2. Emits: `toggle` (expanded: boolean)
3. Collapsed: single row with icon + text + chevron
4. Expanded: shows full `AiProcessBlock` beneath
5. Font: 12px, color `var(--text-secondary)`
6. Use `<transition>` for expand animation
7. Accessibility: `role="button"`, `aria-expanded`

**Patterns to follow:**
- AiProcessBlock usage (step rendering)
- Collapsible accordion pattern (if exists in codebase)
- CSS variable for text color

**Test scenarios:**
- Covers R13. stepCount=5 → shows "查看推理过程 (5 步)"
- Covers R14. expanded=false initially → footnote collapsed
- Covers R15. tap collapsed → emits toggle(true), shows ProcessBlock
- Tap expanded → emits toggle(false), hides ProcessBlock
- aria-expanded reflects state

**Verification:** `pnpm typecheck` passes; component tests pass.

---

### U5. Integrate Artifact Registry into AIChatPage

**Goal:** Add sessionArtifacts state, watch processSteps for extraction, render badge + sheet, handle artifact actions.

**Requirements:** R1-R10 (all artifact registry functional)

**Dependencies:** U1, U2, U3

**Files:**
- Modify: `frontend/apps/main/src/pages/AIChatPage.vue`
- Test: `frontend/apps/main/src/pages/AIChatPage.test.ts` (extend existing)

**Approach:**
1. Add `sessionArtifacts = ref<Artifact[]>([])` and `showArtifactSheet = ref(false)`
2. Watch `messages[].processSteps` changes; call `extractArtifactFromStep` for each new done tool_call step
3. Deduplicate by `sourceStepId` before adding
4. Clear `sessionArtifacts` in `onNewChat()` and when starting new streaming session
5. Render `<AiArtifactBadge>` in template (positioned after message list)
6. Render `<AiArtifactSheet>` with sessionArtifacts
7. Handle `artifact-tap`: link/image → window.open; file → clipboard + toast; report → router.push or window.open; data → showConfirmDialog with JSON preview
8. Message interface: add `processExpanded?: boolean` for footnote toggle state

**Patterns to follow:**
- Existing message state management in AIChatPage
- Watch pattern for processSteps (similar to planSteps watching)
- Toast/dialog usage from Vant
- Router navigation pattern

**Test scenarios:**
- Covers R1. artifact extracted → badge appears
- Covers R2. count matches extracted artifacts
- Covers R3. sessionArtifacts=[] → badge hidden
- Covers R4. tap badge → showArtifactSheet=true
- Covers R5. sessionArtifacts populated → sheet renders list with type icons and titles
- Covers R6. tap link artifact → window.open called
- Covers R7. tap file artifact → clipboard.write, toast shown
- Covers R8. tap report artifact → router.push to report page
- Covers R9. tap data artifact → JSON preview dialog shown
- Covers R10. onNewChat → sessionArtifacts=[]
- Tool result with artifact → added to sessionArtifacts once
- Duplicate stepId → not added twice

**Verification:** `pnpm typecheck` passes; integration tests pass; artifact badge appears in live session.

---

### U6. Extend loadSessionMessages for History Reconstruction

**Goal:** Route all JSONL events through normalizer to reconstruct processSteps for historical messages.

**Requirements:** R11-R15 (session history functional)

**Dependencies:** U1, U4, U5 (processExpanded field)

**Files:**
- Modify: `frontend/apps/main/src/pages/AIChatPage.vue` (loadSessionMessages function)
- Test: `frontend/apps/main/src/pages/AIChatPage.test.ts` (extend existing)

**Approach:**
1. Create `NormalizationState` at start of loadSessionMessages
2. Parse all event types (not just user.message/assistant.message)
3. Route each event through `normalizeAgentEvent(event, normState)`
4. On `assistant.message`: assign `normState.steps` to `message.processSteps`, reset state for next message
5. Extract artifacts from reconstructed steps (same as live streaming)
6. Render `<AiProcessFootnote>` beneath historical assistant messages
7. Render `<AiProcessBlock>` when `processExpanded=true`

**Patterns to follow:**
- Existing loadSessionMessages structure
- NormalizationState creation and usage in onSend()
- syncStepsToMessage() pattern

**Test scenarios:**
- Covers R11. loadSessionMessages handles tool.call event
- Covers R11. loadSessionMessages handles tool.result event
- Covers R12. historical assistant message has processSteps populated
- Covers R13. processSteps.length=3 → footnote shows "查看推理过程 (3 步)"
- Covers R14. processExpanded=false initially → footnote collapsed
- Covers R15. tap footnote → processExpanded=true, ProcessBlock shown
- Error event in history → shows error step
- Malformed JSONL line → skipped gracefully

**Verification:** `pnpm typecheck` passes; history reconstruction test passes; historical session shows process footnote.

---

### U7. Add i18n Keys for New Components

**Goal:** Add i18n keys for badge, sheet, footnote, and related strings in both locales.

**Requirements:** i18n compliance (cross-cutting)

**Dependencies:** none

**Files:**
- Modify: `frontend/apps/main/src/i18n/locales/zh-CN.ts`
- Modify: `frontend/apps/main/src/i18n/locales/en-US.ts`

**Approach:**
1. Add `aiArtifact` section with keys: `badgeLabel`, `sheetTitle`, `emptyMessage`, `openUrl`, `copyPath`, `viewJson`, `pathCopied`, `jsonPreviewTitle`
2. Add `aiProcessFootnote` keys: `viewProcess`, `stepCount`
3. Follow emoji-prefix convention for toast strings
4. Keep zh-CN and en-US in lockstep

**Patterns to follow:**
- Existing `aiProcess` section structure
- Emoji convention for toast strings (✅, ❌)
- Key naming convention (camelCase)

**Test scenarios:**
- All new keys defined in both locales
- No hardcoded strings in components
- `pnpm typecheck` passes (i18n type checking)

**Verification:** `pnpm typecheck` passes; no missing key warnings in dev.

---

## Verification Strategy

### Functional Verification

1. **Artifact badge appears** in live session when tool produces artifact
2. **Badge count updates** as artifacts are extracted
3. **Sheet opens** on badge tap, lists artifacts with correct icons
4. **Artifact actions work** — open URL, copy path, navigate to report
5. **New chat clears** artifact registry
6. **Historical session** shows process footnote with correct step count
7. **Footnote expands** to show full process chain

### Quality Gates

```bash
cd frontend/apps/main
pnpm typecheck     # TypeScript compilation
pnpm lint          # ESLint
pnpm test:run      # Vitest tests
```

### Regression Check

- Existing live streaming unchanged
- Phase A/B features still working (AiStepBlock, plan skeleton)
- Dark mode: badge/sheet/footnote render correctly

---

## Deferred to Implementation

- Exact animation timing for footnote expand
- JSON preview dialog layout (scrollable, monospace font, max-height, size threshold)
- Sheet item action button placement (inline vs separate row)
- Focus trap and keyboard navigation for artifact sheet
- aria-live region for dynamic badge count updates