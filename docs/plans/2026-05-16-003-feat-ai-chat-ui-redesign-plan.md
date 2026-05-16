---
title: "feat: AI Chat Page UI/UX Redesign"
date: 2026-05-16
sequence: "003"
type: feat
status: active
---

# feat: AI Chat Page UI/UX Redesign

## Summary

Redesign the AI chat page (`AIChatPage.vue` + `AIChatInput.vue`) to deliver a clear, progressive AI Agent interaction experience on mobile H5. The redesign focuses on making each phase of the AI response lifecycle (connecting → thinking → tool calls → streaming answer → complete) visually distinct and user-comprehensible, while preserving the existing backend streaming protocol, state machine, and theme system.

The existing `useAITask` composable already tracks `phase`, `thinkContent`, `thinkDone`, `thinkSeconds`, and `toolTimeline`. This plan extends the UI layer on top of that foundation — no backend changes required.

---

## Problem Frame

The current chat UI has several UX gaps:

1. **No connecting state** — after sending, there is no visible feedback until the first token arrives.
2. **Thinking block is always visible** — it does not auto-collapse when the answer starts streaming, cluttering the reading experience.
3. **Tool timeline is outside the thinking block** — tool calls appear as a separate section below the thinking block, not integrated into the process area.
4. **No shimmer/shimmer-sweep animation** — in-progress states lack the left-to-right sweep that signals "processing."
5. **User bubble has no send-state feedback** — the bubble appears but there is no sending/failed state indicator.
6. **No "scroll to bottom" affordance** — when the user scrolls up during streaming, there is no way to jump back.
7. **Input area does not visually switch** between send mode and stop mode during generation.
8. **Overflow issues** — code blocks and tables can break the mobile layout.
9. **Action bar appears during generation** — like/dislike buttons are visible while the answer is still streaming.

---

## Scope Boundaries

### In scope
- `AIChatPage.vue` — message list rendering, state-driven UI regions, scroll behavior, action bar timing
- `AIChatInput.vue` — send/stop toggle, disabled state during generation
- CSS custom properties — shimmer animation, theme-aware variables for new UI regions
- i18n keys — new status strings (connecting, send states, scroll-to-bottom, interrupted)
- `useAITask.ts` — minor state additions: `userMessageStatus` (sending/sent/failed), `isUserScrolledUp`

### Out of scope
- Backend streaming protocol (no changes to NDJSON events or orchestrator)
- Session management, history sidebar, capability filters
- Slash command palette, plus panel, deep think toggle logic
- New design system or theme tokens beyond what already exists in `AIChatPage.vue`
- Markdown renderer swap (keep `marked` + DOMPurify)
- Performance optimization of the markdown render pipeline

### Deferred to Follow-Up Work
- Multi-version answer history (regenerate keeps previous versions with navigation)
- Continue generation after interruption
- Read-aloud / TTS
- Citation / source reference display
- Image/file attachment rendering

---

## State Machine Extension

The existing `useAITask` status/phase model is extended with two additions:

**`userMessageStatus`** (new ref in `AIChatPage.vue` local state, per message):
```
sending → sent → (AI connecting begins)
sending → failed
```

**`isUserScrolledUp`** (new ref in `AIChatPage.vue`):
- `false` by default
- Set `true` when user scrolls up more than ~100px from bottom during streaming
- Set `false` when user taps "scroll to bottom" or stream completes

**Thinking block collapse rule** (extend existing logic):
- `thinkOpen` defaults to `true` while `phase === 'thinking'`
- Auto-set to `false` when `phase` transitions to `'answering'` AND `thinkDone === true`, UNLESS user has manually toggled it
- Track `thinkManuallyToggled: boolean` per message to respect user intent

---

## High-Level Technical Design

This illustrates the intended UI region layout and state-driven visibility. This is directional guidance for review, not implementation specification.

```
┌─────────────────────────────────────┐
│  CHAT HEADER (fixed, compact)       │
├─────────────────────────────────────┤
│  MESSAGE LIST (scrollable)          │
│                                     │
│  ┌─────────────────────────────┐    │
│  │ USER BUBBLE (right-aligned) │    │
│  │  [sending indicator / ❌]   │    │
│  └─────────────────────────────┘    │
│                                     │
│  ┌─────────────────────────────┐    │
│  │ AI MESSAGE BLOCK (left)     │    │
│  │                             │    │
│  │  [CONNECTING REGION]        │    │
│  │   ● 正在连接 · 2s  ~~~sweep │    │
│  │   (hidden once thinking/    │    │
│  │    answering starts)        │    │
│  │                             │    │
│  │  [THINKING REGION]          │    │
│  │   ◎ 思考中 · 8s  [收起▾]   │    │
│  │   ~~~sweep on container     │    │
│  │   ┌─ tool call rows ──────┐ │    │
│  │   │ 🔍 搜索网页 · 3s      │ │    │
│  │   │ ✓  查询完成 · 5s      │ │    │
│  │   └───────────────────────┘ │    │
│  │   [grey think content]      │    │
│  │   (auto-collapsed when      │    │
│  │    answering starts)        │    │
│  │                             │    │
│  │  [ANSWER REGION]            │    │
│  │   streamed markdown text    │    │
│  │   [▌ cursor while streaming]│    │
│  │                             │    │
│  │  [ACTION BAR]               │    │
│  │   (only after complete/     │    │
│  │    interrupted/failed)      │    │
│  └─────────────────────────────┘    │
│                                     │
│  [↓ 查看最新回复] (float, when      │
│   user scrolled up + streaming)     │
├─────────────────────────────────────┤
│  INPUT BAR (fixed bottom)           │
│  [textarea]  [SEND ▶ / STOP ■]     │
└─────────────────────────────────────┘
```

State-to-visibility matrix:

| Phase / Status        | Connecting | Thinking | Answer | Action Bar | Stop btn |
|-----------------------|-----------|---------|--------|------------|----------|
| user_sending          | —         | —       | —      | —          | —        |
| user_failed           | —         | —       | —      | retry      | —        |
| ai_connecting         | ✓ sweep   | —       | —      | —          | ✓        |
| ai_thinking           | hidden    | ✓ open  | —      | stop only  | ✓        |
| ai_tool_calling       | hidden    | ✓ open  | —      | stop only  | ✓        |
| ai_answering          | hidden    | collapsed| ✓     | stop only  | ✓        |
| ai_completed          | —         | collapsed| ✓     | full       | —        |
| ai_interrupted        | —         | keep    | ✓     | full+hint  | —        |
| ai_failed             | —         | keep    | partial| full+retry | —        |

---

## Implementation Units

### U1. User Bubble Send State

**Goal:** Show sending/failed state on user message bubbles so users know their message was received.

**Requirements:** §4.2 (user message states), §18.1 (basic message acceptance)

**Dependencies:** none

**Files:**
- `frontend/apps/main/src/pages/AIChatPage.vue`
- `frontend/apps/main/src/i18n/locales/zh-CN.ts`
- `frontend/apps/main/src/i18n/locales/en-US.ts`

**Approach:**
- Add `sendStatus: 'sending' | 'sent' | 'failed'` field to the local `Message` interface in `AIChatPage.vue`
- When user submits: immediately push message with `sendStatus: 'sending'`
- On stream start (first event received): set `sendStatus: 'sent'`
- On send error (network/API failure before stream starts): set `sendStatus: 'failed'`
- Render a small indicator below the user bubble: a spinner dot for `sending`, nothing for `sent`, a red `❌` icon + retry button for `failed`
- Failed state: show "发送失败" label + "重发" button; clicking retry re-sends the same message content
- Use `--text-muted` for the sending indicator, `--error-color` (or Vant's danger color) for failed

**Patterns to follow:** existing `msg-actions` button pattern in `AIChatPage.vue:289-302`

**Test scenarios:**
- Happy path: user sends message → bubble appears immediately with sending indicator → indicator disappears once first stream event arrives
- Failed send: simulate network error → bubble stays, shows failed indicator with retry button
- Retry: clicking retry re-triggers the send flow, bubble transitions back to sending state
- Long message: sending indicator does not overflow or wrap oddly on 375px viewport

---

### U2. Connecting State Region

**Goal:** Show a visible "connecting" region in the AI message block between user send and first content arrival.

**Requirements:** §6.1–6.6, §13.2 (connecting state row), §18.2 (connecting acceptance)

**Dependencies:** U1

**Files:**
- `frontend/apps/main/src/pages/AIChatPage.vue`
- `frontend/apps/main/src/i18n/locales/zh-CN.ts`
- `frontend/apps/main/src/i18n/locales/en-US.ts`

**Approach:**
- The connecting region is shown when `msg.phase === 'connecting'` (maps to existing `phase.connecting` event)
- Content: animated pulse dot + configurable status text + elapsed seconds counter
- Elapsed seconds: use `elapsedSeconds` from `useAITask` (already tracked)
- Text: `t('aiChat.connecting')` + ` · ` + `elapsedSeconds` + `s` — text must be i18n-configurable, not hardcoded
- Shimmer sweep: apply `shimmer-sweep` CSS animation (left-to-right gradient sweep) on the connecting row container
- Hide rule: when `msg.phase` transitions away from `'connecting'` (to `'thinking'` or `'answering'`), the connecting region is removed from DOM (not just hidden with opacity)
- Failure: if `msg.phase === 'error'` and no content exists yet, show a compact error row with retry button instead of the connecting region
- The pulse dot animation: CSS keyframe `pulse-dot` — scale 0.8→1.2→0.8, opacity 0.4→1→0.4, 1.2s infinite
- `prefers-reduced-motion`: replace pulse + shimmer with a static dot and no sweep

**Patterns to follow:** existing `thinking-placeholder` and `phase-strip` in `AIChatPage.vue:203-220`

**Test scenarios:**
- Connecting region appears immediately after user message is sent (before any stream event)
- Elapsed seconds increment every second
- Region disappears when `phase` changes to `'thinking'`
- Region disappears when `phase` changes to `'answering'` (model with no thinking)
- Connection failure: region shows error state with retry
- `prefers-reduced-motion`: no animation, static dot shown

---

### U3. Thinking Block Redesign — Auto-Collapse and Tool Integration

**Goal:** Redesign the thinking block so tool calls are integrated inside it, it auto-collapses when answering starts, and it respects manual user toggle.

**Requirements:** §7.1–7.8, §8.1–8.6, §13.2 (thinking/tool rows), §18.3–18.4

**Dependencies:** U2

**Files:**
- `frontend/apps/main/src/pages/AIChatPage.vue`
- `frontend/apps/main/src/i18n/locales/zh-CN.ts`
- `frontend/apps/main/src/i18n/locales/en-US.ts`

**Approach:**

**Auto-collapse logic:**
- Add `thinkManuallyToggled: boolean` to the `Message` interface (default `false`)
- When `phase` transitions from `'thinking'` to `'answering'` AND `thinkDone === true`: if `!msg.thinkManuallyToggled`, set `msg.thinkOpen = false`
- When user clicks the think-toggle button: set `msg.thinkManuallyToggled = true`, then toggle `msg.thinkOpen`
- This ensures auto-collapse only fires once and user intent is preserved thereafter

**Tool calls inside thinking block:**
- Move the `tool-timeline` div from its current position (after the think block) to inside the think block's collapsible content area
- Tool rows render above the grey think text content
- Each tool row: icon + display name + status text + elapsed/done time
- In-progress tool: pulse dot + shimmer sweep on the row
- Completed tool: checkmark icon, muted text, no animation
- Failed tool: warning icon, muted red text, "已尝试继续回答" note

**Thinking block header summary (when collapsed):**
- Show: `[done icon] 已思考 Xs` when `thinkDone`
- If tools were called, append summary chips: `· 已搜索网页` or `· 已调用 N 个工具`
- Summary chips use `--text-muted` color, small font

**Shimmer sweep on thinking container:**
- Apply shimmer sweep to the entire think block container while `phase === 'thinking'` or `phase === 'answering'` with `!thinkDone`
- Remove shimmer once `thinkDone === true`

**Patterns to follow:** existing `think-block` CSS in `AIChatPage.vue`, existing `tool-card` structure

**Test scenarios:**
- Thinking block is open while `phase === 'thinking'`
- Auto-collapses when `phase` transitions to `'answering'` (user has not manually toggled)
- Does NOT auto-collapse if user manually opened/closed it before the transition
- Collapsed header shows "已思考 Xs" with correct seconds
- Collapsed header shows tool summary chips when tools were called
- User can re-expand collapsed block and see full think content + tool rows
- Tool rows inside thinking block: in-progress shows pulse, completed shows checkmark
- Tool call failure: shows weak warning, does not block answer rendering
- No thinking content: thinking block not rendered at all (existing behavior preserved)
- `prefers-reduced-motion`: no shimmer, static icons

---

### U4. Answer Streaming Region — Cursor and Overflow Fixes

**Goal:** Add a streaming cursor indicator to the answer region, fix code block / table overflow on mobile, and ensure the action bar only appears after generation is complete.

**Requirements:** §9.1–9.8, §10.1, §18.5–18.6

**Dependencies:** U3

**Files:**
- `frontend/apps/main/src/pages/AIChatPage.vue`

**Approach:**

**Streaming cursor:**
- While `msg.phase === 'answering'`, append a blinking `▌` cursor element after the rendered markdown content
- The cursor is a `<span class="stream-cursor">` positioned inline after the last rendered character
- CSS: `animation: blink 0.8s step-end infinite` — opacity 1→0→1
- Remove cursor when `phase` transitions to `'done'` or `'error'`

**Action bar timing:**
- Currently action buttons (copy, regenerate, like, dislike) are always visible
- Change: wrap action bar in `v-if="msg.phase === 'done' || msg.phase === 'error' || msg.phase === 'interrupted'"`
- During generation: only show the stop button (handled in U5)
- After completion: show full action bar (copy, regenerate, like, dislike)
- Interrupted state: show action bar + a weak "已停止生成" label above the action bar

**Code block overflow fix:**
- Add CSS to `.bubble-text pre, .bubble-text code` blocks: `overflow-x: auto; max-width: 100%; word-break: break-word`
- Wrap pre blocks in a `<div class="code-block-wrapper">` with `overflow-x: auto; -webkit-overflow-scrolling: touch`
- This requires post-processing the rendered HTML or adding CSS that targets the markdown output container

**Table overflow fix:**
- Wrap tables in a scrollable container: target `.bubble-text table` parent with `overflow-x: auto; display: block; max-width: 100%`
- Apply via CSS on `.bubble-text` descendants — no JS needed

**Interrupted state label:**
- Add `'interrupted'` as a valid `phase` value in the `Message` interface
- When user clicks stop: set `msg.phase = 'interrupted'`
- Render a small `t('aiChat.generationStopped')` label above the action bar in interrupted state

**Patterns to follow:** existing `bubble-text` CSS, existing `msg-actions` div

**Test scenarios:**
- Streaming cursor visible while `phase === 'answering'`, gone after `phase === 'done'`
- Action bar hidden during streaming, appears after completion
- Action bar appears after user stops generation (interrupted state)
- "已停止生成" label visible in interrupted state
- Code block with 80+ chars does not overflow 375px viewport (horizontal scroll within block)
- Table with 5+ columns does not overflow 375px viewport (horizontal scroll within table wrapper)
- Like/dislike buttons show selected state after click
- Copy button shows brief success feedback (existing `onCopy` behavior preserved)

---

### U5. Input Bar Send/Stop Toggle

**Goal:** Make the input bar clearly switch between "send" mode and "stop generation" mode during AI generation.

**Requirements:** §11.1–11.3, §18.6 (stop generation)

**Dependencies:** U1

**Files:**
- `frontend/apps/main/src/components/ai/AIChatInput.vue`
- `frontend/apps/main/src/i18n/locales/zh-CN.ts`
- `frontend/apps/main/src/i18n/locales/en-US.ts`

**Approach:**
- `AIChatInput.vue` already receives an `asking` prop — use this to drive the toggle
- When `asking === false`: show send button (existing behavior)
- When `asking === true`: replace send button with a stop button (square ■ icon)
- Stop button: always enabled (not disabled), clicking emits `stop` event to parent
- Send button: disabled when input is empty (existing behavior)
- The stop button uses `--btn-color` / `--btn-hover-bg` variables — same as other action buttons, no special color needed
- Input textarea: remains editable during generation (user can type next question)
- Add `t('aiChat.stopGeneration')` aria-label to the stop button

**Patterns to follow:** existing send button in `AIChatInput.vue`, existing `asking` prop usage

**Test scenarios:**
- Send button visible when `asking === false`
- Stop button visible when `asking === true`
- Clicking stop emits `stop` event (parent handles cancellation via existing `cancelAITask`)
- Stop button has correct aria-label
- Input remains editable during generation
- Send button disabled when input empty, enabled when input has content
- Touch target for stop button ≥ 44×44px

---

### U6. Scroll Behavior — Auto-Follow and Scroll-to-Bottom Button

**Goal:** Auto-scroll during streaming when user is at the bottom; show a "scroll to bottom" button when user has scrolled up; stop auto-scroll when user scrolls up.

**Requirements:** §12.1–12.4, §18.5 (scroll acceptance)

**Dependencies:** U4

**Files:**
- `frontend/apps/main/src/pages/AIChatPage.vue`
- `frontend/apps/main/src/i18n/locales/zh-CN.ts`
- `frontend/apps/main/src/i18n/locales/en-US.ts`

**Approach:**

**Scroll detection:**
- Add a `scroll` event listener on `scrollRef` (the `.chat-body` div)
- Compute `isUserScrolledUp`: `scrollRef.scrollHeight - scrollRef.scrollTop - scrollRef.clientHeight > 100`
- Set `isUserScrolledUp = true` when user scrolls up during streaming
- Set `isUserScrolledUp = false` when user taps the scroll-to-bottom button or when streaming completes

**Auto-scroll during streaming:**
- Current behavior: `scrollRef.scrollTop = scrollRef.scrollHeight` is called on each token
- Wrap this in: `if (!isUserScrolledUp) { scrollRef.scrollTop = scrollRef.scrollHeight }`
- This preserves existing auto-scroll but stops it when user has scrolled up

**Scroll-to-bottom button:**
- Render a floating button `v-if="isUserScrolledUp && asking"` positioned above the input bar
- Content: down-arrow icon + `t('aiChat.scrollToBottom')` text
- Clicking: set `isUserScrolledUp = false`, scroll to bottom
- Position: `position: fixed`, bottom above input bar height + safe area, centered horizontally
- Style: compact pill shape using existing `--suggestion-bg` / `--suggestion-border` variables
- Does not overlap the input bar or the last message

**History load stability:**
- When loading older messages at the top (infinite scroll), preserve scroll position using `scrollTop` delta before/after DOM update — existing `historyScrollRef` pagination already handles this; verify it does not conflict

**Patterns to follow:** existing `scrollRef` usage and `scrollToBottom()` calls in `AIChatPage.vue`

**Test scenarios:**
- Auto-scroll follows new tokens when user is at bottom
- Auto-scroll stops when user scrolls up during streaming
- Scroll-to-bottom button appears when user scrolls up during streaming
- Scroll-to-bottom button disappears when user taps it
- Scroll-to-bottom button disappears when streaming completes
- Scroll-to-bottom button does not appear when not streaming
- Button does not overlap input bar on 375px viewport
- Loading older messages does not jump current reading position

---

### U7. Shimmer Sweep Animation and Reduced-Motion Support

**Goal:** Define the shared shimmer sweep CSS animation used by connecting, thinking, and tool-call regions; ensure it degrades gracefully under `prefers-reduced-motion`.

**Requirements:** §6.4, §7.5, §8.3–8.5, §15.1–15.3

**Dependencies:** U2, U3 (consumes the animation defined here)

**Files:**
- `frontend/apps/main/src/pages/AIChatPage.vue` (scoped `<style>` section)

**Approach:**
- Define `@keyframes shimmer-sweep` in the scoped style block:
  - Background: linear-gradient from transparent → semi-transparent white (light mode) or semi-transparent white (dark mode) → transparent
  - `background-size: 200% 100%`
  - Animation: `background-position` from `200% 0` to `-200% 0`, duration 2s, linear, infinite
- Apply via `.shimmer-active` utility class — components add/remove this class based on their active state
- Dark mode: shimmer uses `rgba(255,255,255,0.06)` highlight — subtle, not glaring
- Light mode: shimmer uses `rgba(255,255,255,0.5)` highlight — soft
- `@media (prefers-reduced-motion: reduce)`: override `.shimmer-active` to have no animation, no background-position transition
- The shimmer is applied as a `background` overlay on the container — it does not affect text readability

**Patterns to follow:** existing CSS variable usage in `AIChatPage.vue` dark/light theme blocks

**Test scenarios:**
- Shimmer visible on connecting region while connecting
- Shimmer visible on thinking block while thinking
- Shimmer visible on in-progress tool call rows
- Shimmer NOT visible on completed/failed states
- Shimmer NOT visible on answer text region
- `prefers-reduced-motion`: no animation, static appearance
- Dark mode: shimmer not glaring (subjective — verify at 375px in dark theme)
- Light mode: shimmer visible but subtle

---

### U8. i18n Keys and Theme Variable Audit

**Goal:** Add all new i18n keys required by U1–U6; audit that no new hardcoded Chinese strings were introduced; verify all new UI elements use existing CSS variables.

**Requirements:** §14.1–14.3, cross-cutting i18n convention

**Dependencies:** U1–U6

**Files:**
- `frontend/apps/main/src/i18n/locales/zh-CN.ts`
- `frontend/apps/main/src/i18n/locales/en-US.ts`

**New i18n keys to add under `aiChat`:**

| Key | zh-CN value | en-US value |
|-----|-------------|-------------|
| `sendingMessage` | `发送中` | `Sending` |
| `sendFailed` | `发送失败` | `Send failed` |
| `resend` | `重发` | `Resend` |
| `connectingAI` | `正在连接` | `Connecting` |
| `stopGeneration` | `停止生成` | `Stop` |
| `generationStopped` | `已停止生成` | `Generation stopped` |
| `scrollToBottom` | `查看最新回复` | `Latest reply` |
| `thinkSummarySearched` | `已搜索网页` | `Searched web` |
| `thinkSummaryTools` | `已调用 {n} 个工具` | `Used {n} tools` |
| `toolCallFailed` | `工具调用失败，已尝试继续回答` | `Tool failed, continuing` |

**Theme variable audit:**
- All new UI elements must use variables already defined in `AIChatPage.vue`'s `:root` / `[data-theme="light"]` blocks
- No new hardcoded hex colors
- Shimmer colors expressed as CSS variables: `--shimmer-light` and `--shimmer-dark` added to the theme blocks
- Verify: connecting region, thinking block header, tool rows, scroll-to-bottom button, send-failed indicator all use semantic variables

**Test scenarios:**
- `npm run typecheck` passes with no new type errors
- All new `t('aiChat.xxx')` keys exist in both `zh-CN.ts` and `en-US.ts`
- No hardcoded Chinese strings in `.vue` files (grep check)
- Light theme: all new elements readable
- Dark theme: all new elements readable, shimmer not glaring

---

## Verification

After all units are implemented:

1. `npm run typecheck` — zero errors
2. `npm run lint` — zero new warnings
3. Manual smoke test on 375px viewport (Chrome DevTools mobile emulation):
   - Send a message → connecting region appears → thinking block opens → answer streams → thinking auto-collapses → action bar appears
   - Scroll up during streaming → scroll-to-bottom button appears → tap it → returns to bottom
   - Stop generation → interrupted state shown → action bar appears
   - Send failure simulation → failed indicator + retry button
   - Code block with long line → horizontal scroll within block, no page overflow
   - Table with many columns → horizontal scroll within table, no page overflow
4. Dark/light theme toggle: all states readable in both themes
5. `prefers-reduced-motion` emulation in DevTools: no animations, static states

---

## Risks

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Auto-collapse fires at wrong time if `thinkDone` and phase transition are not atomic | Medium | UX glitch | Guard collapse with both `thinkDone === true` AND `phase === 'answering'` check |
| Shimmer animation causes jank on low-end Android | Low | Performance | Use `will-change: background-position` only on active shimmer elements; remove on completion |
| Moving tool timeline inside think block breaks existing tool display for non-thinking models | Medium | Regression | Tool timeline outside think block is the fallback when `thinkContent` is empty — keep both render paths |
| Scroll position jump when loading history while streaming | Low | UX glitch | Existing pagination sentinel handles this; verify no conflict with new `isUserScrolledUp` logic |
| `prefers-reduced-motion` not tested on real devices | Low | Accessibility | Test in Chrome DevTools emulation as minimum bar |

---

## Acceptance Checklist

### User bubble
- [ ] Bubble appears immediately on send
- [ ] Sending indicator visible briefly
- [ ] Failed state shows retry button
- [ ] Retry re-sends correctly

### Connecting state
- [ ] Connecting region appears after send, before first content
- [ ] Elapsed seconds increment
- [ ] Shimmer sweep visible
- [ ] Region disappears when thinking/answering starts
- [ ] Connection failure shows error + retry

### Thinking block
- [ ] Open while thinking
- [ ] Tool calls rendered inside thinking block
- [ ] In-progress tools show pulse + shimmer
- [ ] Completed tools show checkmark, muted
- [ ] Auto-collapses when answering starts (no manual toggle)
- [ ] Manual toggle respected (no auto-collapse after user interaction)
- [ ] Collapsed header shows "已思考 Xs"
- [ ] Collapsed header shows tool summary chips
- [ ] User can re-expand

### Answer streaming
- [ ] Streaming cursor visible during answering
- [ ] Cursor gone after completion
- [ ] Action bar hidden during streaming
- [ ] Action bar appears after completion
- [ ] Interrupted state: "已停止生成" label + action bar
- [ ] Code blocks scroll horizontally, no page overflow
- [ ] Tables scroll horizontally, no page overflow

### Input bar
- [ ] Send button → stop button during generation
- [ ] Stop button triggers cancellation
- [ ] Input remains editable during generation

### Scroll
- [ ] Auto-scroll follows streaming when at bottom
- [ ] Auto-scroll pauses when user scrolls up
- [ ] Scroll-to-bottom button appears when scrolled up during streaming
- [ ] Tapping button returns to bottom and hides button

### Theme
- [ ] All states readable in dark theme
- [ ] All states readable in light theme
- [ ] Shimmer not glaring in dark theme
- [ ] No hardcoded colors

### Mobile H5
- [ ] No horizontal page overflow at 375px
- [ ] All tap targets ≥ 44×44px
- [ ] Input not obscured by soft keyboard
- [ ] Bottom safe area respected

### Reduced motion
- [ ] No animations under `prefers-reduced-motion`
- [ ] Static states still convey meaning

---

## Open Questions

1. **Connecting text configurability**: The spec says connecting text should be configurable. For now, a single i18n key `aiChat.connectingAI` is used. If multiple rotating phrases are desired, that is a follow-up.
2. **Tool call failure and answer continuation**: The current backend does not emit a distinct `tool.failed` event that the frontend can distinguish from a tool with no result. Verify with backend team whether `tool.result` with `success: false` is the correct signal, or if a separate event type is needed.
3. **Interrupted vs stopped**: The spec mentions "继续生成" as an optional feature. This plan implements interrupted state UI only; the "continue" action is deferred.
