---
title: "feat: Unified AiStepBlock primitive + collapsible reasoning accordion"
status: completed
origin: docs/brainstorms/2026-06-04-agent-chat-phase-a-requirements.md
created: 2026-06-04
type: feat
---

# feat: Unified AiStepBlock Primitive + Collapsible Reasoning Accordion

## Problem Frame

The agent chat page renders 5 step types through 2 separate components + 3 inline template blocks, each with duplicated animation logic, inconsistent status handling, and no accessibility attributes. On mobile (≤425px), expanded reasoning walls push the final answer off-screen. The current block-level auto-collapse hides all content (including useful tool results) rather than selectively compressing reasoning.

---

## Scope Boundaries

### In Scope

- New `AiStepBlock.vue` component handling all 5 step types (reasoning, tool_call, subagent, artifact, progress)
- Per-reasoning-step accordion with auto-collapse on `phase → answering`
- Gradient-sweep active border for running/streaming steps
- Completion compression for done tool_calls (single-line summary)
- Full accessibility: `aria-expanded`, `aria-controls`, `role="list/listitem"`, `aria-live`
- i18n keys for new labels
- Removal of superseded components after migration

### Deferred to Follow-Up Work

- Plan skeleton rendering (Phase B, Idea #1)
- Subtask card spotlight beyond gradient border (Phase B, Idea #4)
- Citation chips, artifact registry, session history (Phase C)
- Backend plan event types
- Streaming markdown renderer upgrade

---

## Key Technical Decisions

1. **Single component with internal type switch** — not 5 slot-based variants. The requirements spec a flat props interface; internal `v-if` on `type` keeps the template readable while sharing all status/animation/collapse logic. (see origin: §1.2, §1.7)

2. **`autoCollapseSignal` prop instead of event bus** — parent AiProcessBlock passes a reactive boolean computed from `phase`. This avoids global event coordination and keeps the data flow unidirectional. (see origin: §2.6, §2.7)

3. **Block-level auto-collapse removed** — replaced by per-reasoning-step collapse. The overall AiProcessBlock still has its header + expand/collapse for the entire section, but its `hasAutoCollapsed` timer logic is deleted. (see origin: §2.7)

4. **CSS `::before` pseudo-element for gradient border** — avoids wrapper div overhead, works with `border-radius: 8px`, and degrades gracefully under `prefers-reduced-motion`. (see origin: §1.5)

5. **`compressed` prop driven by parent** — AiProcessBlock sets `compressed=true` on tool_call steps when they transition to `done`. This keeps the compression decision centralized and predictable. (see origin: Implementation Notes)

6. **`useStepCollapse` composable** — extracts the auto-collapse + manual-override + timer cleanup logic into a reusable composable, preventing duplication if future step types need collapsibility.

---

## System-Wide Impact

- **AiProcessBlock.vue** — template rewritten to use `<AiStepBlock>` in v-for; block-level auto-collapse logic removed
- **i18n files** — 2 new keys per locale (`aiProcess.reasoningDuration`, `aiProcess.thinkingLabel`)
- **No changes to**: `aiEventNormalizer.ts`, `useAgentEventStream.ts`, `agent-stream.ts` types, backend

---

## Implementation Units

### U1. Extract `getToolDisplayInfo` imports and add i18n keys

**Goal:** Prepare shared utilities and i18n entries that downstream units depend on.

**Requirements:** Origin §2.3 (summary fallback label), §2.4 (duration format)

**Dependencies:** None

**Files:**
- `frontend/apps/main/src/i18n/locales/zh-CN.ts` (modify)
- `frontend/apps/main/src/i18n/locales/en-US.ts` (modify)

**Approach:** Add `aiProcess.reasoningDuration` (`"思考 {seconds}s"` / `"Thought {seconds}s"`), `aiProcess.thinkingLabel` (`"思考中..."` / `"Thinking..."`) to both locale files. Verify `getToolDisplayInfo` in `utils/toolDisplayMapping.ts` is already exported cleanly (it is — no extraction needed, just confirm import path).

**Patterns to follow:** Existing `aiProcess.*` keys in `zh-CN.ts`.

**Test scenarios:**
- i18n key interpolation: `t('aiProcess.reasoningDuration', { seconds: 5 })` returns `"思考 5s"` in zh-CN locale
- Fallback label: `t('aiProcess.thinkingLabel')` returns non-empty string in both locales

**Verification:** `pnpm typecheck` passes; keys accessible via `useI18n()`.

---

### U2. Create `useStepCollapse` composable

**Goal:** Encapsulate expand/collapse state, auto-collapse timing, and manual-override logic into a reusable composable.

**Requirements:** Origin §2.6 (auto-collapse timing), §2.2 (accordion states)

**Dependencies:** U1

**Files:**
- `frontend/apps/main/src/composables/useStepCollapse.ts` (create)
- `frontend/apps/main/src/composables/useStepCollapse.test.ts` (create)

**Approach:**

Composable signature:
```
useStepCollapse(options: { defaultExpanded: boolean, autoCollapseSignal: Ref<boolean>, status: Ref<string> })
→ { isExpanded: Ref<boolean>, toggle: () => void, hasAutoCollapsed: Ref<boolean> }
```

Internal logic:
- Watch `autoCollapseSignal`: when it becomes `true` and status is `done` and `!hasAutoCollapsed`, set 1s timer to collapse
- `toggle()`: clears pending timer, sets `hasAutoCollapsed = true`, flips `isExpanded`
- Cleanup: `onUnmounted` clears timer

**Patterns to follow:** Timer pattern in `composables/useAITask.ts` (setInterval/clearInterval with onUnmounted cleanup).

**Test scenarios:**
- Auto-collapse fires 1s after signal becomes true when status is `done`
- Auto-collapse does NOT fire when status is still `streaming`
- Manual toggle before auto-collapse cancels the timer
- Manual toggle after auto-collapse re-expands without triggering another collapse
- Timer is cleaned up on unmount (no leaked timers)
- `defaultExpanded: false` starts collapsed and auto-collapse signal has no effect

**Verification:** `pnpm test:run` — all 6 scenarios pass.

---

### U3. Create `AiStepBlock.vue` — core structure and status rendering

**Goal:** Build the base component with header, status icon, duration badge, expand/collapse, and gradient-sweep border. Handle `reasoning` and `tool_call` types first (90%+ of real usage).

**Requirements:** Origin §1.2–§1.8, §2.1–§2.5

**Dependencies:** U1, U2

**Files:**
- `frontend/apps/main/src/components/ai/AiStepBlock.vue` (create)
- `frontend/apps/main/src/components/ai/AiStepBlock.test.ts` (create)

**Approach:**

Template structure per origin §1.7. Uses `useStepCollapse` composable for expand/collapse. Status-driven CSS classes:
- `.ai-step-block--pending`, `--streaming`, `--running`, `--done`, `--error`
- `.ai-step-block--active` (streaming OR running) → `::before` gradient sweep
- `.ai-step-block--compressed` → single-line layout

Content switch via `v-if` on `props.type`:
- `reasoning`: streaming text + summary computed (first sentence, ≤40 chars, reactive)
- `tool_call`: args summary (reuse `formatArgsSummary` from toolDisplayMapping) + result area; compressed mode shows `[icon] name · result · elapsed`

Duration badge: `setInterval` ticks while `status === 'streaming' || status === 'running'`, stops on `done/error`. Formatted via `aiProcess.reasoningDuration` for reasoning, raw `Ns` for tool_call.

Accessibility: `role="listitem"`, `aria-expanded`, `aria-controls`, `aria-live="polite"` on status region.

All keyframes (`gradient-sweep`, `shimmer-sweep`, `body-shimmer`, `pulse`) defined once in this component's `<style scoped>`, with `prefers-reduced-motion` guards.

**Patterns to follow:** 
- Existing visual structure from `AiProcessStep.vue` and `AiToolCallStep.vue`
- CSS token usage from `AiProcessBlock.vue` (uses `--card-bg`, `--color-card-border`, `--text-primary`, etc.)
- `getToolDisplayInfo()` import from `@/utils/toolDisplayMapping`

**Test scenarios:**
- Renders reasoning type with streaming status: shows shimmer, expanded content, ticking duration
- Renders reasoning type with done status: shows static content, frozen duration, summary in header
- Renders tool_call type running: shows gradient border, tool name, args summary
- Renders tool_call type done: compresses to single-line (icon + name + result + elapsed)
- Renders tool_call type error: shows error message, red border, no compression
- Tap on compressed tool_call expands to show full args + result
- `aria-expanded` attribute reflects actual expand state
- `prefers-reduced-motion` media query disables all animations (verify via matchMedia mock)
- Summary extraction: reactive update when content prop changes (not frozen at mount time)
- Summary truncation: Chinese content ≤40 chars + `…`, English ≤60 chars + `…`
- No inline `style` attributes for color/background in rendered output (design token compliance)

**Verification:** `pnpm typecheck` + `pnpm test:run` pass; visual check of gradient border animation in browser at 375px.

---

### U4. Extend `AiStepBlock.vue` — subagent, artifact, progress types

**Goal:** Add the remaining 3 step types to complete the unified primitive.

**Requirements:** Origin §1.2 (subagent/artifact/progress props)

**Dependencies:** U3

**Files:**
- `frontend/apps/main/src/components/ai/AiStepBlock.vue` (modify)
- `frontend/apps/main/src/components/ai/AiStepBlock.test.ts` (modify)

**Approach:**

Add `v-else-if` branches for:
- `subagent`: title + description + status icon + result/error display. Status maps: running→gradient border, done→green icon, failed→red icon+error text.
- `artifact`: rendered as a link card (`<a>` with icon, title, path). Not collapsible by default.
- `progress`: title + description + status icon. Not collapsible by default.

These types are simpler — no compression, no auto-collapse. They only use the shared header/status/border logic.

**Patterns to follow:** Current inline template blocks in `AiProcessBlock.vue` lines 40–74 (subagent, artifact, progress).

**Test scenarios:**
- Subagent running: gradient border, title from props, spinning icon
- Subagent done: static border, result text visible
- Subagent failed: red border, error text visible
- Artifact: renders as link with href, icon, and title; no collapse toggle
- Progress running: shows title + description, gradient border
- Progress done: static state, no collapse toggle present

**Verification:** `pnpm typecheck` + `pnpm test:run` pass.

---

### U5. Integrate AiStepBlock into AiProcessBlock

**Goal:** Replace all step rendering in AiProcessBlock with `<AiStepBlock>`, wire up `autoCollapseSignal`, and remove block-level auto-collapse.

**Requirements:** Origin §2.7 (integration), §3 (state flow), §4.2 (AiProcessBlock modifications)

**Dependencies:** U4

**Files:**
- `frontend/apps/main/src/components/ai/AiProcessBlock.vue` (modify)

**Approach:**

Template changes:
- Replace the entire `<template v-for="step in steps">` block with a single:
  ```
  <AiStepBlock v-for="step in steps" :key="step.id" v-bind="stepProps(step)" :auto-collapse-signal="reasoningAutoCollapse" />
  ```
- Add `role="list"` to `.process-body` div
- Remove imports of `AiProcessStep` and `AiToolCallStep`

Script changes:
- Add `import AiStepBlock from './AiStepBlock.vue'`
- Add computed `reasoningAutoCollapse`: `computed(() => props.phase === 'answering' || props.phase === 'done')`
- Add `stepProps(step: ProcessStep)` helper that maps ProcessStep union to AiStepBlock props (type, status, title, icon, content, etc.)
- Remove: `hasAutoCollapsed` ref, `autoCollapseTimer`, `clearAutoCollapseTimer()`, the watch block that handles block-level auto-collapse
- Keep: header toggle logic (the overall process block expand/collapse stays), `nowMs` tick for the block-level elapsed display, error/retry handling

Style changes:
- Remove the step-specific vertical-line connector styles (`.process-body > :deep(.ai-tool-call-step)::before` etc.) — the new AiStepBlock will handle its own spacing
- Keep all process-header and process-body styles

**Patterns to follow:** Current prop-passing pattern in AiProcessBlock (pass typed props down to child components).

**Test scenarios:**
- Rendering with mixed steps (reasoning + tool_call + subagent): all render through AiStepBlock
- Phase transition to `answering`: reasoning steps collapse after 1s, tool_call steps remain visible
- Block-level header toggle still works (expands/collapses entire body)
- Error state: retry button still visible, block stays expanded
- Empty running state: spinner + connecting label still shows
- tool_call steps receive `compressed=true` when their status transitions to `done`

**Verification:** `pnpm typecheck` passes; manual test in browser — start an agent chat, observe reasoning appears expanded with shimmer, transitions to collapsed when answer starts, tool_calls compress on completion.

---

### U6. Remove superseded components

**Goal:** Delete old components that are fully replaced by AiStepBlock.

**Requirements:** Origin §4.3 (files removed)

**Dependencies:** U5 (verified working)

**Files:**
- `frontend/apps/main/src/components/ai/AiProcessStep.vue` (delete)
- `frontend/apps/main/src/components/ai/AiToolCallStep.vue` (delete)

**Approach:** 
- Delete the two files
- Grep for any remaining imports of these components across the codebase (there should be none after U5)
- Verify no test files reference them

**Test scenarios:**
- Test expectation: none — deletion only, verified by build passing

**Verification:** `pnpm typecheck` + `pnpm build` pass with no unresolved imports.

---

## Deferred Implementation Notes

- Exact summary extraction regex may need tuning for edge cases (mixed CJK + Latin, markdown headings as first line) — adjust during implementation based on real agent output
- Whether `compressed` triggers immediately on `done` or waits for the next step to appear is a UX call best made during visual testing — default to immediate
- The vertical connector line between steps (currently in AiProcessBlock) may need a new approach in AiStepBlock — evaluate during U5 whether margin/gap alone provides sufficient visual grouping

---

## Verification Strategy

1. **Type safety:** `pnpm typecheck` after each unit
2. **Unit tests:** New test file for `useStepCollapse` (composable logic) and `AiStepBlock` (component rendering + interactions)
3. **Integration:** Manual browser test with real agent chat — verify streaming → thinking → answering flow with auto-collapse
4. **Mobile:** Test at 375px viewport — verify compressed tool_calls are readable, reasoning accordion doesn't overflow
5. **Dark mode:** Verify gradient border uses `--van-primary-color` (lavender in dark), tokens work in both themes
6. **Accessibility:** Check `aria-expanded` toggles via DevTools; verify reduced-motion disables animations
