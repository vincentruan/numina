---
artifact_contract: ce-unified-plan/v1
artifact_readiness: implementation-ready
product_contract_source: ce-plan-bootstrap
execution: code
title: "feat: i18n notification templates (zh-CN / en-US)"
date: 2026-09-15
---

# feat: i18n notification templates (zh-CN / en-US)

## Summary

Internationalize the backend notification template system so that messages sent via Feishu, Telegram, email, and Web Push are rendered in the family owner's language (zh-CN or en-US). The existing Chinese templates move into a locale subdirectory; new English templates are added alongside them. The environment prefix (`【测试】` / `[Test]`) follows the resolved locale.

## Problem Frame

All 11 notification templates (`server/apps/backend/app/services/notification/templates/*.json`) contain hardcoded Chinese text. When a family member uses the app in English, notifications (e.g., large-purchase reminders, AI report completion) still arrive in Chinese. The `_env_prefix()` function added in the previous commit also hardcodes a Chinese prefix.

The `User` model already stores `language` (`zh-CN` / `en-US`, default `zh-CN`), and the frontend switches UI locale from it — but the notification dispatcher has no locale awareness.

## Requirements

| ID | Requirement |
|----|-------------|
| R1 | Templates are stored per-locale: `templates/{locale}/{type}.json` |
| R2 | `render_template()` accepts a `locale` parameter and loads the matching file |
| R3 | Locale resolution: use the family owner's `User.language` (where `role='owner'`) |
| R4 | Fallback: if owner not found or `language` is empty, default to `zh-CN` |
| R5 | Locale logic: `zh-CN` → Chinese, anything else → English (`en-US`) |
| R6 | Non-production prefix is locale-aware: `【测试】` for zh-CN, `[Test]` for en-US |
| R7 | All 11 existing templates get English translations |
| R8 | No breaking changes to the `render_template()` public API — existing callers without `locale` must still work (default to `zh-CN`) |

---

## Key Technical Decisions

**KTD1 — Template directory structure: locale subdirectories** (session-settled: user-directed)

```
templates/
├── zh-CN/
│   ├── large_purchase.json
│   ├── ...
└── en-US/
    ├── large_purchase.json
    ├── ...
```

Alternative considered: locale key inside each JSON (`{"zh-CN": {...}, "en-US": {...}}`). Rejected because it makes files large, harder to review translations in bulk, and harder for non-developers to contribute translations.

**KTD2 — Language resolution: family owner** (session-settled: user-directed)

`NotificationChannel` is family-level (no user link). The user explicitly directed: "use the family unique admin's language as the family-wide notification language." Resolution:

```python
owner = db.query(User).filter_by(family_id=family_id, role='owner').first()
locale = owner.language if owner and owner.language else 'zh-CN'
```

Per-channel language settings are out of scope.

**KTD3 — Two-tier locale normalization**

User requirement: "Chinese → Chinese, everything else → English." The resolution function normalizes any locale to either `zh-CN` or `en-US`:

```python
def _normalize_locale(locale: str) -> str:
    if locale.startswith("zh"):
        return "zh-CN"
    return "en-US"
```

This means `ja-JP`, `fr-FR`, etc. all fall back to English, which is correct for a two-language app.

---

## Implementation Units

### U1. Restructure templates into locale subdirectories

**Goal:** Move existing templates from `templates/*.json` to `templates/zh-CN/*.json` without changing content.

**Requirements:** R1

**Dependencies:** none

**Files:**
- `server/apps/backend/app/services/notification/templates/` (all 11 files — move to `zh-CN/` subdirectory)

**Approach:**
1. Create `templates/zh-CN/` directory
2. Move all 11 existing JSON files into `templates/zh-CN/`
3. Content unchanged — these remain the source-of-truth Chinese templates

**Test expectation:** none — file move only, verified by U3 (render_template still loads them)

---

### U2. Create English template translations

**Goal:** Provide `en-US/` translations for all 11 notification types.

**Requirements:** R7

**Dependencies:** U1

**Files:**
- `server/apps/backend/app/services/notification/templates/en-US/` (11 new JSON files)

**Approach:**
1. Create `templates/en-US/` directory
2. For each of the 11 template files, create an English translation preserving:
   - The same JSON structure (`telegram.text`, `email.subject`, `email.body`, `feishu.text`, `webpush.title`, `webpush.body`)
   - The same `{variable}` placeholders
   - The same emoji prefixes
3. Translation guidelines:
   - Keep emoji prefixes identical
   - `【Numina】` → `[Numina]` in email subjects
   - `¥` stays as-is (currency symbol)
   - Telegram Markdown formatting (`*bold*`, `_italic_`) preserved
   - Line breaks and structure preserved

**Test scenarios:**
- Each en-US file is valid JSON
- Each en-US file has the same top-level keys as its zh-CN counterpart
- Each template string contains the same `{variable}` placeholders as the zh-CN version

---

### U3. Update `render_template()` to accept locale

**Goal:** Make the template loader resolve files by locale with fallback.

**Requirements:** R2, R5, R8

**Dependencies:** U1

**Files:**
- `server/apps/backend/app/services/notification/sender.py`

**Approach:**
1. Add `locale: str = "zh-CN"` parameter to `render_template()`
2. Normalize the locale via `_normalize_locale()` (private helper in `sender.py`)
3. Build template path: `_TEMPLATE_DIR / locale / f"{reminder_type}.json"`
4. If the locale-specific file doesn't exist, fall back to `zh-CN`
5. Existing callers (no `locale` arg) default to `zh-CN` — backward compatible

```python
def _normalize_locale(locale: str) -> str:
    if locale.startswith("zh"):
        return "zh-CN"
    return "en-US"

def render_template(reminder_type: str, channel_type: str, variables: dict, locale: str = "zh-CN") -> str:
    normalized = _normalize_locale(locale)
    template_path = _TEMPLATE_DIR / normalized / f"{reminder_type}.json"
    if not template_path.exists():
        template_path = _TEMPLATE_DIR / "zh-CN" / f"{reminder_type}.json"
    # ... rest unchanged
```

**Test scenarios:**
- `render_template("large_purchase", "feishu", {...})` returns Chinese (default locale)
- `render_template("large_purchase", "feishu", {...}, locale="en-US")` returns English
- `render_template(..., locale="ja-JP")` returns English (normalized)
- `render_template(..., locale="zh-TW")` returns Chinese (starts with "zh")
- `render_template(..., locale="en-US")` for a non-existent file falls back to zh-CN

**Verification:** Add unit test in `server/tests/backend/test_notification_sender.py` (or create if not exists)

---

### U4. Update dispatcher to resolve locale and pass to renderer

**Goal:** The dispatcher resolves the family owner's language and passes it through to `render_template()` and `_env_prefix()`.

**Requirements:** R3, R4, R6

**Dependencies:** U3

**Files:**
- `server/apps/backend/app/services/notification/dispatcher.py`

**Approach:**
1. Add `_resolve_locale(db, family_id)` helper:
   ```python
   def _resolve_locale(db: Session, family_id: int) -> str:
       owner = db.query(User).filter_by(family_id=family_id, role='owner').first()
       if owner and owner.language:
           return owner.language
       return "zh-CN"
   ```
2. Update `_env_prefix()` to accept locale:
   ```python
   def _env_prefix(locale: str = "zh-CN") -> str:
       if settings.ENVIRONMENT != "production":
           return "【测试】" if locale.startswith("zh") else "[Test]"
       return ""
   ```
3. In `_dispatch_notifications()`, resolve locale once and pass to all channel senders
4. Update `_send_feishu_async()`, `_send_telegram_async()`, `_send_webpush_sync()`, and the inline email block to:
   - Accept `locale` parameter
   - Pass `locale` to `render_template()`
   - Pass `locale` to `_env_prefix()`

**Test scenarios:**
- Family owner with `language='zh-CN'` → Chinese templates + `【测试】` prefix (in dev)
- Family owner with `language='en-US'` → English templates + `[Test]` prefix (in dev)
- Family with no owner → falls back to `zh-CN`
- Owner with empty `language` → falls back to `zh-CN`
- Production environment → no prefix regardless of locale

**Verification:** Unit test in `server/tests/backend/test_notification_dispatcher.py` with mock DB sessions

---

### U5. Backend tests

**Goal:** Comprehensive test coverage for the i18n notification pipeline.

**Requirements:** R2, R3, R4, R5, R6, R8

**Dependencies:** U3, U4

**Files:**
- `server/tests/backend/test_notification_sender.py` (create or extend)
- `server/tests/backend/test_notification_dispatcher.py` (create or extend)

**Test scenarios:**
- `test_render_template_default_locale` — no locale arg returns Chinese
- `test_render_template_en_us` — en-US returns English
- `test_render_template_normalizes_locale` — ja-JP → English, zh-TW → Chinese
- `test_render_template_fallback_missing_file` — unknown type falls back to zh-CN
- `test_resolve_locale_owner_found` — returns owner's language
- `test_resolve_locale_no_owner` — returns zh-CN
- `test_resolve_locale_empty_language` — returns zh-CN
- `test_env_prefix_zh_cn` — returns `【测试】` in dev
- `test_env_prefix_en_us` — returns `[Test]` in dev
- `test_env_prefix_production` — returns empty in production

**Verification:** `cd server && uv run pytest tests/backend/ -v -k "notification"` passes

---

## Scope Boundaries

### In Scope
- Backend template restructuring and locale resolution
- English translations for all 11 notification types
- Locale-aware environment prefix

### Deferred for Later
- Per-channel language override (user requirement is family-level only)
- Frontend notification settings UI for language selection (not needed — language is already per-user)
- User-specific notification routing (no current use case)
- Additional languages beyond zh-CN / en-US

### Not a Goal
- Changing the notification delivery mechanism
- Modifying the frontend i18n system
- Adding locale to `NotificationChannel` model

---

## Risks

| Risk | Impact | Mitigation |
|------|--------|------------|
| Existing deployments have templates at old path | Template loading fails after upgrade | `_TEMPLATE_DIR` base path unchanged; only subdirectory added. If a template file isn't found at the locale path, falls back to `zh-CN/` |
| English translations may not match user expectations | Confusing messages | Keep translations close to original meaning; emoji and structure identical |

---

## Definition of Done

1. All 11 templates exist in both `templates/zh-CN/` and `templates/en-US/`
2. `render_template()` accepts `locale` parameter with backward-compatible default
3. Dispatcher resolves locale from family owner and passes it to all render calls
4. `_env_prefix()` is locale-aware (`【测试】` / `[Test]`)
5. All new and existing notification tests pass
6. No breaking changes to the `render_template()` public API
