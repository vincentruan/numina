# Phase A: AiStepBlock + Collapsible Reasoning Accordion — Requirements

Date: 2026-06-04
Source: `docs/ideation/2026-06-04-agent-chat-interaction-ideation.md` (#2 + #3)
Status: Ready for planning

## Summary

Two complementary components that form the foundation for agent chat process visualization:

1. **AiStepBlock** — unified composable primitive replacing all 5 step-type renderers
2. **Collapsible Reasoning Accordion** — per-reasoning-step accordion with auto-collapse on answer start

Together they solve: inconsistent step rendering, missing accessibility, duplicated animation logic, and the mobile viewport problem (reasoning walls pushing answers off-screen).

---

## 1. AiStepBlock — Unified Step Primitive

### 1.1 Purpose

Replace `AiProcessStep.vue`, `AiToolCallStep.vue`, and the 3 inline template blocks in `AiProcessBlock.vue` (subagent, artifact, progress) with a single composable component that handles all step types with consistent UX patterns.

### 1.2 Component Interface

```ts
// AiStepBlock.vue props
interface AiStepBlockProps {
  // Identity
  stepId: string
  type: 'reasoning' | 'tool_call' | 'subagent' | 'artifact' | 'progress'

  // Status (drives visual state)
  status: 'pending' | 'streaming' | 'running' | 'done' | 'error'

  // Content — shape varies by type, rendered via named slots or internal switch
  title: string                    // Primary label (tool display name, "思考中", subagent title, etc.)
  icon?: string                    // Emoji or icon identifier
  elapsedMs?: number               // Duration badge value

  // Type-specific props (optional, consumed by internal content renderers)
  // reasoning:
  content?: string                 // Streaming markdown text
  summary?: string                 // First-line auto-extracted summary for collapsed state

  // tool_call:
  toolName?: string                // Raw tool name
  toolType?: string                // Category (web_search, code, mcp, etc.)
  args?: Record<string, unknown>   // Tool arguments
  resultSummary?: string           // One-line result for compressed state
  error?: string                   // Error message

  // subagent:
  taskId?: string
  description?: string
  result?: string

  // artifact:
  url?: string
  path?: string
  kind?: 'report' | 'file' | 'image' | 'link' | 'other'

  // progress:
  // (uses title + description + status only)

  // Behavior
  collapsible?: boolean            // Default: true for reasoning/tool_call, false for artifact/progress
  defaultExpanded?: boolean        // Default: true when status is streaming/running
  compressed?: boolean             // When true, renders single-line summary mode (for done tool_calls)
}
```

### 1.3 Emitted Events

```ts
interface AiStepBlockEmits {
  'toggle-expand': [expanded: boolean]
}
```

### 1.4 Visual States

| Status | Border | Background | Icon | Animation |
|--------|--------|-----------|------|-----------|
| `pending` | `var(--color-card-border)` | `var(--card-bg)` at 55% opacity | `⏳` | None |
| `streaming` | Gradient sweep (see §1.5) | `var(--card-bg)` | Type-specific | Shimmer on content |
| `running` | Gradient sweep (see §1.5) | `var(--card-bg)` | Type-specific | Gradient sweep border |
| `done` | `var(--color-card-border)` | `var(--card-bg)` | `✓` (green) | None |
| `error` | `var(--color-error)` | `rgba(error, 0.08)` | `✕` (red) | None |

### 1.5 Gradient Sweep Active Border

CSS-only implementation, no JS animation library:

```css
.ai-step-block--active {
  border: 1px solid transparent;
  background-clip: padding-box;
  position: relative;
}

.ai-step-block--active::before {
  content: '';
  position: absolute;
  inset: -1px;
  border-radius: inherit;
  background: linear-gradient(
    90deg,
    var(--van-primary-color) 0%,
    var(--color-action-blue) 50%,
    var(--van-primary-color) 100%
  );
  background-size: 200% 100%;
  animation: gradient-sweep 2s linear infinite;
  z-index: -1;
  border-radius: 9px; /* outer = inner + border-width */
}

@keyframes gradient-sweep {
  from { background-position: 0% center; }
  to { background-position: 200% center; }
}

@media (prefers-reduced-motion: reduce) {
  .ai-step-block--active::before {
    animation: none;
    background: var(--van-primary-color);
  }
}
```

### 1.6 Completion Compression (tool_call)

When a `tool_call` step transitions to `done`:
- Height compresses to single line (~40px): `[icon] toolDisplayName · resultSummary · elapsedMs`
- Tap expands to show full args + result
- CSS transition: `max-height 0.3s ease, opacity 0.2s ease`
- Minimum touch target: 44px height maintained

### 1.7 Internal Structure

```
AiStepBlock
├── .step-header (always visible)
│   ├── .step-marker (status icon, 20×20)
│   ├── .step-title (title text)
│   ├── .step-duration (elapsed badge, tabular-nums)
│   └── .step-expand-toggle (van-icon arrow, only when collapsible)
├── .step-body (collapsible content area)
│   ├── [reasoning]: markdown content via v-html or streaming text
│   ├── [tool_call]: args section + result section
│   ├── [subagent]: description + result/error
│   ├── [artifact]: link card
│   └── [progress]: description text
└── .step-compressed (single-line summary, visible only when compressed=true)
```

### 1.8 Accessibility Requirements

- Container: `role="listitem"` (parent AiProcessBlock body gets `role="list"`)
- Expand toggle: `aria-expanded="true|false"`, `aria-controls="step-body-{stepId}"`
- Body: `id="step-body-{stepId}"`
- Status changes: `aria-live="polite"` on status text region
- All animations respect `prefers-reduced-motion: reduce`
- Touch targets minimum 44×44px

---

## 2. Collapsible Reasoning Accordion

### 2.1 Purpose

Each reasoning step renders as an independently collapsible accordion section with:
- One-line summary header + duration badge
- Shimmer while streaming
- Auto-collapse when answering phase begins (1s delay, one-shot)

### 2.2 Behavior: Accordion States

```
[Phase: thinking, step streaming]
  → Expanded, shimmer pulse on header title
  → Duration badge ticking: "思考 Ns"
  → Content streaming in via markdown

[Phase: thinking, step done (tool_call interrupts)]
  → Expanded (stays open until answering)
  → Duration badge frozen: "思考 3s"
  → Static content

[Phase: answering starts]
  → All done reasoning steps: 1s delay → collapse to summary line
  → One-shot flag per step: hasAutoCollapsed = true
  → User tap re-expands; once manually toggled, no further auto-collapse

[History view / session reload]
  → All reasoning steps start collapsed
  → Show: summary line + duration badge
```

### 2.3 Summary Extraction

Auto-extract one-line summary from reasoning content:
1. Take first sentence (up to first `。` or `.` or `\n`)
2. Truncate at 40 characters (Chinese) / 60 characters (English) with `…`
3. Fallback if content is empty or whitespace: `t('aiProcess.thinkingLabel')`

This is a `computed` — reactive to streaming content updates (fixes the current truncation bug where `truncateContent` is called once at setup).

### 2.4 Duration Badge

- Format: `"思考 {N}s"` (i18n: `t('aiProcess.reasoningDuration', { seconds })`)
- Ticks every 1s via `setInterval` while step is `streaming`
- Stops ticking when step status changes to `done`
- Font: `font-variant-numeric: tabular-nums` (prevents layout shift)
- Color: `var(--text-tertiary)` when done, `var(--text-secondary)` while streaming

### 2.5 Shimmer on Streaming Header

While `status === 'streaming'`:
- Header title text gets the existing shimmer-sweep animation (same as current `AiProcessBlock .process-title.is-thinking`)
- Body content area gets background shimmer (existing `body-shimmer` keyframe)
- Both disabled under `prefers-reduced-motion: reduce`

### 2.6 Auto-Collapse Timing

```ts
// Inside AiStepBlock when type === 'reasoning'
// Triggered by parent passing a reactive `autoCollapseSignal` prop or event

watch(
  () => props.autoCollapseSignal, // becomes true when phase → 'answering'
  (shouldCollapse) => {
    if (shouldCollapse && props.status === 'done' && !hasAutoCollapsed.value) {
      autoCollapseTimer = setTimeout(() => {
        isExpanded.value = false
        hasAutoCollapsed.value = true
      }, 1000)
    }
  }
)

// User manual toggle cancels pending auto-collapse and prevents future ones
function toggleExpand() {
  clearTimeout(autoCollapseTimer)
  hasAutoCollapsed.value = true
  isExpanded.value = !isExpanded.value
  emit('toggle-expand', isExpanded.value)
}
```

### 2.7 Integration with AiProcessBlock

AiProcessBlock passes a reactive signal to reasoning AiStepBlocks:

```ts
// In AiProcessBlock — derived from phase prop
const reasoningAutoCollapse = computed(() => props.phase === 'answering' || props.phase === 'done')
```

This replaces the current block-level `hasAutoCollapsed` logic. The block-level auto-collapse (collapsing the entire process block) is REMOVED — individual reasoning step collapse provides sufficient space saving without hiding tool call results.

---

## 3. State Flow Diagram

```
NDJSON event arrives
    ↓
aiEventNormalizer.ts  →  steps[] array mutated
    ↓
AiProcessBlock (reactive to steps[])
    ↓
v-for step in steps → <AiStepBlock :type :status :content ... />
    ↓
Each AiStepBlock manages its own expand/collapse state internally
    ↓
phase prop change (thinking → answering) flows down as autoCollapseSignal
    ↓
Reasoning steps auto-collapse after 1s delay
```

---

## 4. Dependencies & Migration

### 4.1 Files Created

| File | Purpose |
|------|---------|
| `src/components/ai/AiStepBlock.vue` | New unified step component |

### 4.2 Files Modified

| File | Change |
|------|--------|
| `src/components/ai/AiProcessBlock.vue` | Replace all step rendering with `<AiStepBlock>`, remove block-level auto-collapse, add `role="list"` to body |
| `src/types/agent-stream.ts` | No change (existing `ProcessStep` union is sufficient) |
| `src/i18n/locales/zh-CN.ts` | Add `aiProcess.reasoningDuration`, `aiProcess.thinkingLabel` |
| `src/i18n/locales/en-US.ts` | Same keys in English |

### 4.3 Files Removed (after migration)

| File | Reason |
|------|--------|
| `src/components/ai/AiProcessStep.vue` | Superseded by AiStepBlock type='reasoning' |
| `src/components/ai/AiToolCallStep.vue` | Superseded by AiStepBlock type='tool_call' |

### 4.4 Dependencies

- No new npm packages required
- CSS-only animations (no animation libraries)
- Existing `getToolDisplayInfo` utility reused for tool_call display names/icons
- Existing design tokens from `style.css` and `DESIGN.md`

---

## 5. Acceptance Criteria

### 5.1 AiStepBlock — Functional

- [ ] All 5 step types (reasoning, tool_call, subagent, artifact, progress) render correctly through AiStepBlock
- [ ] Running/streaming steps show gradient-sweep animated border
- [ ] Done tool_call steps compress to single-line summary (~40px height)
- [ ] Tapping compressed tool_call expands to show full args + result
- [ ] Duration badge displays and ticks correctly for all timed steps
- [ ] Status icon transitions: pending → running → done/error
- [ ] Error steps show error message with red border, no compression

### 5.2 Collapsible Reasoning Accordion — Functional

- [ ] Each reasoning step has its own expand/collapse toggle
- [ ] Collapsed state shows: summary line (first sentence, ≤40 chars) + duration badge
- [ ] Streaming reasoning stays expanded with shimmer on header
- [ ] When phase changes to `answering`: all done reasoning steps collapse after 1s
- [ ] Auto-collapse fires only once per step per session
- [ ] User tap after auto-collapse re-expands; no subsequent auto-collapse
- [ ] User tap DURING streaming prevents that step from auto-collapsing later
- [ ] Summary text is reactive (updates as content streams in)

### 5.3 Accessibility

- [ ] `aria-expanded` on all expand toggles
- [ ] `aria-controls` linking toggle to content region
- [ ] `role="list"` on process-body, `role="listitem"` on each AiStepBlock
- [ ] `aria-live="polite"` on status region
- [ ] All animations disabled under `prefers-reduced-motion: reduce`
- [ ] All interactive elements have ≥44×44px touch target

### 5.4 Visual / Design System Compliance

- [ ] Colors use design tokens (no hardcoded hex in component)
- [ ] Dark mode: gradient border uses `--van-primary-color` (becomes `#bdbbff` in dark)
- [ ] Border radius: 8px for step cards (per DESIGN.md)
- [ ] Font sizes: ≥12px on mobile, ≥13px for primary text
- [ ] Shadows: `rgba(1, 1, 32, 0.1)` if used (per DESIGN.md)
- [ ] No inline `style="background:..."` or `style="color:..."` (dark mode red line)

### 5.5 Mobile (≤425px)

- [ ] Step cards fill width with 8px horizontal margin
- [ ] Compressed tool_call is readable at 375px (text truncates with ellipsis, not wrap)
- [ ] 5+ steps don't push content beyond reasonable scroll depth
- [ ] Accordion collapse/expand transition is smooth (no layout jank)
- [ ] Touch: expand/collapse button easily tappable

### 5.6 Regression

- [ ] `pnpm typecheck` passes
- [ ] `pnpm test:run` passes (existing AI component tests)
- [ ] Existing NDJSON streaming behavior unchanged (no event normalizer modifications)
- [ ] AiProcessBlock header + overall collapse still works
- [ ] Error state with retry button still functions

---

## 6. Non-Goals (Deferred)

- Plan skeleton rendering (#1) — Phase B
- Subtask card spotlight effect beyond gradient border (#4) — Phase B
- Citation chips (#5) — Phase C
- Session history process reconstruction (#7) — Phase C
- New event types from backend (plan events) — separate backend work
- Streaming markdown renderer upgrade — separate concern

---

## 7. Implementation Notes (for planning reference)

- Start with AiStepBlock handling reasoning + tool_call. Add subagent/artifact/progress once the primitive proves stable.
- The `compressed` prop is driven by parent logic, not internal state — AiProcessBlock decides when a tool_call should compress (e.g., after next step begins or after a timeout).
- The existing `getToolDisplayInfo` in `AiToolCallStep.vue` should be extracted to a shared utility before deletion.
- Consider a `useStepCollapse` composable to encapsulate the auto-collapse + manual-override logic, shared between reasoning accordion and potential future collapsible types.
