---
title: Living Family Crest - Plan
type: feat
date: 2026-09-09
topic: living-family-crest
artifact_contract: ce-unified-plan/v1
artifact_readiness: implementation-ready
product_contract_source: ce-brainstorm
execution: code
---

# Living Family Crest - Plan

## Goal Capsule

- **Objective:** Add a dynamic SVG family crest above the manifesto document that visualizes the family's identity and grows as members sign — turning the document from a static contract into a living family artifact.
- **Product authority:** This plan owns the FamilyCrest component and its integration into both ClassicTemplate and ModernTemplate. It does not own the ceremony room container (CeremonyRoom), the wax seal (WaxSeal), the calligraphy signature pad, the scroll reveal, or the signing timeline. See "How This Work Fits Together."
- **Open blockers:** None. All product decisions resolved via agent recommendation (user did not intervene).

---

## Product Contract

### Summary

Create a `FamilyCrest` component that renders a dynamic SVG emblem above the manifesto document. The crest displays the family name character at its center, with member initials arranged around a circular ring. Members' initials transition from "pending" (muted) to "sealed" (gold/active) as they sign, making the crest a living record of the family's collective commitment.

### Problem Frame

The ideation document (`docs/ideation/2026-09-08-manifesto-ceremony-ideation.html`, Idea 3) identifies the gap: the ClassicTemplate has a static ⚜ emoji emblem that may not render, and ModernTemplate has no emblem at all. A family covenant lacks the visual identity marker that makes it feel like *this family's* document. Other ceremony investments (chamber, calligraphy, wax seal) enhance the experience but none address family identity directly.

### Key Decisions

- **Universal component, not template-scoped.** The crest appears in both ClassicTemplate and ModernTemplate, positioned above the document content. A single component serves both, with visual style adapting via CSS variables — Classic uses gold accent (#c9a84c), Modern uses a cleaner line-based treatment. (Chosen over "ClassicTemplate only" and "separate components per template": a single component is simpler to maintain and the family identity should not be fragmented by template style.)
- **"Living" = signing-reactive.** The crest reflects real-time signing state. Pending members show muted initials; signed members show gold/active initials with a subtle glow. The transition animates when a member signs. (Chosen over "static decorative": the living aspect is the core emotional value — it turns the crest from ornament into narrative.)
- **Pure SVG, no backend changes.** All data (family name, member names, roles, signing status) is already available via the template props (`MemberInfo[]`). The crest is a pure function of this data. (session-settled: agent-recommended — all needed data already flows through props, no API changes required.)
- **Circular ring layout.** Members arranged evenly around a circle, family character centered. Simpler and more aesthetically predictable than shield/heraldic shapes for arbitrary member counts (1–8+). (Chosen over shield/heraldic: shield layout is non-trivial for 1 member vs 8 members; circular is mathematically clean and culturally neutral.)
- **Position: above document title.** The crest sits between the ceremony room's top edge and the document's title, centered. This is the most prominent position and matches the ceremonial-chamber plan's expectation (R12). (session-settled: agent-recommended — above the document title is the most visible position in both templates.)
- **Dark mode via CSS variables.** The crest uses ceremony tokens already defined in `style.css` (`--ceremony-gold`, `--ceremony-ink`, etc.) with dark mode overrides. No hardcoded colors.
- **prefers-reduced-motion respected.** Signing-state transitions skip animation when reduced motion is preferred — the crest still reflects current state, just without animation.

### Requirements

**Visual Composition**

- R1. The crest renders as an inline SVG element, approximately 80×80px, centered horizontally above the manifesto document title.
- R2. The crest displays the family's first character (from `family.name` or the first member's name) at the center of the SVG.
- R3. Each family member's name initial (first character) is positioned around a circular ring, evenly distributed.
- R4. Members with signing status `signed` or `confirmed` display their initial in the active/gold style. Members with `pending_sign`, `pending_confirm`, `rejected`, or `expired` display in a muted style.
- R5. The ring itself is a thin circle in the accent color, connecting the member positions visually.

**Living Behavior**

- R6. When a member's signing status changes from pending to signed (via real-time update or page reload), their initial transitions from muted to active style with a subtle animation (opacity + scale, ~300ms).
- R7. When `prefers-reduced-motion` is set, the state transition is instant — no animation, but the visual state still reflects the current signing data.

**Template Integration**

- R8. ClassicTemplate: the crest uses gold accent (#c9a84c) for the ring and active initials, matching the existing ceremony palette. The static ⚜ emblem is replaced by the FamilyCrest component.
- R9. ModernTemplate: the crest uses the modern palette (line-based, system accent color). The component is added above the document title.
- R10. The crest component receives `members: MemberInfo[]` and `familyName: string` as props — no direct store dependency, consistent with the existing template prop pattern.

**Compatibility**

- R11. The crest must not alter the layout or behavior of ManifestoViewer, SignaturePad, ManifestoFlowViewer, or the publish action. It is a decorative addition, not a structural change.
- R12. The crest must render correctly inside the CeremonyRoom container (ceremony-chamber plan R12 compliance).

### Key Flows

- F1. User views manifesto with mixed signing states
  - **Trigger:** User navigates to the sign page or preview page.
  - **Steps:** Page loads → CeremonyRoom activates → FamilyCrest receives `members` prop → SVG renders with family character centered → each member's initial positioned on ring → signed members show gold/active, pending show muted.
  - **Outcome:** User sees a family crest that immediately communicates "who" and "who has signed."

- F2. Member signs during the ceremony
  - **Trigger:** A family member completes their signature (or confirmation for children).
  - **Steps:** Member's signing status updates → prop change propagates to FamilyCrest → the member's initial transitions from muted to gold with a 300ms animation (opacity 0.4→1, scale 0.9→1).
  - **Outcome:** The crest visibly "grows" — the family's collective commitment becomes visually richer.

### Acceptance Examples

- AE1. Covers R1, R2, R3, R5.
  - **Given:** A family with 3 members (Alice, Bob, Charlie) navigates to the sign page.
  - **When:** The page loads and the crest renders.
  - **Then:** An ~80×80px SVG appears above the document title. "A", "B", "C" are positioned evenly around a circle. A family character (e.g., "家" or first character of family name) sits at the center. A thin circle connects the three positions.

- AE2. Covers R4, R6.
  - **Given:** Alice has signed, Bob and Charlie are pending.
  - **When:** The crest renders.
  - **Then:** "A" is displayed in gold/active style. "B" and "C" are displayed in muted style. When Bob signs, "B" transitions to gold with a subtle animation.

- AE3. Covers R7.
  - **Given:** User has `prefers-reduced-motion` enabled.
  - **When:** Bob signs while the crest is visible.
  - **Then:** "B" changes from muted to gold instantly — no scale or opacity animation.

- AE4. Covers R8, R9.
  - **Given:** The manifesto uses ClassicTemplate (gold ceremony palette) and ModernTemplate (line-based style) respectively.
  - **When:** Both render the crest.
  - **Then:** ClassicTemplate crest uses gold (#c9a84c) ring and active initials. ModernTemplate crest uses a cleaner line-based treatment with system accent color. Both display the same member data.

- AE5. Covers R10, R11.
  - **Given:** A family with 1 member (only the owner).
  - **When:** The crest renders.
  - **Then:** A single initial appears on the ring (positioned at top-center). The layout is not broken or empty-looking. The crest does not interfere with the document title or any interactive element.

### Scope Boundaries

**In scope:**
- FamilyCrest component (SVG rendering + prop interface)
- Integration into ClassicTemplate (replacing static ⚜)
- Integration into ModernTemplate (new addition)
- Dark mode adaptation via CSS variables
- Reduced motion support
- Signing-state reactive animation

**Out of scope:**
- Changes to the ceremony room container (CeremonyRoom)
- Changes to the wax seal, calligraphy signature pad, scroll reveal, or flow viewer
- Backend data model changes (no new API endpoints)
- Animated SVG "growth" transitions beyond the per-member sign animation (e.g., the ring drawing itself)
- Custom crest shape selection by the user (shield vs circle vs other)
- Crest display outside the manifesto pages (e.g., dashboard card)

### How This Work Fits Together

<!-- ce-section: work-relationships -->

This plan owns the **dynamic family crest** — the visual identity element above the manifesto document. It is one of seven ceremony investments identified in `docs/ideation/2026-09-08-manifesto-ceremony-ideation.html`. Six of the seven are already implemented; this is the last remaining.

- **This plan (Living Family Crest)** — the identity. Dynamic SVG emblem above the document, reactive to signing state.
- **Ceremonial Chamber** (implemented) — the room. The crest renders inside the ceremony room; no dependency on chamber internals.
- **Parchment & Ink Theme** (implemented) — the paint. The crest consumes ceremony CSS tokens defined by this investment.
- **Progressive Scroll Reveal** (implemented) — the pacing. Independent; the crest sits above the scroll-reveal area.
- **Calligraphy Signature** (implemented) — the gesture. Independent; the crest is above the document, the signature pad is below.
- **Digital Wax Seal** (implemented) — the climax. Independent; the wax seal appears after all members sign, the crest is visible throughout.
- **Signing Milestone Timeline** (implemented) — the story. Independent; the timeline is below the document, the crest is above.

### Dependencies / Assumptions

- **Dependency:** The ceremony CSS tokens (`--ceremony-gold`, `--ceremony-ink`, etc.) defined in the Parchment & Ink Theme implementation. If those tokens change, the crest adapts automatically via CSS variable cascade.
- **Assumption:** The `MemberInfo` interface (name, role, signingStatus) provides sufficient data for the crest. No additional member metadata (avatar, title, etc.) is needed.
- **Assumption:** The family name or first member name is always available when the manifesto is displayed. Edge case: empty family (no members) — the crest should not render or show a placeholder.

### Outstanding Questions

- **Deferred to Implementation:** Exact easing curve for the signing-state transition (300ms ease-out vs 250ms ease-in-out). Verify visually during implementation.

---

## Planning Contract

### Key Technical Decisions

- **KTD1. Single crest treatment for both templates.** Both ClassicTemplate and ModernTemplate use the same FamilyCrest component with identical visual styling. The "different palette" framing from the Product Contract (R8 vs R9) collapses because ceremony tokens (`--ceremony-gold`, `--ceremony-ink`) already cascade into both templates via the CeremonyRoom container. The gold accent is the ceremony's visual language, not a template-specific choice. (session-settled: agent-recommended — research confirmed both templates render inside CeremonyRoom which provides ceremony tokens; separate styling would be redundant.) Governs R8, R9.
- **KTD2. WaxSeal.vue pattern for SVG structure.** FamilyCrest follows the WaxSeal precedent: inline `<svg viewBox="0 0 100 100">`, CSS variable-driven stroke/fill (no inline `style` for theme colors — per `docs/solutions/ui-bugs/dark-mode-inline-style-specificity-2026-05-30.md`), character overlay via `<span>` positioned over the SVG (not SVG `<text>`), `defineOptions({ name: 'FamilyCrest' })`, scoped CSS. (session-settled: agent-recommended — WaxSeal is the only existing dynamic SVG component in the manifesto module; mirroring its pattern avoids inventing a new approach.)
- **KTD3. Family character with multi-level fallback.** `sealChar` computed: `familyName.trim().charAt(0)` → if empty, first member's `name.trim().charAt(0)` → if no members, `'家'`. Mirrors WaxSeal's fallback pattern. (session-settled: agent-recommended.) Governs R2.
- **KTD4. Trigonometric circular positioning.** Members positioned on a circle of radius `r` within a `100×100` viewBox. For N members, member at index `i` is placed at angle `θ = (2π × i / N) - π/2` (start from top). x = 50 + r × cos(θ), y = 50 + r × sin(θ). Edge cases: N=1 → top-center (θ = -π/2); N=2 → top and bottom (θ = -π/2, π/2, producing (50,15) and (50,85)). Ring radius `r = 35` for the member circles, ring stroke circle at `r = 35`. Resolves Outstanding Question from Product Contract.
- **KTD5. CSS class–driven signing state (no inline styles).** Signing state conveyed via CSS modifier classes: `.family-crest__member--active` (gold/visible) vs `.family-crest__member--muted` (low opacity). Never set `style="fill: ..."` or `:style` bindings for theme-sensitive colors — inline styles defeat `[data-theme='dark']` overrides. Transition handled by CSS `transition: opacity 0.3s, transform 0.3s` on the member group. (session-settled: agent-recommended — per dark mode specificity learning.) Governs R4, R6, R7.
- **KTD6. Local MemberInfo interface definition.** FamilyCrest defines its own `MemberInfo` interface matching the shape already used in ClassicTemplate (line 84-89), ModernTemplate (line 69-74), and ManifestoViewer (line 33-38). Follows the existing project convention of local interface definition rather than shared type extraction. (session-settled: agent-recommended — extracting to a shared file would touch 3 existing files, out of scope.) Governs R10.
- **KTD7. Empty family → no render.** When `members` array is empty AND `familyName` is empty, the component renders nothing (`v-if` guard on the root element). When members exist but familyName is empty, the family character falls back to the first member's initial (KTD3). Resolves the "empty family" edge case noted in Dependencies/Assumptions.

---

## Implementation Units

### U1. FamilyCrest core component

- **Goal:** Create the `FamilyCrest.vue` component with dynamic SVG rendering, circular member layout, signing-state reactivity, dark mode support, reduced motion handling, and scroll reveal integration.
- **Requirements:** R1, R2, R3, R4, R5, R6, R7, R10, R11, R12
- **Dependencies:** None
- **Files:**
  - `frontend/apps/main/src/components/manifesto/FamilyCrest.vue` (create)
- **Approach:**
  1. Define prop interface: `members: MemberInfo[]` and `familyName: string`. Define local `MemberInfo` interface (KTD6).
  2. Computed properties:
     - `sealChar`: `familyName.trim().charAt(0)` || `members[0]?.name.trim().charAt(0)` || `'家'` (KTD3)
     - `memberPositions`: array of `{ member, x, y, isActive }` — compute trigonometric positions (KTD4). `isActive` = `signingStatus === 'signed' || signingStatus === 'confirmed'`.
  3. Template structure (following WaxSeal pattern, KTD2):
     - Root `<div class="family-crest" role="img" :aria-label="crestAriaLabel" v-if="members.length || familyName">` — ARIA label for screen readers (e.g., "Family crest: Demo, 2 of 3 members have signed"). Does NOT use `data-reveal` — ManifestoViewer's unscoped scroll-reveal CSS would conflict with the crest's own entrance animation (feasibility finding).
     - `<svg viewBox="0 0 100 100">` containing: ring `<circle>` (R5), member `<g>` groups positioned via `transform="translate(x, y)"` (R3).
     - Member `<g>` groups positioned via `transform="translate(x, y)"` (R3). Each member group: `<circle r="10">` for the background + `<text font-size="10" text-anchor="middle" dominant-baseline="central">` for the initial character. Font-size 10 in viewBox coords ensures legibility at the minimum 80px render size.
     - `<span class="family-crest__center" style="font-size: 28%">` overlay for the family character (R2) — positioned via CSS over the SVG center. Font-size as percentage of container width ensures consistent proportions.
  4. CSS (scoped):
     - `.family-crest`: `width: clamp(80px, 18vw, 96px); height: auto; margin: 0 auto 0.75rem; display: block; position: relative;` — responsive sizing, floor raised to 80px to keep member initials legible on mobile H5.
     - `.family-crest__member--active circle`: `fill: var(--ceremony-gold, #c9a84c); opacity: 1;` — uses CSS variable, not inline style (KTD5).
     - `.family-crest__member--muted circle`: `fill: var(--ceremony-ink, #1a1a2e); opacity: 0.3;`
     - `.family-crest__member`: `transition: opacity 0.3s ease-out, transform 0.3s ease-out;` — signing-state animation (R6).
     - `.family-crest__member--muted`: `transform: scale(0.9); opacity: 0.5;` — muted state (raised from 0.3 for WCAG contrast compliance).
     - `.family-crest__member--active`: `transform: scale(1); opacity: 1;` — active state.
     - `@media (prefers-reduced-motion: reduce)`: `.family-crest__member { transition: none; }` — reduced motion (R7).
     - Dark mode: `:global([data-theme='dark']) .family-crest__member--muted circle { fill: var(--ceremony-ink-dark, #f0ece4); opacity: 0.45; }` — dark mode opacity raised to 0.45 for contrast (per WCAG AA 3:1 for graphical objects).
  5. Entrance animation: use double-`requestAnimationFrame` pattern from WaxSeal (flip a `revealed` ref on mount). Skip if `prefersReducedMotion()` returns true.
- **Patterns to follow:** `WaxSeal.vue` — SVG structure, CSS variable usage, double-rAF animation, `defineOptions`, scoped CSS with `:global([data-theme='dark'])`.
- **Verification:** Component mounts without errors. SVG renders correct number of member positions. CSS classes match signing states. No inline styles for theme colors.

### U2.. ClassicTemplate integration

- **Goal:** Replace the static ⚜ emblem in ClassicTemplate with the FamilyCrest component, passing the required props.
- **Requirements:** R8, R10, R11
- **Dependencies:** U1
- **Files:**
  - `frontend/apps/main/src/components/manifesto/templates/ClassicTemplate.vue` (modify)
- **Approach:**
  1. Import `FamilyCrest` component.
  2. Replace the existing `.certificate-emblem` block (lines 13-16: `<div class="certificate-emblem"><div class="emblem-shield">⚜</div></div>`) with `<FamilyCrest :members="members" :familyName="familyStore.family?.name ?? ''" />`.
  3. The `useFamilyStore()` is already imported and used in ClassicTemplate (line 108). Pass `familyStore.family?.name ?? ''` as `familyName` prop.
  4. Pass the existing `members` prop (already available from the template's own props).
  5. Remove ALL `.certificate-emblem` and `.emblem-shield` CSS rules — both the layout styles (lines ~188-206) AND the scroll-reveal animation references (lines ~331-333 and the prefers-reduced-motion override at line ~356). These classes no longer exist in the template.
  6. No other template changes. The FamilyCrest occupies the same visual position as the old emblem.
- **Patterns to follow:** Existing prop-passing pattern in ClassicTemplate (e.g., how WaxSeal receives `familyName` at line 110).
- **Test scenarios:**
  - ClassicTemplate renders FamilyCrest instead of the static emblem
  - FamilyCrest receives correct `members` prop (forwarded from template props)
  - FamilyCrest receives correct `familyName` from family store
  - No `.certificate-emblem` or `.emblem-shield` elements in the rendered output
  - Existing template functionality (title, body, signatures, WaxSeal) is unaffected
- **Verification:** bsk screenshot of ClassicTemplate sign page shows FamilyCrest above the document title in gold ceremony style. No ⚜ emoji visible.

### U3. ModernTemplate integration

- **Goal:** Add the FamilyCrest component above the document title in ModernTemplate.
- **Requirements:** R9, R10, R11
- **Dependencies:** U1
- **Files:**
  - `frontend/apps/main/src/components/manifesto/templates/ModernTemplate.vue` (modify)
- **Approach:**
  1. Import `FamilyCrest` component.
  2. Insert `<FamilyCrest :members="members" :familyName="familyStore.family?.name ?? ''" />` between the accent bar (lines 7-11) and the `<div class="modern-header">` (line 13).
  3. The `useFamilyStore()` needs to be imported (check if already present; if not, add `const familyStore = useFamilyStore()`).
  4. Pass `members` from the template's existing props.
  5. No CSS changes needed — FamilyCrest provides its own styling.
- **Patterns to follow:** Same prop-passing pattern as U2.
- **Test scenarios:**
  - ModernTemplate renders FamilyCrest above the modern-header
  - FamilyCrest receives correct `members` and `familyName` props
  - Existing template functionality (title, body, signatures, WaxSeal) is unaffected
- **Verification:** bsk screenshot of ModernTemplate sign page shows FamilyCrest above the document title. Layout is clean, no overlap with accent bar or header.

### U4. Unit tests

- **Goal:** Comprehensive Vitest + @vue/test-utils test suite for FamilyCrest.
- **Requirements:** R1, R2, R3, R4, R5, R6, R7
- **Dependencies:** U1
- **Files:**
  - `frontend/apps/main/src/components/manifesto/__tests__/FamilyCrest.spec.ts` (create)
- **Approach:**
  1. Follow `scrollReveal.spec.ts` test setup pattern:
     - Mock `vue-i18n`: `vi.mock('vue-i18n', () => ({ useI18n: () => ({ t: (key: string) => key }) }))`
     - Mock `matchMedia` for `prefers-reduced-motion` support (per scrollReveal.spec.ts lines 38-48).
     - Stub child components if needed.
  2. Test categories:
     - **Happy path:** SVG renders with correct member count, family character, ring circle, member positions.
     - **Edge cases:** Empty members + empty familyName (no render, KTD7). Single member (N=1). Empty familyName with members (fallback character, KTD3).
     - **Signing states:** Each status value maps to correct CSS class. Transition between states.
     - **Accessibility:** `data-reveal` attribute present. CSS transition respects `prefers-reduced-motion`.
  3. Helper to create test members: `createMember(name, status)` factory.
- **Patterns to follow:** `scrollReveal.spec.ts` — mount with props, assert DOM structure, use `wrapper.find()` for SVG elements.
- **Test scenarios:**
  - Covers AE1: mounts with 3 members, verifies 3 member groups in SVG, verifies ring circle present, verifies family character text.
  - Covers AE2: mounts with mixed statuses, verifies active/muted class assignment per member.
  - Covers AE3: mounts with `prefers-reduced-motion: reduce`, verifies no CSS transition on member groups.
  - Covers AE5: mounts with 1 member, verifies single member group at expected position.
  - Renders nothing when members=[] and familyName=''.
  - `sealChar` fallback chain: familyName → first member name → '家'.
  - Root element has `role="img"` and computed `aria-label` attribute.
  - Root element does NOT have `data-reveal` attribute (scroll reveal conflict avoidance).
  - Prop interface accepts `members: MemberInfo[]` and `familyName: string` (R10).
  - CSS transition on `.family-crest__member` includes both `opacity` and `transform`.
- **Verification:** All tests pass. `cd frontend/apps/main && pnpm vitest run src/components/manifesto/__tests__/FamilyCrest.spec.ts`.

---

## Verification Contract

| Gate | Command | Applies to | Done when |
|------|---------|-----------|-----------|
| Type check | `cd frontend/apps/main && pnpm typecheck` | U1–U3 | Zero errors |
| Unit tests | `cd frontend/apps/main && pnpm vitest run src/components/manifesto/__tests__/FamilyCrest.spec.ts` | U1, U4 | All tests pass |
| Visual (classic) | bsk screenshot of `/manifesto/sign` with ClassicTemplate | U2 | FamilyCrest visible above title, gold ceremony style, no ⚜ emoji |
| Visual (modern) | bsk screenshot of `/manifesto/sign` with ModernTemplate | U3 | FamilyCrest visible above title, clean layout |
| Dark mode | bsk screenshot in dark mode | U1 | Muted initials visible against dark background, gold active initials |
| Reduced motion | bsk screenshot with `prefers-reduced-motion` | U1 | Crest renders correctly, no animation on signing state change |
| Edge case | bsk screenshot with 1-member family | U1 | Single initial on ring, no layout breakage |

---

## Definition of Done

- All 4 implementation units are implemented and type-check cleanly.
- Unit tests pass for FamilyCrest covering signing states, edge cases, and accessibility.
- bsk screenshots of both ClassicTemplate and ModernTemplate confirm the crest renders above the document title.
- Dark mode renders correctly — muted initials visible, gold active initials.
- `prefers-reduced-motion` skips signing-state animation.
- The static ⚜ emblem in ClassicTemplate is fully removed (no dead CSS).
- No regressions in existing manifesto functionality (signing, flow viewer, WaxSeal, scroll reveal).
- CeremonyRoom container (R12) is not affected — crest renders inside it without layout conflict.

### Product Contract preservation

R-IDs, F-IDs, AE-IDs preserved. KTD1 clarifies that R8 and R9 share a single visual treatment via ceremony token cascade — R9's original "line-based, system accent color" framing is superseded by KTD1's "identical gold ceremony styling" for both templates. AE4's expectation of visually distinct templates is resolved by KTD1: both render identically. No other scope changes.
