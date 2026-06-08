---
title: feat: Agent Execution Canvas for AI Chat UI
type: feat
status: active
date: 2026-06-08
origin: docs/superpowers/specs/2026-06-08-agent-execution-canvas-design.md
---

# feat: Agent Execution Canvas for AI Chat UI

## Summary

Implement full-width "execution canvas" for AI chat UI when running long tasks (≥3 steps, deep think, or report generation). Extends existing `AiProcessBlock.vue` and `AiStepBlock.vue` components rather than creating parallel implementations. Backend-side sensitive data redaction required before frontend masking. Chinese tool summaries via `aiStepSummary.ts`. Mobile responsive strategy and ARIA accessibility defined upfront per review findings.

---

## Problem Frame

Current AI chat UI treats all agent responses uniformly in narrow bubble width, causing visual mismatch for complex multi-step tasks. Users see raw technical tool names and sensitive data may be exposed via HTTP/logs before frontend can mask. Interrupted sessions show only final state without execution trajectory. Mobile screens lack responsive treatment for canvas display.

---

## Requirements

- R1. Auto-detect long-running tasks and switch to full-width "execution canvas" display
- R2. Transform technical tool names into user-friendly Chinese summaries
- R3. Provide collapsible detail panels with sensitive data redaction
- R4. Handle interrupted sessions with execution progress indicator
- R5. Maintain backward compatibility with existing chat sessions
- R6. Backend-side redaction before streaming (addresses P1 security finding)
- R7. Mobile responsive strategy for 320-428px screens with 44×44px touch targets
- R8. ARIA accessibility: roles, labels, keyboard navigation for all interactive elements

---

## Scope Boundaries

**Explicitly out of scope:**
- Not changing backend orchestrator logic (DeerFlow stays unchanged)
- Not modifying JSONL session journal format
- Not adding new API endpoints (all data already available in stream events)
- Not replacing existing component architecture (build on top of current components)

### Deferred to Follow-Up Work

- Phase 2 backend changes (optional category field in stream_events.py): separate PR after frontend validation
- Child app (`frontend/apps/child`) i18n sync: evaluate after main app implementation
- Virtualization for >20 steps: performance optimization deferred until real-world usage data

---

## Context & Research

### Relevant Code and Patterns

- `frontend/apps/main/src/pages/AIChatPage.vue` — main chat page, wraps `AiProcessBlock`
- `frontend/apps/main/src/components/ai/AiProcessBlock.vue` — process container, `stepProps()` mapping
- `frontend/apps/main/src/components/ai/AiStepBlock.vue` (688 lines) — step renderer with displayName/icon/status handling, collapsible patterns, ARIA roles
- `frontend/apps/main/src/utils/aiEventNormalizer.ts` — event normalization, maintains `steps[]` array
- `frontend/apps/main/src/utils/toolDisplayMapping.ts` — `getToolDisplayInfo()` with backend displayName precedence
- `frontend/apps/main/src/composables/useStepCollapse.ts` — collapse logic with auto-collapse signal
- `frontend/apps/main/src/types/agent-stream.ts` — `ProcessStep` union type (5 variants)
- `server/apps/agent/services/stream_events.py` — SSE event streaming, `tool_call()` with display_name/icon/tool_type

### Institutional Learnings

- MCP SSE requires per-call DB sessions (`with SessionLocal() as db:`), never FastAPI DI
- Freeze tenant identity (`family_id`) at SSE handshake, never from tool arguments (security)
- localStorage: module-level singleton pattern (`ref` + `watchEffect`) with namespace keys (`canvas:preference`)
- Vant 4: use `:model-value` (not `:value`) for reactive field bindings
- CSS: avoid inline `style` for theme-dependent elements; use CSS classes with `[data-theme]` selectors
- Touch targets: 44×44px minimum; use negative margin trick for visual collapse while preserving tap area

### Existing Patterns to Follow

- `AiStepBlock.vue` collapsible pattern: `canCollapse` computed, `aria-expanded/controls`, `@keydown.enter/space`
- Mobile responsive: `@media (max-width: 768px)` with reduced padding/gaps
- ARIA: `role="listitem"` for container, `role="button"` + `tabindex="0"` for clickable headers
- Focus-visible: `outline: 2px solid var(--van-primary-color)` on focus
- Reduced motion: `@media (prefers-reduced-motion: reduce)` disables animations

---

## Key Technical Decisions

- **Backend-side redaction required**: Sensitive data must be redacted in `stream_events.py` before streaming; frontend `aiEventRedactor.ts` is defense-in-depth only (resolves P1 #1 from review)
- **Extend existing components**: Modify `AiStepBlock.vue` with new slots/props rather than creating `AiStepSummary.vue` and `AiStepDetail.vue` as parallel components (resolves P2 #7 from review)
- **Chinese summary only**: `aiStepSummary.ts` provides Chinese UX transformation on top of backend `display_name`, not duplicating category mapping (backend already provides `tool_type`)
- **LocalStorage namespace**: Use `canvas:collapse-preference` key following module-level singleton pattern
- **Mobile drawer pattern**: `AiStepDetail` content slides in as `van-popup` drawer on mobile (≤428px), inline expand on tablet/desktop

---

## Open Questions

### Resolved During Planning

- Duplicate components vs extend existing: Resolved — extend `AiStepBlock.vue` per review finding
- Backend vs frontend redaction: Resolved — backend required per P1 security finding
- Chinese mapping scope: Resolved — UX transformation only, backend provides category

### Deferred to Implementation

- Exact merge debounce timing: Real-time with 100ms debounce (tunable post-launch)
- Resume button trigger conditions: Depends on backend session resume capability (document during implementation)
- Depth threshold rationale: Document rationale for depth=5 in redaction logic

---

## Implementation Units

### U1. Backend-side Sensitive Data Redaction

**Goal:** Redact sensitive fields in `stream_events.py` before streaming to frontend, preventing HTTP/log exposure.

**Requirements:** R6

**Dependencies:** None (Phase A foundation)

**Files:**
- Modify: `server/apps/agent/services/stream_events.py`
- Modify: `server/apps/agent/services/orchestrator.py`
- Test: `server/apps/agent/tests/test_stream_events.py`

**Approach:**
- Add `SENSITIVE_KEYS` list (api_key, password, token, secret, credential, private) at module level
- Create `redact_sensitive_fields(args: dict)` helper function with exact case-insensitive matching + known-safe whitelist
- Apply redaction in `tool_call()` before yielding event: `arguments = redact_sensitive_fields(arguments)`
- Add audit logging when redaction occurs (optional, for debugging)

**Patterns to follow:**
- Security patterns from `docs/solutions/best-practices/security-protection.md`
- Per-call DB session pattern (but redaction is pure function, no DB needed)

**Test scenarios:**
- Happy path: Tool with non-sensitive args streams unmodified
- Edge case: Tool with `api_key` field → value replaced with `***REDACTED***`
- Edge case: Tool with nested `config.secret` → nested value redacted
- Edge case: Tool with `keyboard` field (false positive prevention) → not redacted
- Error path: Tool with `data` key (ambiguous) → check whitelist behavior

**Verification:**
- Curl streaming endpoint, verify sensitive fields masked in raw SSE output
- Backend logs show no raw sensitive values

---

### U2. Frontend Defense-in-Depth Redaction

**Goal:** Add frontend `aiEventRedactor.ts` as secondary redaction layer for defense-in-depth.

**Requirements:** R3, R6

**Dependencies:** U1

**Files:**
- Create: `frontend/apps/main/src/utils/aiEventRedactor.ts`

**Approach:**
- Create `redactSensitiveFields(obj, depth = 0)` function mirroring backend logic
- Use exact case-insensitive matching + whitelist (same list as backend)
- Add depth limit (5) to prevent deep recursion
- Apply in `AiStepBlock.vue` detail panel rendering (U5)

**Patterns to follow:**
- Pure utility function pattern from existing `utils/`
- Depth-limited recursion pattern

**Test scenarios:**
- Happy path: Object with non-sensitive fields → unchanged
- Edge case: Object with `password` field → `***REDACTED***`
- Edge case: Nested object with `secret` → nested value redacted
- Edge case: Deep nesting (>5 levels) → `{ _truncated: '...' }`

**Verification:**
- Unit tests pass for all edge cases
- Console inspection shows no raw sensitive values in ProcessStep objects

---

### U3. AgentRunCanvas Full-Width Container

**Goal:** Create full-width wrapper component that conditionally wraps `AiProcessBlock` for long tasks.

**Requirements:** R1

**Dependencies:** None

**Files:**
- Create: `frontend/apps/main/src/components/ai/AgentRunCanvas.vue`
- Modify: `frontend/apps/main/src/pages/AIChatPage.vue`

**Approach:**
- `AgentRunCanvas.vue`: Wrapper with `max-width: 100%` (vs 720px bubble), receives `steps` prop
- Transition state: Show skeleton/loading during first 1-2 steps before detection
- Smooth transition: CSS transition for bubble→canvas (0.3s fade/slide)
- `AIChatPage.vue`: Add `isLongTask` detection, wrap `AiProcessBlock` in `AgentRunCanvas` when true

**Execution note:** Add characterization test for existing bubble width before modifying `AIChatPage.vue`

**Patterns to follow:**
- Wrapper component pattern from existing container components
- CSS transition pattern from `AiStepBlock.vue` (max-height transition)

**Test scenarios:**
- Happy path: Short Q&A (1-2 steps) → remains in bubble width
- Happy path: Long task (≥3 steps) → transitions to full-width canvas
- Edge case: Deep think session → immediately full-width (no transition delay)
- Integration: Canvas appears before first step (loading/skeleton state)

**Verification:**
- Visual inspection: bubble→canvas transition smooth on real session
- Short Q&A still renders in narrow bubble

---

### U4. AgentRunHeader Task Summary Header

**Goal:** Create header component showing task status, elapsed time, model info, and collapse toggle.

**Requirements:** R1

**Dependencies:** U3

**Files:**
- Create: `frontend/apps/main/src/components/ai/AgentRunHeader.vue`

**Approach:**
- Props: `status`, `elapsedMs`, `modelName`, `canCollapse`
- Status badge: `执行中` / `已完成` / `执行中断` (for interrupted sessions)
- Collapse toggle button: 44×44px touch target, aria-expanded/controls
- Model info display: compact text with model name

**Patterns to follow:**
- Header component pattern from existing `AiProcessBlock.vue` header
- ARIA `role="button"` + `tabindex="0"` + `@keydown.enter/space`
- 44×44px touch target with negative margin trick

**Test scenarios:**
- Happy path: Running task → status badge shows `执行中`
- Happy path: Completed task → status badge shows `已完成`
- Edge case: Interrupted session → status badge shows `执行中断` with gray styling
- Integration: Collapse toggle → aria-expanded toggles, canvas collapses

**Verification:**
- Visual inspection: header renders correctly for all states
- Keyboard: Enter/Space toggles collapse

---

### U5. Extend AiStepBlock with Summary/Detail Slots

**Goal:** Extend existing `AiStepBlock.vue` with summary display and collapsible detail panel, avoiding parallel component creation.

**Requirements:** R2, R3, R7, R8

**Dependencies:** U2

**Files:**
- Modify: `frontend/apps/main/src/components/ai/AiStepBlock.vue`
- Modify: `frontend/apps/main/src/i18n/locales/zh-CN.ts`

**Approach:**
- Add new props: `summaryText` (Chinese display), `showDetail` (toggle for detail panel)
- Add computed: `chineseSummary` from `summaryText` prop or fallback to `displayName`
- Add slot: `detail-panel` for redacted args display
- Detail panel: Collapsible section showing redacted args, timestamp, error message
- Mobile: On ≤428px, detail panel opens as `van-popup` drawer; on tablet/desktop, inline expand

**Execution note:** Preserve existing behavior for reasoning/tool_call/artifact types; add enhancement only when `summaryText` provided

**Patterns to follow:**
- Existing `AiStepBlock.vue` collapsible pattern
- `van-popup` drawer pattern for mobile (from Vant patterns)
- ARIA: `aria-expanded` + `aria-controls` for detail panel

**Test scenarios:**
- Happy path: Tool with `summaryText` → displays Chinese summary
- Happy path: Tool without `summaryText` → falls back to `displayName`
- Edge case: User clicks "详情" → detail panel expands with redacted args
- Edge case: Error step → detail panel shows error message + suggested action
- Integration: Mobile (428px) → detail opens as drawer; tablet → inline expand

**Verification:**
- Existing `AiStepBlock` tests pass (backward compatibility)
- Visual: Chinese summary displays correctly
- Keyboard: Enter/Space opens detail panel

---

### U6. Chinese Summary Mapping (aiStepSummary.ts)

**Goal:** Create utility for tool name → Chinese summary transformation (UX layer only, not category mapping).

**Requirements:** R2

**Dependencies:** None

**Files:**
- Create: `frontend/apps/main/src/utils/aiStepSummary.ts`
- Modify: `frontend/apps/main/src/i18n/locales/zh-CN.ts`

**Approach:**
- Map tool names to Chinese summaries: `get_asset_allocation` → `获取资产配置`, `calculate_trend` → `计算趋势`
- Use backend `display_name` as fallback when no mapping exists
- Add i18n keys for all summaries under `aiStepSummary` namespace
- Keep mapping focused: Chinese UX transformation only, category logic from backend `tool_type`

**Patterns to follow:**
- Utility mapping pattern from `toolDisplayMapping.ts`
- i18n namespace pattern from existing `aiProcess` namespace

**Test scenarios:**
- Happy path: Known tool → returns Chinese summary
- Edge case: Unknown tool → falls back to backend `displayName`
- Edge case: Tool with no `displayName` → falls back to raw `name`

**Verification:**
- Unit tests cover known/unknown/fallback cases
- i18n keys exist for all mapped tools

---

### U7. Merge Strategy Implementation

**Goal:** Merge consecutive same-category steps into single summary line with expandable history.

**Requirements:** R2

**Dependencies:** U6

**Files:**
- Modify: `frontend/apps/main/src/utils/aiStepSummary.ts`
- Modify: `frontend/apps/main/src/components/ai/AiStepBlock.vue`

**Approach:**
- Add `mergeConsecutiveSteps(steps)` function: groups by `toolType`, returns merged summary items
- Merged display: "计算分析 (3次)" with expand button
- Expand shows: individual tool calls with timestamps
- Edge cases: zero steps → empty; single step → no merge; empty category → fallback to raw name

**Patterns to follow:**
- Grouping utility pattern
- Existing expand/collapse pattern from `AiStepBlock.vue`

**Test scenarios:**
- Happy path: 3 consecutive `calculation` tools → merged as "计算分析 (3次)"
- Edge case: 1 step → no merge, displays normally
- Edge case: Mixed categories (data_query → calculation) → no merge, separate displays
- Edge case: Tool with no `toolType` → displays as raw name

**Verification:**
- Visual: Merged summary displays correctly
- Expand: Individual calls show with timestamps

---

### U8. Long Task Detection Logic

**Goal:** Implement `isLongTask()` detection in `AIChatPage.vue` with configurable thresholds.

**Requirements:** R1

**Dependencies:** U3

**Files:**
- Modify: `frontend/apps/main/src/pages/AIChatPage.vue`
- Create: `frontend/apps/main/src/utils/aiTaskDetection.ts`

**Approach:**
- Detection criteria: `hasDeepThink` OR `steps.length >= 3` OR `generate_report` OR `web_search > 3 results`
- Expose thresholds as configurable constants (for tuning)
- Show loading state during detection (first 1-2 steps)
- Transition animation: 0.3s fade/slide when switching to canvas

**Patterns to follow:**
- Computed detection pattern from existing `AIChatPage.vue`
- CSS transition pattern

**Test scenarios:**
- Happy path: 3 steps → triggers canvas
- Happy path: Deep think → immediately triggers canvas
- Edge case: 2 steps → remains bubble
- Edge case: `generate_report` → triggers canvas regardless of step count

**Verification:**
- Detection triggers correctly for all criteria
- Transition animation smooth

---

### U9. localStorage User Preference Persistence

**Goal:** Store canvas collapse preference in localStorage with proper cleanup strategy.

**Requirements:** R1

**Dependencies:** U3, U4

**Files:**
- Create: `frontend/apps/main/src/utils/canvasPreference.ts`
- Modify: `frontend/apps/main/src/components/ai/AgentRunCanvas.vue`

**Approach:**
- Module-level singleton: `ref` + `watchEffect` at module scope (pattern from vue3-i18n-locale-switching)
- Namespace key: `canvas:collapse-preference` (avoid cross-app collision)
- Read/write: automatic persistence via `watchEffect`
- Cleanup: add `clearCanvasPreference()` function for logout scenarios (optional, preference is non-sensitive UI state)

**Patterns to follow:**
- Module-level singleton pattern from `docs/solutions/developer-experience/vue3-i18n-locale-switching-persistence-2026-05-15.md`
- Namespace key pattern (`child:locale`, `main:locale`)

**Test scenarios:**
- Happy path: User collapses canvas → preference stored
- Happy path: New session → preference restored on next long task
- Edge case: Logout → preference cleared (if cleanup called)
- Integration: Preference persists across browser sessions

**Verification:**
- localStorage key exists after collapse
- Preference respected on new session

---

### U10. Interrupted Session Handling

**Goal:** Detect and display interrupted sessions with progress indicator and optional resume action.

**Requirements:** R4

**Dependencies:** U4

**Files:**
- Modify: `frontend/apps/main/src/pages/AIChatPage.vue`
- Modify: `frontend/apps/main/src/components/ai/AgentRunHeader.vue`
- Modify: `frontend/apps/main/src/components/ai/AiStepBlock.vue`

**Approach:**
- Detection: `finalStatus='ended'` with running steps, or `finalStatus='error'` without error step
- Display: "执行中断" badge, progress summary "已完成 3/5 步骤"
- Gray out incomplete steps in `AiStepBlock.vue`
- Resume button: Conditional display (depends on backend capability — document during implementation)

**Patterns to follow:**
- Status badge pattern from existing components
- Gray/disabled styling pattern

**Test scenarios:**
- Happy path: Session ends with running steps → shows interrupted badge
- Edge case: Session error without explicit failure → shows interrupted badge
- Edge case: Normal completion → no interrupted display
- Integration: Gray styling applied to incomplete steps

**Verification:**
- Interrupted sessions display correctly
- Progress summary accurate

---

### U11. Mobile Responsive Strategy

**Goal:** Define responsive behavior for canvas on 320-428px screens.

**Requirements:** R7

**Dependencies:** U3, U5

**Files:**
- Modify: `frontend/apps/main/src/components/ai/AgentRunCanvas.vue`
- Modify: `frontend/apps/main/src/components/ai/AiStepBlock.vue`

**Approach:**
- Breakpoint: `@media (max-width: 428px)` for mobile
- Canvas width: Full viewport width on mobile
- Step summaries: Truncate long summaries with ellipsis
- Detail panel: `van-popup` drawer on mobile, inline expand on tablet/desktop
- Touch targets: All interactive elements 44×44px minimum (use negative margin trick)

**Patterns to follow:**
- Existing `@media (max-width: 768px)` pattern from `AiProcessBlock.vue`
- `van-popup` drawer pattern for mobile
- 44×44px touch target with negative margin from `AiPlanProgressBar.vue`

**Test scenarios:**
- Happy path: Mobile (320px) → canvas full-width, touch targets accessible
- Edge case: Tablet (768px) → canvas adapts, inline detail expand
- Integration: All buttons keyboard/touch accessible

**Verification:**
- Visual: Canvas renders correctly on mobile viewport
- Touch: All buttons respond with proper tap area

---

### U12. ARIA Accessibility Enhancement

**Goal:** Add complete ARIA accessibility to all new canvas components.

**Requirements:** R8

**Dependencies:** U3, U4, U5

**Files:**
- Modify: `frontend/apps/main/src/components/ai/AgentRunCanvas.vue`
- Modify: `frontend/apps/main/src/components/ai/AgentRunHeader.vue`
- Modify: `frontend/apps/main/src/components/ai/AiStepBlock.vue`
- Modify: `frontend/apps/main/src/i18n/locales/zh-CN.ts`

**Approach:**
- Canvas container: `role="region"` + `aria-label`
- Header: `role="banner"` for task summary
- Collapse toggle: `role="button"` + `tabindex="0"` + `aria-expanded` + `aria-controls`
- Detail panel: `aria-expanded` + `aria-controls` when collapsible
- Progress: `aria-live="polite"` for running status text
- Add i18n keys for all aria-labels

**Patterns to follow:**
- Existing ARIA patterns from `AiStepBlock.vue`: `role="listitem"`, `aria-expanded`, `aria-controls`
- `@keydown.enter` + `@keydown.space.prevent` pattern
- Focus-visible: `outline: 2px solid var(--van-primary-color)`
- Reduced motion: `@media (prefers-reduced-motion: reduce)` disables animations

**Test scenarios:**
- Happy path: Screen reader announces canvas region and header
- Happy path: Keyboard navigation: Tab → Enter toggles collapse
- Edge case: Focus-visible outline visible on keyboard focus
- Integration: `aria-live` announces running status changes

**Verification:**
- Accessibility audit: all interactive elements keyboard accessible
- Screen reader: correct announcements for all states

---

## System-Wide Impact

- **Interaction graph:** `AIChatPage.vue` now wraps `AiProcessBlock` conditionally; affects existing message rendering flow
- **Error propagation:** Backend redaction errors logged but don't break stream; frontend falls back to raw args if redaction fails
- **State lifecycle risks:** localStorage preference must clear on logout; interrupted session state must reset on resume/fail
- **API surface parity:** No new endpoints; all data from existing SSE stream
- **Integration coverage:** Test canvas transition in real agent session (not just unit tests)
- **Unchanged invariants:** Existing `AiProcessBlock` and `AiStepBlock` behavior preserved when `isLongTask=false`

---

## Risks & Dependencies

| Risk | Mitigation |
|------|------------|
| Backend redaction misses new sensitive key pattern | Periodic audit of `SENSITIVE_KEYS`; add logging for unexpected field patterns |
| Threshold misjudgment (2 vs 3 steps) | User override via localStorage; thresholds configurable in code |
| Old sessions without JSONL logs | Graceful degradation: show text-only message without progress |
| Component extension breaks existing behavior | Characterization tests before modification; backward-compatible props |
| Mobile canvas too cramped on 320px | Drawer pattern for detail; truncate summaries; test on real device |
| Resume button depends on backend capability | Document conditions during implementation; graceful disable if unavailable |

---

## Documentation / Operational Notes

- Update `frontend/apps/main/CLAUDE.md` with canvas component documentation
- Add ARIA key reference to accessibility section
- Document `SENSITIVE_KEYS` maintenance process: quarterly audit + automated detection proposal for Phase 2

---

## Sources & References

- **Origin document:** [docs/superpowers/specs/2026-06-08-agent-execution-canvas-design.md](docs/superpowers/specs/2026-06-08-agent-execution-canvas-design.md)
- Related code: `frontend/apps/main/src/components/ai/AiStepBlock.vue`
- Related learnings: `docs/solutions/best-practices/security-protection.md`
- External docs: Vant 4 accessibility guidelines