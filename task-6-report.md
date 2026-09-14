# Task 6 Report: Prevent Duplicate Webpush for Reminder-Pipeline Events

**Status:** DONE
**Date:** 2026-09-14
**Commit:** `927be46f`

## Summary

Added a skip list to `push_service.send_family_interaction_push()` so that events already handled by the reminder/dispatcher pipeline (Task 5) do not produce duplicate webpush notifications.

## Problem

The reminder/dispatcher pipeline (Task 5) creates reminders for `chore_completed`, `treasure_redeemed`, and `wish_redeemed` events and dispatches push notifications on their behalf. If `push_service.send_family_interaction_push()` were also called for these same event types (e.g., from router-level R12 hooks), users would receive two push notifications for a single event — one from the dispatcher and one from the direct push path.

## Changes

### 1. `server/apps/backend/app/services/notification/push_service.py`

- Added module-level constant:
  ```python
  REMINDER_PIPELINE_EVENTS: set[str] = {
      "chore_completed",
      "treasure_redeemed",
      "wish_redeemed",
  }
  ```
- Added early-return guard at the top of `send_family_interaction_push()`:
  ```python
  if reminder_type in REMINDER_PIPELINE_EVENTS:
      logger.debug("Skipping push for %s — handled by reminder pipeline", reminder_type)
      return
  ```
- Updated function docstring to document the skip behavior.

### 2. `server/tests/backend/test_web_push.py`

Added two new tests:

- `test_push_service_skips_reminder_pipeline_events` — verifies `send_webpush` is NOT called for any event in `REMINDER_PIPELINE_EVENTS`.
- `test_push_service_sends_for_non_pipeline_events` — verifies `send_webpush` IS still called for events outside the skip list (e.g., `family_interaction`).

## Verification

- Ruff lint: `All checks passed!`
- Module imports cleanly: `REMINDER_PIPELINE_EVENTS = {'chore_completed', 'treasure_redeemed', 'wish_redeemed'}`
- Full notification test suite: **29 passed** (27 pre-existing + 2 new)
  - `tests/backend/test_web_push.py` — 11 passed
  - `tests/backend/test_notification_channels.py` — 4 passed
  - `tests/backend/test_notification_rules.py` — 9 passed
  - `tests/backend/services/test_notification_registry.py` — 5 passed

## Design Notes

- The skip set is defined at module level as a `set[str]` for O(1) lookup and easy extension if more events are later moved into the reminder pipeline.
- The early return happens **before** the lazy import of `NotificationSender`, so skipped events pay zero import/DB cost.
- A `logger.debug` message is emitted on skip for observability without polluting logs at normal level.
- The guard is defensive: currently no caller in the codebase passes these reminder_type values to `send_family_interaction_push` (the only caller in `chores.py` passes `"family_interaction"`), but future refactors that consolidate event dispatch must not accidentally re-introduce duplicate pushes.
