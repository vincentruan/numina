# DeerFlow vs Numina AI Chat Feature Comparison Checklist

**Generated:** 2026-06-14
**DeerFlow Demo:** https://deerflow.tech/workspace/chats/fe3f7974-1bcb-4a01-a950-79673baafefd
**Numina Target:** `/ai/chat?agentId=100000000000005&newSession=1&source=system_default`

---

## 1. Welcome State (Initial Input Screen)

| Feature | DeerFlow | Numina | Status | Notes |
|---------|----------|--------|--------|-------|
| Hero title centered | "有什么想问的？" | ? | 🔍 | Need visual verification |
| Subtitle/引导 text | "输入问题，智能助手帮你..." | ? | 🔍 | Need visual verification |
| Input box centered | Large, centered textarea | ? | 🔍 | Need visual verification |
| Example questions | Clickable suggestion chips | ? | 🔍 | Need visual verification |
| Mode selector | Flash/Thinking/Pro/Ultra | ? | 🔍 | Check ModeSelector.vue |
| Model selector | Dropdown popup | ? | 🔍 | Check ModelSelectorPopup.vue |

## 2. Session State (Active Conversation)

### 2.1 User Message Display

| Feature | DeerFlow | Numina | Status | Notes |
|---------|----------|--------|--------|-------|
| Right-aligned bubble | ✅ Yes | ? | 🔍 | Check UserBubble.vue |
| Max-width 70% | ✅ Yes | ? | 🔍 | Mobile viewport |
| Safe-area padding | ✅ Yes | ? | 🔍 | env(safe-area-inset-*) |
| Attachments preview | ✅ Yes (cards above bubble) | ? | 🔍 | File upload feature |
| Send status indicator | ✅ (sending → sent) | ? | 🔍 | Optimistic update |

### 2.2 Assistant Message Display

| Feature | DeerFlow | Numina | Status | Notes |
|---------|----------|--------|--------|-------|
| Full-width, left-aligned | ✅ Yes | ? | 🔍 | Check layout |
| Markdown rendering | ✅ Yes (marked) | ✅ Yes | ✅ | MarkdownContent.vue |
| Code blocks highlighted | ✅ Yes | ? | 🔍 | CodeBlock.vue |
| Copy button | ✅ Yes (hover to show) | ? | 🔍 | CopyButton.vue |
| Feedback buttons | ✅ 👍👎 | ? | 🔍 | FeedbackButtons.vue |

### 2.3 Message Grouping (6-type)

| Type | DeerFlow Behavior | Numina Component | Status |
|------|-------------------|------------------|--------|
| `human` | Right-aligned bubble | UserBubble.vue | 🔍 |
| `assistant` | Full-width markdown | AssistantMessage.vue | 🔍 |
| `assistant:processing` | ChainOfThought (collapsible) | ChainOfThought.vue | 🔍 |
| `assistant:clarification` | "需要补充信息" card | ? | 🔍 |
| `assistant:present-files` | Text + file list cards | ArtifactFileList.vue | 🔍 |
| `assistant:subagent` | SubtaskCard (status + progress) | SubtaskCard.vue | 🔍 |

### 2.4 Tool Call Visualization

| Feature | DeerFlow | Numina | Status | Notes |
|---------|----------|--------|--------|-------|
| Collapsible history | ✅ "X more steps" button | ✅ Yes | 🔍 | ChainOfThought.vue |
| Last tool highlight | ✅ FlipDisplay animation | ✅ Yes | ✅ | FlipDisplay.vue |
| Tool-specific icons | ✅ (search, file, terminal) | ✅ Yes | ✅ | tool-icon-map.ts |
| Action explanation | ✅ "正在搜索/读取..." | ✅ Yes | ✅ | tool-explainer.ts |
| Result badge | ✅ success/error | ? | 🔍 | Badge component |
| Search results list | ✅ clickable URLs | ✅ Yes | ✅ | ChainOfThoughtSearchResults.vue |
| No raw JSON (default) | ✅ Hidden unless devMode | ✅ Yes | ✅ | devMode toggle |

### 2.5 Subagent/Subtask Display

| Feature | DeerFlow | Numina | Status | Notes |
|---------|----------|--------|--------|-------|
| Task card | ✅ Independent card | ✅ Yes | ✅ | SubtaskCard.vue |
| Status icon | ✅ Check/X/Loader | ✅ Yes | ✅ | Status icon mapping |
| Shimmer text | ✅ for in_progress | ✅ Yes | ✅ | ShimmerText.vue |
| Shine border | ✅ Animated border | ✅ Yes | ✅ | ShineBorder.vue |
| Auto-expand on start | ✅ Yes | ✅ Yes | ✅ | watch() immediate |
| Prompt display | ✅ Collapsible | ? | 🔍 | MarkdownContent inside |
| Token usage | ✅ Show total | ? | 🔍 | usage.total_tokens |

### 2.6 Artifact Display

| Feature | DeerFlow | Numina | Status | Notes |
|---------|----------|--------|--------|-------|
| Badge count | ✅ Number badge | ? | 🔍 | AiArtifactBadge.vue |
| Sheet/drawer | ✅ Bottom drawer | ? | 🔍 | AiArtifactSheet.vue |
| File list cards | ✅ Icon + name + kind | ✅ Yes | ✅ | ArtifactFileList.vue |
| Full-screen preview | ✅ Popup fullscreen | ✅ Yes | ✅ | ArtifactPreviewPopup.vue |
| Code preview | ✅ Highlighted | ✅ Yes | ✅ | CodeBlock.vue |
| Markdown preview | ✅ Rendered | ✅ Yes | ✅ | MarkdownContent.vue |
| HTML sandbox iframe | ✅ With sandbox attr | ✅ Yes | ✅ | iframe sandbox |
| Image preview | ✅ Direct display | ✅ Yes | ✅ | img tag |
| PDF preview | ✅ iframe or download | ✅ Yes | ✅ | iframe + download btn |
| Download button | ✅ NavBar action | ✅ Yes | ✅ | NavBar right action |
| Copy content | ✅ NavBar action | ✅ Yes | ✅ | Copy to clipboard |
| Open in new window | ✅ NavBar action | ✅ Yes | ✅ | window.open |

### 2.7 Follow-up Suggestions

| Feature | DeerFlow | Numina | Status | Notes |
|---------|----------|--------|--------|-------|
| Auto-generate on complete | ✅ Yes | ✅ Yes | ✅ | useSuggestions watch |
| 3 suggestions | ✅ Yes | ✅ Yes | ✅ | n=3 parameter |
| Above input box | ✅ Yes | ✅ Yes | ✅ | Suggestions.vue position |
| Stagger animation | ✅ Fade-in sequentially | ✅ Yes | ✅ | animation-delay |
| Click to send (empty) | ✅ Direct fill + send | ✅ Yes | ✅ | handleSuggestionClick |
| Click (non-empty) → confirm | ✅ Append/Replace dialog | ✅ Yes | ✅ | SuggestionConfirmDialog.vue |
| Hide button | ✅ X to close | ✅ Yes | ✅ | hideSuggestions() |
| Quota failure toast | ✅ "额度不足" | ? | 🔍 | Error handling |

---

## 3. Input Box Features

| Feature | DeerFlow | Numina | Status | Notes |
|---------|----------|--------|--------|-------|
| Auto-grow textarea | ✅ Yes | ? | 🔍 | Vant Field autosize |
| Empty → disabled send | ✅ Yes | ? | 🔍 | :disabled check |
| Streaming → stop button | ✅ Red square | ? | 🔍 | submit-btn.stop class |
| Welcome vs Chat mode | ✅ Different layouts | ? | 🔍 | isWelcomeMode prop |
| Sticky bottom (chat) | ✅ Yes | ? | 🔍 | position sticky |
| Safe-area bottom | ✅ env() | ? | 🔍 | padding calculation |

### 3.1 Mode Selector

| Mode | DeerFlow Icon | DeerFlow Color | Numina | Status |
|------|---------------|----------------|--------|--------|
| Flash | Zap | Yellow | ? | 🔍 |
| Thinking | Lightbulb | Blue | ? | 🔍 |
| Pro | GraduationCap | Purple | ? | 🔍 |
| Ultra | Rocket | Red | ? | 🔍 |

### 3.2 Model Selector

| Feature | DeerFlow | Numina | Status |
|---------|----------|--------|--------|
| Tenant-filtered list | ✅ Yes | ✅ Yes | ✅ |
| Capability tags | ✅ "思考" "视觉" | ? | 🔍 |
| Search filter | ✅ Yes | ? | 🔍 |
| Default model | ✅ Checked | ? | 🔍 |

---

## 4. Stability Features

| Feature | DeerFlow | Numina | Status | Notes |
|---------|----------|--------|--------|-------|
| Thread recovery after refresh | ✅ URL → state restore | ? | 🔍 | sessionId from query |
| URL binding on new thread | ✅ Push state | ? | 🔍 | router.push after send |
| Stop/cancel cleanup | ✅ No dirty content | ? | 🔍 | abortController |
| SSE reconnect | ✅ Last-Event-ID | ? | 🔍 | EventSource resume |
| Error state recovery | ✅ Toast + reset | ? | 🔍 | Error handling |
| Network failure UI | ✅ Offline indicator | ? | 🔍 | Network status |

---

## 5. Tenant Security

| Check | Implementation | Status |
|-------|---------------|--------|
| Family ID header | X-Family-Id on all requests | 🔍 |
| Session ownership | `_get_session_for_family()` | ✅ |
| Artifact path traversal | `.resolve().relative_to()` | ✅ |
| Model tenant filter | `/api/v1/ai/models` | ✅ |
| Suggestions quota | `check_quota(family_id)` | 🔍 |
| Cross-family 403/404 | AppError(ErrorCode.NOT_FOUND) | ✅ |

---

## 6. Mobile Responsiveness (375px)

| Element | DeerFlow | Numina | Status |
|---------|----------|--------|--------|
| No horizontal scroll | ✅ Yes | ? | 🔍 |
| User bubble max 85% | ✅ Yes | ? | 🔍 |
| Tool step font 12px | ✅ Yes | ? | 🔍 |
| Suggestion chip padding | ✅ 6px 12px | ? | 🔍 |
| Safe-area inset | ✅ Yes | ? | 🔍 |

---

## 7. Dark Mode (WCAG AA)

| Check | DeerFlow | Numina | Status |
|-------|----------|--------|--------|
| Primary text #f5f5f5 | ✅ Yes | ? | 🔍 |
| Secondary text alpha ≥ 0.55 | ✅ Yes | ? | 🔍 |
| Card bg rgba overlay | ✅ Yes | ? | 🔍 |
| No inline style colors | ✅ Yes | ? | 🔍 |

---

## Verification Status Legend

- ✅ Verified: Code exists and matches DeerFlow pattern
- 🔍 Needs Browser Test: Requires runtime verification
- ❌ Missing: Feature not implemented or diverges from DeerFlow
- ⚠️ Partial: Implemented but may need adjustment

---

## Next Steps

1. Run browser testing with Chrome DevTools
2. Compare each 🔍 item visually with DeerFlow demo
3. Update status based on actual runtime behavior
4. Run ce-code-review for code-level validation
5. Document any divergences and their rationale (tenant constraints)