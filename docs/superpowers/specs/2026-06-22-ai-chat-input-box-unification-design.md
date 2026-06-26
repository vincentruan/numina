# AI Chat Input Box Unification Design

## Goal

Merge the two AI chat input components (`AIChatInput.vue` used in AIHubPage, `InputBox.vue` used in AIChatPage) into a single unified component, aligned with DeerFlow's interaction framework and four-mode execution model.

## Background

Numina currently has two input components with overlapping but incompatible capabilities:

| Aspect | InputBox.vue (chat page) | AIChatInput.vue (hub page) |
|--------|-------------------------|---------------------------|
| Location | `components/ai-chat/` | `components/common/` |
| Lines | 525 | 898 |
| Mode | 4-mode DeerFlow (flash/thinking/pro/ultra) | 2-state (normal/smart) |
| Agent selection | Hardcoded van-popover | Emits event, parent handles action sheet |
| Model selector | Popup | None |
| Expand button | None | Full-screen textarea |
| Web search | None | Independent toggle |
| Slash palette | None | `/commands` popup |
| Attachment | None | Plus panel (camera/file/image) |
| Welcome mode | Hero + examples | None |
| Tenant resources | `useTenantAiResources` | None |
| Styling | Vant-aligned | Custom dark/light CSS vars |

## Design

### Component: Unified InputBox

**Location:** Replace `components/ai-chat/InputBox.vue` (the merged version)

**Base styling:** AIChatInput.vue style (custom CSS variables, gradient buttons, expand/attach)

**Removed:** Slash palette (`/commands`)

### Layout (bottom to top)

```
┌─────────────────────────────────────────────┐
│  Welcome hero (welcome mode only)            │
│  Welcome examples (welcome mode only)        │
├─────────────────────────────────────────────┤
│  [Agent icon]  [textarea...]  [↗ expand]    │
│                                             │
│  [Agent btn] [Mode] [WebSearch] [+] [Send]  │
└─────────────────────────────────────────────┘
```

### Bottom Toolbar (left to right)

1. **Agent button** — Leftmost
   - Welcome mode (no active thread): Clickable, opens agent picker (van-action-sheet, parent handles)
   - Chat mode (active thread): Static display of current agent's icon/logo only, no click action

2. **Mode selector** — Reuses `ModeSelector.vue` (4-mode: Flash/Thinking/Pro/Ultra)
   - Replaces the old 2-state deep think toggle
   - Maps to DeerFlow parameters: `thinking_enabled`, `is_plan_mode`, `subagent_enabled`

3. **Web search toggle** — Independent on/off switch
   - When on, injects web_search context into the backend request
   - Pre-checks that at least one search provider is configured

4. **Plus button** — Camera, file, image (same as current AIChatInput)
   - Popup panel positioned above

5. **Send/Stop button** — Rightmost
   - Send (arrow up icon) when idle
   - Stop (red square) when streaming

### Textarea Area

- Auto-height (default ~3 rows, grows to 120px)
- Expand button (top-right) toggles full-screen mode (75vh)
- Attachment preview row (above textarea, shown when attachments present)
- Ctrl+Enter to submit

### Props/Events

```typescript
interface Props {
  status: 'ready' | 'streaming' | 'submitted' | 'error' | 'reconnecting'
  isWelcomeMode?: boolean
  threadId?: string
  initialMode?: InputMode       // flash/thinking/pro/ultra
  initialModelName?: string
  agentId?: string              // current agent ID
  agents?: AgentOption[]        // available agents for picker
  agentIcon?: string            // current agent's icon/emoji
  agentLabel?: string           // current agent's display name
  disabled?: boolean
  webSearch?: boolean           // v-model
  modelValue?: string           // v-model
}

interface Emits {
  submit: [payload: SubmitPayload]
  stop: []
  'update:modelValue': [value: string]
  'update:webSearch': [value: boolean]
  selectAgent: []               // parent opens agent picker
  action: [type: 'file' | 'image' | 'camera']
  removeAttachment: [index: number]
}
```

### Data Flow

**Welcome mode → Chat page:**
1. User selects agent → parent sets query params
2. User submits text → parent navigates to `/ai/chat?agentId=X&q=...`
3. On arrival, AIChatPage creates thread and starts streaming

**Chat mode (active thread):**
1. User types → submits via same SubmitPayload interface
2. Payload includes: `text`, `mode` (flash/thinking/pro/ultra), `webSearch`, `agentId`
3. Backend maps mode to `thinking_enabled`, `is_plan_mode`, `subagent_enabled`

### Tenant Isolation

All tenant-aware config (models, subagent availability, web search) flows through `useTenantAiResources` composable which fetches from `/api/v1/ai/models` with `X-Family-Id` header. The component only presents what the tenant allows.

## Files to Modify

| File | Action | Description |
|------|--------|-------------|
| `components/ai-chat/InputBox.vue` | Replace | Merge AIChatInput features into this file with DeerFlow alignment |
| `components/common/AIChatInput.vue` | Delete (or keep as dead) | No longer used after unification |
| `components/ai/AIChatBox.vue` | Modify | Update InputBox usage to match new props/events |
| `components/ai/WelcomePage.vue` | Modify | Update InputBox usage |
| `pages/AIHubPage.vue` | Modify | Switch from AIChatInput to InputBox, update event handling |
| `pages/AIChatPage.vue` | No change | Already uses InputBox via AIChatBox |

## Key Design Decisions

1. **AIChatInput styling as base** — The custom dark/light theme with gradient buttons and expand feature is more polished and better suited for the hub entry point
2. **ModeSelector replaces deep think toggle** — Aligns with DeerFlow's four-mode model
3. **Agent picker owned by parent** — The component only emits `selectAgent`; parent shows the action sheet (same pattern as AIHubPage currently uses)
4. **No slash palette** — Removed to simplify and align with DeerFlow
5. **Welcome mode preserved** — InputBox already supports this; keep hero + examples
