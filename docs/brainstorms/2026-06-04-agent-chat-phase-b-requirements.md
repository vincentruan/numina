# Phase B: Plan Skeleton + Subtask Card Upgrade — Requirements

Date: 2026-06-04
Source: `docs/ideation/2026-06-04-agent-chat-interaction-ideation.md` (#1 + #4)
Depends on: Phase A (AiStepBlock + Collapsible Reasoning Accordion) — completed
Status: Ready for planning

## Summary

Two parallel workstreams delivering DeerFlow-inspired progressive disclosure:

1. **Plan Skeleton with Progress Dots** — top progress bar (dot indicators) + inline plan steps in the activity stream. Dual-source: explicit DeerFlow plan events preferred, tool-type + keyword inference as fallback.
2. **Full Subtask Card Upgrade** — tap-to-expand for compressed tool_calls, live FlipDisplay-style status text (hybrid: backend `tool.progress` preferred, frontend inference fallback), full tool event pipeline from backend.

Together they solve: opaque execution with no progress visibility, irreversible tool_call compression, and the silent dropping of DeerFlow plan/tool events at the adapter layer.

---

## 1. Plan Skeleton with Progress Dots

### 1.1 Purpose

When the agent has a plan (explicit or inferred), communicate execution progress via:
- A compact top progress bar with dot indicators (~24px height)
- Plan steps appearing inline in the activity stream as AiStepBlock entries
- Scrolling to the corresponding inline step when a dot is tapped

This answers "where am I in the process?" without consuming significant mobile viewport space.

### 1.2 Progress Bar Component (`AiPlanProgressBar.vue`)

```ts
interface AiPlanProgressBarProps {
  steps: PlanStep[]
  activeStepIndex: number  // -1 when no step is active
}

interface PlanStep {
  id: string
  label: string           // Short label: "搜索", "分析", "生成" (≤4 chars Chinese / ≤8 chars English)
  status: 'pending' | 'active' | 'done' | 'error'
}

interface AiPlanProgressBarEmits {
  'step-tap': [stepId: string]  // Scrolls to corresponding inline step
}
```

**Visual specification:**
- Height: 24px (fixed, no vertical growth regardless of step count)
- Dot size: 8px diameter, 12px gap between dots
- Dot states:
  - `pending`: `var(--text-tertiary)` at 40% opacity
  - `active`: `var(--van-primary-color)` with pulse animation (scale 1→1.3→1, 1.5s ease infinite)
  - `done`: `var(--van-primary-color)` solid, no animation
  - `error`: `var(--color-error)` solid
- Dots connected by a 2px line: completed portion uses `var(--van-primary-color)`, pending portion uses `var(--separator)`
- Tap target: each dot has 44×44px invisible hit area
- Overflow: if >7 steps, show first 6 dots + "..." dot that reveals tooltip with full list
- Position: pinned at top of `AiProcessBlock`, above the steps list

**Accessibility:**
- Container: `role="progressbar"`, `aria-valuemin="0"`, `aria-valuemax="{totalSteps}"`, `aria-valuenow="{completedSteps}"`
- Each dot: `role="button"`, `aria-label="{label} - {status}"`
- Pulse animation respects `prefers-reduced-motion: reduce` (degrades to solid color, no motion)

### 1.3 Plan Step in Activity Stream

Plan steps appear inline as `AiStepBlock` with `type='progress'` (reusing the existing dead type). When the plan arrives, all steps are inserted into `steps[]` with `status: 'pending'`. As execution progresses, their status updates in-place.

**Rendering (within AiStepBlock type='progress'):**
- `pending`: dimmed text, no border animation
- `running`/`active`: gradient-sweep border (same as reasoning/tool_call active state)
- `done`: compressed single-line: `[✓] {label} · {elapsedMs}`
- `error`: red border, error message visible

### 1.4 Dual-Source Plan Data

#### Source A: Explicit DeerFlow Plan Events (preferred)

Backend extracts `todos` from DeerFlow `values` events and emits structured plan events:

```
plan.update → { todos: [{ id, content, status }] }
```

Frontend normalizer produces:
```ts
{ type: 'plan_update'; steps: Array<{ id: string; content: string; status: 'pending' | 'in_progress' | 'completed' }> }
```

**Diffing logic:** On each `plan_update`, compare incoming `todos` array against last-seen state by index + content hash. Only update steps whose status or content changed. This prevents flicker from redundant `values` events (DeerFlow emits the full list on every graph node transition).

#### Source B: Inferred Labels (fallback)

When no explicit plan events arrive within the first 3 seconds of execution, the frontend infers plan structure from observed events:

1. **Tool-type mapping** (primary): When a `tool_call` event fires, derive a label from tool type:
   - `web_search` → "搜索"
   - `code_interpreter` / `python` → "计算"
   - `mcp_*` → "工具调用"
   - `write_todos` → suppressed (internal mechanism)
   - Other → tool display name truncated to 4 chars

2. **Keyword extraction** (secondary, for reasoning-only phases): First 10 characters of reasoning content matched against:
   - Contains "搜索" / "查找" / "search" → "搜索"
   - Contains "分析" / "analyz" → "分析"
   - Contains "计算" / "calculat" → "计算"
   - Contains "生成" / "generat" / "写" / "write" → "生成"
   - Contains "对比" / "compar" → "对比"
   - Fallback → "思考"

3. **Deduplication**: Consecutive steps with the same inferred label merge into one (e.g., three sequential web_search calls = one "搜索" dot, not three).

#### Source switching

- Start with no plan visible
- If `plan_update` event arrives → switch to Source A, render all steps
- If 3s pass with no `plan_update` → activate Source B inference
- If Source B is active and `plan_update` arrives late → replace inferred steps with explicit plan
- Source B dots appear one-by-one as events arrive (progressive, not retroactive)

### 1.5 `write_todos` Tool Call Display

The DeerFlow `write_todos` tool call is an internal mechanism for plan creation. Display strategy:

1. When `tool.call` with `name === 'write_todos'` arrives → render as a special inline step: `[🗂️] AI 正在规划...` with status `running`
2. When the corresponding `plan_update` arrives (within ~1s) → auto-collapse the `write_todos` step to single-line compressed state: `[✓] 制定了 N 步计划`
3. The plan progress dots appear simultaneously with the `plan_update`

This provides continuity ("the AI is planning") without polluting the activity stream with raw tool call noise.

### 1.6 Scroll-to-Step on Dot Tap

When user taps a progress dot:
1. Find the corresponding inline `AiStepBlock` by `stepId`
2. Smooth-scroll the process block container to that element: `element.scrollIntoView({ behavior: 'smooth', block: 'center' })`
3. Briefly flash the target step border (200ms highlight via CSS class toggle)

---

## 2. Full Subtask Card Upgrade

### 2.1 Purpose

Transform tool_call steps from static compressed rows into interactive cards with:
- Tap-to-expand for done tool_calls (fixing current irreversible compression)
- Live FlipDisplay-style status text during execution
- Clear visual hierarchy: one bright active card, trail of compact completed ones

### 2.2 Tap-to-Expand for Done Tool Calls

Current behavior: `compressed: true` + `display: none` on `.step-toggle` = permanently hidden body.

New behavior:
- Done tool_calls remain compressed by default (single-line summary)
- A small chevron icon (`van-icon name="arrow-down"`, 16px, `var(--text-tertiary)`) appears at trailing edge
- Tapping anywhere on the compressed row expands to show full args + result
- Tapping again (or the chevron) re-collapses
- Expand/collapse uses existing `max-height` CSS transition from AiStepBlock

**Implementation in AiStepBlock:**
```ts
// New internal state for tool_call type
const isManuallyExpanded = ref(false)

// compressed + !isManuallyExpanded → single-line
// compressed + isManuallyExpanded → show body (override compression)
function toggleCompressedExpand() {
  if (props.type === 'tool_call' && props.compressed) {
    isManuallyExpanded.value = !isManuallyExpanded.value
    emit('toggle-expand', isManuallyExpanded.value)
  }
}
```

**Accessibility:**
- Compressed row: `role="button"`, `aria-expanded="false"`, `tabindex="0"`
- Expanded state: `aria-expanded="true"`
- Enter/Space key triggers toggle

### 2.3 Live Status Text (FlipDisplay Pattern)

During tool execution (`status === 'running'`), display a live-updating status line below the tool name that communicates what's happening:

```
[🔍 gradient-border]
  网络搜索 · 搜索中...               ← live status text
                                      (flips to)
  网络搜索 · 找到 3 个结果 · 2.1s    ← final compressed state
```

#### Data source: Hybrid

**Backend-driven (preferred):** New `tool.progress` event type:
```ts
// AgentEvent
{ type: 'tool.progress', tool_id: string, message: string }

// NormalizedAiEvent
{ type: 'tool_progress'; toolCallId: string; message: string }
```

When `tool.progress` events arrive, display `message` verbatim as the status text.

**Frontend-inferred (fallback):** When no `tool.progress` events arrive for a running tool_call, generate status text from tool type + elapsed time:

| Tool type | 0–2s | 2–5s | 5s+ |
|-----------|------|------|-----|
| `web_search` | "搜索中..." | "等待搜索结果..." | "搜索耗时较长..." |
| `code_interpreter` | "执行中..." | "计算中..." | "处理中..." |
| `mcp_*` | "调用中..." | "等待响应..." | "处理中..." |
| Other | "执行中..." | "处理中..." | "等待中..." |

**Transition animation:**
- Text change uses CSS `opacity` fade (0.15s): old text fades out, new text fades in
- No vertical layout shift — status text area has fixed line-height
- `font-size: 12px`, `color: var(--text-secondary)`

### 2.4 Visual Hierarchy Enhancement

Active vs. completed cards should have distinct visual weight:

| State | Border | Opacity | Height | Status text |
|-------|--------|---------|--------|-------------|
| `running` | Gradient-sweep (existing) | 1.0 | Full (~80px with status text) | Live updating |
| `done` | `var(--color-card-border)` | 1.0 | Compressed (~40px) | Hidden (result in summary) |
| `error` | `var(--color-error)` | 1.0 | Full | Error message |
| `pending` | `var(--color-card-border)` | 0.55 | Compressed | None |

The existing gradient-sweep border from Phase A already provides the active spotlight. Phase B adds:
- Status text area (only visible during `running`)
- Pending state opacity reduction (for plan steps visible but not yet started)
- Smooth height transition between running → done (300ms ease)

### 2.5 ProcessStep Type Extension

Add `statusText` and `progressMessage` to tool_call ProcessStep:

```ts
// Extend existing tool_call ProcessStep
| {
    type: 'tool_call'
    id: string
    name: string
    displayName: string
    icon: string
    toolType?: string
    args: Record<string, unknown>
    status: 'pending' | 'running' | 'done' | 'error'
    resultSummary?: string
    error?: string
    elapsedMs?: number
    progressMessage?: string  // NEW: live status text from backend or inference
  }
```

---

## 3. Backend Pipeline

### 3.1 `StreamChunk` Extension

Current: `type: Literal["thinking", "text"]`

Extended:
```python
class StreamChunk:
    type: Literal["thinking", "text", "tool_call", "tool_result", "tool_progress", "plan_update"]
    content: str  # For thinking/text: the text content
    # For tool_call/tool_result/tool_progress/plan_update: JSON-serialized payload
    data: dict | None = None
```

### 3.2 Adapter `_process_event()` Extension

Add handling for three previously-dropped event patterns:

```python
def _process_event(event) -> None:
    # ... existing messages-tuple + ai handling ...

    # NEW: Tool call invocation (AI decides to call a tool)
    if (event.type == "messages-tuple"
        and isinstance(event.data, dict)
        and event.data.get("type") == "ai"
        and event.data.get("tool_calls")):
        for tc in event.data["tool_calls"]:
            if tc["name"] == "write_todos":
                # Emit as plan-related, not raw tool call
                queue.put_nowait(StreamChunk("tool_call", data={
                    "name": "write_todos",
                    "args": tc["args"],
                    "id": tc["id"],
                    "internal": True  # Signal to orchestrator: suppress as normal tool
                }))
            else:
                queue.put_nowait(StreamChunk("tool_call", data={
                    "name": tc["name"],
                    "args": tc["args"],
                    "id": tc["id"],
                }))

    # NEW: Tool result
    if (event.type == "messages-tuple"
        and isinstance(event.data, dict)
        and event.data.get("type") == "tool"):
        queue.put_nowait(StreamChunk("tool_result", data={
            "name": event.data.get("name"),
            "tool_call_id": event.data.get("tool_call_id"),
            "content": event.data.get("content"),
        }))

    # NEW: Plan state from values snapshot
    if (event.type == "values"
        and isinstance(event.data, dict)
        and event.data.get("todos") is not None):
        queue.put_nowait(StreamChunk("plan_update", data={
            "todos": event.data["todos"]
        }))
```

### 3.3 `_chunk_to_event_lines()` Extension

Add branches for new chunk types:

```python
async def _chunk_to_event_lines(self, builder, chunk, answer_parts, ...):
    if chunk.type == "thinking":
        yield builder.phase("thinking").to_ndjson()
        yield builder.token(chunk.content, is_thinking=True).to_ndjson()
        return

    if chunk.type == "text":
        answer_parts.append(chunk.content)
        yield builder.phase("answering").to_ndjson()
        yield builder.token(chunk.content, is_thinking=False).to_ndjson()
        return

    # NEW: Tool call
    if chunk.type == "tool_call" and chunk.data:
        d = chunk.data
        if d.get("internal"):
            # write_todos: emit as tool.call but mark internal
            yield builder.tool_call(
                tool_name=d["name"],
                arguments=d.get("args", {}),
                display_name="规划步骤",
                icon="🗂️",
                tool_type="internal",
            ).to_ndjson()
        else:
            yield builder.tool_call(
                tool_name=d["name"],
                arguments=d.get("args", {}),
            ).to_ndjson()
        return

    # NEW: Tool result
    if chunk.type == "tool_result" and chunk.data:
        d = chunk.data
        yield builder.tool_result(
            tool_id=d["tool_call_id"],
            success=True,
            execution_time_ms=0,  # DeerFlow doesn't provide timing
            data=d.get("content"),
        ).to_ndjson()
        return

    # NEW: Plan update
    if chunk.type == "plan_update" and chunk.data:
        yield builder.plan_update(d["todos"]).to_ndjson()
        return
```

### 3.4 New EventStreamBuilder Methods

```python
def plan_update(self, todos: list[dict]) -> StreamEvent:
    """Emit plan state update with todo list."""
    return self._event("plan.update", {
        "todos": [
            {"id": f"plan-{i}", "content": t.get("content", ""), "status": t.get("status", "pending")}
            for i, t in enumerate(todos)
        ]
    })

def tool_progress(self, tool_id: str, message: str) -> StreamEvent:
    """Emit tool execution progress text."""
    return self._event("tool.progress", {
        "tool_id": tool_id,
        "message": message,
    })
```

### 3.5 New AgentEventType Entries

Add to the event type system:
- `plan.update` — carries todo list state
- `tool.progress` — carries live status text for a running tool

---

## 4. Frontend Event Pipeline Extension

### 4.1 `AgentEventType` Additions

```ts
export type AgentEventType =
  | ... // existing
  | 'plan.update'
  | 'tool.progress'
```

### 4.2 `AgentEvent` Additions

```ts
export interface AgentEvent {
  // ... existing fields ...
  // plan.update payload
  todos?: Array<{ id: string; content: string; status: 'pending' | 'in_progress' | 'completed' }>
  // tool.progress payload
  tool_id?: string
  progress_message?: string
}
```

### 4.3 `NormalizedAiEvent` Additions

```ts
export type NormalizedAiEvent =
  | ... // existing
  | { type: 'plan_update'; steps: Array<{ id: string; content: string; status: 'pending' | 'in_progress' | 'completed' }> }
  | { type: 'tool_progress'; toolCallId: string; message: string }
```

### 4.4 `NormalizationState` Additions

```ts
export interface NormalizationState {
  // ... existing fields ...
  planSteps: PlanStep[]           // Current plan state (from explicit events)
  lastPlanHash: string            // For diffing repeated plan_update events
  planSource: 'explicit' | 'inferred' | null  // Which source is active
  inferredSteps: PlanStep[]       // Steps derived from Source B
  planWaitTimer: number | null    // 3s timer before activating inference
}
```

### 4.5 Normalizer Cases

```ts
// In normalizeAgentEvent switch:

case 'plan.update':
  const newHash = hashTodos(event.todos)
  if (newHash !== state.lastPlanHash) {
    state.lastPlanHash = newHash
    state.planSource = 'explicit'
    state.planSteps = mapTodosToPlanSteps(event.todos)
    clearTimeout(state.planWaitTimer)
    return { type: 'plan_update', steps: state.planSteps }
  }
  return null  // Unchanged, skip

case 'tool.progress':
  const step = state.steps.find(s => s.type === 'tool_call' && s.id === event.tool_id)
  if (step && step.type === 'tool_call') {
    step.progressMessage = event.progress_message
  }
  return { type: 'tool_progress', toolCallId: event.tool_id, message: event.progress_message }
```

---

## 5. State Flow Diagram

```
DeerFlow Runtime
    ↓ (LangGraph stream: values + messages-tuple + custom)
adapter._process_event()
    ↓ (StreamChunk: thinking | text | tool_call | tool_result | plan_update)
orchestrator._chunk_to_event_lines()
    ↓ (NDJSON: phase.* | token.stream | tool.call | tool.result | plan.update | tool.progress)
useAgentEventStream.ts (NDJSON parse)
    ↓ (AgentEvent)
aiEventNormalizer.ts
    ↓ (NormalizedAiEvent → mutates NormalizationState.steps[] + planSteps[])
AiProcessBlock.vue
    ├── <AiPlanProgressBar :steps="planSteps" :activeIndex="..." />
    └── v-for step in steps → <AiStepBlock ... />
            ├── [tool_call, running]: gradient border + live status text
            ├── [tool_call, done]: compressed, tap-to-expand
            ├── [progress/plan_step]: inline plan step with status
            └── [progress, name=write_todos]: brief "规划中..." → auto-collapse
```

---

## 6. Files Created

| File | Purpose |
|------|---------|
| `src/components/ai/AiPlanProgressBar.vue` | Top progress dots component |
| `src/composables/usePlanInference.ts` | Source B inference logic (tool-type + keyword mapping) |
| `src/utils/planDiff.ts` | Hash + diff utility for plan_update deduplication |

## 7. Files Modified

### Frontend

| File | Change |
|------|--------|
| `src/components/ai/AiProcessBlock.vue` | Add `<AiPlanProgressBar>` above steps list; pass plan state; handle `step-tap` scroll |
| `src/components/ai/AiStepBlock.vue` | Add tap-to-expand for compressed tool_calls; add status text area for running tools; add pending opacity; render progress/plan steps |
| `src/types/agent-stream.ts` | Add `plan.update`, `tool.progress` event types; extend `ProcessStep` with `progressMessage`; extend `NormalizationState` |
| `src/utils/aiEventNormalizer.ts` | Add `plan.update` and `tool.progress` cases; add plan diffing; add Source B 3s timer + inference activation |
| `src/i18n/locales/zh-CN.ts` | Add plan/tool status i18n keys |
| `src/i18n/locales/en-US.ts` | Same keys in English |

### Backend

| File | Change |
|------|--------|
| `server/apps/agent/services/chat_adapter.py` | Extend `_process_event()` to extract tool_calls, tool results, and plan todos from DeerFlow events |
| `server/apps/agent/services/orchestrator.py` | Extend `_chunk_to_event_lines()` with tool_call, tool_result, plan_update branches |
| `server/apps/agent/services/stream_events.py` | Add `plan_update()` and `tool_progress()` methods to EventStreamBuilder |
| `server/apps/agent/models/stream_chunk.py` (or inline) | Extend `StreamChunk` type discriminator and add `data` field |

## 8. Dependencies

- No new npm packages
- No new Python packages
- CSS-only animations (dot pulse, text fade)
- Existing design tokens from `style.css` and `DESIGN.md`
- Existing `getToolDisplayInfo` utility for tool-type → label mapping

---

## 9. Acceptance Criteria

### 9.1 Plan Skeleton — Functional

- [ ] Progress dots appear at top of AiProcessBlock when plan data is available
- [ ] Dots reflect correct status: pending (dim), active (pulse), done (solid), error (red)
- [ ] Connected line fills progressively as steps complete
- [ ] Tapping a dot smooth-scrolls to the corresponding inline step
- [ ] Inline plan steps render as AiStepBlock type='progress' with correct status transitions
- [ ] `write_todos` call displays as "AI 正在规划..." then auto-collapses to "制定了 N 步计划"
- [ ] When explicit plan events arrive, progress dots + inline steps render from DeerFlow data
- [ ] When no plan events arrive within 3s, inference mode activates and builds dots from observed events
- [ ] If explicit plan arrives after inference activated, explicit replaces inferred (no duplicate dots)
- [ ] Consecutive same-label inferred steps deduplicate into one dot
- [ ] >7 steps truncate to 6 dots + overflow indicator

### 9.2 Subtask Cards — Functional

- [ ] Done tool_call steps show a chevron indicating expandability
- [ ] Tapping a compressed tool_call expands to show full args + result
- [ ] Tapping again re-collapses
- [ ] Running tool_calls display live status text below tool name
- [ ] Status text updates via backend `tool.progress` events when available
- [ ] Status text falls back to frontend inference when no `tool.progress` events arrive
- [ ] Status text transitions use fade animation (no layout jank)
- [ ] Running → done transition smoothly compresses height (300ms)
- [ ] Pending steps (plan steps not yet started) render at 55% opacity

### 9.3 Backend Pipeline — Functional

- [ ] `_process_event()` extracts tool_call events from DeerFlow `messages-tuple` stream
- [ ] `_process_event()` extracts tool_result events from DeerFlow `messages-tuple` stream
- [ ] `_process_event()` extracts plan todos from DeerFlow `values` events
- [ ] `_chunk_to_event_lines()` emits `tool.call` NDJSON events
- [ ] `_chunk_to_event_lines()` emits `tool.result` NDJSON events
- [ ] `_chunk_to_event_lines()` emits `plan.update` NDJSON events
- [ ] `write_todos` tool_call is emitted with `tool_type: "internal"` marker
- [ ] EventStreamBuilder.plan_update() produces valid NDJSON
- [ ] EventStreamBuilder.tool_progress() produces valid NDJSON
- [ ] Existing thinking/text streaming behavior unchanged

### 9.4 Accessibility

- [ ] Progress bar: `role="progressbar"` with `aria-valuenow`/`aria-valuemax`
- [ ] Each dot: `role="button"` with `aria-label` describing step name + status
- [ ] Compressed tool_calls: `role="button"`, `aria-expanded`, keyboard accessible
- [ ] Pulse animation respects `prefers-reduced-motion: reduce`
- [ ] Status text area uses `aria-live="polite"` for screen reader updates
- [ ] All interactive elements ≥44×44px touch target

### 9.5 Visual / Design System Compliance

- [ ] Dot colors use design tokens (no hardcoded hex)
- [ ] Dark mode: dots use `--van-primary-color` which becomes `#bdbbff`
- [ ] Status text uses `var(--text-secondary)`, 12px minimum
- [ ] Connecting line uses `var(--separator)` for pending, `var(--van-primary-color)` for filled
- [ ] No inline `style="..."` on themable elements
- [ ] Shadows (if used): `rgba(1, 1, 32, 0.1)` per DESIGN.md

### 9.6 Mobile (≤425px)

- [ ] Progress bar stays within 24px height at 375px width
- [ ] Dots don't overflow horizontally (truncate with overflow indicator)
- [ ] Status text readable at 375px (single line, ellipsis on overflow)
- [ ] Expand/collapse transitions smooth on low-end devices
- [ ] Scroll-to-step works correctly within the scrollable process block

### 9.7 Regression

- [ ] `pnpm typecheck` passes
- [ ] `pnpm test:run` passes
- [ ] `uv run pytest apps/agent/tests/ -v` passes (new backend tests)
- [ ] `uv run ruff check apps/agent/` passes
- [ ] Existing NDJSON streaming (thinking/answering) unchanged
- [ ] Existing AiStepBlock reasoning accordion still works
- [ ] Phase A acceptance criteria remain passing

---

## 10. Non-Goals (Deferred)

- Citation chips (#5) — Phase C
- Artifact registry (#6) — Phase C
- Session history process reconstruction (#7) — Phase C
- `tool.progress` emission from actual DeerFlow tool execution (requires DeerFlow middleware hooks) — the backend schema is ready but actual emission may be a follow-up
- Replay/scrubber for plan execution timeline
- Backend retry/error recovery for failed tools

---

## 11. Implementation Notes (for planning reference)

- **Parallel workstreams**: Backend pipeline (adapter + orchestrator + EventStreamBuilder) can ship independently from frontend plan UI. Frontend uses inference fallback until backend is wired.
- **Incremental frontend**: Start with tap-to-expand fix (smallest, highest value). Then add status text inference. Then add plan progress bar. Plan event handling last (needs backend).
- **Plan diffing**: A simple JSON hash (`JSON.stringify(todos.map(t => t.content + t.status))`) is sufficient — no need for deep structural diff. The todo list is small (≤10 items).
- **`write_todos` filtering**: The normalizer filters by `tool_type === 'internal'` on the already-emitted `tool.call` event — no special event type needed. Frontend displays it as a brief activity indicator.
- **Inferred plan step lifecycle**: Inferred steps are append-only during a session. They never transition back to `pending` once `done`. New inferred steps appear as new dots.
- **Status text timer**: Frontend inference starts a 2s/5s timer per tool type. If `tool.progress` event arrives, it resets the inference and uses backend text. If the tool completes before any progress, skip status text entirely (only show final summary).
