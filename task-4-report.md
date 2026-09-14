# Task 4 Report: API Endpoint + Router Updates

## Status
DONE

## Commits
- `8cc84915` feat(notification): add GET /events endpoint with registry-derived validation

## Test Summary
15 passed (6 new + 4 existing channels + 5 registry) in 3.36s — no regressions.

## Changes

### `server/apps/backend/app/routers/notification_channels.py`
- Imported `VALID_REMINDER_TYPES` and `get_categorized_events` from `apps.backend.app.services.notification.registry`, replacing the hardcoded 3-element set
- Added `GET /events` endpoint (`get_events`) with explicit `require_adult` auth, positioned before the `GET ""` list endpoint to avoid path-parameter conflicts with `/{channel_id}`
- Wired `digest_mode` / `digest_time` into `_to_response` (reads from ORM model)
- Wired `digest_mode` / `digest_time` into `create_channel` using `getattr(req, "...", default)` as the brief specified
- Wired `digest_mode` / `digest_time` into `update_channel` with `getattr(..., None)` guard so unset fields are left alone

### `server/tests/backend/routers/test_notification_channels_events.py` (new)
- `test_get_events_returns_four_categories` — asserts 200 + 4 categories in canonical order (`asset`, `ai_task`, `children`, `wish`)
- `test_get_events_asset_category_has_three_events` — asserts `asset` has `large_purchase`, `expiring_soon`, `maturity`
- `test_get_events_requires_auth` — asserts 401/403 without auth
- `test_create_channel_persists_digest_fields` — asserts custom `digest_mode="daily"` and `digest_time="08:30"` round-trip
- `test_create_channel_digest_defaults` — asserts default `immediate` / `21:00`
- `test_create_channel_accepts_registry_event_types` — asserts ai/children/wish events are accepted (proves registry-derived validation works)

### Test conventions used (adapted from brief template)
- Used `(client, auth_headers)` as explicit function params (matching existing `test_notification_channels.py`), rather than the brief's `@pytest.mark.usefixtures("auth_headers")` style
- Unauth test uses `client` alone (no `auth_headers` arg); no `client_no_auth` fixture exists in this project
- Response envelope accessed via `resp.json()["data"]` (matching existing tests)

## Concerns
None. All tests pass; existing notification_channels + registry tests are unaffected.
