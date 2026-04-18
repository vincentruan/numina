---
date: 2026-04-18
topic: landing-page
---

# Landing Page Requirements

## Problem Frame

Numina needs a marketing site to introduce the product to potential users **before** they deploy. Currently, discovery happens through GitHub README, but a dedicated marketing site provides better visual presentation, SEO presence, and conversion-focused UX.

**Target audience:** Families considering asset tracking, evaluating whether Numina fits their needs. Secondary audience: technical evaluators (deployers) who control deployment decisions.

**Deployment:** GitHub Pages at `numina.app` or `numina.github.io` — independent of the self-hosted app, accessible before deployment.

## Requirements

**Hosting & Deployment**

- R1. Static site hosted on GitHub Pages (free, no infrastructure cost)
- R2. Custom domain: `numina.app` (or `numina.github.io` if custom domain unavailable)
- R3. Built from `landing/` directory in repo root, pushed to `gh-pages` branch or GitHub Actions
- R4. Mobile-responsive design (matches app's mobile-first approach)

**Hero Section (Family-Focused)**

- R5. Hero displays family value proposition: dashboard screenshot + children incentive feature highlight
- R6. Use polished screenshots from `docs/images/current/`: dashboard-final-top.png, dashboard-final-cards.png, wishes-page.png
- R7. Primary CTA: "部署试用" → GitHub repo quick-start; Secondary CTA: "了解更多" → scroll to features
- R8. Headline in Chinese: emphasizes family asset clarity + children financial education
- R9. Hierarchy: Dashboard screenshot 60% hero width, feature callout 40% secondary position

**Deploy Section (Below Hero)**

- R10. Terminal-style block showing `docker-compose up -d` command with blinking cursor
- R11. CSS-only animation (keyframes), no animation libraries
- R12. Copy: "一键启动，30秒就绪"
- R13. Links to README quick-start section with step-by-step guide

**Trust Badges Section**

- R14. Badge row: "36+ Tests ✓", "Self-Hosted ✓", "Open Source ✓", "MIT License ✓"
- R15. Tap-to-expand detail (touch-first, works on all devices):
  - "36+ Tests" → "Automated tests passing on every commit"
  - "Self-Hosted" → "Your data stays on your hardware"
  - "Open Source" → "Auditable code on GitHub"
  - "MIT License" → "Free for personal and commercial use"
- R16. Links: CI dashboard, GitHub repo, GitHub repo, LICENSE file respectively
- R17. Badge color: #007aff (Apple HIG primary)

**Comparison Grid Section**

- R18. Feature comparison: Numina vs Traditional Budget Apps vs Spreadsheets (generic categories, not specific brands)
- R19. Rows: Privacy (self-hosted vs cloud), Family Structure (multi-user vs single), Liability Tracking, Children Incentives, Cost (free vs subscription)
- R20. Semantic HTML for SEO (`<thead>`, `<tbody>`, `<th>`)
- R21. Numina column highlighted (border or subtle background)
- R22. "Last updated: [date]" footer for maintenance transparency

**Feature Showcase Section**

- R23. 4 feature cards: Asset Tracking, Liability Management, Dashboard Visualization, Children Incentive System
- R24. Each card: icon + title + 2-3 sentence description + screenshot thumbnail
- R25. Interaction states: hover (lift 2px + shadow), focus (2px outline), active (press down 1px)
- R26. Links: GitHub repo feature section or README descriptions (not app pages — users haven't deployed)

**Footer**

- R27. Links: GitHub repo, documentation (`docs/` folder link), LICENSE
- R28. "Made with ❤️ by Numina Team"

**Performance**

- R29. All images: WebP format, max 200KB each, lazy loading for below-fold
- R30. Target: <2s load time on mobile (3G connection baseline)

## Success Criteria

- Site accessible at `numina.app` (or GitHub Pages URL) before user deploys
- Hero clearly communicates family value proposition with visual hierarchy
- Deploy section proves one-command simplicity for technical evaluators
- Trust badges establish credibility without overwhelming
- Comparison grid uses generic categories, avoids legal/reputation risk

## Scope Boundaries

- **Not included:** Interactive demo, live metrics, backend integration
- **Not included:** Specific competitor names (Mint, YNAB) — use generic categories
- **Not included:** i18n for English (Chinese-only MVP)
- **Not included:** Animation libraries (Lottie, GSAP)
- **Not included:** User testimonials (may add later)

## Key Decisions

- **GitHub Pages deployment:** True pre-deployment discovery, independent of self-hosted stack
- **Generic comparison categories:** Avoids legal risk from outdated competitor claims
- **Family-first hero, deploy secondary:** Visual hierarchy reflects primary audience
- **Tap-first badges:** Works on all devices, no hover dependency
- **Use existing screenshots:** No new design asset creation needed

## Dependencies / Assumptions

- Assumes GitHub Pages custom domain configuration works (standard GitHub feature)
- Assumes screenshots sufficient for marketing (verified: dashboard-final-* are polished)
- Assumes WebP conversion maintains screenshot quality at 200KB limit

## Outstanding Questions

### Resolve Before Planning

- None — premise contradiction resolved

### Deferred to Planning

- [Affects R2][Technical] Custom domain DNS configuration for GitHub Pages
- [Affects R3][Technical] GitHub Actions workflow for gh-pages deployment
- [Affects R11][Technical] CSS keyframes implementation for blinking cursor
- [Affects R29][Technical] WebP conversion script for existing PNG screenshots
- [Affects R23][Technical] Icon source for feature cards (SVG vs emoji)

## Next Steps

-> `/ce:plan` for implementation planning (GitHub Pages setup, CSS layout, image optimization)