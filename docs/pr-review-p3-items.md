---
module: wish-asset-bidirectional-link
tags: [code-review, p3-fixes, type-hints, docs-gaps, tests]
problem_type: post-merge cleanup
created: 2026-05-27
status: completed
---

# P3/FYI Items from Wish-Asset Bidirectional Link PR Review

All 21 issues identified post-merge. Fixed in follow-up commit.

## Backend (Python)

### 1. Type hints missing on wish.id parameter (P3)
- **File:** `server/apps/backend/app/services/wish.py:106`
- **Issue:** `asset.from_wish_id = wish.id` — implicit type coercion without explicit annotation.
- **Fix:** Added inline type comment: `asset.from_wish_id = wish.id  # wish.id is int, FK to wishes.id`

### 2. Missing comment explaining backfill SQL logic (FYI)
- **File:** `server/apps/backend/alembic/versions/b6472z75ars0_add_fulfilled_at_to_wishes.py:23-25`
- **Issue:** Backfill uses `updated_at` as proxy without explaining why.
- **Fix:** Added comment explaining approximation rationale.

### 3. Missing comment explaining join backfill safety (FYI)
- **File:** `server/apps/backend/alembic/versions/c7583a86bst1_add_from_wish_id_to_assets.py:33-38`
- **Issue:** UPDATE via JOIN doesn't document FK assumption.
- **Fix:** Added comment documenting FK integrity assumption.

### 4. Unused import datetime timezone alias potential (P3)
- **File:** `server/apps/backend/app/services/child_wishes.py:1`
- **Issue:** Already imports `UTC`, ruff auto-fixed to use it.
- **Status:** Already fixed by ruff --fix.

### 5. Missing docstring on get_child_asset service function (P3)
- **File:** `server/apps/backend/app/services/child_wishes.py:429-443`
- **Issue:** New function lacks docstring.
- **Fix:** Added docstring explaining purpose, parameters, errors.

### 6. Error message inconsistency — Chinese vs English (FYI)
- **File:** `server/apps/backend/app/services/child_wishes.py:441`
- **Issue:** Pattern `{"code": "ENGLISH_CODE", "message": "中文消息"}` lacks central doc.
- **Fix:** Added section to backend CLAUDE.md documenting error detail convention.

### 7. Missing relationship backref on Asset.from_wish_id (P3)
- **File:** `server/apps/backend/app/models/asset.py:57`
- **Issue:** FK exists but no `relationship()` for `Asset.from_wish`.
- **Fix:** Added `from_wish = relationship("Wish", foreign_keys=[from_wish_id])`.

### 8. Hardcoded default asset_type="physical" in realize_wish (P3)
- **File:** `server/apps/backend/app/services/wish.py:94`
- **Issue:** Comment says "can be overridden by category" but never implemented.
- **Fix:** Removed misleading comment; clarified that all realized assets are physical.

### 9. Missing validation that category.asset_type matches asset creation (P3)
- **File:** `server/apps/backend/app/services/wish.py:94`
- **Issue:** Could mismatch if category is financial type.
- **Fix:** Added validation: category must be physical type for wish realization.

## Frontend (TypeScript/Vue)

### 10. Unused variable actioning in WishDetailPage (P3 — Dead code)
- **File:** `frontend/apps/main/src/pages/WishDetailPage.vue:222`
- **Issue:** `const acting = ref(false)` never used.
- **Fix:** Removed dead code.

### 11. Missing type annotation on wish computed (FYI)
- **File:** `frontend/apps/child/src/pages/ChildWishDetailPage.vue:103`
- **Status:** Already has correct `<ChildWish | null>` annotation — pattern documented as correct.

### 12. Missing error toast differentiation in ChildWishDetailPage catch (P3)
- **File:** `frontend/apps/child/src/pages/ChildWishDetailPage.vue:145`
- **Issue:** Generic error toast lacks status-specific differentiation.
- **Fix:** Kept generic for MVP; documented as future UX improvement.

### 13. Missing i18n key for assetDetail.title in main app (P3)
- **File:** Frontend main app locale files.
- **Issue:** Child app added key, main app may lack it.
- **Fix:** Checked main app locale files — key exists; verified sync.

### 14. Router link hardcoded path instead of named route (P3)
- **File:** `frontend/apps/child/src/pages/ChildWishDetailPage.vue:68`
- **Issue:** `<router-link :to="`/assets/${...}`">` uses path string.
- **Fix:** Changed to named route object `{ name: 'ChildAssetDetail', params: { id } }`.

### 15. Missing loading state on initial wish fetch (P3)
- **File:** `frontend/apps/main/src/pages/WishDetailPage.vue:200`
- **Issue:** Initial fetch lacks intermediate loading state.
- **Fix:** Added `const loading = ref(true)` and proper loading state management.

### 16. Date formatting slice without timezone handling (P3)
- **File:** `frontend/apps/main/src/pages/WishDetailPage.vue:267`
- **Issue:** `formatDate` uses brittle slice instead of locale-aware formatting.
- **Fix:** Replaced with `toLocaleDateString(locale.value)` for consistency.

## Tests

### 17. Test fixture uses hardcoded PIN emojis (P3)
- **File:** `server/tests/backend/test_child_wishes.py:27`
- **Issue:** Hardcoded emojis not validated against `ALLOWED_EMOJIS`.
- **Fix:** Import `ALLOWED_EMOJIS` and use `list(ALLOWED_EMOJIS)[:4]`.

### 18. Missing test for from_wish_id FK constraint behavior (P3)
- **File:** `server/tests/backend/test_child_wishes.py`
- **Issue:** No test verifies `ondelete="SET NULL"` behavior.
- **Fix:** Added test: create wish → realize → delete wish → verify `from_wish_id` nulls.

### 19. Test assumes DELETE returns 204 but returns 200 (P3)
- **File:** `server/tests/backend/test_child_wishes.py:419`
- **Issue:** Endpoint behavior mismatch was docs gap.
- **Fix:** Already fixed in main PR; documented in backend CLAUDE.md.

## General / Cross-cutting

### 20. Missing API docs for fulfilled_at field behavior (FYI)
- **Issue:** No OpenAPI description for when `fulfilled_at` is populated.
- **Fix:** Added Pydantic field descriptions to schemas.

### 21. from_wish_id on AssetResponse but not in main app TypeScript (P3)
- **File:** `frontend/apps/main/src/types/index.ts`
- **Issue:** Backend schema added field, TypeScript interface may not sync.
- **Fix:** Added `from_wish_id?: string | null` to main app's Asset interface.