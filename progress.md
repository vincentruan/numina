# SDD ledger — plan: docs/superpowers/plans/2026-09-14-notification-module-enhancement.md

## Pre-flight Scan

### Task Interface Matrix

| Task Pair | Shared File/Interface | Producer → Consumer | Status |
|-----------|----------------------|---------------------|--------|
| T1 → T4 | VALID_REMINDER_TYPES | T1 defines → T4 imports | ✅ Consistent |
| T1 → T5 | NOTIFICATION_CATEGORIES | T1 defines → T5 imports | ✅ Consistent |
| T2 → T4 | digest_mode, digest_time columns | T2 adds → T4 uses in schema | ✅ Consistent |
| T2 → T5 | digest_sent_at column | T2 adds → T5 uses in _dispatch_digest | ✅ Consistent |
| T5 → T7 | _dispatch_digest | T5 defines → T7 calls | ✅ Consistent (both async) |
| T5 → T8 | notify_* functions | T5 defines → T8 calls | ✅ Consistent signatures |
| T5 → T6 | REMINDER_PIPELINE_EVENTS | T6 references event types T5 dispatches | ✅ Consistent |
| T9 → T10 | getEvents API, NotificationEventCategory | T9 defines → T10 uses | ✅ Consistent |
| T10 → T11 | EventSelectorPopup component | T10 creates → T11 imports | ✅ Consistent |

### Internal Consistency Check

| Task | Self-Consistency | Status |
|------|------------------|--------|
| T1 | Tests match implementation | ✅ |
| T2 | Migration matches model changes | ✅ |
| T3 | Templates match event types | ✅ |
| T4 | Endpoint test matches endpoint code | ✅ |
| T5 | Dispatcher hooks match test signatures | ✅ |
| T6 | Skip list matches T5 event types | ✅ |
| T7 | Job function matches scheduler registration | ✅ |
| T8 | Hook locations have family_id context | ️ Needs verification at impl time |
| T9 | API types match backend response | ✅ |
| T10 | Component props match T9 types | ✅ |
| T11 | i18n keys match T10 template usage | ✅ |

### Rulings

**Ruling 1:** Task 8 integration hooks need family_id verification at implementation time — each hook location (ai_internal.py, chores.py, child_wishes.py) must be inspected to confirm family_id is available in request context. If not, add lookup logic. — Cost if wrong: dispatcher calls fail or notify wrong family — detected at test time.

---

## Progress

### Task 1: Event Registry
- **Status:** ✅ COMPLETE
- **Commit:** `88956caa` (feat: add event registry to replace hardcoded VALID_REMINDER_TYPES)
- **Files:** registry.py (120 lines), test_notification_registry.py (51 lines)
- **Tests:** 5/5 passing
- **Review:** APPROVED (Spec ✅, Quality ✅)

### Task 2: Database Migration
- **Status:** ✅ COMPLETE
- **Commit:** `6fa3ffbf` (feat: add digest_mode, digest_time, digest_sent_at columns)
- **Bonus:** `1c9b6795` (fix: harden pre-existing migrations for fresh-DB idempotency)
- **Files:** 12 changed (3 migrations, 2 models, 1 schema, 1 registry, 1 test)
- **Review:** APPROVED (Spec ✅, Quality ✅, Pre-existing fixes ✅)

### Task 3: Notification Templates
- **Status:** ✅ COMPLETE
- **Commit:** `3dd53817` (feat: add 7 templates for new event types)
- **Files:** 7 new template JSON files (+112 lines)
- **Verification:** 42/42 renders pass (7 templates × 6 channel types)
- **Adaptations:** Nested JSON keys + plain-text email_body (verified correct)
- **Review:** APPROVED (Spec ✅, Adaptations ✅, Quality ✅)

### Task 4: API Endpoint + Router Updates
- **Status:** ✅ COMPLETE
- **Commit:** `8cc84915` (feat: add GET /events endpoint with registry-derived validation)
- **Files:** 2 changed (113 lines added)
- **Tests:** 15 passed (6 new + 4 existing + 5 registry), no regressions
- **Review:** APPROVED (Spec ✅, Quality ✅, Tests ✅)

### Task 5: Dispatcher Hooks + Mention Support + Dedup
- **Status:** Implementer dispatching next
- **Dependencies:** Tasks 1-4 ✅
- **Review:** Pending

---
