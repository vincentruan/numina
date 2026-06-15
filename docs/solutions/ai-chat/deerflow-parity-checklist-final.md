# DeerFlow Interaction Parity Checklist

Generated: 2026-06-15
Purpose: Final verification of Numina AI Chat against DeerFlow demo interaction patterns

## Demo Reference
- DeerFlow Demo URL: https://deerflow.tech/workspace/chats/fe3f7974-1bcb-4a01-a950-79673baafefd
- DeerFlow Source: /Volumes/LexarSSDNQ790/geek_space/github/deer-flow-reference

---

## 1. Welcome State (欢迎态)

| Feature | DeerFlow | Numina | Status | Notes |
|---------|----------|--------|--------|-------|
| Centered input box | Hero section with centered textarea | `WelcomeExamples.vue` + `InputBox.vue` welcome-mode | 🔍 Verify | Need browser test |
| Example questions | Quick-start suggestion cards | `WelcomeExamples.vue` with preset questions | 🔍 Verify | Need browser test |
| Hero title | "有什么想问的？" | Should match DeerFlow styling | 🔍 Verify | Need browser test |
| Model selector visible | Model dropdown in input area | `ModelSelectorPopup.vue` | 🔍 Verify | Need browser test |
| Mode selector visible | Flash/Thinking/Pro/Ultra buttons | `ModeSelector.vue` | 🔍 Verify | Need browser test |

---

## 2. Message Grouping (消息分组)

| Feature | DeerFlow | Numina | Status | Notes |
|---------|----------|--------|--------|-------|
| HumanMessageGroup | Right-aligned bubble, max 70% width | `MessageGroup.vue` type='human' | 🔍 Verify | Need browser test |
| AssistantMessageGroup | Left-aligned full-width, markdown | `MessageGroup.vue` type='assistant' | 🔍 Verify | Need browser test |
| AssistantProcessingGroup | Tool calls merged, collapsible | `ChainOfThought.vue` | 🔍 Verify | Need browser test |
| AssistantSubagentGroup | Task cards with status | `SubtaskCard.vue` | 🔍 Verify | Need browser test |
| AssistantPresentFilesGroup | File list with preview | `ArtifactFileList.vue` | 🔍 Verify | Need browser test |
| AssistantClarificationGroup | "需要补充信息" card | Clarification card in MessageList | 🔍 Verify | Need browser test |

---

## 3. Chain of Thought (思考链)

| Feature | DeerFlow | Numina | Status | Notes |
|---------|----------|--------|--------|-------|
| Collapsible history | "X more steps" button | `ChainOfThought.vue` expand-btn | 🔍 Verify | Need browser test |
| Tool-specific icons | web_search=search, bash=terminal | `tool-icon-map.ts` | 🔍 Verify | Need browser test |
| Current step highlight | FlipDisplay animation, left border | `FlipDisplay.vue` | 🔍 Verify | Need browser test |
| Reasoning section | "思考" collapsible with lightbulb icon | `ChainOfThought.vue` thinking-btn | 🔍 Verify | Need browser test |
| Status badges | success/error/running badges | Badge component in ChainOfThoughtStep | 🔍 Verify | Need browser test |
| No raw JSON display | Action text only, not parameters | `ChainOfThoughtStep.vue` actionText | 🔍 Verify | Need browser test |

---

## 4. Subtask Card (子任务卡片)

| Feature | DeerFlow | Numina | Status | Notes |
|---------|----------|--------|--------|-------|
| Status icon | CheckCircle/XCircle/Loader | statusIcon computed in SubtaskCard | 🔍 Verify | Need browser test |
| ShimmerText effect | Gradient shimmer for in_progress | `ShimmerText.vue` | 🔍 Verify | Need browser test |
| ShineBorder animation | Animated border colors | `ShineBorder.vue` | 🔍 Verify | Need browser test |
| Auto-expand on start | Collapsed by default, expand when running | watch(task) in SubtaskCard | 🔍 Verify | Need browser test |
| Progress message | Current action from latestMessage | currentAction computed | 🔍 Verify | Need browser test |
| Token usage display | Show total_tokens | usage-section in SubtaskCard | 🔍 Verify | Need browser test |

---

## 5. Artifact Preview (文件预览)

| Feature | DeerFlow | Numina | Status | Notes |
|---------|----------|--------|--------|-------|
| Full-screen popup | Vant Popup fullscreen | `ArtifactPreviewPopup.vue` | 🔍 Verify | Need browser test |
| NavBar with actions | Back, Copy, Download, Open New | NavBar in ArtifactPreviewPopup | 🔍 Verify | Need browser test |
| Code preview mode | CodeBlock with syntax highlighting | `CodeBlock.vue` | 🔍 Verify | Need browser test |
| Markdown preview | MarkdownContent rendering | `MarkdownContent.vue` | 🔍 Verify | Need browser test |
| HTML sandbox iframe | sandbox="allow-scripts allow-forms" | iframe with srcdoc | 🔍 Verify | Need browser test |
| Image preview | Direct img display | image-preview section | 🔍 Verify | Need browser test |
| PDF preview | iframe or download fallback | pdf-preview section | 🔍 Verify | Need browser test |
| URL encoding | encodeURIComponent for filepath | `artifactUrl.ts` | 🔍 Verify | Need browser test |

---

## 6. Tool Call Visualization (工具调用可视化)

| Feature | DeerFlow | Numina | Status | Notes |
|---------|----------|--------|--------|-------|
| Action explanation | "正在搜索: query" not raw JSON | `explainToolCall()` in tool-icon-map.ts | 🔍 Verify | Need browser test |
| Tool icon per type | search, file-text, terminal, etc. | `TOOL_ICON_MAP` in tool-icon-map.ts | 🔍 Verify | Need browser test |
| Search results list | Clickable result links | `ChainOfThoughtSearchResults.vue` | 🔍 Verify | Need browser test |
| Error display | Red border + error message | step-error in ChainOfThoughtStep | 🔍 Verify | Need browser test |
| File path display | Simple path text | filePath computed in ChainOfThoughtStep | 🔍 Verify | Need browser test |
| Dev mode toggle | Optional raw JSON for debugging | devMode prop in ChainOfThoughtStep | 🔍 Verify | Need browser test |

---

## 7. Suggestions (追问建议)

| Feature | DeerFlow | Numina | Status | Notes |
|---------|----------|--------|--------|-------|
| Auto-generate on complete | Streaming end triggers request | `useSuggestions.ts` watch(phase) | 🔍 Verify | Need browser test |
| Stagger animation | Buttons fade-in sequentially | animationDelay in SuggestionChip | 🔍 Verify | Need browser test |
| Empty input click | Direct fill and send | handleSuggestionClick() | 🔍 Verify | Need browser test |
| Non-empty input click | Confirm dialog with append/replace options | `SuggestionConfirmDialog.vue` | 🔍 Verify | Need browser test |
| Append and send | Original + newline + suggestion | confirmAppendAndSend() | 🔍 Verify | Need browser test |
| Replace and send | Clear and fill suggestion | confirmReplaceAndSend() | 🔍 Verify | Need browser test |
| Hide button | X button to dismiss | close-btn in Suggestions.vue | 🔍 Verify | Need browser test |

---

## 8. Input Box (输入框)

| Feature | DeerFlow | Numina | Status | Notes |
|---------|----------|--------|--------|-------|
| Auto-resize textarea | Max-height 120px | adjustHeight() in InputBox.vue | 🔍 Verify | Need browser test |
| Stop button | Red square when streaming | submit-btn.stop style | 🔍 Verify | Need browser test |
| Mode selector | Flash/Thinking/Pro/Ultra popup | `ModeSelector.vue` | 🔍 Verify | Need browser test |
| Model selector | Popup with tenant-filtered models | `ModelSelectorPopup.vue` | 🔍 Verify | Need browser test |
| Ultra disabled check | Tenant subagent check | isUltraDisabled computed | 🔍 Verify | Need browser test |
| Mode downgrade toast | Auto-switch when model doesn't support | showToast on mode downgrade | 🔍 Verify | Need browser test |

---

## 9. Stability & Recovery (稳定性)

| Feature | DeerFlow | Numina | Status | Notes |
|---------|----------|--------|--------|-------|
| Thread persistence | URL query sessionId | route.query.sessionId in AIChatPage | 🔍 Verify | Need browser test |
| Stop/cancel clean | No dirty content after abort | abort() in useAiChatStream | 🔍 Verify | Need browser test |
| SSE reconnect | Network recovery handling | reconnect handling in useAiChatStream | 🔍 Verify | Need browser test |
| Error state recovery | UI reset on backend error | error handling in stream | 🔍 Verify | Need browser test |

---

## 10. Mobile Responsiveness (移动端响应式)

| Feature | DeerFlow | Numina | Status | Notes |
|---------|----------|--------|--------|-------|
| 375px width | No horizontal scroll | @media (max-width: 375px) styles | 🔍 Verify | Need browser test |
| Safe area inset | env(safe-area-inset-bottom) | padding-bottom calc in styles | 🔍 Verify | Need browser test |
| Touch-friendly buttons | Adequate tap targets | Button sizes in 375px breakpoint | 🔍 Verify | Need browser test |

---

## 11. Tenant Security (租户安全)

| Feature | DeerFlow | Numina | Status | Notes |
|---------|----------|--------|--------|-------|
| Model filtering | Family-filtered model list | `/api/v1/ai/models` endpoint | 🔍 Verify | Backend test |
| Subagent permission | Ultra mode disabled if not allowed | supportsSubagent check | 🔍 Verify | Backend test |
| Artifact ownership | 403/404 for cross-family access | session ownership check | 🔍 Verify | Backend test |
| Thread ownership | 404 for invalid sessionId | get_session family_id filter | 🔍 Verify | Backend test |

---

## Verification Procedure

### Step 1: Browser Testing
1. Restart frontend dev server: `pnpm dev`
2. Restart backend servers: `uvicorn apps.backend`, `uvicorn apps.agent`
3. Login as demouser
4. Navigate to "数鸣"智能体
5. Test each feature with Chrome DevTools screenshots

### Step 2: DeerFlow Demo Comparison
1. Open DeerFlow demo URL in parallel tab
2. Compare visual appearance and interaction patterns
3. Document any discrepancies

### Step 3: Code Review
1. Run ce-code-review for implementation vs plan check
2. Compare Numina implementation with DeerFlow source code
3. Verify component reuse vs "re-inventing the wheel"

---

## Status Legend
- ✅ Verified - Confirmed working
- 🔍 Verify - Needs browser testing
- ❌ Issue - Discrepancy found
- ⏳ Pending - Not yet tested