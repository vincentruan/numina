---
date: 2026-04-05
topic: svg-icon-system
---

# SVG Icon System for Categories and UI Elements

## Problem Frame

Numina's mobile H5 app currently uses emoji characters (🏠🚗📱💰) for category icons and status indicators. Emojis render inconsistently across platforms, cannot be themed for dark mode, and screen readers announce them unpredictably. This creates accessibility barriers and visual inconsistency with the Vant icon system used in the tab bar.

**Affected Components:**
- CategoryGrid.vue (13 physical + 8 financial category icons)
- AssetCard.vue (fallback icon when no image)
- LiabilityCard.vue (5 liability type icons)
- AlertCards.vue (idle, expiring, warning icons)

**Users Affected:**
- All mobile H5 users (visual consistency)
- Screen reader users (accessibility)
- Dark mode users (theming)

## Requirements

**Icon System Architecture**
- R1. All category and UI icons shall use SVG format in a sprite sheet at `public/icons.svg`
- R2. Icons shall use `currentColor` for fill/stroke to inherit text color and support theming
- R3. Each icon shall have a unique ID following the pattern `icon-{name}` (e.g., `icon-home`, `icon-car`)
- R4. Icon fallback: If a referenced icon ID does not exist in the sprite, components shall render the default `icon-other` icon

**Category Icons (21 total)**
- R5. Replace all 21 category emoji icons with custom-designed SVG icons matching Vant's line-art style
- R6. Physical asset icons: `icon-home`, `icon-car`, `icon-digital`, `icon-appliance`, `icon-furniture`, `icon-jewelry`, `icon-clothing`, `icon-beauty`, `icon-sports`, `icon-toys`, `icon-pets`, `icon-music`, `icon-bags`
- R7. Financial asset icons: `icon-deposit`, `icon-fund`, `icon-stock`, `icon-bond`, `icon-insurance`, `icon-wealth`, `icon-crypto`, `icon-other-finance`

**Liability Icons (5 total)**
- R8. Replace liability type emojis with SVG icons: `icon-mortgage`, `icon-car-loan`, `icon-credit-card`, `icon-personal-loan`, `icon-other-liability`

**Alert Icons (3 total)**
- R9. Replace alert card emojis with SVG icons: `icon-idle`, `icon-expiring`, `icon-warning`

**Accessibility**
- R10. All icon usages shall include `aria-hidden="true"` when decorative (icon accompanies visible text label)
- R11. Icons without visible labels shall include `aria-label` describing their purpose

**Component Integration**
- R12. CategoryGrid.vue shall render SVG icons using Vue template syntax: `<svg><use :href="`#icon-${cat.icon}`" /></svg>`
- R13. AssetCard.vue fallback icon shall use the category's SVG icon instead of emoji
- R14. LiabilityCard.vue shall reference SVG icons from the sprite instead of hardcoded emoji map (frontend-only refactoring; liability types are distinct from database categories)
- R15. AlertCards.vue shall use SVG icons instead of hardcoded emojis

**Backend Compatibility**
- R16. Database `categories.icon` field values shall be updated from emoji strings to icon IDs (e.g., "🏠" → "icon-home")
- R17. Migration script shall convert existing emoji icons to icon IDs for all 21 system categories (custom user-created categories are unaffected; they may continue using emoji)
- R18. Alembic migration shall expand `categories.icon` column from `String(10)` to `String(50)` to accommodate icon ID format before data migration

**Emoji-to-IconID Mapping (21 system categories)**
| Emoji | Icon ID | Category Name |
|-------|---------|---------------|
| 🏠 | icon-home | 房产 |
| 🚗 | icon-car | 车辆 |
| 📱 | icon-digital | 数码 |
| 📺 | icon-appliance | 家电 |
| 🛋️ | icon-furniture | 家具 |
| 💎 | icon-jewelry | 珠宝 |
| 👔 | icon-clothing | 服饰 |
| 💄 | icon-beauty | 美妆 |
| ⚽ | icon-sports | 运动 |
| 🎮 | icon-toys | 玩具 |
| 🐾 | icon-pets | 宠物 |
| 🎸 | icon-music | 乐器 |
| 👜 | icon-bags | 箱包 |
| 🏦 | icon-deposit | 存款 |
| 📊 | icon-fund | 基金 |
| 📈 | icon-stock | 股票 |
| 📜 | icon-bond | 债券 |
| 🛡️ | icon-insurance | 保险 |
| 💰 | icon-wealth | 理财产品 |
| ₿ | icon-crypto | 数字货币 |
| 💳 | icon-other-finance | 其他金融 |

## Success Criteria

- All 29 icons (21 category + 5 liability + 3 alert) render consistently across iOS, Android, and desktop browsers
- Icons adapt to dark mode via `currentColor` (no hardcoded fill colors)
- SVG icons maintain visual feedback for hover, focus, active, and selected states in CategoryGrid (currentColor inherits parent state colors)
- Screen readers announce icons correctly (aria-hidden for decorative, aria-label for standalone)
- No emoji characters remain in CategoryGrid, AssetCard, LiabilityCard, or AlertCards components
- Lighthouse accessibility score improves by addressing "Elements describe contents with emoji" warnings

## Scope Boundaries

- Out of scope: Redesigning category taxonomy or adding new categories
- Out of scope: Replacing Vant icons in the tab bar (already consistent)
- Out of scope: Custom icons for user-uploaded assets (use category icon as fallback)

## Key Decisions

- **SVG sprite vs. component library**: SVG sprite chosen for zero runtime cost, consistency with existing icons.svg, and CSS theming support
- **Icon design source**: Custom minimal line-art icons matching Vant's 1.5px stroke style, designed to be recognizable at 22-24px size
- **Theming approach**: `currentColor` allows icons to inherit text color, automatically adapting to light/dark themes

## Dependencies / Assumptions

- Vant icons use 1.5px stroke width; custom icons should match for visual consistency
- Category icon size in CategoryGrid is 22px (font-size), SVG viewBox should be optimized for this scale
- Database migration required for 21 system categories (seed data)

## Outstanding Questions

### Resolve Before Planning
- None

### Deferred to Planning
- [Affects R15][Technical] Should migration be a one-time script or integrated into seed_categories() function?
- [Affects R11][Technical] Should we create a reusable `<AppIcon name="home" />` component or use inline SVG pattern? (Recommendation: inline SVG pattern for simplicity; component adds abstraction cost without significant benefit for 4 use sites)
- [Affects R5-R8][Design] Exact SVG path specifications for each of the 29 icons. Approach: Adapt icons from Lucide/Heroicons where semantic match exists (e.g., `home`, `car`, `credit-card`), design custom icons only where no open-source equivalent exists. Reference Vant's 1.5px stroke width and 24x24 viewBox for consistency.

## Next Steps
→ `/ce:plan` for structured implementation planning