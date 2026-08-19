---
name: button-ui-audit-fix
description: Audit and fix mobile button style issues — touch targets, hardcoded hex colors, missing dark mode, Vant 4 consistency
---

# Button UI Audit & Fix Plan — COMPLETE ✅

## Tasks Completed

### Phase 1: P0 — Sub-size Touch Target Fix ✅
- [x] **Task 1.1**: Fixed `.grant-btn` in BabyPage (24px→32px, 11px→13px font)

### Phase 2: P0 — Hardcoded Hex Colors → CSS Variables ✅
- [x] **Task 2.1**: BabyPage wish-card/chore-card action buttons — 7 variants use CSS vars + dark mode
- [x] **Task 2.2**: BabyPage dialog buttons — 4 classes use CSS vars + dark mode

### Phase 3: P1 — WishCostEditDialog Dark Mode ✅
- [x] **Task 3.1**: Added dark mode overrides for `.btn-cancel` and `.btn-confirm`

### Phase 4: P1 — BabyPage / FamilyPage Missing Dark Mode ✅
- [x] **Task 4.1**: BabyPage action-btn dark mode active states
- [x] **Task 4.2**: FamilyPage action-btn dark mode color adjustments + active state

## Verification
- [x] Typecheck: 0 errors
- [x] Tests: 1228 passed, 0 failed
- [x] No duplicate CSS declarations
