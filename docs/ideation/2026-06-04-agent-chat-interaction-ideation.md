---
date: 2026-06-04
topic: agent-chat-interaction
focus: 仿照DeerFlow智能体对话交互设计，优化智能体多步思考过程、过程输出、结果值的展示
mode: repo-grounded
---

# Ideation: 智能体对话交互设计优化 — Agent Chat Process Visualization

## Grounding Context

### Codebase Context
- **项目形态**: Vue 3 + Vant 4 mobile-first H5, consuming NDJSON events from Python FastAPI agent backend
- **核心组件**: `AIChatPage.vue` → `AiProcessBlock.vue` (collapsible step container) → `AiProcessStep.vue` / `AiToolCallStep.vue` (individual steps)
- **事件流**: `useAgentEventStream.ts` → `aiEventNormalizer.ts` handles: `session.start → phase.connecting → phase.thinking → token.stream[is_thinking] → phase.answering → token.stream → capability.end`
- **已有能力**: auto-collapse thinking (1s delay), shimmer animation, elapsed time, streaming dots, steps in arrival order (reasoning interleaved with tool calls), subagent/artifact/progress step types
- **未使用组件**: `AiFinalAnswer.vue`, `TaskConsole.vue`, `AiArtifactLink.vue` (exist but not wired into AIChatPage)
- **关键空白**: 无plan skeleton渲染、历史记录丢失过程步骤、无结构化引用卡片、backend已发plan event但frontend无handler

### DeerFlow Reference (`/Users/vincentruan/geek_space/github/deer-flow-reference`)
- **ai-elements组件库**: `plan.tsx` (Collapsible Plan + Shimmer), `reasoning.tsx` (auto-close + duration tracking), `chain-of-thought.tsx` (嵌套步骤), `subtask-card.tsx` (ShineBorder + FlipDisplay + ChainOfThought), `sources.tsx` (citation list), `task.tsx` (collapsible task)
- **三层递进展示**: Plan panel (执行前) → Activity stream (SubtaskCards) → Report (final answer独立视图)
- **核心模式**: ShineBorder动画标识活跃任务, FlipDisplay实时切换工具调用状态文本, Streamdown动画markdown

### Past Learnings (Critical)
- NDJSON path是唯一暴露 `phase.thinking` + `is_thinking` 的通道
- Thinking event sequence: `session.start → phase.connecting → phase.thinking → token.stream[is_thinking:true] → phase.answering → token.stream[is_thinking:false] → capability.end`
- Provider cascade可能在failover期间暂停流 — UI不得在短延迟时关闭连接

### External Context
- **Perplexity**: sources displayed ABOVE answer, activity log accordion
- **Claude.ai**: collapsed thinking with shimmer, auto-collapse on answer start, re-expand on user click
- **Stripe**: vertical timeline with status color transitions
- **Flight progress**: showing remaining phases (greyed out) alongside completed reduces perceived wait by 30-40%

## Topic Axes

1. **Plan & progress skeleton** — 执行前展示agent意图，进度追踪
2. **Thinking/reasoning visualization** — 推理token流式展示、折叠/展开、时长跟踪
3. **Tool call & subtask display** — 工具调用/子任务的状态转换、实时活动说明
4. **Final answer & artifact presentation** — 结构化结果渲染（报告、图表、引用/来源）
5. **Session history & replay** — 历史会话中保留并重现过程步骤

## Ranked Ideas

### 1. Plan Skeleton with Progressive Fill & Inferred Labels

**Description:** When the backend emits a `plan` event (skills already have `planning.enabled: true`, `max_steps: 5`), immediately render a numbered step skeleton with shimmer placeholders. As each step completes, fill the skeleton with real content, status icons, and duration badges. For runs WITHOUT explicit plan events, infer phase labels from the first tokens of each reasoning step via a keyword map (e.g., "Let me search..." → "搜索中", "分析..." → "分析中"). Every run gets visual structure, not just plan-aware ones.

**Axis:** Plan & progress skeleton

**Basis:** `external:` DeerFlow's `plan.tsx` renders the full Plan card before execution begins with Shimmer on streaming text; flight progress UIs show all future phases greyed out and fill them progressively. `direct:` Backend already emits plan events (`planning.enabled: true` in SKILL.md) but `agent-stream.ts` event type schema has no `plan.step` handler — the frontend currently ignores these events.

**Rationale:** Users currently see a blank spinner during the connecting phase — the most anxiety-inducing part of the interaction. A skeleton communicates "I have a plan, I'm executing it" which dramatically reduces perceived latency. DeerFlow proves this pattern works. The inferred-label fallback ensures the two-tier experience gap (structured vs. raw) doesn't penalize users of ad-hoc agents.

**Downsides:** Inferred labels may be inaccurate for unusual reasoning patterns; requires defining the plan event contract between backend and frontend; skeleton layout needs careful mobile design to avoid consuming too much vertical space.

**Confidence:** 90%

**Complexity:** Medium

**Status:** Specified → `docs/brainstorms/2026-06-04-agent-chat-phase-b-requirements.md`

---

### 2. Unified Step Primitive Component (`AiStepBlock`)

**Description:** Create a single composable `AiStepBlock.vue` component accepting a step type (reasoning, tool_call, subagent, plan_step, artifact) and rendering appropriate visualization with consistent: expand/collapse transition, duration timer, streaming indicator, status badge (pending/running/done/failed), and active-step border animation (CSS shimmer, not ShineBorder library). All higher-level views compose from this one primitive. This is DeerFlow's `SubtaskCard` pattern adapted for Vant 4 mobile constraints.

**Axis:** Tool call & subtask display (cross-cutting — enables all axes)

**Basis:** `direct:` DeerFlow's `subtask-card.tsx` wraps `ChainOfThought` + `FlipDisplay` + `ShineBorder` into one reusable unit; current Numina code has `AiProcessStep` and `AiToolCallStep` as separate components with duplicated status logic. `reasoned:` Every future step type (web search, file read, code execution, MCP tool) would get consistent UX for free — one investment pays off N times.

**Rationale:** Without a shared primitive, each new tool/capability requires bespoke UI work. DeerFlow achieves its polished feel because SubtaskCard handles all the animation, state, and accessibility in one place. The active-step border animation (CSS `@keyframes` with gradient) immediately answers "what is it doing right now?" without reading text.

**Downsides:** Requires refactoring existing `AiProcessStep` and `AiToolCallStep` into the new primitive; must handle the diversity of step content shapes; initial investment before visible user benefit.

**Confidence:** 85%

**Complexity:** Medium

**Status:** Unexplored

---

### 3. Collapsible Reasoning Accordion with Duration Badges

**Description:** Replace flat reasoning text display with an accordion pattern: each reasoning block shows a one-line summary (first sentence auto-extracted) with a duration badge ("思考 3s"). While streaming, the block stays expanded with shimmer pulse; once thinking ends and answering begins, it auto-collapses to its summary line. Tapping re-expands. Multiple reasoning blocks (interleaved with tool calls) each get their own accordion section. Matches DeerFlow's `reasoning.tsx` pattern of auto-close with `AUTO_CLOSE_DELAY = 1000ms` and duration tracking.

**Axis:** Thinking/reasoning visualization

**Basis:** `external:` DeerFlow's `reasoning.tsx` implements exactly this: auto-close after 1s, duration display, controllable open state via React context. Claude.ai ships the same pattern. `direct:` Current `AiProcessBlock` already has auto-collapse logic (`hasAutoCollapsed` ref) but applies it to the entire process block, not individual reasoning sections — mobile users must scroll past all expanded reasoning to reach the answer.

**Rationale:** On a ≤425px viewport, reasoning steps that stay expanded consume the entire screen. Per-section accordion with auto-collapse means users see progress (section appeared, duration badge growing) without scrolling past walls of internal monologue. The duration badge builds user calibration — they learn "reasoning takes ~5s, tool calls ~2s" which reduces wait anxiety.

**Downsides:** Auto-collapse can be jarring if content the user was reading suddenly collapses; need careful timing (collapse only when answering phase starts, not mid-thought); accessibility requires focus management on collapse.

**Confidence:** 92%

**Complexity:** Low-Medium

**Status:** Unexplored

---

### 4. Streaming Subtask Cards with Active Spotlight

**Description:** Each `tool_call` or `subagent` step renders as a distinct bordered card (not just a list item inside the process block). The currently-active card gets a subtle animated border (CSS gradient keyframe animation). On completion, the card visually compresses: front shows tool name + duration + one-line result summary; full output available on tap expand. Completed cards reduce to ~60% height. This creates visual rhythm: one bright active card, a trail of compact completed ones — directly mirroring DeerFlow's SubtaskCard with ShineBorder.

**Axis:** Tool call & subtask display

**Basis:** `direct:` DeerFlow's `subtask-card.tsx` uses `ShineBorder` on `in_progress` cards and `FlipDisplay` for live status text; current `AiToolCallStep` renders all steps at equal visual weight making it hard to distinguish active from completed. `reasoned:` Equal-weight rendering fails on mobile because 5+ expanded tool cards push the answer off-screen; progressive visual compression solves scroll depth.

**Rationale:** The single most impactful visual change — gives immediate visual answer to "what is it doing right now?" without reading text. The compression of completed cards solves the core mobile problem: long tool-call chains pushing the answer below the fold. DeerFlow proves the ShineBorder pattern works for creating visual hierarchy in agent UIs.

**Downsides:** Card borders add visual noise if too many run in sequence; compression must be smooth (CSS transition) to avoid layout jank; need to ensure compressed cards are still tappable (44px minimum touch target).

**Confidence:** 88%

**Complexity:** Medium

**Status:** Specified → `docs/brainstorms/2026-06-04-agent-chat-phase-b-requirements.md`

---

### 5. Inline Citation Chips with Source Sheet

**Description:** When the agent uses web search tools and returns source URLs, embed small numbered citation chips `[1]` `[2]` inline within the final answer markdown. Tapping a chip opens a Vant `ActionSheet` showing: source title, domain favicon, one-line snippet. A collapsible "引用了 N 个来源" section (mirroring DeerFlow's `sources.tsx`) appears above the answer text for bulk review. This surfaces the trust signals that currently exist in tool results but are invisible to users.

**Axis:** Final answer & artifact presentation

**Basis:** `direct:` DeerFlow's `sources.tsx` implements "Used N sources" collapsible with `SourcesTrigger` (count badge) + `SourcesContent` (link list); current `AiToolCallStep` only shows `resultSummary` as plain text string — web search URLs are not surfaced as structured cards. `external:` Perplexity places sources ABOVE the answer because users want to evaluate grounding before reading conclusions.

**Rationale:** Trust is built at point-of-claim, not in a footnote. For a family asset management tool, when the agent says "当前市场利率为3.5%", users need to verify this. Inline citations let them tap `[1]` to see the source without losing reading position. This transforms the agent from a black box into a verifiable advisor.

**Downsides:** Requires backend to structure web search results with title/URL/snippet (may need parser changes); inline chips add visual density to answer text; mobile popup must be lightweight to avoid covering the answer.

**Confidence:** 82%

**Complexity:** Medium-High

**Status:** Unexplored

---

### 6. Artifact Registry with Bottom-Sheet Access

**Description:** Create an `AiArtifactRegistry` that collects all artifacts produced during a conversation (reports, charts, tables, generated recommendations) into a persistent bottom-sheet accessible via a floating "📎 N" badge. Each artifact gets a type icon, title, and timestamp. Tapping opens the artifact in the existing `AiFinalAnswer.vue` component (currently unused). The registry persists across messages — artifacts from message 2 remain accessible while reading message 5 without scrolling back.

**Axis:** Final answer & artifact presentation

**Basis:** `direct:` `AiFinalAnswer.vue` and `AiArtifactLink.vue` exist in the codebase but are not imported in `AIChatPage.vue` — the architecture anticipated this pattern but never wired it. `external:` OpenAI Canvas renders long outputs as compact artifact cards in chat with "Open" button to full view; Notion AI leaves persistent block-level artifacts that remain accessible.

**Rationale:** The chat paradigm loses artifacts in the scroll. For family asset management, the agent might produce a budget breakdown, an allocation chart, and an optimization recommendation — all in one conversation. Random access to these outputs (not just sequential scroll) is essential. This also activates two existing but dead components, recovering sunk development cost.

**Downsides:** Need to define what constitutes an "artifact" vs. normal answer text; bottom-sheet on mobile competes with the input area; persistence across messages requires conversation-level state management.

**Confidence:** 78%

**Complexity:** Medium

**Status:** Unexplored

---

### 7. Session History with Collapsed Process Footnotes

**Description:** Persist the full process chain in message history but render it as a single expandable row "查看推理过程 (N 步)" beneath the final answer when loading past sessions. The answer is always immediately visible; the process steps are one tap away for debugging or trust verification. Current `loadSessionMessages()` only handles `user.message` and `assistant.message` event types — extend it to reconstruct `steps[]` from stored NDJSON events and render them via the same `AiStepBlock` primitive (Idea #2) in collapsed state.

**Axis:** Session history & replay

**Basis:** `direct:` Current gap documented in web research: "loadSessionMessages() only handles user.message and assistant.message event types — tool call timelines and reasoning content are not reconstructed from session history." The NDJSON events are already stored; the problem is purely a rendering/persistence decision. `reasoned:` The data exists — the stream events were written to the session store. Rendering them in history is a read-side-only change that requires no backend modification.

**Rationale:** Users revisiting past answers often want to understand WHY the agent concluded something — especially for financial decisions. Without process steps, the agent's answers are opaque black boxes in history. This restores transparency without cluttering the default view (collapsed by default). For family scenarios, one member may need to verify what the agent recommended to another member.

**Downsides:** Increases storage/bandwidth for session replay (full event log per message); collapsed footnote adds ~32px per message in history view; need to handle cases where events were not stored (legacy sessions).

**Confidence:** 85%

**Complexity:** Medium

**Status:** Unexplored

---

## Rejection Summary

| # | Idea | Reason Rejected |
|---|------|-----------------|
| 1 | Progress Ring replacing TaskConsole | Too expensive — requires new UI paradigm + backend step counting; plan skeleton already solves "is it still working?" |
| 2 | Answer-First Rendering (pin answer at top) | Breaks streaming chat mental model; complex DOM reordering mid-stream; conflicts with mobile scroll-to-bottom paradigm |
| 3 | State-Aware Suggestion Chips | Scope overrun — SuggestionChips enhancement is orthogonal to process visualization focus |
| 4 | Event Replay with Timeline Scrubber | Too expensive for mobile H5 — full scrubber is heavy UX; session history footnotes (#7) achieves 80% value at 20% cost |
| 5 | Error Recovery with Inline Retry | Scope overrun — requires backend retry infrastructure; can't be solved at UI layer alone |
| 6 | `useAgentStream` Composable | Duplicates a stronger idea — the unified step primitive (#2) already requires extracting reactive state; a full provider refactor is premature until the rendering layer proves the need |

## Implementation Priority (Suggested)

```
Phase A (Foundation):     #2 Unified Step Primitive → #3 Collapsible Reasoning  ✅ COMPLETE
Phase B (Plan & Activity): #1 Plan Skeleton → #4 Subtask Cards with Spotlight     📋 SPECIFIED (docs/brainstorms/2026-06-04-agent-chat-phase-b-requirements.md)
Phase C (Output & History): #5 Citation Chips → #6 Artifact Registry → #7 History Footnotes  ⏳ Pending
```

Phase A creates the architectural foundation; B delivers the DeerFlow-inspired progressive disclosure; C enriches the output layer.

## Next Steps

Use `ce-brainstorm` on any individual idea to produce a detailed requirements spec, or proceed directly to `ce-plan` for implementation planning of a chosen subset.
