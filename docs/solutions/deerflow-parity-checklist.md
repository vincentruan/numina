# DeerFlow Interaction Parity Checklist

Generated: 2026-06-14
Reference Demo: https://deerflow.tech/workspace/chats/fe3f7974-1bcb-4a01-a950-79673baafefd
Local Implementation: `/ai/chat?agentId=100000000000005&newSession=1`

## 1. Welcome State (欢迎态)

| # | Feature | DeerFlow Source | Numina Implementation | Status | Notes |
|---|---------|-----------------|----------------------|--------|-------|
| 1.1 | Centered input box | `input-box.tsx` welcome-mode class | `AIChatPage.vue` suggestion-grid | ⚠️ | DeerFlow uses centered input with suggestions below; Numina uses suggestion cards grid |
| 1.2 | Hero title "有什么想问的？" | `input-box.tsx` welcome-hero | `AIChatPage.vue` hero-title with AuroraText | ⚠️ | Different styling - AuroraText gradient vs DeerFlow plain text |
| 1.3 | Subtitle guidance text | `input-box.tsx` hero-subtitle | `AIChatPage.vue` hero-subtitle | ✅ | Both have subtitle |
| 1.4 | Example suggestions on welcome | `input-box.tsx` SuggestionList | `AIChatPage.vue` suggestion-card grid | ⚠️ | Different layout - DeerFlow horizontal below input, Numina vertical grid |
| 1.5 | Model selector visible | `ModelSelectorPopup.vue` | Missing in welcome state | ❌ | Not shown in welcome state |
| 1.6 | Mode selector (Flash/Thinking/Pro/Ultra) | `ModeSelector.vue` | Missing | ❌ | Not implemented |

## 2. Message Flow (消息流)

| # | Feature | DeerFlow Source | Numina Implementation | Status | Notes |
|---|---------|-----------------|----------------------|--------|-------|
| 2.1 | User bubble right-aligned, max 70% width | `message-list-item.tsx` human-wrapper | `ChatMessage.vue` user-bubble | ✅ | Implemented |
| 2.2 | Assistant full-width, left-aligned | `message-list-item.tsx` assistant-wrapper | `ChatMessage.vue` assistant-wrapper | ✅ | Implemented |
| 2.3 | 6-type MessageGroup discrimination | `messages/utils.ts` getMessageGroups | `useMessageGroups.ts` getMessageGroups | ✅ | USE_MESSAGE_GROUP_RENDERING=true |
| 2.4 | Hide control messages (summary, loop_warning) | `messages/utils.ts` HIDDEN_CONTROL_MESSAGE_NAMES | `messageGroups.ts` isHiddenFromUIMessage | ✅ | Implemented |
| 2.5 | Strip private thinking tags (十六条思考链) | `messages/utils.ts` splitInlineReasoning | `reasoning-filter.ts` splitInlineReasoning | ✅ | Implemented |

## 3. ChainOfThought (工具调用可视化)

| # | Feature | DeerFlow Source | Numina Implementation | Status | Notes |
|---|---------|-----------------|----------------------|--------|-------|
| 3.1 | aboveLastToolCallSteps hidden by default | `chain-of-thought.tsx` hidden history | `ChainOfThought.vue` line 116-120 | ✅ | Verified matches DeerFlow pattern exactly |
| 3.2 | lastToolCallStep always visible | `chain-of-thought.tsx` last visible | `ChainOfThought.vue` line 110-113 | ✅ | Verified matches DeerFlow pattern |
| 3.3 | "X more steps" expand button | `chain-of-thought.tsx` expand-btn | `ChainOfThought.vue` expand-btn | ✅ | Implemented |
| 3.4 | FlipDisplay animation for last tool call | `message-group.tsx` FlipDisplay wrapper | `FlipDisplay.vue` wrapper | ✅ | Implemented |
| 3.5 | Tool-specific icons (web_search=search, bash=terminal) | `tool-icon-map.ts` TOOL_ICON_MAP | `tool-icon-map.ts` TOOL_ICON_MAP | ✅ | Implemented |
| 3.6 | Result badges (success=✓, error=✗, running=spinner) | `chain-of-thought.tsx` Badge | `ChainOfThought.vue` Badge | ✅ | Vant auto-import |
| 3.7 | Search results clickable list | `chain-of-thought.tsx` SearchResults | `ChainOfThoughtSearchResults.vue` | ✅ | Implemented |
| 3.8 | Thinking collapsible AFTER tool calls | `chain-of-thought.tsx` lastReasoningStep | `ChainOfThought.vue` line 124-133 | ✅ | Verified matches DeerFlow pattern |
| 3.9 | "思考" label with lightbulb icon | `chain-of-thought.tsx` thinking-toggle | `ChainOfThought.vue` thinking-toggle | ✅ | Implemented |

## 4. SubtaskCard (子任务卡片)

| # | Feature | DeerFlow Source | Numina Implementation | Status | Notes |
|---|---------|-----------------|----------------------|--------|-------|
| 4.1 | Status icons (completed=check-circle, failed=x-circle) | `subtask-card.tsx` statusIcon | `SubtaskCard.vue` statusIcon | ✅ | Implemented |
| 4.2 | Shimmer text effect for in_progress | `shimmer.tsx` with spread={3} | `ShimmerText.vue` spread prop | ⚠️ | DeerFlow uses pixel-based spread (motion/react), Numina uses percentage-based |
| 4.3 | ShineBorder ambilight animation | `shine-border.tsx` colors array | `ShineBorder.vue` colors prop | ✅ | Colors match: ["#A07CFE", "#FE8FB5", "#FFBE7B"] |
| 4.4 | Auto-expand on in_progress | `subtask-card.tsx` watch immediate | `SubtaskCard.vue` watch immediate | ✅ | Implemented |
| 4.5 | Current action from explainLastToolCall | `subtask-card.tsx` currentAction | `SubtaskCard.vue` currentAction | ✅ | Uses explainLastToolCallKey |
| 4.6 | FlipDisplay for action updates | `subtask-card.tsx` FlipDisplay | `SubtaskCard.vue` FlipDisplay | ✅ | :unique-key="currentAction" |

## 5. Artifact Preview (文件产物)

| # | Feature | DeerFlow Source | Numina Implementation | Status | Notes |
|---|---------|-----------------|----------------------|--------|-------|
| 5.1 | File list card with type icons | `artifact-file-list.tsx` Card | `ArtifactFileList.vue` Card | ✅ | Implemented |
| 5.2 | Full-screen preview popup | `artifact-file-detail.tsx` Popup | `ArtifactPreviewPopup.vue` Popup | ✅ | Implemented |
| 5.3 | Code preview with syntax highlighting | `artifact-file-detail.tsx` CodeBlock | `ArtifactPreviewPopup.vue` CodeBlock | ✅ | Implemented |
| 5.4 | HTML sandbox iframe | `artifact-file-detail.tsx` iframe sandbox | `ArtifactPreviewPopup.vue` html-iframe | ✅ | Implemented with sandbox |
| 5.5 | Image preview | `artifact-file-detail.tsx` img | `ArtifactPreviewPopup.vue` preview-image | ✅ | Implemented |
| 5.6 | NavBar with copy/download/open actions | `artifact-file-detail.tsx` NavBar | `ArtifactPreviewPopup.vue` NavBar | ✅ | Implemented |

## 6. Suggestions (追问建议)

| # | Feature | DeerFlow Source | Numina Implementation | Status | Notes |
|---|---------|-----------------|----------------------|--------|-------|
| 6.1 | Generate on streaming end | `input-box.tsx` useEffect streaming end | `useSuggestions.ts` watch phase | ✅ | Implemented |
| 6.2 | Stagger animation (60ms delay) | `suggestion.tsx` STAGGER_DELAY_MS = 60 | `Suggestions.vue` STAGGER_DELAY_MS = 60 | ✅ | Verified exact match |
| 6.3 | Click fills input (empty) or confirms (non-empty) | `suggestion.tsx` onClick | `useSuggestions.ts` handleSuggestionClick | ✅ | Implemented |
| 6.4 | Append/Replace dialog for non-empty input | `input-box.tsx` confirm dialog | `SuggestionConfirmDialog.vue` | ✅ | Implemented |
| 6.5 | Close button to hide suggestions | `suggestion.tsx` close-btn | `Suggestions.vue` close-btn | ✅ | Implemented |

## 7. InputBox Controls (输入控制)

| # | Feature | DeerFlow Source | Numina Implementation | Status | Notes |
|---|---------|-----------------|----------------------|--------|-------|
| 7.1 | Send button disabled on empty input | `input-box.tsx` disabled check | `AIChatInput.vue` submit-btn disabled | ✅ | Implemented |
| 7.2 | Stop button on streaming (red square) | `input-box.tsx` stop class | `AIChatInput.vue` submit-btn.stop | ✅ | Implemented |
| 7.3 | Ctrl+Enter to submit | `input-box.tsx` onKeyDown | `AIChatInput.vue` @keydown.enter.ctrl | ✅ | Implemented |
| 7.4 | Auto-grow textarea (max 120px) | `input-box.tsx` adjustHeight | `AIChatInput.vue` adjustHeight | ✅ | Implemented |

## 8. Stability & Recovery (稳定性)

| # | Feature | DeerFlow Source | Numina Implementation | Status | Notes |
|---|---------|-----------------|----------------------|--------|-------|
| 8.1 | Thread recovery on refresh | `useThread.ts` localStorage | `useAiChatStream.ts` reconnect | ⚠️ | Needs verification |
| 8.2 | URL binding after first send | `useThread.ts` history.pushState | `AIChatPage.vue` URL update | ⚠️ | Needs verification |
| 8.3 | Stop/cancel clean state | `input-box.tsx` abort handling | `useAiChatStream.ts` abort | ⚠️ | Needs verification |
| 8.4 | SSE error recovery | `stream_bridge/base.py` reconnect | `aiEventNormalizer.ts` reconnect | ⚠️ | Needs verification |

## 9. Tenant Security (租户安全)

| # | Feature | DeerFlow Source | Numina Implementation | Status | Notes |
|---|---------|-----------------|----------------------|--------|-------|
| 9.1 | Family ID in all requests | N/A (Numina specific) | `get_family_id` middleware | ✅ | Backend enforced |
| 9.2 | Model list filtered by tenant | N/A | `/api/v1/ai/models` family filter | ✅ | Backend implemented |
| 9.3 | Artifact ownership check | N/A | `get_session_by_id(session_id, family_id)` | ✅ | Backend enforced |
| 9.4 | Suggestions quota check | N/A | `check_quota(family_id, "suggestions")` | ✅ | Backend enforced |

## 10. Mobile 375px (移动端适配)

| # | Feature | DeerFlow Source | Numina Implementation | Status | Notes |
|---|---------|-----------------|----------------------|--------|-------|
| 10.1 | No horizontal scroll | DeerFlow mobile layout | CSS max-width constraints | ⚠️ | Needs browser verification |
| 10.2 | Safe area inset bottom | `env(safe-area-inset-bottom)` | CSS safe-area-bottom | ⚠️ | Needs browser verification |
| 10.3 | Touch targets min 44x44px | DeerFlow touch targets | CSS button min dimensions | ⚠️ | Needs browser verification |

---

## Verification Summary

| Category | ✅ Verified | ⚠️ Partial | ❌ Not Implemented |
|----------|------------|-----------|-------------------|
| Welcome State | 1 | 3 | 2 |
| Message Flow | 5 | 0 | 0 |
| ChainOfThought | 9 | 0 | 0 |
| SubtaskCard | 5 | 1 | 0 |
| Artifact Preview | 6 | 0 | 0 |
| Suggestions | 5 | 0 | 0 |
| InputBox Controls | 4 | 0 | 0 |
| Stability | 0 | 4 | 0 |
| Tenant Security | 4 | 0 | 0 |
| Mobile 375px | 0 | 3 | 0 |
| **Total** | **34** | **11** | **2** |

## Critical Gaps (P0/P1)

1. **1.5 Model selector not visible in welcome state** - DeerFlow shows model selector in welcome mode
2. **1.6 Mode selector (Flash/Thinking/Pro/Ultra) not implemented** - Core DeerFlow feature missing

## Browser Testing Required

Items marked ⚠️ require interactive browser testing:
- 1.1-1.4 Welcome state layout comparison
- 8.1-8.4 Stability features
- 10.1-10.3 Mobile 375px verification

---

## Verification Method

1. **Source Code Comparison**: Read DeerFlow source at `/Volumes/LexarSSDNQ790/geek_space/github/deer-flow-reference/frontend/src/`
2. **Visual Comparison**: Open both demos in Chrome, use DevTools to inspect DOM structure
3. **Interaction Testing**: Execute same flows in both demos, compare behavior

## Status Legend

- ✅ Verified and matches DeerFlow
- ⚠️ Partial match, needs adjustment
- ❌ Does not match, requires fix