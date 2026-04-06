---
date: 2026-04-03
topic: mobile-h5-ui-ux-optimization
focus: Mobile H5 UI/UX optimization for family asset visualization app
---

# Ideation: Mobile H5 UI/UX Optimization

## Codebase Context

**Project Shape:**
- Full-stack family asset visualization: FastAPI/SQLite backend + Vue 3/Vant 4 frontend
- Mobile-first H5 design with bottom tab bar navigation
- Core pages: Dashboard, Wishes, Liabilities, Stats, Settings
- Asset management with card/list views, status filtering, batch operations

**UI/UX Observations from Live Testing (Chrome DevTools @ 375x812 mobile viewport):**
- Tab bar has 6 items (exceeds 5-item guideline) with elevated "add" button
- NetWorthCard uses gradient blue background (good visual hierarchy)
- StatusSummaryGrid shows horizontal scrollable pills with counts
- Empty states show only text + button, no illustrations
- Category icons use emojis (🏠, 🚗, 📱) instead of SVG icons
- Charts show empty state placeholders without skeleton loading
- AssetForm uses segmented control for asset type, icon grid for categories

**Past Learnings:**
- ALTCHA captcha best practices documented (2026-04-03)
- Stack overflow fix for AltchaWidget component (2026-04-02)

## Ranked Ideas

### 1. Replace Emoji Icons with SVG Icon System
**Description:** Replace all emoji-based category icons (🏠房产, 🚗车辆, etc.) with SVG icons from a consistent icon family (e.g., Lucide, Heroicons). This affects CategoryGrid, AssetCard fallback icons, LiabilityCard icon map, and AlertCards icons.

**Rationale:** Emojis render inconsistently across platforms, cannot be themed (color, size), and screen readers announce them unpredictably. SVG icons provide consistent rendering, themeable colors, and proper accessibility via aria-labels. This is a CRITICAL accessibility and brand consistency issue.

**Downsides:** Requires designing or selecting 21+ category icons; migration effort for existing data.

**Confidence:** 95%

**Complexity:** Medium

**Status:** Unexplored

### 2. Add Skeleton Loading States
**Description:** Implement van-skeleton components for NetWorthCard, StatusSummaryGrid, and asset lists during initial data fetch. Use skeleton cards that match the layout of actual content.

**Rationale:** Users currently see blank white space during loading (1-2 seconds on dashboard), creating perception of app slowness. Skeleton screens reduce perceived wait time by 50% and provide immediate visual feedback.

**Downsides:** Additional component complexity; must maintain skeleton layouts in sync with actual components.

**Confidence:** 90%

**Complexity:** Low

**Status:** Unexplored

### 3. Add Swipe Actions on Asset/Liability Cards
**Description:** Wrap AssetCard and AssetListItem with van-swipe-cell to reveal quick actions (archive, edit, share) on left/right swipe.

**Rationale:** Currently users must navigate to detail page for every action. Swipe gestures reduce 2-3 taps per common operation and match iOS/Android conventions. Swipe cells already exist on management pages (TagManagePage, CategoryManagePage) - extend to main content.

**Downsides:** May conflict with horizontal scroll in StatusSummaryGrid; needs careful gesture boundary handling.

**Confidence:** 85%

**Complexity:** Medium

**Status:** Unexplored

### 4. Fix Touch Target Sizes
**Description:** Increase touch targets for StatusSummaryGrid pills (currently ~24x36px), CategoryGrid items (~60x40px), and UsageFreqSelector items to meet 44x44pt minimum. Use padding and hitSlop to expand tap area without changing visual size.

**Rationale:** Current touch targets fail WCAG accessibility guidelines. Users with motor impairments or larger fingers struggle to tap accurately. This is a CRITICAL accessibility issue.

**Downsides:** May require layout adjustments; could increase component height.

**Confidence:** 95%

**Complexity:** Low

**Status:** Unexplored

### 5. Add Onboarding Flow for New Users
**Description:** Create a guided 3-step walkthrough after registration: (1) explain dashboard, (2) guide first asset creation, (3) show family invite sharing. Use van-overlay with spotlight and tooltips.

**Rationale:** New users see empty dashboard with no context on how to start. RegisterPage immediately redirects to "/" without guidance. Onboarding improves new user retention and reduces support burden.

**Downsides:** Additional development effort; must track onboarding completion state.

**Confidence:** 80%

**Complexity:** Medium

**Status:** Unexplored

### 6. Add Accessibility Labels Throughout
**Description:** Add aria-label and role attributes to AssetCard, LiabilityCard, status pills, FAB buttons, and all interactive elements. Ensure screen reader focus order matches visual order.

**Rationale:** Current accessibility is minimal - only 1 aria reference found in entire frontend. Screen reader users cannot distinguish card types or understand status pill meanings. Violates WCAG 2.1 Level A.

**Downsides:** Requires systematic audit of all components; ongoing maintenance.

**Confidence:** 90%

**Complexity:** Medium

**Status:** Unexplored

### 7. Establish 8dp Spacing Grid System
**Description:** Standardize all padding/margin values to 4px increments (4, 8, 12, 16, 24, 32, 48px). Create CSS utility classes or design tokens for spacing.

**Rationale:** Current spacing varies arbitrarily (4px, 6px, 8px, 10px, 12px, 14px, 16px, 24px) creating visual noise. An 8dp grid aligns content, improves readability, and speeds development decisions.

**Downsides:** Requires refactoring existing styles; may cause subtle layout shifts.

**Confidence:** 75%

**Complexity:** Medium

**Status:** Unexplored

## Rejection Summary

| # | Idea | Reason Rejected |
|---|------|-----------------|
| 1 | Tab Bar Navigation Overload (6 items) | Valid issue but tab bar already implemented with elevated add button as intentional design; restructure would break user muscle memory |
| 2 | Long-Press to Enter Selection Mode | Lower priority than swipe actions; adds complexity for discoverability |
| 3 | Form Keyboard Avoidance | Vant handles this via viewport units; not a critical pain point in testing |
| 4 | Empty State Illustrations | Nice-to-have but skeleton loading and onboarding address the core issue first |
| 5 | Haptic Feedback | Platform-dependent; lower priority than accessibility fixes |
| 6 | Spring Physics for Animations | Micro-optimization; current scale(0.98) is adequate |
| 7 | Success Micro-Animation on Submit | Nice-to-have but toast notification provides sufficient feedback |
| 8 | Faster Exit Transitions | Vant handles this; minimal user impact |
| 9 | Stagger Animation on List Appear | Performance concern on large lists; skeleton loading is better solution |
| 10 | Data Export UI in Settings | Batch export exists in selection mode; not a primary user need |
| 11 | Family Member Ownership Indicators | Backend has user_id but feature not requested by users |
| 12 | Unify Primary Color Token Usage | Technical debt but not user-facing issue |
| 13 | Consolidate Dark Mode Overrides | Technical debt; dark mode works adequately |
| 14 | Define Typography Scale | Nice-to-have; current typography is readable |
| 15 | Harmonize Icon Family Across Tab Bar | Tab bar icons are Vant; content icons need SVG migration (covered by #1) |
| 16 | Unify Button Style Variants | Low user impact; buttons function correctly |
| 17 | Standardize Card Shadow Elevation | Visual polish; lower priority than accessibility |
| 18 | Pull-to-Refresh on All Pages | Already implemented on main list pages; edge cases don't justify effort |

## Session Log
- 2026-04-03: Initial ideation - 32 raw ideas generated across 4 frames (user pain, missing capabilities, visual consistency, interaction patterns), 7 survivors after adversarial filtering