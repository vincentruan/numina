---
date: 2026-08-05
module: frontend + agent + backend (cross-cutting)
problem_type: ui_bug
component: frontend_stimulus
severity: high
root_cause: logic_error
resolution_type: code_fix
symptoms:
  - "Blank screen after back navigation from sub-pages (Devices, ChangePassword) to cached tab pages"
  - "Onboarding guide overlay (z-index 9999) blocks tab bar taps, page appears stuck"
  - "MCP tools: 0 on every agent run — DeerFlow MCP tools fail to load"
  - "Session titles show raw thinking blocks like [{'type':'thinking','thinking':'...'}] instead of summaries"
  - "English ASR scores 100% WER despite correct recognition"
  - "Action-sheet inside van-tabs animated swipeable appears empty but remains clickable"
  - "DB CheckViolation for agent_name with underscores despite Pydantic allowing them"
  - "Spurious MANIFESTO_NOT_FOUND fail-toast on feedback list page load"
tags:
  - vue3-transition
  - keepalive
  - asyncio-lock
  - threading
  - deerflow-mcp
  - thinking-block
  - asr-wer
  - css-containing-block
applies_when:
  - "Vue 3 Transition + KeepAlive + dynamic :key combination causes blank router-view"
  - "Module-level asyncio.Lock accessed from worker threads with separate event loops"
  - "LLM structured content blocks (thinking + text) leak into downstream string consumers"
  - "CSS transform:translateZ(0) creates new containing block that clips popups"
  - "DB check constraint regex diverges from Pydantic validator regex"
---

# fix/user-feedback Branch: 25 Commits of Cross-Cutting Bug Fixes

This document captures the key bugs found and fixed on the `fix/user-feedback` branch, organized by root cause category. Each bug includes the symptom, root cause, fix, and prevention strategy.

---

## Bug 1: Vue 3 Transition + KeepAlive Blank Screen

### Problem
The `<Transition mode="out-in">` + `<KeepAlive>` + `:key="route.path"` combination in `MainLayout.vue` caused a Vue 3 rendering bug where navigating back from any non-cached sub-page to a cached tab page left the `<router-view>` permanently blank.

### Symptoms
- Navigate from Dashboard (cached tab) to Devices (non-cached sub-page), then press back
- Router-view renders nothing permanently — no content, no error
- Affects all sub-page → cached-tab navigation flows

### What Didn't Work
- Keeping `mode="out-in"` and adjusting transition duration — the issue is structural, not timing
- Switching to `mode="in-out"` — same blank result because the leave transition never completes for KeepAlive components

### Solution
Remove the `<Transition>` wrapper and the dynamic `:key` entirely. KeepAlive handles caching without transition animation.

**Before** (`frontend/apps/main/src/layouts/MainLayout.vue`):
```vue
<router-view v-slot="{ Component, route }">
  <Transition name="page-fade" mode="out-in">
    <KeepAlive :include="cachedTabs">
      <component :is="Component" :key="route.path" />
    </KeepAlive>
  </Transition>
</router-view>
```

**After**:
```vue
<router-view v-slot="{ Component }">
  <KeepAlive :include="cachedTabs">
    <component :is="Component" />
  </KeepAlive>
</router-view>
```

### Why This Works
Vue 3's `<Transition mode="out-in">` waits for the leaving component's transition to finish before mounting the entering component. When combined with `<KeepAlive>`, the "leaving" component is deactivated (not destroyed), and the transition's `afterLeave` hook may never fire for certain deactivation paths — specifically when navigating back from a non-cached page to a cached one. The `:key="route.path"` exacerbates this by forcing Vue to treat every route as a distinct component instance, breaking KeepAlive's name-based cache matching. Removing both the Transition and the dynamic key lets KeepAlive manage the component lifecycle directly.

### Prevention
- **Avoid `<Transition mode="out-in">` + `<KeepAlive>` + `:key` combinations** in Vue 3. If page transitions are needed, use `mode="default"` (simultaneous) or apply transitions per-component via `onMounted`/`onActivated` hooks.
- **Test all navigation paths**: tab→sub-page→back, tab→tab, sub-page→sub-page. The blank-screen bug only manifests on specific navigation directions.
- Commit: `d47bd967` fix(frontend): remove page Transition to fix blank screen after back navigation (local-only SHA, will be rewritten on merge)

---

## Bug 2: Onboarding Guide Overlay Blocks Tab Bar Navigation

### Problem
`StepGuideOverlay` (z-index 9999, pointer-events: all) covers the entire viewport when active, intercepting clicks on the bottom tab bar (z-index 1000). When a user taps a tab to navigate away from the onboarding guide, `router.push()` never fires because the overlay captures the click.

### Symptoms
- Dashboard or Tasks page shows onboarding guide
- User taps a bottom tab bar icon — nothing happens, page appears stuck
- No console errors, no network requests — click silently swallowed

### What Didn't Work
- Reducing overlay z-index below tab bar — overlay must be above page content to function
- Adding `pointer-events: none` to overlay — breaks the guide's own interactive elements (next/skip buttons)

### Solution
Add a route watcher in pages that show the onboarding guide. When navigation is detected, call `guide.skip()` to dismiss the overlay immediately. Also save/restore body scroll position to prevent scroll leakage.

**Before** (`frontend/apps/main/src/pages/DashboardPage.vue`):
```typescript
// No route watcher — overlay persists across navigation
onMounted(() => { guide.start() })
```

**After**:
```typescript
const route = useRoute()
watch(() => route.path, (newPath, oldPath) => {
  if (newPath !== oldPath && guide.isActive.value) {
    guide.skip()  // Dismiss overlay before navigation completes
  }
})
```

Additionally, the `StepGuideOverlay` component was updated to save/restore body scroll position:
```typescript
// Before open: save scroll
const savedScrollTop = document.body.scrollTop

// After close: restore scroll, zero on route-change dismiss
document.body.scrollTop = savedScrollTop
```

### Why This Works
The overlay is a full-viewport element with the highest z-index. When a tab bar tap triggers `router.push()`, the overlay intercepts the click event before it reaches the tab bar's `<a>` element. By watching for route changes and proactively dismissing the overlay, the overlay is removed from the DOM before the navigation completes, allowing the tab bar click to reach its target on subsequent taps. The scroll save/restore prevents the onboarding guide's `overflow: hidden` body lock from leaking to the target page.

### Prevention
- **Full-viewport overlays must self-dismiss on route change** — any overlay with z-index above navigation elements should watch `route.path` and auto-dismiss.
- **Test overlay + navigation interaction** — tap tab bar while overlay is visible; the expected behavior is immediate navigation, not "stuck" state.
- Commits: `d587eb24` fix(ui): dismiss onboarding guide on route change; `eb1c8584` fix(ui): prevent onboarding guide from leaking body scroll (local-only SHAs, will be rewritten on merge)

---

## Bug 3: DeerFlow MCP Cache asyncio.Lock Threading Deadlock

### Problem
DeerFlow's MCP tool cache uses `_initialization_lock = asyncio.Lock()` created at module import time, bound to the main thread's event loop. Worker threads (`deerflow_N`) access this lock via `asyncio.run()` which creates a new event loop — cross-thread `create_future()` raises `RuntimeError`. Result: **MCP tools: 0** on every agent run.

### Symptoms
- Agent logs show `MCP tools: 0` on every run
- `/ai/chat` reports "MCP tools unavailable" — cannot query family data
- `/ai/report` works (different code path)
- `RuntimeError: There is no current event loop in thread 'deerflow_N'` in agent logs

### What Didn't Work
- The upstream `except RuntimeError` retry at `cache.py:177` — it catches the initial `get_event_loop()` failure but retries with `asyncio.run()` which also fails at `initialize_mcp_tools` line 125 (`async with _initialization_lock`) for the same cross-thread reason
- Restarting the agent process — the module-level lock re-initializes bound to the same main-thread loop, and worker threads hit the same deadlock

### Solution
Monkey-patch `deerflow.mcp.cache.get_cached_mcp_tools` to replace the broken `asyncio.Lock` with a `threading.Lock` + `asyncio.run()` combination that works correctly in any thread.

**Before** (upstream DeerFlow library `deerflow/mcp/cache.py` in site-packages):
```python
_initialization_lock = asyncio.Lock()  # Bound to main thread's loop at import time

async def initialize_mcp_tools():
    async with _initialization_lock:  # Cross-thread RuntimeError
        ...
```

**After** (`server/apps/agent/services/deerflow_adapter/sync_tool_patch.py`):
```python
def _apply_mcp_cache_threading_lock_patch() -> None:
    import deerflow.mcp.cache as _cache_mod
    import asyncio as _asyncio
    import threading as _threading

    _lazy_init_thread_lock = _threading.Lock()

    def _patched_get_cached_mcp_tools():
        if _cache_mod._cache_initialized and not _cache_mod._is_cache_stale():
            return _cache_mod._mcp_tools_cache or []

        if not _lazy_init_thread_lock.acquire(blocking=False):
            _lazy_init_thread_lock.acquire()  # Wait for other thread
            _lazy_init_thread_lock.release()
            return _cache_mod._mcp_tools_cache or []
        try:
            if _cache_mod._cache_initialized:
                return _cache_mod._mcp_tools_cache or []
            from deerflow.mcp.tools import get_mcp_tools
            _cache_mod._mcp_tools_cache = _asyncio.run(get_mcp_tools())
            _cache_mod._cache_initialized = True
        finally:
            _lazy_init_thread_lock.release()
        return _cache_mod._mcp_tools_cache or []

    _cache_mod.get_cached_mcp_tools = _patched_get_cached_mcp_tools
```

### Why This Works
`threading.Lock` is not bound to any event loop — it works across any thread. `asyncio.run()` creates a fresh event loop scoped to the call, avoiding the cross-thread loop access that `asyncio.Lock` requires. The double-check pattern after acquiring the lock prevents redundant initialization when multiple worker threads race to initialize simultaneously.

### Prevention
- **Never create `asyncio.Lock()` / `asyncio.Event()` / `asyncio.Semaphore()` at module import time** when the code may be called from worker threads with separate event loops. Use `threading.Lock` for cross-thread synchronization.
- **Test MCP tool loading in multi-threaded scenarios** — the bug only manifests when DeerFlow's ThreadPoolExecutor dispatches to a worker thread, not in single-threaded test harnesses.
- Commit: `ab28dda3` fix(agent): patch DeerFlow MCP cache threading deadlock + fix get_assets query (local-only SHA, will be rewritten on merge)

---

## Bug 4: Thinking-Block Content Leaking into Session Titles

### Problem
LLM models with thinking (Claude extended thinking, Qwen3) return `response.content` as a list of dicts: `[{"type": "thinking", "thinking": "..."}, {"type": "text", "text": "..."}]`. When `str()` is called on this list for title generation, the result is a Python repr like `[{'signature': '', 'thinking': '...'}]` — raw thinking block data becomes the session title.

### Symptoms
- Session titles show `[{'signature': '', 'thinking': 'Let me analyze...'}]` instead of human-readable summaries
- Python list-literal repr appears in the chat history sidebar
- Suggestion generation also receives contaminated thinking content

### What Didn't Work
- Checking for `[SKILL:` prefix only — old fallback detection missed the new thinking-block repr pattern
- Stripping at a single write path — multiple code paths (`threads.update_thread_state`, `patch_thread`, `agent_dispatch._persist_session_metadata`) all write titles independently

### Solution
Add `_strip_thinking_from_text` and `_extract_text_from_content_blocks` helpers, then apply them at ALL title/suggestion write paths. Also detect Python list-literal repr in `_is_fallback_title`.

**Before** (`server/apps/agent/services/runtime/run_extras.py`):
```python
# Title was extracted by calling str() on the content directly
title = str(response.content)  # Produces "[{'type': 'thinking', ...}]"
```

**After**:
```python
def _extract_text_from_content_blocks(content: Any) -> str:
    """Extract only text portions from structured LLM output."""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for block in content:
            if isinstance(block, dict):
                if block.get("type", "") == "thinking":
                    continue  # skip thinking blocks entirely
                text_val = block.get("text") or block.get("content")
                if isinstance(text_val, str) and text_val.strip():
                    parts.append(text_val.strip())
        return " ".join(parts) if parts else str(content)
    return str(content)

def _strip_thinking_from_text(text: str) -> str:
    """Remove <think>...</think> blocks from text."""
    import re
    text = re.sub(r"<think>[\s\S]*?</think>", "", text, flags=re.IGNORECASE).strip()
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()
```

### Why This Works
The `_extract_text_from_content_blocks` function walks the structured content list and only concatenates `text`/`content` fields from non-thinking blocks. The `_strip_thinking_from_text` function handles the case where thinking is embedded as XML-style `<think>` tags within a text string. By applying both at every title write path (defense in depth), thinking content never reaches the user-visible title field.

### Prevention
- **Always use structured content extraction** when consuming LLM responses — never `str()` on content blocks that may contain thinking/reasoning data.
- **Apply sanitization at every write path** — the bug recurred because fixing one path (e.g., `update_thread_state`) didn't prevent the same contamination through `patch_thread` or `_persist_session_metadata`.
- **Test with thinking-enabled models** — the bug only manifests with models that return structured content blocks.
- Commit: `6fd4e9dd` fix(agent): prevent thinking-block fallback titles across all write paths (local-only SHA, will be rewritten on merge)

---

## Bug 5: ASR 100% WER from Whitespace Stripping

### Problem
The custom `_strip_punctuation()` function in `asr_wer.py` removed whitespace along with punctuation, collapsing multi-word English sentences into a single untokenizable string. The WER/CER calculation then compared the collapsed string against the reference, producing 100% error rate even for correct recognitions.

### Symptoms
- English ASR output scores 100% WER despite correct recognition
- `'hi welcome to numina'` becomes `'hiwelcometouninena'` — one giant word
- Chinese CER works (character-level comparison doesn't need word boundaries)

### What Didn't Work
- Adjusting the edit-distance threshold — the underlying tokenization was broken
- Only stripping punctuation characters (`.?!`,) — still lost whitespace between words

### Solution
Replace the custom edit-distance implementation with `jiwer`, which provides proper `process_characters` (CJK CER) and `process_words` (English WER) with correct normalization.

**Before** (`server/apps/backend/app/services/asr_wer.py`):
```python
def _strip_punctuation(text: str) -> str:
    return re.sub(r'[^\w\s]', '', text)  # Also strips whitespace!

def calculate_wer(reference: str, hypothesis: str) -> float:
    ref = _strip_punctuation(reference.lower())   # "hi welcome" → "hiwelcome"
    hyp = _strip_punctuation(hypothesis.lower())
    # Edit distance on collapsed strings → 100% error
```

**After**:
```python
import jiwer

def calculate_wer(reference: str, hypothesis: str) -> dict:
    # English: replace punctuation with spaces to preserve word boundaries
    ref_normalized = re.sub(r'[^\w\s]', ' ', reference.lower())
    hyp_normalized = re.sub(r'[^\w\s]', ' ', hypothesis.lower())
    result = jiwer.process_words(ref_normalized, hyp_normalized)
    return {"wer": result.wer, "operations": _expand_chunks(result)}

def calculate_cer(reference: str, hypothesis: str) -> dict:
    # CJK: strip punctuation entirely, character-level comparison
    ref_normalized = re.sub(r'[^一-鿿]', '', reference)
    hyp_normalized = re.sub(r'[^一-鿿]', '', hypothesis)
    result = jiwer.process_characters(ref_normalized, hyp_normalized)
    return {"cer": result.cer, "operations": _expand_chunks(result)}
```

### Why This Works
The key insight is that English WER needs **word-level** comparison (preserving whitespace as word boundaries), while CJK CER needs **character-level** comparison (whitespace is irrelevant). The old code used a single normalization that destroyed word boundaries for English. `jiwer` provides separate `process_words` and `process_characters` functions that handle each case correctly. The fix also expands jiwer's alignment chunks into individual token-level operations for backward-compatible frontend diff display.

### Prevention
- **Use established NLP libraries for text comparison metrics** — WER/CER are well-defined metrics with established implementations. Custom edit-distance code is error-prone for tokenization edge cases.
- **Test with multi-word inputs** — the bug only manifested with English text containing spaces. Single-character CJK text was unaffected.
- **Separate normalization by language** — CJK and alphabetic scripts have fundamentally different tokenization requirements.
- Commit: `06199252` fix(asr): use jiwer for proper WER/CER calculation with text normalization

---

## Bug 6: Action-Sheet Clipped Inside van-tabs Swipeable

### Problem
The "操作类型" picker on `/ai/time-machine` rendered inside `<van-tabs animated swipeable>`, whose `transform: translateZ(0)` creates a new CSS containing block and `overflow: hidden` clips the popup. The action-sheet appeared empty but remained clickable.

### Symptoms
- Action-sheet popup on the WhatIfSimulator page renders but appears invisible
- The popup backdrop and items are present in the DOM but clipped by the parent container
- Clicking "blind" still triggers item selection — the popup works but is visually hidden

### What Didn't Work
- Increasing z-index on the action-sheet — the issue is a containing block / clipping problem, not z-index stacking
- Removing `overflow: hidden` from the tab container — breaks the swipe animation

### Solution
Add `teleport="body"` to the `van-action-sheet` component so it mounts on `<body>`, bypassing the Swipe containing block entirely.

**Before** (`frontend/apps/main/src/components/ai/WhatIfSimulator.vue`):
```vue
<van-action-sheet v-model:show="showPicker" :actions="actions" />
```

**After**:
```vue
<van-action-sheet v-model:show="showPicker" :actions="actions" teleport="body" />
```

### Why This Works
CSS `transform: translateZ(0)` creates a new containing block for `position: absolute` / `position: fixed` descendants. The `van-tabs animated swipeable` component uses this for GPU-accelerated swipe transitions. The action-sheet, positioned absolutely within the tab panel, is confined to the tab panel's bounding box. With `overflow: hidden` on the same container, the popup is clipped. `teleport="body"` moves the popup's DOM node to `<body>`, completely outside the transform/overflow clipping context.

### Prevention
- **Always use `teleport="body"` for Vant popups inside transformed containers** — any `van-popup`, `van-action-sheet`, `van-picker`, or `van-dialog` inside `<van-tabs animated>` or other `transform`-using parents needs teleport.
- **Test popups inside swipeable tabs specifically** — the containing block issue only manifests with CSS transforms, not with static-positioned parents.
- Commit: `101a34ff` fix(ui): teleport action-sheet to body in WhatIfSimulator (local-only SHA, will be rewritten on merge)

---

## Bug 7: DB Check Constraint Regex Mismatch with Pydantic

### Problem
The DB `CheckConstraint` on `ai_agents.agent_name` used regex `^[a-z][a-z0-9-]*$` (no underscore), but the Pydantic validator allowed `^[a-z][a-z0-9_-]*$` (with underscore). Agent names like `stock_research_agent` passed app validation but failed at the DB level.

### Symptoms
- `CheckViolation` error when inserting agent names containing underscores
- Pydantic validation passes — the error only surfaces at the database layer
- Error message: `new row for relation "ai_agents" violates check constraint "ck_ai_agents_name_format"`

### What Didn't Work
- Changing Pydantic to reject underscores — the agent names with underscores are intentional and valid
- Only updating the model — existing databases need a migration to drop and recreate the constraint

### Solution
Update the `CheckConstraint` regex to include `_` and add an alembic migration.

**Before** (`server/apps/backend/app/models/ai_agent.py:31`):
```python
CheckConstraint(
    "agent_name ~ '^[a-z][a-z0-9-]*$'",  # Missing underscore
    name="ck_ai_agents_name_format",
    _create_rule=_pg_only,
),
```

**After**:
```python
CheckConstraint(
    "agent_name ~ '^[a-z][a-z0-9_-]*$'",  # Now includes underscore
    name="ck_ai_agents_name_format",
    _create_rule=_pg_only,
),
```

### Why This Works
The DB constraint and the Pydantic validator are independent validation layers that must agree on the allowed format. When they diverge, the stricter layer rejects valid inputs that passed the looser layer. The fix aligns both to allow underscores.

### Prevention
- **Keep DB constraints and app-level validators in sync** — whenever updating a Pydantic regex, check for corresponding DB check constraints.
- **Use the same regex source of truth** — consider defining the regex pattern once and referencing it from both the model and the migration.
- **Test with realistic data** — `stock_research_agent` is a valid name that should have been caught by integration tests.
- Commit: `af6143ef` fix(ai): align DB check constraint with Pydantic regex for agent_name (local-only SHA, will be rewritten on merge)

---

## Bug 8: Spurious MANIFESTO_NOT_FOUND Toast on Feedback List

### Problem
The global axios interceptor shows a `showFailToast()` for any non-2xx response. `getFeedbackList()` returns a 404 `MANIFESTO_NOT_FOUND` when no manifesto exists yet, triggering an ugly error toast on a page that should handle this gracefully.

### Symptoms
- Opening the feedback list page shows a red fail toast "家庭宣言尚未创建" even though the page correctly renders an empty state
- The toast is confusing — the page works fine, but the error message suggests something broke

### Solution
Add `_silentErrorCodes` to the request config so the global interceptor skips the toast for expected error codes.

**Before** (`frontend/apps/main/src/api/manifesto.ts`):
```typescript
export function getFeedbackList() {
  return http.get<ManifestoFeedback[]>('/family/manifesto/feedback')
}
```

**After**:
```typescript
export function getFeedbackList() {
  return http.get<ManifestoFeedback[]>('/family/manifesto/feedback', {
    _silentErrorCodes: ['MANIFESTO_NOT_FOUND'],
  })
}
```

### Why This Works
The axios interceptor in `frontend/apps/main/src/api/index.ts` checks `config._silentErrorCodes` before showing the toast. When the error code is in the silent list, the interceptor passes the error through to the caller without showing a toast. The caller already handles the 404 gracefully by showing an empty state.

### Prevention
- **Use `_silentErrorCodes` for all expected error responses** — any endpoint that returns a known error code as part of normal operation (not a real failure) should declare it as silent.
- **Audit 404 responses** — "not found" responses for resources that may legitimately not exist yet (manifesto, feedback, settings) are common candidates for silent error codes.
- Commit: `c4653aaf` fix(api): silence MANIFESTO_NOT_FOUND toast on feedback list (local-only SHA, will be rewritten on merge)

---

## Bug 9: Family Page Action Buttons Overflow Viewport

### Problem
Full-width buttons (`width: 100%`) with horizontal `margin: 0 16px` totaled `100% + 32px`, overflowing the viewport on narrow screens.

### Symptoms
- Action buttons on the Family page (regenerate invite code, add child) extend beyond the right edge of the screen
- Horizontal scrollbar appears on mobile viewport
- Last few pixels of button text are cut off

### What Didn't Work
- `box-sizing: border-box` — already set, but margin is outside the box
- Reducing button width to `calc(100% - 32px)` — works but is fragile and not semantic

### Solution
Wrap buttons in a padding div so the block button fills the padded interior instead.

**Before**:
```vue
<van-button type="primary" block style="margin: 0 16px">
  {{ t('family.regenerateInviteCode') }}
</van-button>
```

**After**:
```vue
<div class="section-action">
  <van-button type="primary" block>
    {{ t('family.regenerateInviteCode') }}
  </van-button>
</div>
```
```css
.section-action { padding: 0 16px; }
```

### Why This Works
CSS box model: `width: 100%` + `margin: 0 16px` = `100% + 32px` total width. By moving the horizontal spacing to a parent container's `padding`, the `width: 100%` button fills the parent's content area (which is already inset by the padding). This is the standard CSS solution for full-width elements within padded containers.

### Prevention
- **Never combine `width: 100%` with horizontal `margin`** — use parent padding instead.
- **Test on narrow viewports** (320px) — overflow issues only manifest on small screens.
- Commit: `d6bdd008` fix(ui): prevent family page action buttons from overflowing (local-only SHA, will be rewritten on merge)

---

## Cross-Cutting Patterns & Lessons

### Pattern 1: CSS Containing Block Surprises
Both Bug 6 (action-sheet clipping) and Bug 9 (button overflow) are CSS containing block / box model issues. The common thread: CSS properties like `transform`, `overflow: hidden`, and `margin` interact in non-obvious ways. **Prevention**: always use `teleport="body"` for popups inside transformed containers, and use parent padding instead of child margin for full-width elements.

### Pattern 2: Cross-Thread Async State
Bug 3 (MCP cache deadlock) is a classic Python async/threading mismatch. Module-level `asyncio.Lock` objects are bound to the event loop that was current at creation time. When worker threads create new event loops via `asyncio.run()`, the lock becomes unusable. **Rule**: never create asyncio synchronization primitives at module import time when worker threads may access them.

### Pattern 3: Multi-Layer Validation Divergence
Bug 7 (DB constraint vs Pydantic) and Bug 4 (thinking-block titles) both involve validation divergence between layers. When two independent layers validate the same data with different rules, the stricter layer silently rejects valid inputs or the looser layer passes invalid inputs that break downstream. **Rule**: keep validation rules in sync across all layers, and test with realistic data that exercises boundary cases.

### Pattern 4: Full-Vendor Overlays vs Navigation
Bug 2 (onboarding blocking tab bar) is a specific case of a general pattern: full-viewport overlays with high z-index intercept navigation events. **Rule**: any overlay with z-index above navigation elements must self-dismiss on route change.

### Pattern 5: LLM Structured Output Leakage
Bug 4 (thinking-block titles) is an instance of a broader problem: LLM APIs return structured content blocks, but downstream consumers often expect plain strings. Any code path that calls `str()` on structured content risks leaking thinking/reasoning metadata. **Rule**: always use structured extraction helpers, never `str()` on LLM response content.

### Verification Evidence
- Backend tests: 1246+ passed, 0 failed
- Frontend typecheck: 0 errors
- Frontend vitest: 968+ passed
- Specific bug verifications noted in each commit message
