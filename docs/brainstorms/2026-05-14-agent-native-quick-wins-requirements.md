# Agent-Native Quick Wins Requirements

**Created:** 2026-05-14
**Source:** Agent-native architecture audit (2026-05-14) — items 6, 7, 10 from Top 10 Recommendations
**Scope:** Lightweight — one frontend feature (R1) plus two backend cleanup items (R2/R3 are preparatory, see note)

---

## Problem Frame

The agent-native audit identified three quick wins. Investigation revealed that items 6 and 10 require a prerequisite clarification before implementation:

1. **Slash command discovery** — absent from the chat interface. Users cannot discover agent capabilities via keyboard or command syntax. *(Becomes R1 — ready to implement.)*
2. **Disposal scoring thresholds** (`FREQ_SCORE`, cost/age cutoffs) are hardcoded in `server/apps/agent/services/disposal_advisor.py`. However, investigation shows this service is **not called by the live execution path** — routers dispatch through `orchestrator.dispatch()` → DeerFlow only. The service is legacy code predating the DeerFlow migration. *(Becomes R2 — delete dead code, not externalize config.)*
3. **Aging alert thresholds** (180-day high, 365-day medium) are hardcoded in `server/apps/agent/services/aging_alert.py`. Same situation — this service is also dead code relative to the current DeerFlow execution path. *(Becomes R3 — delete dead code.)*
4. **Policy rules** in `server/apps/agent/services/policy_guard.py` are already data-driven from the backend `CapabilityPolicy` object. No code change needed. *(Removed from scope.)*

---

## Requirements

### Frontend Requirements

#### R1 — Slash command discovery in chat interface

Users typing `/` in the chat input should see a command palette listing available agent capabilities. This surfaces the same data already returned by `GET /capabilities`.

**Implementation note:** The slash detection and palette rendering must live inside `AIChatInput.vue` (not `AIChatPage.vue`), since that component owns the textarea ref, focus state, and `onInput` handler. The capability list is passed in as a prop from the page.

**Acceptance criteria:**
- Typing `/` as the first character in the chat input opens an inline suggestion list showing all capabilities (name + description) from the capability store.
- Selecting a capability inserts its first `examples` entry if present, otherwise its `placeholder`, otherwise its `name` as a prompt seed.
- The list is dismissed on `Escape` or when the input no longer starts with `/`.
- No new backend endpoint is required — the frontend uses the capability store already populated by `GET /capabilities`.
- Works on both desktop and mobile (Vant-compatible touch interaction).
- All new UI strings are defined in `frontend/apps/main/src/i18n/locales/zh-CN.ts`.
- `alerts` and `disposal` skill files gain `examples` or `placeholder` entries so they produce non-empty insertions.

**Out of scope:** Server-side slash command parsing, `/help` as a routed backend command, custom slash commands beyond capability shortcuts.

---

### Backend Cleanup Requirements

#### R2 — Delete dead rule-engine service: disposal_advisor

`server/apps/agent/services/disposal_advisor.py` is unreachable from the live execution path. All disposal requests route through `orchestrator.dispatch("disposal")` → DeerFlow. This file predates the DeerFlow migration and was never wired into the orchestrator.

**Acceptance criteria:**
- `server/apps/agent/services/disposal_advisor.py` is deleted.
- `server/apps/agent/tests/unit/test_disposal_advisor.py` is deleted (tests for dead code).
- No import of `disposal_advisor` exists anywhere in the codebase after deletion.
- All remaining agent tests pass.

#### R3 — Delete dead rule-engine service: aging_alert

Same situation as R2 for `server/apps/agent/services/aging_alert.py`.

**Acceptance criteria:**
- `server/apps/agent/services/aging_alert.py` is deleted.
- `server/apps/agent/tests/unit/test_aging_alert.py` is deleted.
- No import of `aging_alert` exists anywhere in the codebase after deletion.
- All remaining agent tests pass.

---

## Scope Boundaries

- **Threshold externalization:** Not in scope. The rule-engine services that held the thresholds are dead code — the thresholds live in DeerFlow skill prompts now, not Python constants.
- **Policy rules (item 10):** `policy_guard.py` is already data-driven from the backend `CapabilityPolicy` object. No change needed.
- **Per-family threshold tuning:** Not in scope.
- **New capabilities or agent tools:** Not in scope.

---

## Success Criteria

- A user typing `/` in the Numina chat sees a list of available capabilities and can select one to pre-fill a prompt.
- `disposal_advisor.py` and `aging_alert.py` and their test files are removed; the codebase has no dangling imports.
- All existing backend and agent tests continue to pass.

---

## Dependencies

- R1 depends on the capability store (`frontend/apps/main/src/stores/capability.ts`) already being populated — confirmed by audit.
- R2 and R3 require confirming no remaining imports before deletion — grep check is part of the acceptance criteria.
- R1, R2, and R3 are independent of each other and can be implemented in any order.

---

## Files Affected

**Frontend (R1)**

| File | Change |
|------|--------|
| `server/apps/agent/skills/alerts.md` | Add `examples` or `placeholder` to frontmatter |
| `server/apps/agent/skills/disposal.md` | Add `examples` or `placeholder` to frontmatter |
| `frontend/apps/main/src/components/ai/AIChatInput.vue` | Add slash detection + capability palette |
| `frontend/apps/main/src/pages/AIChatPage.vue` | Pass capability list as prop to AIChatInput |
| `frontend/apps/main/src/i18n/locales/zh-CN.ts` | Add slash command UI strings |

**Backend cleanup (R2, R3)**

| File | Change |
|------|--------|
| `server/apps/agent/services/disposal_advisor.py` | Delete |
| `server/apps/agent/services/aging_alert.py` | Delete |
| `server/apps/agent/tests/unit/test_disposal_advisor.py` | Delete |
| `server/apps/agent/tests/unit/test_aging_alert.py` | Delete |
