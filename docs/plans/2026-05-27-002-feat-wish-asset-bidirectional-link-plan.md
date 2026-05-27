---
date: 2026-05-27
type: feat
status: active
origin: docs/brainstorms/2026-05-27-wish-asset-modeling-requirements.md
---

# feat: Wish-Asset Bidirectional Linking

## Summary

Add `fulfilled_at` timestamps to both wish tables, a `from_wish_id` FK on assets (parent-side wishes only), parent-side router-link fix, and a new child `/assets/:id` detail page. Completes the wish→asset story arc for both parent and child.

**Scope boundaries:**
- Activity-table wish lifecycle events (R9 Activity events / R10) are deferred — blocked on OQ-2 (entity_type extension strategy). Note: the origin doc has a duplicate R9 numbering; the deferred R9 here is the Activity-events requirement, not the child-wish-detail-link R9.
- `from_wish_id` is scoped to `wishes` (parent-created) only; child-realized assets remain traceable via `child_wishes.realized_asset_id`.

---

## Problem Frame

`Wish.realized_asset_id` is a one-way link with no timestamp. Parents cannot navigate from the wish detail to the asset. Children see only a ✅ icon with no connection to the real object. Assets have no back-reference to their wish origin.

---

## Key Technical Decisions

1. **`from_wish_id` targets `wishes.id` only** — child-realized assets already have their back-reference via `child_wishes.realized_asset_id`. A separate `from_child_wish_id` column would add schema complexity with no query advantage; parent-side `from_wish_id` covers the "family ledger story" use case specified in the requirements.

2. **`fulfilled_at` added to both `wishes` and `child_wishes`** — `realize_child_wish()` mirrors `realize_wish()` structurally; omitting child-side would leave the child detail page unable to show "实现于 YYYY-MM-DD" despite OQ-4 decision to include it.

3. **New `GET /child/assets/{id}` endpoint** — existing `GET /assets/{asset_id}` uses `require_adult`. A dedicated child-scoped endpoint (bounded to `asset.user_id == current_user.id`) preserves the auth boundary and follows the existing `/child/*` pattern.

4. **Minimal `ChildAssetResponse` schema** — child page needs: `id`, `name`, `image_url`, `purchase_date`, `purchase_price`, `current_value`, `status`. Mirrors the `TreasureItem` shape; no full `AssetResponse` exposure.

5. **Migration deployment order** — `fulfilled_at` columns (both tables) + `from_wish_id` column must be deployed before service code. Two migration files: one for `wishes`/`child_wishes`, one for `assets`. Both chained to current head `x2581y64zqr9`.

6. **`datetime.now(timezone.utc)` not `datetime.utcnow()`** — Python 3.12 deprecates the latter; aware datetime avoids timezone comparison bugs (see origin doc Key Decisions).

---

## Implementation Units

### U1. Alembic Migration — fulfilled_at on wishes and child_wishes

**Goal:** Add nullable `TIMESTAMP WITH TIME ZONE` column to both wish tables. Must deploy before any service code changes.

**Requirements:** R1

**Dependencies:** None

**Files:**
- `server/apps/backend/alembic/versions/<revid>_add_fulfilled_at_to_wishes.py` *(new)*

**Approach:**
- Single migration file covering both `wishes` and `child_wishes` tables
- `op.add_column('wishes', sa.Column('fulfilled_at', sa.TIMESTAMP(timezone=True), nullable=True))`
- `op.add_column('child_wishes', sa.Column('fulfilled_at', sa.TIMESTAMP(timezone=True), nullable=True))`
- `down_revision = 'a53453cf574b'` (current head as of plan date — run `uv run alembic heads` to confirm before generating the file)
- Downgrade: `op.drop_column` on both tables

**Patterns to follow:** Recent migrations in `alembic/versions/` — short alphanumeric revision ID, snake_case description, nullable column additions use `sa.TIMESTAMP(timezone=True)` not `sa.DateTime`

**Test scenarios:**
- `alembic upgrade head` applies cleanly with no errors
- `alembic downgrade -1` removes both columns without error
- After upgrade: `wishes` and `child_wishes` tables contain `fulfilled_at` column (nullable, no default)

**Verification:** `uv run alembic upgrade head` exits 0; `uv run alembic downgrade -1` exits 0; schema inspection confirms column presence.

---

### U2. Alembic Migration — from_wish_id on assets

**Goal:** Add nullable FK `from_wish_id → wishes.id` to `assets` table with composite index `(family_id, from_wish_id)`. Must deploy before U4 service changes.

**Requirements:** R3

**Dependencies:** U1 (establishes clean migration chain)

**Files:**
- `server/apps/backend/alembic/versions/<revid>_add_from_wish_id_to_assets.py` *(new)*

**Approach:**
- `op.add_column('assets', sa.Column('from_wish_id', sa.BigInteger(), nullable=True))`
- `op.create_foreign_key('fk_assets_from_wish_id', 'assets', 'wishes', ['from_wish_id'], ['id'], ondelete='SET NULL')`
- `op.create_index('ix_assets_family_from_wish', 'assets', ['family_id', 'from_wish_id'])`
- `down_revision = '<U1_revid>'` — chained after U1
- Downgrade: drop index, drop FK constraint, drop column (in that order)

**Patterns to follow:** Existing FK migrations in `alembic/versions/` for `ondelete='SET NULL'` pattern

**Test scenarios:**
- Migration applies cleanly after U1
- `from_wish_id` column is nullable with FK constraint
- Index `ix_assets_family_from_wish` exists
- Downgrade removes index, constraint, and column without error
- FK referential integrity: inserting an asset with a non-existent `from_wish_id` raises IntegrityError

**Verification:** `uv run alembic upgrade head` exits 0; schema inspection confirms FK and index.

---

### U3. Model updates — Wish, ChildWish, Asset

**Goal:** Add ORM columns to SQLAlchemy models so service code can write to the new DB columns.

**Requirements:** R1, R3

**Dependencies:** None (development) — U1, U2 required before deployment to any environment (columns must exist in DB before models reference them in production)

**Files:**
- `server/apps/backend/app/models/wish.py` *(modify)*
- `server/apps/backend/app/models/child_wish.py` *(modify)*
- `server/apps/backend/app/models/asset.py` *(modify)*

**Approach:**
- `wish.py`: add `fulfilled_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True), nullable=True)`
- `child_wish.py`: same column definition
- `asset.py`: add `from_wish_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey('wishes.id', ondelete='SET NULL'), nullable=True)` — no relationship ORM object needed; bare FK column is sufficient since queries will use `from_wish_id` directly
- Import `datetime`, `TIMESTAMP`, `BigInteger`, `ForeignKey` where not already present

**Patterns to follow:** Existing nullable timestamp columns in `wish.py` (`created_at`, `updated_at`); existing nullable FK columns in `asset.py`

**Test scenarios:**
- ORM model instantiation succeeds without providing `fulfilled_at` or `from_wish_id`
- Setting `wish.fulfilled_at = datetime.now(timezone.utc)` persists correctly (round-trip test)
- Setting `asset.from_wish_id = <wish_id>` persists and reads back as the same integer value

**Verification:** `uv run pytest tests/ -v -k "wish or asset"` passes; `uv run alembic check` reports no pending autogenerate changes.

---

### U4. Service updates — realize_wish() and realize_child_wish()

**Goal:** Write `fulfilled_at` and `from_wish_id` (parent-side only) inside the existing atomic transactions.

**Requirements:** R1, R4

**Dependencies:** U3

**Files:**
- `server/apps/backend/app/services/wish.py` *(modify)*
- `server/apps/backend/app/services/child_wishes.py` *(modify)*

**Approach:**

`wish.py` — `realize_wish()`:
1. After creating the `Asset` object and `db.flush()`, set `wish.fulfilled_at = datetime.now(timezone.utc)`
2. Set `asset.from_wish_id = wish.id` (the wish's integer PK)
3. Existing `wish.status = "realized"` and `wish.realized_asset_id = asset.id` remain unchanged
4. Order within transaction: create asset → flush → set `wish.fulfilled_at` → set `asset.from_wish_id` → `db.commit()`
5. Import `datetime` from `datetime` and `timezone` if not already imported

`child_wishes.py` — `realize_child_wish()`:
1. After `db.flush()`, set `wish.fulfilled_at = datetime.now(timezone.utc)`
2. No `from_wish_id` write — child wishes leave this NULL on the asset (see Key Technical Decisions)
3. Existing `wish.status = "realized"` and `wish.realized_asset_id = asset.id` remain unchanged

**Patterns to follow:** Existing `db.flush()` → field assignment → `db.commit()` pattern already in both functions

**Test scenarios:**
- Happy path `realize_wish()`: returns asset; `wish.fulfilled_at` is non-NULL and recent; `asset.from_wish_id == wish.id`
- Happy path `realize_child_wish()`: returns response; `child_wish.fulfilled_at` is non-NULL and recent; `asset.from_wish_id` is NULL
- Double-realization guard: calling `realize_wish()` on an already-realized wish raises an error (existing guard via `status == "realized"` check — `fulfilled_at` will be set automatically by the guard path)
- Transaction atomicity: if `db.commit()` fails, neither `fulfilled_at` nor `from_wish_id` persists (verify via rollback simulation or existing transaction tests)

**Verification:** `uv run pytest tests/ -v -k "realize"` passes; manual DB inspection shows correct field values after API call.

---

### U5. Schema updates — WishResponse, ChildWishResponse, ParentWishResponse, AssetResponse

**Goal:** Expose `fulfilled_at` and `from_wish_id` in API responses.

**Requirements:** R2, R5

**Dependencies:** U3

**Files:**
- `server/apps/backend/app/schemas/wish.py` *(modify — WishResponse)*
- `server/apps/backend/app/schemas/child_wish.py` *(modify — ChildWishResponse, ParentWishResponse)*
- `server/apps/backend/app/schemas/asset.py` *(modify)*

**Approach:**

`wish.py` schemas:
- `WishResponse`: add `fulfilled_at: datetime | None = None`

`child_wish.py` schemas:
- `ChildWishResponse`: add `fulfilled_at: datetime | None = None`
- `ParentWishResponse`: add `fulfilled_at: datetime | None = None`
- All three already inherit `SnowflakeBase`; no serializer changes needed

`asset.py` schemas:
- `AssetResponse`: add `from_wish_id: str | None = None` (R5: bigint → string rule; SnowflakeBase passes `str` fields through unchanged)
- New minimal `ChildAssetResponse(SnowflakeBase)` with fields: `id: int`, `name: str`, `image_url: str | None`, `purchase_date: date | None`, `purchase_price: float | None`, `current_value: float | None`, `status: str`, `created_at: datetime`

**Patterns to follow:** `SnowflakeBase` inheritance pattern in existing schemas; `int | None = None` field definitions with `from_attributes=True` (via `model_config`)

**Test scenarios:**
- `WishResponse` serializes `fulfilled_at` as ISO 8601 datetime string when set; `null` when not set
- `AssetResponse` serializes `from_wish_id` as string (e.g. `"1234567890"`) when set; `null` when not set — verify no JS-precision integer leakage
- `ChildAssetResponse` serializes `id` as string (SnowflakeBase rule)
- Schema round-trip: ORM object → `model_validate()` → JSON includes all new fields

**Verification:** `uv run pytest tests/ -v -k "schema or response"` passes; `uv run python -c "from app.schemas.wish import WishResponse; print('ok')"` exits 0.

---

### U6. New child asset endpoint — GET /child/assets/{id}

**Goal:** Provide a child-scoped asset detail endpoint, bounded to the child's own assets.

**Requirements:** R8

**Dependencies:** U5

**Files:**
- `server/apps/backend/app/routers/child_wishes.py` *(modify — add endpoint to existing child router)*

**Approach:**
- Add `@router.get("/child/assets/{asset_id}", response_model=ChildAssetResponse)` to the existing child_wishes router (already handles `/child/*` routes)
- Auth dependency: `get_current_child_user` (same as other child endpoints)
- Query: `db.query(Asset).filter(Asset.id == asset_id, Asset.user_id == user.id, Asset.family_id == user.family_id).first()`
- 404 with Chinese detail: `raise HTTPException(status_code=404, detail="资产不存在")` if not found
- Return `ChildAssetResponse.model_validate(asset)`
- Decorator path is `/child/assets/{asset_id}` — the router has no additional prefix beyond `/api/v1`, matching all other child_wishes router endpoints (e.g. `/child/wishes`, `/child/wishes/{wish_id}`)

**Patterns to follow:** Existing `GET /child/wishes/{wish_id}` endpoint in same router file

**Test scenarios:**
- `GET /child/assets/{id}` with valid child auth and own asset → 200 with `ChildAssetResponse`
- `GET /child/assets/{id}` with valid child auth but asset belongs to different user → 404
- `GET /child/assets/{id}` with adult auth → 401/403 (child auth dependency rejects)
- `GET /child/assets/{id}` with non-existent asset ID → 404
- Response `id` field is serialized as string (SnowflakeBase)

**Verification:** `uv run pytest tests/ -v -k "child_asset"` passes; manual curl with child token returns 200.

---

### U7. Parent frontend — WishDetailPage router-link fix

**Goal:** Convert the static `<div>` on the parent wish detail page to a navigable `<router-link>`.

**Requirements:** R7, R2 (parent-side fulfilled_at display)

**Dependencies:** None (purely frontend; can land independently)

**Files:**
- `frontend/apps/main/src/pages/WishDetailPage.vue` *(modify)*
- `frontend/apps/main/src/i18n/locales/zh-CN.ts` *(modify)*
- `frontend/apps/main/src/i18n/locales/en-US.ts` *(modify)*

**Approach:**
```vue
<!-- Before (line ~55) -->
<div v-if="wish.realized_asset_id" class="hero-realized-info">
  {{ t('wish.realizedAsset') }}
</div>

<!-- After -->
<div v-if="wish.realized_asset_id" class="hero-realized-info">
  <p v-if="wish.fulfilled_at" class="fulfilled-date">
    {{ t('wish.fulfilledAt', { date: new Date(wish.fulfilled_at).toLocaleDateString(locale, { year: 'numeric', month: '2-digit', day: '2-digit' }) }) }}
  </p>
  <router-link :to="`/assets/${wish.realized_asset_id}`">
    {{ t('wish.realizedAsset') }} →
  </router-link>
</div>
```
- Update `wish.realizedAsset` i18n key value to include `' →'` suffix (keeps all user-visible text in locale files)
- Add `wish.fulfilledAt` key with value `'实现于 {date}'` — use Vue i18n named interpolation
- Use `locale` from `useI18n()` for date formatting (never hardcode `'zh-CN'`)
- Verify `/assets/:id` route exists in the main app router before landing

`zh-CN.ts` additions:
- `wish.fulfilledAt`: `'实现于 {date}'`
- Update `wish.realizedAsset`: append ` →` to existing value

`en-US.ts` additions:
- `wish.fulfilledAt`: `'Fulfilled on {date}'`
- Update `wish.realizedAsset`: append ` →` to existing value

**Patterns to follow:** Other `<router-link>` usages in `frontend/apps/main/src/pages/`; `useI18n()` locale usage for date formatting

**Test scenarios:**
- Wish with `realized_asset_id` and `fulfilled_at` set: shows "实现于 YYYY-MM-DD" date line + "已转为资产 →" router-link
- Wish with `realized_asset_id` but `fulfilled_at` null: shows link only, no date line
- Wish without `realized_asset_id`: entire block not rendered (v-if guard)
- Clicking the link navigates to `/assets/<id>` (manual smoke test)
- No TypeScript errors (`npm run typecheck` passes)

**Verification:** `npm run typecheck` from `frontend/apps/main` passes; visual inspection confirms date + link render correctly.

---

### U8. Child frontend — new ChildAssetDetailPage + router route

**Goal:** Create a new `/assets/:id` detail page in the child SPA with its own route.

**Requirements:** R8

**Dependencies:** U6 (backend endpoint must exist)

**Files:**
- `frontend/apps/child/src/pages/ChildAssetDetailPage.vue` *(new)*
- `frontend/apps/child/src/router/index.ts` *(modify — add route)*
- `frontend/apps/child/src/api/assets.ts` *(new)*
- `frontend/apps/child/src/i18n/locales/zh-CN.ts` *(modify)*
- `frontend/apps/child/src/i18n/locales/en-US.ts` *(modify)*

**Approach:**

`api/assets.ts`:
- `ChildAsset` interface: `{ id: string; name: string; image_url: string | null; purchase_date: string | null; purchase_price: number | null; current_value: number | null; status: string; created_at: string }`
- `getChildAsset(id: string): Promise<ChildAsset>` — calls `GET /child/assets/${id}`
- Follow pattern of `frontend/apps/child/src/api/childWishes.ts`

`router/index.ts`:
- Add `{ path: 'assets/:id', component: () => import('../pages/ChildAssetDetailPage.vue') }` as a child of the layout route
- Verify the catch-all redirect does not intercept this new path (ordering matters)

`ChildAssetDetailPage.vue`:
- Fetch asset via `getChildAsset(route.params.id as string)` in `onMounted`
- Display: asset name, status badge, purchase_date formatted as YYYY-MM-DD, purchase_price / current_value
- Loading state: centered `t('common.loading')` text, matching `ChildWishDetailPage.vue` pattern
- 404/error state: show an empty-state card (emoji + `t('assets.notFound')` message + back button pointing to `/wishes`) — do not silently redirect; follows `ChildWishDetailPage.vue` empty-state pattern
- All strings via `t('assets.*')` keys — no hardcoded Chinese
- Follow Clay design system conventions (`frontend/apps/child/DESIGN.md`)
- Back navigation button: use `router.replace({ path: '/wishes' })` — not `router.back()` (history may be empty on direct-link entry); matches the pattern in `ChildWishCreatePage.vue`

`zh-CN.ts` additions (under `assets` namespace):
- `assets.title`: `'资产详情'`
- `assets.purchaseDate`: `'购入日期'`
- `assets.purchasePrice`: `'购入价格'`
- `assets.currentValue`: `'当前价值'`
- `assets.statusInUse`: `'使用中'`
- `assets.statusIdle`: `'闲置'`
- `assets.statusSold`: `'已出售'`
- `assets.statusRetired`: `'已退役'`
- `assets.notFound`: `'⚠️ 找不到该资产'`

`en-US.ts` additions (under `assets` namespace):
- `assets.title`: `'Asset Details'`
- `assets.purchaseDate`: `'Purchase Date'`
- `assets.purchasePrice`: `'Purchase Price'`
- `assets.currentValue`: `'Current Value'`
- `assets.statusInUse`: `'In Use'`
- `assets.statusIdle`: `'Idle'`
- `assets.statusSold`: `'Sold'`
- `assets.statusRetired`: `'Retired'`
- `assets.notFound`: `'⚠️ Asset not found'`

In `ChildAssetDetailPage.vue`, map `status` to i18n key via a computed map (same pattern as `AssetDetailPage.vue` in the main app):
```ts
const statusLabelKey: Record<string, string> = {
  in_use: 'assets.statusInUse',
  idle: 'assets.statusIdle',
  sold: 'assets.statusSold',
  retired: 'assets.statusRetired',
}
```

**Patterns to follow:** `ChildWishDetailPage.vue` for page structure; `ChildTreasuresPage.vue` for asset-like display; `frontend/apps/child/src/api/childWishes.ts` for API module pattern

**Test scenarios:**
- Navigating to `/assets/:id` with valid child-owned asset ID → page renders with name and details
- Navigating to `/assets/:id` with non-owned or non-existent ID → shows 404 state or redirects to `/wishes`
- Back button returns to previous page
- All displayed strings come from i18n keys (no hardcoded Chinese)
- `npm run typecheck` passes (child app)

**Verification:** `npm run typecheck` from `frontend/apps/child` passes; `npm run test:run` passes.

---

### U9. Child frontend — ChildWishDetailPage realized link + fulfilled_at display

**Goal:** Show "愿望实现了！点击查看 →" link and "实现于 YYYY-MM-DD" date on the child wish detail page when the wish is realized.

**Requirements:** R2 (child-side fulfilled_at display), R9

**Dependencies:** U5 (ChildWishResponse exposes fulfilled_at and realized_asset_id), U8 (child asset route exists)

**Files:**
- `frontend/apps/child/src/pages/ChildWishDetailPage.vue` *(modify)*
- `frontend/apps/child/src/api/childWishes.ts` *(modify — add `fulfilled_at: string | null` to `ChildWish` interface)*
- `frontend/apps/child/src/i18n/locales/zh-CN.ts` *(modify)*
- `frontend/apps/child/src/i18n/locales/en-US.ts` *(modify)*

**Approach:**
- The page already fetches all wishes and finds by ID — `wish.realized_asset_id` is already in the `ChildWish` interface
- Add `fulfilled_at: string | null` to the `ChildWish` TypeScript interface in `frontend/apps/child/src/api/childWishes.ts`
- When `wish.status === 'realized'`:
  - **Replace** the existing `<span class="status-line">{{ t('wishes.realized') }}</span>` with a structured block:
    1. Date line (shown only if `wish.fulfilled_at` is non-null): `<p class="fulfilled-date">{{ t('wishes.fulfilledAt', { date: ... }) }}</p>`
    2. Router-link below it: `<router-link :to="\`/assets/${wish.realized_asset_id}\`">{{ t('wishes.viewLinkedAsset') }}</router-link>` (shown only if `realized_asset_id` is non-null)
  - Remove the standalone `wishes.realized` span — the link text `'愿望实现了！点击查看 →'` serves the same purpose with added navigation affordance
- Format `fulfilled_at` using `new Date(wish.fulfilled_at).toLocaleDateString(locale.value, {year:'numeric',month:'2-digit',day:'2-digit'})` — import `const { t, locale } = useI18n()` (never hardcode `'zh-CN'`, per child CLAUDE.md §i18n)

`zh-CN.ts` additions (under `wishes` namespace):
- `wishes.fulfilledAt`: `'实现于 {date}'` (or format inline in template with `t` + computed)
- `wishes.viewLinkedAsset`: `'愿望实现了！点击查看 →'`

**Patterns to follow:** Existing `v-if="wish.status === 'realized'"` block in `ChildWishDetailPage.vue`; `<router-link>` usage in other child pages

**Test scenarios:**
- Realized wish with `realized_asset_id` and `fulfilled_at`: shows "实现于 2026-05-27" and "愿望实现了！点击查看 →" link
- Realized wish with `realized_asset_id` but `fulfilled_at` null: shows link but omits date (graceful null handling)
- Realized wish with `realized_asset_id` null: link not rendered (v-if guard)
- Unrealized wish: neither date nor link renders
- Clicking link navigates to `/assets/${realized_asset_id}`
- `npm run typecheck` passes (child app)

**Verification:** `npm run typecheck` from `frontend/apps/child` passes; `npm run test:run` passes.

---

### U10. Parent frontend — AssetDetailPage from_wish_id display

**Goal:** Show "来自心愿：{name}" entry on the parent asset detail page with a link to the wish.

**Requirements:** R6

**Dependencies:** U5 (AssetResponse exposes from_wish_id)

**Files:**
- `frontend/apps/main/src/pages/AssetDetailPage.vue` *(modify)*
- `frontend/apps/main/src/api/assets.ts` *(modify — add `from_wish_id: string | null` to the `Asset` TypeScript interface; confirm exact file path at implementation time)*
- `frontend/apps/main/src/i18n/locales/zh-CN.ts` *(modify)*
- `frontend/apps/main/src/i18n/locales/en-US.ts` *(modify)*

**Approach:**
- Locate the `Asset` TypeScript interface in the main app API module (likely `frontend/apps/main/src/api/assets.ts`) and add `from_wish_id: string | null` — required for `asset.from_wish_id` to type-check in the template
- `AssetResponse` already includes `from_wish_id: string | null` after U5
- If `asset.from_wish_id` is non-null, render a section showing "来自心愿：{wish name}"
- The wish name is not in `AssetResponse` — two options:
  - (a) Fetch the wish separately via existing `GET /wishes/{id}` using `from_wish_id` and extract the name
  - (b) Embed `from_wish_name: str | None` in `AssetResponse` (denormalized, set at query time in the assets endpoint)
  - **Recommended: option (a)** — lazy fetch on demand, avoids schema coupling. Only fires when `from_wish_id` is non-null.
- Render as `<router-link :to="\`/wishes/${asset.from_wish_id}\`">来自心愿：{{ wishName }}</router-link>`
- While secondary fetch is in-flight: show the row with a placeholder dash `'—'` for the name (prevents layout shift)
- Wrap secondary fetch in try/catch: on any error (404, 401, 500), set `wishName = null` and hide the section silently — no toast, no thrown error; the asset detail page is fully usable without the wish name

`zh-CN.ts` additions:
- `asset.fromWish`: `'来自心愿：'`

**Patterns to follow:** Existing secondary-fetch patterns in `AssetDetailPage.vue` if any; otherwise follow the pattern from `WishDetailPage.vue`

**Test scenarios:**
- Asset with `from_wish_id` set: "来自心愿：{name}" renders as a link; clicking navigates to `/wishes/{id}`
- Asset with `from_wish_id` null: section not rendered
- Secondary wish fetch fails (404): section not rendered or shows fallback (no hard crash)
- `npm run typecheck` passes (main app)

**Verification:** `npm run typecheck` from `frontend/apps/main` passes; visual confirmation of link render.

---

## Scope Boundaries

### Deferred (conditional on OQ-2)
- R9 (Activity events) / R10 — Activity-table wish lifecycle events (`wish_created`, `wish_realized`, `wish_cancelled`). Blocked on deciding whether to extend `entity_type` values or create a separate `wish_events` table.

### Deferred to Follow-Up Work
- `fulfillment_note` field — low-effort v1.1 addition (see origin doc Scope Boundaries)
- `Wish.status` enum extension (new `approved` value)
- Anniversary reminder push notifications (requires push notification infrastructure)
-承诺负债 dashboard card — pending UX validation with parents

### Not in scope
- Changes to `GET /assets/{asset_id}` adult auth (child uses new `/child/assets/{id}` endpoint)
- Full `AssetResponse` exposure to child (child gets lean `ChildAssetResponse` only)

---

## System-Wide Impact

| Layer | Change | Risk |
|-------|--------|------|
| DB schema | 3 new nullable columns + 1 FK + 1 index | Low — additive only |
| Backend services | 2 transaction writes added | Low — within existing atomic boundary |
| Backend schemas | 4 schema field additions + 1 new schema | Low — additive, backward-compatible |
| Backend routers | 1 new child-scoped endpoint | Low — follows existing pattern |
| Frontend (main) | 1 `<div>` → `<router-link>` swap + 1 secondary fetch on asset detail | Low |
| Frontend (child) | 1 new page + 1 new route + 1 API module + updates to 2 existing pages | Medium — new surface |
| Migrations | 2 migration files, must deploy before code | High if order violated |

---

## Risks & Dependencies

1. **Migration ordering** (High if violated) — U1+U2 must deploy before U4 goes live. Service code writing `wish.fulfilled_at = ...` raises `OperationalError` if the column doesn't exist. Mitigate: deploy migrations first in Docker CI pipeline; document in PR description.

2. **Child auth boundary** (Medium) — U6 adds a new child-accessible endpoint. Must verify `get_current_child_user` dependency correctly rejects adult tokens and family-isolation is enforced via `Asset.family_id == user.family_id`.

3. **`from_wish_id` nullable FK with ondelete=SET NULL** (Low) — if a wish is deleted, the asset's `from_wish_id` silently becomes NULL. This is intentional (assets survive wish deletion) but means the "来自心愿" link on the asset detail page must handle the null case gracefully.

4. **Child wish list fetch pattern** (Low) — `ChildWishDetailPage.vue` fetches all wishes and filters client-side. If `fulfilled_at` is added to the response but the list endpoint doesn't include it, the detail page won't see it. Verify the child wish list endpoint uses `ChildWishResponse` (which will have `fulfilled_at` after U5).

---

## Deferred Implementation Notes

- The exact revision IDs for U1 and U2 migrations will be generated by Alembic at implementation time — use `uv run alembic revision` to get the IDs and chain U2's `down_revision` to U1's generated ID.
- The `AssetDetailPage.vue` wish-name secondary fetch (U10 option a): implementation should check whether a `useWish(id)` composable already exists before writing new fetch logic.
- i18n keys for child app must be added to both `zh-CN.ts` and `en-US.ts` (check if `en-US.ts` exists in child app; if not, follow the pattern from `frontend/apps/main`).
