---
title: feat: Replace emoji icons with SVG icon system
type: feat
status: active
date: 2026-04-05
origin: docs/brainstorms/2026-04-05-svg-icon-system-requirements.md
---

# SVG Icon System Implementation Plan

## Overview

Replace emoji-based category and UI icons with a themed SVG sprite system. This addresses accessibility barriers, enables dark mode theming via `currentColor`, and provides consistent cross-platform rendering across 9 frontend files and 1 utility.

## Problem Frame

Numina's mobile H5 app uses emoji characters (🏠🚗📱💰) for category icons and status indicators. Emojis render inconsistently across platforms, cannot be themed for dark mode, and screen readers announce them unpredictably. This creates accessibility barriers and visual inconsistency with the Vant icon system used in the tab bar.

## Requirements Trace

- R1. All category and UI icons shall use SVG format in a sprite sheet at `public/icons.svg`
- R2. Icons shall use `currentColor` for fill/stroke to inherit text color and support theming
- R3. Each icon shall have a unique ID following the pattern `icon-{name}`
- R4. Icon fallback: If a referenced icon ID does not exist, render default `icon-other`
- R5. Replace all 21 category emoji icons with custom-designed SVG icons matching Vant's line-art style
- R6. Category icons (21 physical + financial) shall be created: `icon-home`, `icon-car`, `icon-digital`, `icon-appliance`, `icon-furniture`, `icon-jewelry`, `icon-clothing`, `icon-beauty`, `icon-sports`, `icon-toys`, `icon-pets`, `icon-music`, `icon-bags`, `icon-deposit`, `icon-fund`, `icon-stock`, `icon-bond`, `icon-insurance`, `icon-wealth`, `icon-crypto`, `icon-other-finance`
- R7. Liability icons (5) shall be created: `icon-mortgage`, `icon-car-loan`, `icon-credit-card`, `icon-personal-loan`, `icon-other-liability`
- R8. Alert icons (3) shall be created: `icon-idle`, `icon-expiring`, `icon-warning`
- R9. Fallback icon `icon-other` shall be created for missing icon references
- R10. Decorative icons (accompanying visible text labels) shall use `aria-hidden="true"`
- R11. Standalone icons (without visible labels) shall include `aria-label` describing their purpose
- R12. CategoryGrid.vue shall render SVG icons using inline `<svg><use>` pattern
- R13. AssetCard.vue fallback icon shall use the category's SVG icon instead of emoji
- R14. LiabilityCard.vue shall reference SVG icons from the sprite instead of hardcoded emoji map
- R15. AlertCards.vue shall use SVG icons instead of hardcoded emojis
- R16. AssetDetailPage.vue, AssetListItem.vue shall use SVG icons for category display
- R17. LiabilityDetailPage.vue, LiabilityForm.vue shall use SVG icons for liability type icons
- R18. shareImage.ts shall render SVG icons in share images
- R19. Database `categories.icon` column shall be expanded from `String(10)` to `String(50)`
- R20. Seed data `SYSTEM_CATEGORIES` shall be updated from emoji strings to icon IDs
- R21. Migration script shall convert existing emoji icons to icon IDs for system categories only

## Scope Boundaries

- Out of scope: Redesigning category taxonomy or adding new categories
- Out of scope: Replacing Vant icons in the tab bar (already consistent)
- Out of scope: Custom icons for user-uploaded assets (use category icon as fallback)
- Out of scope: Custom icon designs for user-created categories (they may retain emoji)

## Success Criteria

**Technical outcomes:**
- All 30 icons render consistently across iOS Safari, Android Chrome, and desktop browsers
- Icons adapt to dark mode via `currentColor` (no hardcoded fill colors)
- Lighthouse accessibility score improves from current baseline (target: +5 points)
- No "Elements describe contents with emoji" warnings in Lighthouse audit

**User outcomes:**
- Screen readers announce icons correctly (aria-hidden for decorative, aria-label for standalone)
- Keyboard users can navigate CategoryGrid with visible focus indicators
- Touch targets meet 44x44pt minimum for all interactive icon areas

**Validation:**
- Icon semantic clarity verified through quick review (icons clearly represent their categories to Chinese users)

## Context & Research

### Relevant Code and Patterns

- **Existing SVG sprite**: `frontend/public/icons.svg` uses `<symbol id="name-icon">` pattern with hardcoded fill colors
- **CategoryGrid**: `frontend/src/components/asset/CategoryGrid.vue` — renders `{{ cat.icon }}` as emoji text
- **AssetCard**: `frontend/src/components/asset/AssetCard.vue` — uses `{{ asset.category?.icon || '📦' }}`
- **LiabilityCard**: `frontend/src/components/liability/LiabilityCard.vue` — hardcoded `categoryMap` with emoji strings
- **AlertCards**: `frontend/src/components/dashboard/AlertCards.vue` — direct emoji literals
- **Category model**: `backend/app/models/category.py` — `icon: Mapped[str] = mapped_column(String(10))` (too short for icon IDs)
- **Seed data**: `backend/app/seed/categories.py` — `SYSTEM_CATEGORIES` uses emoji icons
- **AssetDetailPage**: `frontend/src/pages/AssetDetailPage.vue` — uses `{{ asset.category?.icon || '📦' }}`
- **AssetListItem**: `frontend/src/components/asset/AssetListItem.vue` — uses `{{ asset.category?.icon || '📦' }}`
- **LiabilityDetailPage**: `frontend/src/pages/LiabilityDetailPage.vue` — has `categoryMap` with emojis
- **LiabilityForm**: `frontend/src/components/liability/LiabilityForm.vue` — has `categoryColumns` with emojis
- **shareImage**: `frontend/src/utils/shareImage.ts` — renders emoji in share images

### Institutional Learnings

No relevant institutional learnings exist in `docs/solutions/` for SVG icons, database migrations, or accessibility patterns.

### External References

- Vant icons use 1.5px stroke width for line-art consistency
- WCAG 2.1 requires 4.5:1 contrast ratio for text/icons
- `currentColor` allows SVG to inherit text color from CSS

## Key Technical Decisions

- **Direct icon field migration**: Replace `icon` field values from emoji to icon IDs (e.g., "🏠" → "icon-home") rather than adding a separate `svg_icon` field. Simpler data model, no fallback complexity.
- **Inline SVG pattern**: Use `<svg><use :href="`#icon-${iconId}`" /></svg>` directly in components rather than creating an `<AppIcon>` component. Only 4 use sites, not worth the abstraction cost.
- **currentColor for theming**: All SVG paths use `stroke="currentColor"` or `fill="currentColor"` to automatically adapt to light/dark themes via CSS color inheritance.
- **24x24 viewBox**: Standard size matching Vant icons, optimized for 22-24px rendering.
- **1.5px stroke width**: Matches Vant's visual style for consistency.

## Open Questions

### Resolved During Planning

- **Icon design source**: Adapt icons from Lucide/Heroicons where semantic match exists, design custom icons only where no open-source equivalent exists.
- **Migration approach**: One-time migration script rather than modifying `seed_categories()` function, since it only affects existing system category records.

### Deferred to Implementation

- **Exact SVG path specifications**: Each of the 30 icons will be designed/adapted during implementation, referencing Vant's 1.5px stroke style.

## Implementation Units

- [ ] **Unit 1: Database schema migration**

**Goal:** Expand `categories.icon` column from `String(10)` to `String(50)` to accommodate icon ID format.

**Requirements:** R19

**Dependencies:** None

**Files:**
- Create: `backend/alembic/versions/XXXX_expand_icon_field_length.py`
- Modify: `backend/app/models/category.py`

**Approach:**
1. Create Alembic migration with `op.alter_column` to expand icon field length
2. Update model definition to `String(50)`
3. Migration must run before data migration (Unit 3)

**Patterns to follow:**
- Existing migrations in `backend/alembic/versions/`
- Model uses `Mapped[str]` with `mapped_column(String(N))`

**Test scenarios:**
- Happy path: Migration runs successfully on SQLite, MySQL, PostgreSQL
- Edge case: Existing emoji icons (1-2 chars) remain intact after migration
- Integration: Application starts without errors after migration

**Verification:**
- Migration applies cleanly with `alembic upgrade head`
- Model reflects new field length
- Existing category data preserved

---

- [ ] **Unit 2: Create SVG icon sprite**

**Goal:** Create `icons.svg` sprite with 30 icons (21 category + 5 liability + 3 alert + 1 fallback) using `currentColor` and `icon-{name}` ID pattern.

Note: 21 category icons are split into 13 physical and 8 financial categories, plus 5 liability icons, 3 alert icons, and 1 fallback = 30 total.

**Requirements:** R1, R2, R3, R5-R9

**Dependencies:** None (can run in parallel with Unit 1)

**Files:**
- Modify: `frontend/public/icons.svg`

**Approach:**
1. Evaluate Vant 4 built-in icons first for semantic matches (e.g., `home-o`, `shopping-cart-o`, `gold-coin-o`)
2. Design custom icons only where Vant lacks semantic equivalent or visual match is too abstract
3. Validate icon semantics with quick review by Chinese speakers before finalizing
4. Use 24x24 viewBox for all icons
4. Apply `stroke="currentColor"` for line-art icons, `fill="currentColor"` for solid icons
5. Migrate existing `{name}-icon` pattern to `icon-{name}` pattern (e.g., `bluesky-icon` → `icon-bluesky`)
6. Follow `icon-{name}` naming convention for all new icons
7. Include fallback `icon-other` for missing icons

**Icon size guidelines:**
- 18px: Inline list items (LiabilityCard)
- 22px: Grid items (CategoryGrid)
- 24px: Card icons (AlertCards)
- 36px: Large feature icons (AssetCard)

**Icon list to create:**
- Category (21): `icon-home`, `icon-car`, `icon-digital`, `icon-appliance`, `icon-furniture`, `icon-jewelry`, `icon-clothing`, `icon-beauty`, `icon-sports`, `icon-toys`, `icon-pets`, `icon-music`, `icon-bags`, `icon-deposit`, `icon-fund`, `icon-stock`, `icon-bond`, `icon-insurance`, `icon-wealth`, `icon-crypto`, `icon-other-finance`
- Liability (5): `icon-mortgage`, `icon-car-loan`, `icon-credit-card`, `icon-personal-loan`, `icon-other-liability`
- Alert (3): `icon-idle`, `icon-expiring`, `icon-warning`
- Fallback (1): `icon-other`

**Test scenarios:**
- Happy path: All 30 icons render at 22px, 24px, 36px without distortion
- Visual: Icons match Vant's line-art style (1.5px stroke, consistent weight)
- Theme: `currentColor` correctly inherits from parent text color in light/dark modes
- Accessibility: Screen reader ignores decorative icons with `aria-hidden`

**Verification:**
- Sprite file contains all 30 `<symbol>` elements
- Each symbol has correct `id` and `viewBox`
- All paths use `currentColor` (no hardcoded fill colors)
- Icons render correctly in browser at multiple sizes
- Icon semantics validated by Chinese speaker review

---

- [ ] **Unit 3: Migrate category icon data**

**Goal:** Update `categories.icon` field from emoji strings to icon IDs for all 21 system categories.

**Requirements:** R20, R21

**Dependencies:** Unit 1 (schema migration)

**Files:**
- Modify: `backend/app/seed/categories.py`
- Create: `backend/scripts/migrate_icons.py` (one-time migration script)

**Approach:**
1. Create `backend/scripts/` directory if it doesn't exist
2. Update `SYSTEM_CATEGORIES` in seed data to use icon IDs
3. Create migration script to update existing database records:
   - Map emoji → icon ID using the mapping table from requirements
   - Update only system categories (`is_system=True`)
   - Preserve custom user categories
4. Run migration against database

**Emoji-to-IconID Mapping:**
| Emoji | Icon ID |
|-------|---------|
| 🏠 | icon-home |
| 🚗 | icon-car |
| 📱 | icon-digital |
| 📺 | icon-appliance |
| 🛋️ | icon-furniture |
| 💎 | icon-jewelry |
| 👔 | icon-clothing |
| 💄 | icon-beauty |
| ⚽ | icon-sports |
| 🎮 | icon-toys |
| 🐾 | icon-pets |
| 🎸 | icon-music |
| 👜 | icon-bags |
| 🏦 | icon-deposit |
| 📊 | icon-fund |
| 📈 | icon-stock |
| 📜 | icon-bond |
| 🛡️ | icon-insurance |
| 💰 | icon-wealth |
| ₿ | icon-crypto |
| 💳 | icon-other-finance |

**Patterns to follow:**
- Existing seed data structure in `categories.py`
- Database session patterns from existing code

**Test scenarios:**
- Happy path: All 21 system categories updated with icon IDs
- Edge case: Custom user categories with emoji icons remain unchanged
- Integration: New database seeded with icon IDs correctly

**Verification:**
- Query shows all system categories have `icon` values starting with `icon-`
- Custom categories (if any) retain original emoji values
- Seed function works for fresh database

---

- [ ] **Unit 4: Update CategoryGrid component**

**Goal:** Replace emoji rendering with SVG icon pattern in CategoryGrid.

**Requirements:** R12

**Dependencies:** Unit 2 (SVG sprite), Unit 3 (icon data)

**Files:**
- Modify: `frontend/src/components/asset/CategoryGrid.vue`

**Approach:**
1. Replace `{{ cat.icon }}` with inline SVG pattern:
   ```vue
   <svg class="category-icon" aria-hidden="true">
     <use :href="`#${cat.icon.startsWith('icon-') ? cat.icon : 'icon-other'}`" />
   </svg>
   ```
2. Add CSS for `.category-icon` (22px size, inherits color)
3. Handle fallback: if `cat.icon` is emoji (no `icon-` prefix) or is an unknown custom category icon, show `icon-other`
4. Custom user categories with emoji icons: display emoji as fallback text, wrapped in span for consistent sizing
5. Add focus state: visible outline when parent button is focused (WCAG 2.1 requirement)
6. Add active/pressed state: subtle `scale(0.95)` transform on tap for tactile feedback
7. Selected state: icon inherits category color (no special treatment, uses existing selection styling from parent)

**Patterns to follow:**
- Existing CSS patterns for `.icon` class
- Vue template syntax for dynamic attributes

**Test scenarios:**
- Happy path: All category icons render as SVG with correct symbol reference
- Edge case: Missing icon ID falls back to `icon-other`
- Accessibility: `aria-hidden="true"` present for screen readers
- Theme: Icon color adapts to light/dark mode via `currentColor`

**Verification:**
- No emoji characters visible in CategoryGrid (except custom user categories displaying as fallback)
- All icons render with correct SVG references
- Touch targets verified using Chrome DevTools device mode (inspect tap area dimensions)
- Touch targets remain accessible (44x44pt minimum)
- Focus states visible with keyboard navigation
- Dark mode icons correctly colored

---

- [ ] **Unit 5: Update AssetCard component**

**Goal:** Replace emoji fallback with SVG icon in AssetCard.

**Requirements:** R13

**Dependencies:** Unit 2 (SVG sprite), Unit 3 (icon data)

**Files:**
- Modify: `frontend/src/components/asset/AssetCard.vue`

**Approach:**
1. Replace `{{ asset.category?.icon || '📦' }}` with SVG pattern
2. Handle fallback when category is null (use `icon-other`)
3. Maintain colored circular background for icon
4. Size: 36px to match current emoji size

**Patterns to follow:**
- Existing `.card-icon` CSS styling
- Vue optional chaining for null safety

**Test scenarios:**
- Happy path: Asset with category shows category's SVG icon
- Edge case: Asset without category shows `icon-other`
- Visual: Icon centered in colored circular background
- Accessibility: `aria-hidden="true"` on decorative icon

**Verification:**
- No emoji fallback (`📦`) in AssetCard
- Icons render correctly at 36px
- Category color background preserved

---

- [ ] **Unit 6: Update LiabilityCard component**

**Goal:** Replace hardcoded emoji map with SVG icon references in LiabilityCard.

**Requirements:** R14

**Dependencies:** Unit 2 (SVG sprite)

**Files:**
- Modify: `frontend/src/components/liability/LiabilityCard.vue`

**Approach:**
1. Update `categoryMap` to use SVG icon IDs instead of emojis:
   ```typescript
   const categoryMap: Record<string, { text: string; icon: string; color: string }> = {
     mortgage: { text: '房贷', icon: 'icon-mortgage', color: '#1989fa' },
     car_loan: { text: '车贷', icon: 'icon-car-loan', color: '#07c160' },
     credit_card: { text: '信用卡', icon: 'icon-credit-card', color: '#FAAD14' },
     personal_loan: { text: '其他贷款', icon: 'icon-personal-loan', color: '#722ED1' },
     other: { text: '其他', icon: 'icon-other-liability', color: '#64748B' },
   }
   ```
2. Replace `{{ categoryMap[liability.liability_type]?.icon }}` with inline SVG

**Patterns to follow:**
- Existing `categoryMap` structure
- Same SVG rendering pattern as CategoryGrid

**Test scenarios:**
- Happy path: Each liability type shows correct SVG icon
- Edge case: Unknown liability type falls back to `icon-other-liability`
- Visual: Icon size 18px matches current emoji size
- Accessibility: `aria-hidden="true"` on decorative icon

**Verification:**
- No emoji characters in LiabilityCard
- All 5 liability types have corresponding SVG icons
- Icon colors inherit correctly

---

- [ ] **Unit 7: Update AlertCards component**

**Goal:** Replace hardcoded emoji strings with SVG icons in AlertCards.

**Requirements:** R15

**Dependencies:** Unit 2 (SVG sprite)

**Files:**
- Modify: `frontend/src/components/dashboard/AlertCards.vue`

**Approach:**
1. Replace emoji literals with SVG pattern:
   - `📦` → `icon-idle`
   - `📅` → `icon-expiring` (for expiring physical assets)
   - `⚠️` → `icon-warning` (for expiring financial assets, when `hasFinancialExpiring` is true)
2. Update template to use inline SVG for card icons
3. Maintain existing color scheme and styling

**Patterns to follow:**
- Existing `.card-icon` CSS styling
- Conditional icon rendering based on `hasFinancialExpiring`

**Test scenarios:**
- Happy path: Idle assets card shows `icon-idle`
- Conditional: Expiring card shows `icon-expiring` or `icon-warning` based on financial assets
- Visual: Icon size 24px matches current emoji size
- Accessibility: `aria-hidden="true"` on decorative icons

**Verification:**
- No emoji characters in AlertCards
- Icons correctly differentiate between idle/expiring/warning states
- Existing popup sheet icons also updated

---

- [ ] **Unit 8: Update AssetDetailPage and AssetListItem**

**Goal:** Replace emoji fallback icons with SVG in asset detail and list item views.

**Requirements:** R16

**Dependencies:** Unit 2 (SVG sprite), Unit 3 (icon data)

**Files:**
- Modify: `frontend/src/pages/AssetDetailPage.vue`
- Modify: `frontend/src/components/asset/AssetListItem.vue`

**Approach:**
1. Replace `{{ asset.category?.icon || '📦' }}` with inline SVG pattern
2. Handle null category fallback to `icon-other`
3. Use same SVG rendering pattern as AssetCard

**Patterns to follow:**
- Same SVG pattern as Unit 4 (CategoryGrid) and Unit 5 (AssetCard)

**Test scenarios:**
- Happy path: Assets with categories show SVG icons
- Edge case: Assets without categories show `icon-other`

**Verification:**
- No emoji fallback (`📦`) in AssetDetailPage or AssetListItem

---

- [ ] **Unit 9: Update LiabilityDetailPage and LiabilityForm**

**Goal:** Replace emoji icons with SVG in liability detail and form pages.

**Requirements:** R17

**Dependencies:** Unit 2 (SVG sprite)

**Files:**
- Modify: `frontend/src/pages/LiabilityDetailPage.vue`
- Modify: `frontend/src/components/liability/LiabilityForm.vue`

**Approach:**
1. Update `categoryMap` in LiabilityDetailPage to use SVG icon IDs
2. Update `categoryColumns` in LiabilityForm to use SVG icon IDs
3. Replace emoji rendering with inline SVG pattern

**Patterns to follow:**
- Same `categoryMap` structure as Unit 6 (LiabilityCard)
- Same SVG rendering pattern

**Test scenarios:**
- Happy path: Liability detail shows correct SVG icons
- Integration: Liability form picker shows SVG icons for each type

**Verification:**
- No emoji characters in LiabilityDetailPage or LiabilityForm

---

- [ ] **Unit 10: Update shareImage utility**

**Goal:** Render SVG icons in generated share images instead of emojis.

**Requirements:** R18

**Dependencies:** Unit 2 (SVG sprite)

**Files:**
- Modify: `frontend/src/utils/shareImage.ts`

**Approach:**
1. Update share image generation to render SVG icons via canvas
2. Convert SVG symbol to canvas-compatible image (may require inline SVG or base64 data URL)
3. Maintain share image layout and quality

**Technical design:**
- SVG symbols cannot be directly rendered to canvas — must either:
  - Embed SVG as inline image with xmlns attribute
  - Convert to base64 data URL before drawing to canvas
- Implementation should cache converted icons to avoid repeated conversion

**Test scenarios:**
- Happy path: Share image includes correct category SVG icon
- Visual: Icon quality maintained in generated image

**Verification:**
- Share images display SVG icons without emoji artifacts

---

- [ ] **Unit 11: Add CSS styles for SVG icons**

**Goal:** Add reusable CSS classes for SVG icon styling across components.

**Requirements:** R2

**Dependencies:** Unit 2 (SVG sprite)

**Files:**
- Modify: `frontend/src/style.css` (or create `frontend/src/assets/icons.css`)

**Approach:**
1. Add base `.svg-icon` class:
   ```css
   .svg-icon {
     display: inline-block;
     width: 1em;
     height: 1em;
     fill: currentColor;
     vertical-align: middle;
   }
   ```
2. Add reduced-motion support:
   ```css
   @media (prefers-reduced-motion: reduce) {
     .svg-icon {
       transition: none;
     }
   }
   ```
3. Ensure inheritance from parent color
4. Add size variants if needed (`.svg-icon-sm`, `.svg-icon-lg`)

**Patterns to follow:**
- Existing CSS patterns in the project
- Vant's icon sizing conventions

**Test scenarios:**
- Happy path: Icons scale correctly with font-size
- Theme: `currentColor` correctly inherits in light/dark modes
- Visual: Icons align vertically with adjacent text

**Verification:**
- CSS classes available globally
- No inline style duplication across components
- Dark mode icons correctly colored

---

- [ ] **Unit 12: Backend tests and verification**

**Goal:** Verify backend changes don't break existing functionality.

**Requirements:** All

**Dependencies:** Unit 1, Unit 3

**Files:**
- Run: `backend/tests/` (existing test suite)

**Approach:**
1. Run existing test suite: `uv run pytest tests/ -v`
2. Verify category-related tests pass with new icon format
3. Check that asset/liability creation still works

**Test scenarios:**
- Happy path: All 36 existing tests pass
- Integration: Category seeding works with icon IDs
- Edge case: Custom category creation still works

**Verification:**
- `pytest` reports all tests passing
- No regression in category/asset/liability CRUD operations

---

- [ ] **Unit 13: Frontend build verification**

**Goal:** Verify frontend builds successfully with SVG changes.

**Requirements:** All

**Dependencies:** Units 4-10

**Files:**
- Run: `frontend/` (build process)

**Approach:**
1. Run type check: `npx vue-tsc -b --noEmit`
2. Run build: `npm run build`
3. Preview build: `npm run preview`

**Test scenarios:**
- Happy path: Build completes without errors
- Type safety: No TypeScript errors
- Runtime: Preview shows icons correctly

**Verification:**
- `npm run build` succeeds
- No TypeScript errors
- Preview renders all icons correctly

## System-Wide Impact

- **Interaction graph:** No callbacks or observers affected. Components render icons statically.
- **Error propagation:** Missing SVG symbols render `icon-other` fallback icon (graceful degradation per R4).
- **State lifecycle risks:** None. Icon data is static per category.
- **API surface parity:** Backend API unchanged. Only `icon` field content changes from emoji to icon ID string.
- **Integration coverage:** Frontend components tested individually. No cross-layer integration tests needed.
- **Unchanged invariants:**
  - Category CRUD API endpoints unchanged
  - Database foreign key relationships unchanged
  - User authentication and family scoping unchanged

## Risks & Dependencies

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| SVG icons look different at small sizes | Medium | Medium | Test at 18px, 22px, 24px, 36px during design |
| Missing icon ID causes broken display | Low | Medium | Fallback to `icon-other` implemented in all components |
| Database migration fails on some DB backend | Low | High | Test migration on SQLite, MySQL, PostgreSQL |
| Custom user categories with emoji break | Low | Low | Migration only touches `is_system=True` records; components handle emoji fallback |
| Dark mode contrast insufficient | Medium | Medium | Use `currentColor` and test contrast ratios |

## Documentation / Operational Notes

- **Migration sequence:** Run backend migration (Unit 1, Unit 3) before frontend deployment
- **Rollback:** Alembic migration includes `downgrade()` to revert field length
- **Monitoring:** Check browser console for SVG symbol not found errors after deployment

## Sources & References

- **Origin document:** [docs/brainstorms/2026-04-05-svg-icon-system-requirements.md](../brainstorms/2026-04-05-svg-icon-system-requirements.md)
- **Existing SVG sprite:** `frontend/public/icons.svg`
- **Category model:** `backend/app/models/category.py`
- **Seed data:** `backend/app/seed/categories.py`