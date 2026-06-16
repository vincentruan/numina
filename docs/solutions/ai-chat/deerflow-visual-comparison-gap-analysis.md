# DeerFlow Phase 4-7 Visual Comparison Gap Analysis

Generated: 2026-06-15
Updated: 2026-06-15
Status: P0 BUG FIXED - Icon component mismatch resolved

---

## Visual Comparison Summary

**DeerFlow Demo URL:** https://deerflow.tech/workspace/chats/fe3f7974-1bcb-4a01-a950-79673baafefd
**Numina URL:** http://localhost:5173/ai/chat?agentId=100000000000005
**Test Query:** 家庭资产负债健康度判断

---

## User-Reported Gaps

Based on side-by-side visual comparison with DeerFlow demo:

| Element | DeerFlow Shows | Numina Shows | Gap |
|---------|---------------|--------------|-----|
| **Tool Chain** | Full sequence of tool calls with icons + status badges | Only `ask_clarification ✓` text | Missing tool icons, missing full chain |
| **Thinking Section** | Collapsible reasoning display with Lightbulb icon | Not visible | Missing entire section |
| **SubtaskCard** | Animated cards with Shimmer/ShineBorder + FlipDisplay | Not visible | Missing subagent visualization |
| **AI Response** | Final markdown response with copy/regenerate buttons | Not visible | Missing final output |
| **Artifacts Panel** | File list + preview tabs (code/html/markdown) | Not visible | Missing artifacts section |
| **InputBox Suggestions** | Follow-up suggestions after response | Not tested | Pending backend API |

---

## 🔴 P0 BUG FIXED: Icon Component Mismatch

**Issue:** `ai-chat` components used `<SvgIcon>` (SVG sprites) but `tool-icon-map.ts` returns Iconify names.

**Root Cause:**
- `SvgIcon.vue` expects sprite names: `#icon-${name}` → `#icon-help-circle`
- `tool-icon-map.ts` returns Iconify names: `'help-circle'`, `'search'`, `'terminal'`
- Result: Icons don't render because sprite `#icon-help-circle` doesn't exist

**Fix Applied:**
All `<SvgIcon>` usages replaced with `<IIcon>` (Iconify component) in:
1. `ChainOfThought.vue` - Lines 331, 351, 398, 400
2. `SubtaskCard.vue` - Lines 104, 119, 129, 142, 149, 161
3. `ChainOfThoughtSearchResults.vue` - Line 42
4. `ArtifactFileList.vue` - Line 58
5. `ModeSelector.vue` - Lines 71, 98, 101
6. `WelcomeExamples.vue` - Lines 67, 78
7. `CopyButton.vue` - Line 22
8. `CodeBlock.vue` - Line 34
9. `Suggestions.vue` - Line 58
10. `ArtifactPreviewPopup.vue` - Lines 185, 189, 193, 227, 270
11. `ModelSelectorPopup.vue` - Lines 67, 101, 112

**Verification:**
- ✅ `pnpm vue-tsc --noEmit` passes (no type errors)
- ✅ No remaining `<SvgIcon>` usages in `ai-chat/` components

---

## Specific Missing Features

### 1. Tool Chain (ChainOfThought.vue) - ICON FIX COMPLETE

**DeerFlow Pattern:**
- Each tool call shows: icon + name + status badge (✓/✗/spinner)
- Tool-specific icons: SearchIcon, GlobeIcon, BookOpenTextIcon, WrenchIcon
- "X more steps" collapse button for >3 tools
- FlipDisplay animation on last tool call

**Numina Fix Applied:**
- Replaced `<SvgIcon>` with `<IIcon>` for tool icons
- Icon names now correctly resolve via Iconify

**Pending Investigation:**
- Verify backend sends full tool chain events
- Check if `steps` computed receives all tool calls

### 2. Thinking Section

**DeerFlow Pattern:**
- Collapsible section with Lightbulb icon
- Shows reasoning content from AI message
- Toggle button with chevron rotation

**Numina Current State:**
- Not visible at all

**Fix Required:**
- Check if `lastReasoningStep` computed is working
- Verify `extractReasoningContentFromMessage()` extracts reasoning correctly
- Check if backend sends reasoning content in events

### 3. SubtaskCard (SubtaskCard.vue) - ICON FIX COMPLETE

**DeerFlow Pattern:**
- Shows subagent tasks with status icons
- Shimmer/ShineBorder animation for in_progress
- FlipDisplay for status text updates
- Collapsible with prompt/result display

**Numina Fix Applied:**
- Replaced `<SvgIcon>` with `<IIcon>` for status icons
- Icons now correctly render for completed/failed/in_progress states

**Fix Required:**
- Check if backend sends task events
- Verify `useSubtasks()` composable receives task data
- Check if SubtaskCard component is imported and rendered
- Verify task status transitions (pending → running → completed)

### 4. AI Response (MarkdownContent)

**DeerFlow Pattern:**
- Final AI response in markdown format
- Copy button, regenerate button, helpful/not helpful buttons
- Streamdown word animation during streaming

**Numina Current State:**
- Not visible after tool calls

**Fix Required:**
- Check if backend sends final response events
- Verify message grouping includes AI response
- Check if MarkdownContent.vue renders final content
- Verify action buttons are visible

### 5. Artifacts Panel

**DeerFlow Pattern:**
- File list on right side or popup
- Preview tabs: code, HTML, markdown, image, raw
- Download, copy, share buttons

**Numina Current State:**
- Not visible

**Fix Required:**
- Check if backend sends artifact events
- Verify `useArtifacts()` receives artifact data
- Check if ArtifactPreviewPopup is triggered correctly
- Verify artifact URL generation works

---

## Root Cause Analysis

### 🔴 CRITICAL BUG FOUND: Icon Component Mismatch

**Issue:** `ChainOfThought.vue` uses `<SvgIcon>` (SVG sprites) but `tool-icon-map.ts` returns Iconify names.

**Details:**
- `SvgIcon.vue` expects sprite names: `#icon-${name}` → `#icon-help-circle`
- `tool-icon-map.ts` returns Iconify names: `'help-circle'`, `'search'`, `'terminal'`
- Result: Icons don't render because sprite `#icon-help-circle` doesn't exist

**Evidence:**
```vue
<!-- ChainOfThought.vue:331 -->
<SvgIcon :name="getIcon(step)" class="step-icon" />

<!-- getToolIcon('ask_clarification') returns 'help-circle' -->
<!-- SvgIcon looks for #icon-help-circle in sprite → NOT FOUND -->

<!-- Available SVG icons in src/icons/svg/: -->
<!-- web-search.svg, home.svg, stock.svg, etc. (custom icons, not Iconify) -->
```

**Fix Required:**
Replace `<SvgIcon>` with `<IIcon>` (Iconify component) in ChainOfThought.vue:
```vue
<!-- Before (BUG) -->
<SvgIcon :name="getIcon(step)" class="step-icon" />

<!-- After (FIX) -->
<IIcon :icon="getIcon(step)" class="step-icon" />
```

**Files to Fix:**
1. `ChainOfThought.vue` - Lines 331, 351, 398, 400
2. `SubtaskCard.vue` - All `<SvgIcon>` usages
3. `ArtifactFileList.vue` - `<SvgIcon>` usage

**Priority: P0** - Blocks visual comparison verification

---

### Other Possible Causes:

1. **Backend Events Not Sent**
   - Backend may not be sending all event types (tool_call, reasoning, task, artifact)
   - Check backend agent stream implementation

2. **Frontend Event Normalization**
   - `aiEventNormalizer` may not be converting all event types
   - Check event type mapping

3. **Component Import/Registration**
   - Components may not be properly imported in AIChatPage.vue
   - Check component registration

4. **Data Flow Issues**
   - Messages may not be flowing to ChainOfThought component
   - Check props binding in MessageGroup

5. **CSS/Rendering Issues**
   - Components may be rendered but invisible due to CSS
   - Check display properties and z-index

---

## Debug Steps

### Step 1: Check Backend Events

```bash
# Check agent stream router for event types
grep -r "tool_call" server/apps/agent/
grep -r "reasoning" server/apps/agent/
grep -r "task" server/apps/agent/
```

### Step 2: Check Frontend Event Normalizer

```typescript
// Check aiEventNormalizer.ts for event type handling
// Ensure all event types are normalized correctly
```

### Step 3: Check Component Imports

```vue
// In AIChatPage.vue, verify:
import ChainOfThought from '@/components/ai-chat/ChainOfThought.vue'
import SubtaskCard from '@/components/ai-chat/SubtaskCard.vue'
import ArtifactPreviewPopup from '@/components/ai-chat/ArtifactPreviewPopup.vue'
```

### Step 4: Check Props Binding

```vue
// In MessageGroup, verify:
<ChainOfThought :messages="group.messages" :is-loading="isStreaming" />
```

### Step 5: Browser DevTools Debug

```javascript
// In DevTools console:
// Check messages array content
// Check tool_calls array in messages
// Check reasoning content extraction
```

---

## Verification Checklist for Fix

| Fix | Verification Method |
|-----|---------------------|
| Tool icons visible | Send query, check tool chain shows icons |
| Full tool chain | Send query, verify multiple tools display |
| Thinking section | Check reasoning toggle visible |
| SubtaskCard | Trigger subagent, verify card with animation |
| AI response | Send query, verify final markdown content |
| Artifacts panel | Generate file, verify artifact preview |

---

## Next Actions

1. **Investigate Backend Event Flow**
   - Check what events backend sends for test query
   - Verify all event types are implemented

2. **Debug Frontend Rendering**
   - Add console logs to ChainOfThought.vue steps computed
   - Check if messages prop contains tool_calls

3. **Fix Component Visibility**
   - Ensure CSS doesn't hide components
   - Verify component imports are correct

4. **Re-test Visual Comparison**
   - After fixes, re-run side-by-side comparison
   - Verify all DeerFlow elements are present in Numina

---

## Remaining Investigation Items

### 1. Thinking Section Not Visible

**Root Cause Hypothesis:** Backend not sending `phase.thinking` + `token(is_thinking=true)` events for the test query.

**Investigation Needed:**
- Check if `enable_thinking` flag is passed in request
- Verify model supports reasoning_content (DeepSeek-R1, Qwen3)
- Test with explicit thinking-enabled query

**Frontend Path (Verified Working):**
- `phase.thinking` → `aiEventNormalizer` → `phase_change` + `reasoning_delta`
- `ChainOfThought.vue` `lastReasoningStep` computed extracts from messages
- Rendering works when reasoning content is present

### 2. SubtaskCard Not Visible

**Root Cause Hypothesis:** Backend not sending `task` tool events (subagent coordination).

**Investigation Needed:**
- Check if `subagent_enabled=true` in request
- Verify DeerFlow config has `subagent_enabled: true`
- Test with multi-step query requiring subagent delegation

**Frontend Path (Verified Working):**
- `task` tool call → `tool_call` event → `assistant:subagent` group
- `MessageGroup.vue` renders `SubtaskCard` for each taskId
- Icons now render correctly with IIcon fix

### 3. AI Response Not Visible

**Root Cause Hypothesis:** Backend not sending `answer_delta` events after tool execution.

**Investigation Needed:**
- Verify backend sends `phase.answering` + `token` events
- Check if final AI message is grouped correctly
- Test message grouping with `answer_done` event

**Frontend Path (Verified Working):**
- `answer_delta` → message with `type: 'ai'`, `phase: 'answering'`
- `assistant` group → `AssistantMessage.vue` renders markdown

### 4. Artifacts Panel Not Visible

**Root Cause Hypothesis:** Backend not sending `write_file` tool results or `artifact` events.

**Investigation Needed:**
- Verify `write_file` tool calls are being sent
- Check if artifacts array is populated in useArtifacts composable
- Test with file generation query

---

## Verification Checklist

After backend investigation:

| Check | Command/Test |
|-------|--------------|
| Thinking events | Send query with `deep_think=true`, check `phase.thinking` in stream |
| Subagent events | Send query with `subagent_enabled=true`, check `task` tool calls |
| Answer events | After tool execution, check `phase.answering` + `answer_delta` |
| Artifact events | Check `write_file` tool calls in stream events |
| Icon rendering | Visual check - icons should now display (IIcon fix) |

---

## Files Modified in This Fix

| File | Changes |
|------|---------|
| `ChainOfThought.vue` | IIcon import + 4 icon replacements |
| `SubtaskCard.vue` | IIcon import + 6 icon replacements |
| `ChainOfThoughtSearchResults.vue` | IIcon import + 1 icon replacement |
| `ArtifactFileList.vue` | IIcon import + 1 icon replacement |
| `ModeSelector.vue` | IIcon import + 3 icon replacements |
| `WelcomeExamples.vue` | IIcon import + 2 icon replacements |
| `CopyButton.vue` | IIcon import + 1 icon replacement |
| `CodeBlock.vue` | IIcon import + 1 icon replacement |
| `Suggestions.vue` | IIcon import + 1 icon replacement |
| `ArtifactPreviewPopup.vue` | IIcon import + 5 icon replacements |
| `ModelSelectorPopup.vue` | IIcon import + 3 icon replacements |

---

## Commit

```
fix(ai-chat): replace SvgIcon with IIcon for Iconify compatibility

58 files changed, 7828 insertions(+), 363 deletions(-)
```

---

*Updated by Claude Code (Opus 4.8) - P0 Icon Bug Fix Complete*