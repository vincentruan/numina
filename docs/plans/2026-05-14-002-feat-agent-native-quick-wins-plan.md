---
title: "Agent-Native Quick Wins"
status: active
created: 2026-05-14
origin: docs/brainstorms/2026-05-14-agent-native-quick-wins-requirements.md
---

# Agent-Native Quick Wins

## Problem Frame

Three independent improvements from the agent-native architecture audit (2026-05-14):

- **R1** — Users cannot discover agent capabilities by typing `/` in chat. The capability store is already populated; the UI just doesn't expose it.
- **R2/R3** — Two legacy rule-engine services (`disposal_advisor.py`, `aging_alert.py`) predate the DeerFlow migration and are unreachable from the live execution path. They are dead code.

All three are independent and can be implemented in any order.

(see origin: `docs/brainstorms/2026-05-14-agent-native-quick-wins-requirements.md`)

---

## Scope Boundaries

- No new backend endpoints.
- No changes to `orchestrator.py`, `policy_guard.py`, or `capability_registry.py`.
- No per-family threshold tuning.
- No server-side slash command parsing or routing.
- R2/R3 are deletions only — no replacement code.

---

## Implementation Units

### Unit 1 — Add `examples` to `alerts.md` and `disposal.md` skill frontmatter

**Why first:** R1's slash palette inserts `examples[0]` as the prompt seed. Without this, `alerts` and `disposal` produce empty insertions. This is a two-line YAML change with zero risk — do it before touching any Vue code.

**Files:**
- `server/apps/agent/skills/alerts.md` — add `placeholder` and `examples` fields
- `server/apps/agent/skills/disposal.md` — add `placeholder` and `examples` fields

**Decision:** Use `placeholder: null` (explicit null, matching `string | null` type) for both since they are `input_mode: trigger` capabilities with no free-text input field. Add three `examples` entries each, following the `chat.md` pattern.

**Suggested values:**

`alerts.md`:
```yaml
placeholder: null
examples:
  - 哪些资产快到期了？
  - 有哪些资产维护成本过高？
  - 闲置资产还在产生费用吗？
```

`disposal.md`:
```yaml
placeholder: null
examples:
  - 哪些资产可以出售？
  - 闲置资产推荐哪些处置渠道？
  - 低效资产有哪些？
```

**Pattern reference:** `server/apps/agent/skills/chat.md` lines 10–13.

**Verification:** `GET /capabilities` response includes `example_questions` for `alerts` and `disposal` with non-empty arrays. No Python tests needed — `CapabilityRegistry` already has tests for frontmatter parsing.

**Test scenarios:** None required — this is a data change, not logic. Verify manually via the capabilities endpoint or by reading the parsed output in a unit test fixture.

---

### Unit 2 — Delete dead rule-engine services (R2 + R3)

**Why together:** Both deletions follow the same pattern and have zero risk. Batch them.

**Files to delete:**
- `server/apps/agent/services/disposal_advisor.py` (141 lines, zero imports)
- `server/apps/agent/services/aging_alert.py` (133 lines, zero imports)

**Note:** `server/apps/agent/tests/unit/` does not exist — no test files to delete.

**Pre-deletion check (part of implementation):**
```
grep -rn "disposal_advisor\|aging_alert" server/apps/agent/ --include="*.py" | grep -v "__pycache__"
```
Expected: zero results (confirmed during planning). If any appear, investigate before deleting.

**Verification:** `uv run pytest tests/ -v` from `server/` passes with no failures. No new tests needed.

**Test scenarios:** N/A — deletion only. The acceptance criterion is zero grep hits and green tests.

---

### Unit 3 — Slash command palette in `AIChatInput.vue` (R1)

**Decision: implement inside `AIChatInput.vue`, not `AIChatPage.vue`.** The component owns the textarea ref, `internalValue`, and `onInput` handler. Adding slash detection at the page level would require cross-component positioning. The capability list is accessed by importing `useCapabilityStore` directly inside the component (avoids prop drilling; the store is already used elsewhere in the app).

**Decision: reuse the existing `plus-panel` pattern.** The panel is an absolute-positioned `<div>` with `<transition name="panel">` rendered via `v-if`. The slash palette uses the same structure — no Vant popup needed, consistent with existing UI.

**Decision: trigger on `/` as the first character only.** Dismiss when `internalValue` no longer starts with `/`. This avoids false triggers mid-sentence.

**Decision: selection behavior by `input_mode`:**
- `free_text` capabilities: insert `examples[0]` (or `placeholder` or `name`) into `internalValue` and keep focus in the textarea.
- `trigger` capabilities: navigate to `capability.ui.route` (same as tapping the capability card in AIHubPage).

**Files:**
- `frontend/apps/main/src/components/common/AIChatInput.vue` — primary change
- `frontend/apps/main/src/i18n/locales/zh-CN.ts` — add palette UI strings

**`AIChatInput.vue` changes:**

1. Import `useCapabilityStore` and call it inside `setup`.
2. Add `slashPaletteOpen: ref<boolean>(false)` and `selectedIndex: ref<number>(0)`.
3. Extend `onInput()` to set `slashPaletteOpen.value = internalValue.value === '/' || internalValue.value.startsWith('/')`. Reset `selectedIndex` to 0 when palette opens.
4. Add `@keydown` handler on the textarea for:
   - `ArrowDown` — increment `selectedIndex` (wrap at end), `preventDefault`
   - `ArrowUp` — decrement `selectedIndex` (wrap at start), `preventDefault`
   - `Escape` — close palette, `preventDefault`
   - `Tab` / `Enter` when palette open — select current item, `preventDefault`
5. Add `selectCapability(cap: AICapability)` method:
   - `free_text`: set `internalValue.value` to `cap.ui.example_questions[0] ?? cap.ui.placeholder ?? cap.name`, close palette, focus textarea.
   - `trigger`: close palette, `router.push(cap.ui.route)`.
6. Render the palette as a `<div class="slash-palette">` above the input (same `position: absolute; bottom: calc(100% + 8px)` as `plus-panel`), `v-if="slashPaletteOpen"`, listing `capabilityStore.capabilities` with name + description. Highlight `selectedIndex` row.
7. Close palette on outside click — add `@click.outside` or a `v-click-outside` directive if already used in the project; otherwise use a `mousedown` listener on `document` in `onMounted`/`onUnmounted`.

**i18n keys to add** (inside `aiChat` section of `zh-CN.ts`):
```ts
slashPaletteHint: '选择功能，按 Esc 关闭',
slashPaletteEmpty: '暂无可用功能',
```

**Pattern references:**
- `plus-panel` pattern: `AIChatInput.vue` lines 2–21 (template), lines 171–187 (logic), lines 399–412 (CSS)
- `onChipClick` in `AIChatPage.vue` lines 710–713 — same `inputText.value = text` pattern for free_text insertion
- Vant 4 binding rule: use `:model-value` not `:value` on any `van-field` (from `docs/solutions/ui-bugs/vant4-field-modelvalue-binding-2026-04-08.md`)

**Test scenarios:**
1. Typing `/` opens the palette with all capabilities listed.
2. Typing any other character as the first character does not open the palette.
3. Typing `/` mid-sentence (e.g., `hello /`) does not open the palette.
4. `ArrowDown` moves selection to next item; wraps from last to first.
5. `ArrowUp` moves selection to previous item; wraps from first to last.
6. `Escape` closes the palette without changing `internalValue`.
7. Selecting a `free_text` capability inserts `examples[0]` into the input and closes the palette.
8. Selecting a `trigger` capability navigates to its route and closes the palette.
9. Selecting a capability with no `examples` and no `placeholder` inserts the capability `name`.
10. Clicking outside the palette closes it.
11. On mobile (touch), tapping a palette item selects it correctly.
12. `alerts` and `disposal` capabilities produce non-empty insertions (validates Unit 1).

**Verification:** Start the dev server and manually test the golden path (type `/`, see palette, select `chat`, confirm `我的净资产健康吗？` is inserted). Run `vue-tsc --noEmit` from `frontend/apps/main/` to confirm no type errors.

---

## Sequencing

```
Unit 1 (skill frontmatter)  ──┐
Unit 2 (delete dead code)   ──┤── all independent, any order
Unit 3 (slash palette)      ──┘
```

Recommended order: 1 → 2 → 3. Units 1 and 2 are trivial and build confidence before the Vue work.

---

## Risks

| Risk | Likelihood | Mitigation |
|------|-----------|------------|
| `capabilityStore.capabilities` is empty when palette opens (store not yet loaded) | Low — `AIChatPage` loads capabilities on mount | Call `loadCapabilities()` inside `AIChatInput` if `capabilities.length === 0` before opening palette |
| Outside-click handler leaks if component unmounts while palette is open | Low | Clean up `document` listener in `onUnmounted` |
| `router` not available inside `AIChatInput` | Low — Vue Router is globally available via `useRouter()` | Use `useRouter()` composable |
| Palette z-index conflicts with `plus-panel` | Low — they are mutually exclusive (palette closes when `internalValue` no longer starts with `/`) | Ensure `slashPaletteOpen` and `panelOpen` cannot both be true simultaneously |

---

## Checklist

- [ ] Unit 1: Add `placeholder` + `examples` to `server/apps/agent/skills/alerts.md`
- [ ] Unit 1: Add `placeholder` + `examples` to `server/apps/agent/skills/disposal.md`
- [ ] Unit 1: Verify `/capabilities` response includes non-empty `example_questions` for `alerts` and `disposal`
- [ ] Unit 2: Pre-deletion grep confirms zero imports of `disposal_advisor` and `aging_alert`
- [ ] Unit 2: Delete `server/apps/agent/services/disposal_advisor.py`
- [ ] Unit 2: Delete `server/apps/agent/services/aging_alert.py`
- [ ] Unit 2: `uv run pytest tests/ -v` passes from `server/`
- [ ] Unit 3: Slash palette opens on `/` as first character
- [ ] Unit 3: Keyboard navigation (ArrowUp/Down/Escape/Enter) works
- [ ] Unit 3: `free_text` selection inserts prompt seed into input
- [ ] Unit 3: `trigger` selection navigates to capability route
- [ ] Unit 3: `alerts` and `disposal` produce non-empty insertions
- [ ] Unit 3: Mobile touch interaction works
- [ ] Unit 3: `vue-tsc --noEmit` passes
- [ ] Unit 3: i18n keys added to `zh-CN.ts`
