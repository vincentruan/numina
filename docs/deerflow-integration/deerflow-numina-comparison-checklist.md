# DeerFlow vs Numina AI Chat Comparison Checklist

**Generated:** 2026-06-14
**DeerFlow Demo:** https://deerflow.tech/workspace/chats/fe3f7974-1bcb-4a01-a950-79673baafefd
**Numina Target:** `/ai/chat?agentId=100000000000005&newSession=1&source=system_default`

---

## 1. Welcome State (Initial Input Screen)

| Feature | DeerFlow | Numina | Status | Verification Notes |
|---------|----------|--------|--------|---------------------|
| Hero title centered | "有什么想问的？" | ✅ Implemented | ✅ | Check InputBox.vue welcome-hero section |
| Subtitle/引导 text | "输入问题，智能助手帮你..." | ✅ Implemented | ✅ | hero-subtitle in InputBox.vue |
| Input box centered | Large, centered textarea | ✅ Implemented | ✅ | welcome-mode class styling |
| Example questions | Clickable suggestion chips | ⚠️ Partial | 🔍 | SuggestionChips exist, need to verify initial display |
| Mode selector | Flash/Thinking/Pro/Ultra | ✅ Implemented | ✅ | ModeSelector.vue with 4 modes |
| Model selector | Dropdown popup | ✅ Implemented | ✅ | ModelSelectorPopup.vue |

---

## 2. Session State (Active Conversation)

### 2.1 User Message Display

| Feature | DeerFlow | Numina | Status | Verification Notes |
|---------|----------|--------|--------|---------------------|
| Right-aligned bubble | ✅ Yes | ✅ Implemented | ✅ | UserBubble.vue / MessageListItem.vue |
| Max-width 70% | ✅ Yes | ✅ Implemented | ✅ | CSS max-width: 70% in human-wrapper |
| Safe-area padding | ✅ Yes | ✅ Implemented | ✅ | env(safe-area-inset-*) used |
| Attachments preview | ✅ Yes (cards above bubble) | ⚠️ UI exists, onAction toast | 🔍 | Need to verify upload functionality |
| Send status indicator | ✅ (sending → sent) | ✅ Implemented | ✅ | sendStatus in message state |

### 2.2 Assistant Message Display

| Feature | DeerFlow | Numina | Status | Verification Notes |
|---------|----------|--------|--------|---------------------|
| Full-width, left-aligned | ✅ Yes | ✅ Implemented | ✅ | MessageListItem.vue assistant styling |
| Markdown rendering | ✅ Yes (marked) | ✅ Yes | ✅ | MarkdownContent.vue |
| Code blocks highlighted | ✅ Yes | ✅ Implemented | ✅ | CodeBlock.vue with prism |
| Copy button | ✅ Yes (hover to show) | ✅ Implemented | ✅ | CopyButton.vue |
| Feedback buttons | ✅ 👍👎 | ✅ Implemented | ✅ | FeedbackButtons.vue |

### 2.3 Message Grouping (6-type)

| Type | DeerFlow Behavior | Numina Component | Status |
|------|-------------------|------------------|--------|
| `human` | Right-aligned bubble | UserBubble/MessageListItem | ✅ |
| `assistant` | Full-width markdown | AssistantMessage/MessageListItem | ✅ |
| `assistant:processing` | ChainOfThought (collapsible) | ChainOfThought.vue | ✅ |
| `assistant:clarification` | "需要补充信息" card | MessageList.vue clarification-card | ✅ |
| `assistant:present-files` | Text + file list cards | ArtifactFileList.vue | ✅ |
| `assistant:subagent` | SubtaskCard (status + progress) | SubtaskCard.vue | ✅ |

### 2.4 Tool Call Visualization

| Feature | DeerFlow | Numina | Status |
|---------|----------|--------|--------|
| Collapsible history | ✅ "X more steps" button | ✅ Yes | ✅ |
| Last tool highlight | ✅ FlipDisplay animation | ✅ Yes | ✅ |
| Tool-specific icons | ✅ (search, file, terminal) | ✅ Yes | ✅ |
| Action explanation | ✅ "正在搜索/读取..." | ✅ Yes | ✅ |
| Search results list | ✅ clickable URLs | ✅ Yes | ✅ |
| No raw JSON (default) | ✅ Hidden unless devMode | ✅ Yes | ✅ |

### 2.5 Subagent/Subtask Display

| Feature | DeerFlow | Numina | Status |
|---------|----------|--------|--------|
| Task card | ✅ Independent card | ✅ Yes | ✅ |
| Status icon | ✅ Check/X/Loader | ✅ Yes | ✅ |
| Shimmer text | ✅ for in_progress | ✅ Yes | ✅ |
| Shine border | ✅ Animated border | ✅ Yes | ✅ |
| Auto-expand on start | ✅ Yes | ✅ Yes | ✅ |
| Token usage | ✅ Show total | ✅ Yes | ✅ |

### 2.6 Artifact Display

| Feature | DeerFlow | Numina | Status |
|---------|----------|--------|--------|
| File list cards | ✅ Icon + name + kind | ✅ Yes | ✅ |
| Full-screen preview | ✅ Popup fullscreen | ✅ Yes | ✅ |
| Code preview | ✅ Highlighted | ✅ Yes | ✅ |
| Markdown preview | ✅ Rendered | ✅ Yes | ✅ |
| HTML sandbox iframe | ✅ With sandbox attr | ✅ Yes | ✅ |
| Download button | ✅ NavBar action | ✅ Yes | ✅ |
| Copy content | ✅ NavBar action | ✅ Yes | ✅ |
| Open in new window | ✅ NavBar action | ✅ Yes | ✅ |

### 2.7 Follow-up Suggestions

| Feature | DeerFlow | Numina | Status |
|---------|----------|--------|--------|
| Auto-generate on complete | ✅ Yes | ✅ Yes | ✅ |
| 3 suggestions | ✅ Yes | ✅ Yes | ✅ |
| Above input box | ✅ Yes | ✅ Yes | ✅ |
| Stagger animation | ✅ Fade-in sequentially | ✅ Yes | ✅ |
| Click to send (empty) | ✅ Direct fill + send | ✅ Yes | ✅ |
| Click (non-empty) → confirm | ✅ Append/Replace dialog | ✅ Yes | ✅ |

---

## 3. Input Box Features

| Feature | DeerFlow | Numina | Status |
|---------|----------|--------|--------|
| Auto-grow textarea | ✅ Yes | ✅ Yes | ✅ |
| Empty → disabled send | ✅ Yes | ✅ Yes | ✅ |
| Streaming → stop button | ✅ Red square | ✅ Yes | ✅ |
| Welcome vs Chat mode | ✅ Different layouts | ✅ Yes | ✅ |
| Sticky bottom (chat) | ✅ Yes | ✅ Yes | ✅ |
| Safe-area bottom | ✅ env() | ✅ Yes | ✅ |

### 3.1 Mode Selector

| Mode | DeerFlow | Numina | Status |
|------|----------|--------|--------|
| Flash | Zap/Yellow | ✅ Implemented | ✅ |
| Thinking | Lightbulb/Blue | ✅ Implemented | ✅ |
| Pro | GraduationCap/Purple | ✅ Implemented | ✅ |
| Ultra | Rocket/Red | ✅ Implemented | ✅ |

---

## 4. Tenant Security

| Check | Implementation | Status |
|-------|---------------|--------|
| Family ID header | X-Family-Id on all requests | ✅ |
| Session ownership | `_get_session_for_family()` | ✅ |
| Artifact path traversal | `.resolve().relative_to()` | ✅ |
| Model tenant filter | `/api/v1/ai/models` | ✅ |
| Suggestions quota | `check_quota(family_id)` | ✅ |

---

## 5. API Endpoint Verification

| Endpoint | Purpose | Status |
|----------|---------|--------|
| `/api/v1/ai/models` | Tenant-filtered model list | ✅ |
| `/api/v1/ai/sessions/{id}/artifacts/{path}` | Artifact content | ✅ |
| `/api/v1/ai/sessions/{id}/suggestions` | Follow-up suggestions | ✅ |

---

## Fixed Issues (2026-06-14)

1. **P0 useSuggestions API URL**: Changed `/api/sessions/${threadId}/suggestions` → `/ai/sessions/${threadId}/suggestions`
2. **P0 Content-Disposition injection**: Added filename sanitization and quoting
3. **P1 ArtifactPreviewPopup URL**: Changed `/api/sessions/...` → use artifactContentUrl helper
4. **P1 ArtifactPreviewPopup familyId**: Changed localStorage → familyStore.currentFamily?.id

---

## Known Limitations

1. SSE reconnect with Last-Event-ID not fully implemented
2. Upload functionality backend integration pending
3. Pre-existing E501 line-too-long warnings in ai_chat.py

---

## Verification Status Legend

- ✅ Verified: Code exists and matches DeerFlow pattern
- 🔍 Needs Browser Test: Requires runtime verification
- ⚠️ Partial: Implemented but may need adjustment