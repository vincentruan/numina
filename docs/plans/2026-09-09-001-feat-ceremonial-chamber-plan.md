---
title: Ceremonial Chamber - Plan
type: feat
date: 2026-09-09
topic: ceremonial-chamber
artifact_contract: ce-unified-plan/v1
artifact_readiness: implementation-ready
product_contract_source: ce-brainstorm
execution: code
---

# Ceremonial Chamber - Plan

## Goal Capsule

- **Objective:** Transform the manifesto sign page and preview page into an immersive "ceremony room" — a visually distinct space that signals to the user this moment is different from everyday app interactions.
- **Product authority:** This plan owns the ceremony room container. The Parchment & Ink Theme System (from ce-ideate Idea 7) is a companion investment that provides the CSS variable foundation; this plan consumes those tokens but does not define them.
- **Open blockers:** None. All product decisions resolved in brainstorm dialogue.
- **Surrounding areas not in scope:** Calligraphy Signature (Idea 2), Living Family Crest (Idea 3), Progressive Scroll Reveal (Idea 4), Digital Wax Seal (Idea 5), Signing Milestone Timeline (Idea 6). These are separate ceremony investments that layer on top of the chamber. See "How This Work Fits Together."

---

## Product Contract

### Summary

Add a ceremony room mode to the manifesto sign page (`/manifesto/sign`) and preview page (`/manifesto/preview`) that replaces the standard app chrome with a warm parchment background, a centered elevated document, and a minimal close button — making the user feel they have entered a dedicated space for family commitment.

### Problem Frame

The manifesto sign and preview pages currently render as standard app pages: white background, nav-bar with back arrow, content in 16px padding, Vant 4 tab bar at the bottom. There is zero visual distinction between "checking account balances" and "committing to a family covenant." The ClassicTemplate's ornaments (corner flourishes, family crest emblem, gold dividers) exist in code but fail to render visually in the browser. The user experience signals "form" when the moment demands "ceremony."

E-signature platforms (DocuSign, Dropbox Sign) solve this by removing all non-essential UI during the signing moment. A family covenant deserves at least the same spatial respect as a legal contract — and arguably more, because the commitment is emotional, not just legal.

### Key Decisions

- **Both sign and preview pages get the chamber.** The preview is the creator's "first viewing" of the covenant — they should experience the same ceremony the signers will. (session-settled: user-directed — chosen over "sign page only": the creator deserves the same ceremonial framing)
- **Minimal close button (×) replaces nav-bar.** Simplest exit, always discoverable, sits where the back arrow was. (session-settled: user-directed — chosen over swipe-back only and auto-hide)
- **Document scale-up transition.** The document appears at 90% scale and fades to 100% over 600ms. (session-settled: user-directed — chosen over curtain reveal, instant, and two-phase)
- **Warm parchment background with paper texture.** #FAF7F0 base with CSS noise overlay at 3-5% opacity. (session-settled: user-directed)
- **Tab bar stays visible (partial immersion).** Users can still navigate the app; the ceremony is in the document, not the container. (session-settled: user-directed — chosen over fully immersive)
- **Dark mode: deep navy background, parchment-toned document.** Inverts the light-mode relationship while preserving warmth. (session-settled: user-approved from ideation artifact)
- **prefers-reduced-motion: instant appearance.** No animation; the room appears fully formed. (session-settled: user-approved from ideation artifact)
- **Compatible with future ceremony features.** The chamber must not block or conflict with calligraphy signatures, family crests, wax seals, or scroll reveals layered on top. (session-settled: user-approved from ideation artifact)

### Requirements

**Chamber Container**

- R1. When the sign page or preview page loads, the nav-bar is hidden and replaced by a minimal close button (×) in the top-left corner.
- R2. The page background transitions from the app's default white to a warm parchment tone (#FAF7F0 in light mode).
- R3. The manifesto document (ManifestoViewer output) is visually elevated — centered with a subtle drop shadow, appearing as a distinct object on the parchment surface.
- R4. The bottom tab bar remains visible and functional. Users can navigate away at any time.
- R5. The close button (×) triggers `router.back()` — same behavior as the original nav-bar back arrow.
- R6. The transition animation: document scales from 90% to 100% with opacity fade-in over 600ms, using ease-out timing.
- R7. When `prefers-reduced-motion` is set, skip the scale-up animation — the chamber appears instantly in its final state.

**Dark Mode**

- R8. In dark mode, the background is a deep warm tone (deep navy or dark warm brown) and the document retains a parchment-like appearance with adjusted contrast.
- R9. The close button, document shadow, and parchment texture all adapt to dark mode via CSS variables — no hardcoded colors.

**Compatibility**

- R10. The chamber must not alter the DOM structure or data flow of ManifestoViewer, SignaturePad, ManifestoFlowViewer, or the publish action area. It is a visual container, not a behavioral change.
- R11. The chamber must accommodate the ClassicTemplate's existing ornament elements (corner flourishes, emblem, dividers) without layout conflict.
- R12. Future ceremony features (calligraphy signature rendering, dynamic family crest, wax seal animation, scroll-reveal paragraphs) must be layerable on top of the chamber without requiring chamber changes.

### Key Flows

- F1. User enters sign page
  - **Trigger:** User navigates to `/manifesto/sign`.
  - **Steps:** Page loads → nav-bar hides → close button appears → background warms to parchment → document scales up from 90% to 100% with fade-in (600ms) → ceremony room is fully presented.
  - **Outcome:** User sees the manifesto document elevated on a warm parchment surface, with only the close button and tab bar as app chrome.

- F2. User exits ceremony room
  - **Trigger:** User taps the close button (×).
  - **Steps:** `router.back()` fires → user returns to the previous page (dashboard, settings, etc.) with standard app chrome restored.
  - **Outcome:** Clean exit, no disorientation.

- F3. User enters preview page
  - **Trigger:** Creator navigates to `/manifesto/preview` from the edit flow.
  - **Steps:** Same as F1 — page loads → chamber activates → document presents in ceremony mode.
  - **Outcome:** Creator sees their covenant as signers will experience it, with the publish button and TOC sidebar (if clauses exist) still accessible.

### Acceptance Examples

- AE1. Covers R1, R5, R6.
  - **Given:** User is on the dashboard and taps the manifesto sign entry.
  - **When:** The sign page loads.
  - **Then:** The nav-bar is hidden, a × button appears top-left, the background is warm parchment, and the document scales up with a fade-in over ~600ms.

- AE2. Covers R4, R5.
  - **Given:** User is in the ceremony room on the sign page.
  - **When:** User taps the × button.
  - **Then:** User returns to the dashboard with full app chrome (nav-bar + tab bar) restored.

- AE3. Covers R4.
  - **Given:** User is in the ceremony room.
  - **When:** User taps a tab bar item (e.g., Finance, AI, Settings).
  - **Then:** User navigates to that tab with standard app chrome — no trap, no confusion.

- AE4. Covers R7.
  - **Given:** User has `prefers-reduced-motion` enabled in OS settings.
  - **When:** The sign page loads.
  - **Then:** The chamber appears instantly — no scale-up animation, no fade. The document is fully visible from the first frame.

- AE5. Covers R8, R9.
  - **Given:** User is in dark mode.
  - **When:** The sign page loads.
  - **Then:** Background is deep navy/warm dark, document is parchment-toned with appropriate contrast, close button is visible against the dark background.

- AE6. Covers R10, R11.
  - **Given:** The manifesto uses ClassicTemplate with ornaments and emblem.
  - **When:** The chamber activates.
  - **Then:** The ClassicTemplate renders inside the elevated document card without overflow, clipping, or layout conflict. Corner ornaments, emblem, and dividers are visible within the document bounds.

### Scope Boundaries

**In scope:**
- Sign page (`/manifesto/sign`) ceremony mode
- Preview page (`/manifesto/preview`) ceremony mode
- CSS transitions and animations for chamber entry
- Close button replacement for nav-bar
- Dark mode and reduced motion adaptations

**Out of scope:**
- Edit page, template select page, settings page — these are editorial/admin surfaces
- Changes to ClassicTemplate or ModernTemplate styling (separate ceremony investments)
- Signature pad behavior, flow viewer, or publish button
- Backend changes
- The Parchment & Ink Theme System CSS variable definitions (companion plan)

### How This Work Fits Together

This plan owns the **ceremony room container** — the visual space that holds the manifesto document. It is the first and foundational layer of a 7-part ceremony design suite identified in `docs/ideation/2026-09-08-manifesto-ceremony-ideation.html`.

- **This plan (Ceremonial Chamber)** — the room. Enables all downstream ceremony features by providing the atmospheric container.
- **Parchment & Ink Theme (Idea 7)** — the paint. CSS variable tokens that the chamber consumes. Can proceed independently but is most valuable when implemented alongside the chamber.
- **Progressive Scroll Reveal (Idea 4)** — the pacing. Paragraphs fade in as user scrolls. Depends on the chamber being in place so the reveal happens within the ceremony context.
- **Living Family Crest (Idea 3)** — the identity. Dynamic SVG emblem above the document. Layerable on top of the chamber.
- **Calligraphy Signature (Idea 2)** — the gesture. Brush-pen signature rendering. Independent of the chamber but visually enhanced by it.
- **Digital Wax Seal (Idea 5)** — the climax. Animated seal on sign confirmation. Independent of the chamber.
- **Signing Milestone Timeline (Idea 6)** — the story. Integrated flow visualization. Independent of the chamber.

### Dependencies / Assumptions

- **Dependency:** The Parchment & Ink Theme System (Idea 7) should ideally be implemented alongside or before the chamber, as it provides the CSS variable tokens the chamber uses. If implemented without the theme system, the chamber can use hardcoded fallback values with a TODO to migrate to tokens.
- **Assumption:** The MainLayout tab bar is implemented as a fixed-position element that can be styled independently from the page content area. If the tab bar is embedded within each page's template, hiding the nav-bar alone won't achieve partial immersion.
- **Assumption:** The `van-nav-bar` is a standard Vant 4 component that can be conditionally rendered or visually hidden without breaking the page layout.

### Outstanding Questions

- **Deferred to Planning:** Exact parchment texture implementation — CSS `noise()` filter vs. inline SVG data URI vs. base64-encoded texture image. Planning should evaluate performance impact on mobile.
- **Deferred to Planning:** Exact dark mode background color value — deep navy (#0f1a2e) vs. dark warm brown (#1a1612). Planning should test both against the document card for contrast compliance.
- **Deferred to Planning:** Whether the close button should have a brief entrance animation (fade-in after 300ms) or appear instantly.

---

## Planning Contract

### Key Technical Decisions

- **KTD1. Body-class coordination for tab-bar dimming.** The AppTabBar lives in `MainLayout.vue`, outside page scope. The lightest coordination is a `ceremony-mode` class toggled on `document.body` by a `useCeremonyRoom` composable on mount/unmount. MainLayout CSS gains one rule: `.ceremony-mode .app-tabbar { opacity: 0.3; transition: opacity 0.4s ease; }`. (session-settled: user-directed — chosen over Pinia store, provide/inject, or layout prop: body class is zero-infrastructure and the existing pattern for app-wide visual states.)
  - **Governs R4, R9.**
- **KTD2. Parchment texture via inline SVG data URI.** CSS `noise()` lacks broad mobile support. An inline SVG `<filter>` with `feTurbulence` as a `background-image` data URI gives a subtle paper grain at ~200 bytes, zero HTTP requests, and works everywhere. Opacity controlled via a pseudo-element overlay at 4%. (session-settled: user-directed — chosen over CSS noise and base64 image: SVG data URI is the smallest, most portable option.)
  - **Governs R2.**
- **KTD3. Dark mode background: deep navy #0f1a2e.** Tested against the parchment-toned document card (#1a1a2e card with warm text) for WCAG AA contrast. The warm brown alternative (#1a1612) was rejected for being too close to the document card color, reducing the elevation contrast.
  - **Governs R8, R9.**
- **KTD4. Nav-bar hidden via conditional render, not CSS hide.** The `van-nav-bar` is conditionally rendered (`v-if="!ceremonyMode"`) rather than hidden with CSS. This prevents layout shift and avoids the nav-bar occupying space when invisible. The close button occupies the same visual position.
  - **Governs R1, R5.**

---

## Implementation Units

### U1. Ceremony CSS tokens and tab-bar dimming

- **Goal:** Add ceremony-themed CSS custom properties to the global stylesheet and a `.ceremony-mode` body class rule that dims the tab bar.
- **Requirements:** R2, R4, R8, R9
- **Dependencies:** None
- **Files:**
  - `frontend/apps/main/src/style.css` (modify — add ceremony tokens + dark mode overrides)
- **Approach:**
  1. Add ceremony CSS custom properties to the `:root` block in `style.css`:
     - `--ceremony-bg: #FAF7F0` (parchment)
     - `--ceremony-bg-dark: #0f1a2e` (deep navy)
     - `--ceremony-ink: #1a1a2e` (warm black)
     - `--ceremony-ink-dark: #f0ece4` (warm white for dark mode)
     - `--ceremony-gold: #c9a84c` (existing gold, reused)
     - `--ceremony-shadow: rgba(26, 26, 46, 0.12)` (warm drop shadow)
     - `--ceremony-shadow-dark: rgba(0, 0, 0, 0.4)`
  2. Add dark mode overrides in the `[data-theme='dark']` block for each token.
  3. Add `.ceremony-mode .app-tabbar { opacity: 0.3; transition: opacity 0.4s ease; }` rule.
- **Patterns to follow:** Existing CSS variable pattern in `style.css` (light defaults at `:root`, dark overrides at `[data-theme='dark']`). Semantic alias pattern (`--bg-primary: var(--color-canvas)`).
- **Test scenarios:**
  - Light mode: `--ceremony-bg` resolves to #FAF7F0.
  - Dark mode: `[data-theme='dark']` overrides `--ceremony-bg` to #0f1a2e.
  - Tab bar: element with class `.app-tabbar` inside `.ceremony-mode` body has opacity 0.3.
- **Verification:** CSS tokens are defined, dark mode overrides exist, tab bar dimming rule is present.

### U2. CeremonyRoom wrapper component

- **Goal:** Create a reusable `CeremonyRoom.vue` component that provides the parchment background, close button, scale-up animation, body-class coordination, and dark-mode/reduced-motion support.
- **Requirements:** R1, R2, R3, R5, R6, R7, R10, R12
- **Dependencies:** U1
- **Files:**
  - `frontend/apps/main/src/components/manifesto/CeremonyRoom.vue` (create)
  - `frontend/apps/main/src/composables/useCeremonyRoom.ts` (create — body class coordination composable)
- **Approach:**
  1. Create `useCeremonyRoom` composable: on mount, adds `ceremony-mode` class to `document.body`; on unmount, removes it. Returns a `close()` function that calls `router.back()`.
  2. Create `CeremonyRoom.vue`:
     - Template: a `<div class="ceremony-room">` wrapper with a close button (×) positioned absolute top-left, and a `<slot>` for the document content.
     - The nav-bar is NOT rendered inside CeremonyRoom — pages conditionally render their own nav-bar based on a `ceremonyMode` prop or the composable's state.
     - The document slot content is wrapped in a `.ceremony-document` div with elevated styling (shadow, max-width, centered).
     - On mount: trigger scale-up animation (CSS class toggle: `.ceremony-enter` → `.ceremony-active`).
     - Respect `prefers-reduced-motion`: if set, skip animation class and render at full scale immediately.
  3. CSS (scoped to CeremonyRoom):
     - `.ceremony-room`: full-height, `background: var(--ceremony-bg)`, `padding-bottom: env(safe-area-inset-bottom)`.
     - `.ceremony-document`: `max-width: 100%`, `box-shadow: 0 4px 24px var(--ceremony-shadow)`, `border-radius: 4px`, `overflow: hidden`.
     - `.ceremony-enter`: `transform: scale(0.9); opacity: 0; transition: transform 0.6s ease-out, opacity 0.6s ease-out`.
     - `.ceremony-active`: `transform: scale(1); opacity: 1`.
     - `@media (prefers-reduced-motion: reduce)`: skip transition, render at scale(1) opacity(1) immediately.
     - Parchment texture: `.ceremony-room::before` pseudo-element with inline SVG `feTurbulence` data URI background at 4% opacity.
  4. Close button: absolute positioned top-left, 44×44px touch target, `@click="close()"`, uses Iconify `close` icon or inline SVG ×.
- **Patterns to follow:** Scoped CSS with CSS variables (per `frontend/CLAUDE.md`). `defineEmits` for close event. Composable pattern for side effects (per existing composables in `src/composables/`).
- **Test scenarios:**
  - On mount: `document.body` has class `ceremony-mode`.
  - On unmount: `document.body` does NOT have class `ceremony-mode`.
  - Click close button: emits `close` event (parent handles `router.back()`).
  - `prefers-reduced-motion: reduce`: `.ceremony-document` renders without `.ceremony-enter` class.
  - Parchment texture: `.ceremony-room::before` has `background-image` set.
- **Verification:** Component renders with parchment background, close button is visible and clickable, scale-up animation plays (or is skipped for reduced motion), body class is toggled correctly.

### U3. Sign page integration

- **Goal:** Wrap the ManifestoSignPage content in CeremonyRoom, conditionally hide the nav-bar.
- **Requirements:** R1, R3, R5, R10, R11
- **Dependencies:** U1, U2
- **Files:**
  - `frontend/apps/main/src/pages/ManifestoSignPage.vue` (modify)
- **Approach:**
  1. Import `CeremonyRoom` and `useCeremonyRoom` composable.
  2. Initialize composable in `<script setup>` — it handles body class on mount/unmount.
  3. Wrap the entire page content (currently `div.manifesto-sign-page`) in `<CeremonyRoom @close="router.back()">`.
  4. Conditionally render the `van-nav-bar`: `v-if="false"` or remove it entirely (the close button replaces it).
  5. Keep all existing functionality (ManifestoViewer, SignaturePad, ManifestoFlowViewer, signing logic) unchanged inside the CeremonyRoom slot.
  6. Remove the `.manifesto-sign-page` background style (`background: var(--bg-primary, #fff)`) — the CeremonyRoom provides the background.
- **Patterns to follow:** Existing page structure: `<template>` → nav-bar → content. The nav-bar is simply not rendered; the CeremonyRoom provides the replacement chrome.
- **Test scenarios:**
  - Sign page loads: nav-bar is NOT visible, CeremonyRoom close button IS visible.
  - Background is parchment (#FAF7F0 in light mode), not white.
  - ManifestoViewer, SignaturePad, and ManifestoFlowViewer render correctly inside the ceremony room.
  - Click close button: navigates back to previous page.
  - Tab bar is dimmed (opacity 0.3) while on sign page.
- **Verification:** bsk screenshot of sign page shows parchment background, elevated document, close button, dimmed tab bar. No nav-bar visible.

### U4. Preview page integration

- **Goal:** Wrap the ManifestoPreviewPage content in CeremonyRoom, conditionally hide the nav-bar.
- **Requirements:** R1, R3, R4, R10
- **Dependencies:** U1, U2
- **Files:**
  - `frontend/apps/main/src/pages/ManifestoPreviewPage.vue` (modify)
- **Approach:**
  1. Same pattern as U3: import CeremonyRoom + composable, wrap content, remove nav-bar.
  2. The preview page has a two-column layout (TOC sidebar + main content). Both columns go inside the CeremonyRoom slot — the sidebar is part of the document experience.
  3. The publish action area and scroll hint remain inside the ceremony room — they are part of the preview flow.
  4. The TOC sidebar's emoji icon (📜) is outside this plan's scope (noted in brainstorm as a future polish item).
- **Patterns to follow:** Same integration pattern as U3.
- **Test scenarios:**
  - Preview page loads: nav-bar is NOT visible, CeremonyRoom close button IS visible.
  - TOC sidebar (if clauses exist) is visible inside the ceremony room.
  - Publish button is accessible.
  - Tab bar is dimmed while on preview page.
  - Click close button: navigates back to edit page.
- **Verification:** bsk screenshot of preview page shows parchment background, elevated document with TOC sidebar, close button, dimmed tab bar.

---

## Verification Contract

| Gate | Command | Applies to | Done when |
|------|---------|-----------|-----------|
| Type check | `cd frontend/apps/main && pnpm typecheck` | U1–U4 | Zero errors |
| Lint | `cd frontend/apps/main && pnpm lint` | U1–U4 | Zero errors |
| Visual check (sign) | bsk screenshot of `/manifesto/sign` | U3 | Parchment bg, no nav-bar, close button visible, tab bar dimmed |
| Visual check (preview) | bsk screenshot of `/manifesto/preview` | U4 | Same as sign + TOC sidebar visible if clauses exist |
| Dark mode | bsk screenshot in dark mode | U1, U2 | Deep navy background, warm document, visible close button |
| Reduced motion | bsk screenshot with `prefers-reduced-motion` | U2 | No scale-up animation, document visible from first frame |

---

## Definition of Done

- All 4 implementation units are implemented and type-check cleanly.
- bsk screenshots of both sign and preview pages confirm the ceremony room visual (parchment background, elevated document, close button, dimmed tab bar).
- Dark mode renders correctly with deep navy background and warm document.
- `prefers-reduced-motion` skips the scale-up animation.
- Tab bar navigation works while in ceremony mode (partial immersion confirmed).
- ClassicTemplate ornaments render without layout conflict inside the ceremony room.
- No regressions in existing manifesto functionality (signing, flow viewer, publish).

### Product Contract preservation

Unchanged. All R-IDs, F-IDs, and AE-IDs preserved verbatim from the brainstorm. No scope changes.
