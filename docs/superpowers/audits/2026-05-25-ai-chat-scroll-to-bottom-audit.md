# Scroll-to-Bottom Audit — `/ai/chat`

> Phase 3 Bundle B item B1. Source spec: `docs/superpowers/specs/2026-05-25-ai-conversation-phase-3-design.md` §4.B1.

## Inspected code

- `frontend/apps/main/src/pages/AIChatPage.vue:339-352` — button template and visibility gate
- `frontend/apps/main/src/pages/AIChatPage.vue:786-816` — `scrollToBottom`, `onChatScroll`, `onScrollToBottom`

## Findings

| # | Spec criterion | Status | Evidence | Fix needed |
|---|----------------|--------|----------|------------|
| 1 | Button visible when user scrolls up | **Partial** | `v-if="isUserScrolledUp && asking"` (line 340) ties visibility to streaming. User scrolling up to read history while no message is in flight gets no button. | Drop the `&& asking` guard so the button appears whenever the user is scrolled up beyond threshold, regardless of streaming state. Also requires `onChatScroll` to update `isUserScrolledUp` outside streaming. |
| 2 | Auto-hides at bottom | **Pass** | `isUserScrolledUp.value = distFromBottom > 100` (line 806) toggles correctly. | None |
| 3 | Click → smooth scroll | **Partial** | `scrollRef.value.scrollTop = scrollRef.value.scrollHeight` (line 813) jumps instantly. | Switch to `scrollRef.value.scrollTo({ top: scrollHeight, behavior: 'smooth' })` for `onScrollToBottom`. Keep instant scroll inside `scrollToBottom()` (auto-scroll during streaming) to avoid scroll-fight with new tokens. |
| 4 | Auto-scroll pauses when user scrolled up | **Pass** | `scrollToBottom(force=false)` early-returns on `isUserScrolledUp` (line 789). `force=true` is correctly used only by explicit user actions (line 1171 `await scrollToBottom(true)`). | None |

## Decision

Two small patches required (#1 visibility gate, #3 smooth scroll on click). Documented in Task 2.

## Verification

After Task 2 lands:
- Manually scroll up while no message is streaming → button visible
- Click button → smooth animation, not jump
- Scroll up during streaming → auto-scroll pauses; button visible (already passing)
- Scroll back to bottom → button auto-hides (already passing)
