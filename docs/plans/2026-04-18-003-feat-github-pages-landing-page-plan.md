---
created: 2026-04-18
status: completed
origin: docs/brainstorms/2026-04-18-landing-page-requirements.md
depth: standard
---

# Implementation Plan: GitHub Pages Landing Page

## Problem Frame

Numina needs a marketing site for pre-deployment discovery. Currently, users only learn about the product through GitHub README after deciding to deploy. A dedicated landing page at `numina.app` will:

1. Present family value proposition visually (dashboard screenshots + children incentive feature)
2. Prove one-command deployment simplicity (terminal hero)
3. Establish credibility (trust badges, comparison grid)
4. Convert technical evaluators and family users

**Scope boundary:** Pure static HTML/CSS/JS, no backend, no animation libraries, no external dependencies beyond GitHub Pages infrastructure.

## Requirements Traceability

Requirements R1-R30 are defined in the origin document: `docs/brainstorms/2026-04-18-landing-page-requirements.md`. This table maps implementation units to those requirements.

| ID | Requirement | Implementation Unit |
|----|-------------|---------------------|
| R1-R4 | GitHub Pages hosting + custom domain | IU-1 (Infrastructure) |
| R5-R9 | Family-focused hero with screenshots | IU-2 (Hero Section) |
| R10-R13 | Terminal deploy section | IU-3 (Deploy Section) |
| R14-R17 | Trust badges with tooltips | IU-4 (Trust Badges) |
| R18-R22 | Generic comparison grid | IU-5 (Comparison Grid) |
| R23-R26 | Feature showcase cards | IU-6 (Feature Showcase) |
| R27-R28 | Footer links | IU-7 (Footer) |
| R29-R30 | WebP optimization + performance | IU-8 (Image Pipeline) |

**Note:** R28 originally specified "Made with ❤️" but D19 resolves to emoji-free footer per consistency with D13.

## Implementation Units

### IU-1: GitHub Pages Infrastructure

**Files:**
- `landing/index.html` — Main HTML entry point
- `landing/style.css` — All CSS (no separate files per section)
- `landing/assets/` — Image directory for WebP screenshots
- `.github/workflows/deploy-pages.yml` — GitHub Actions deployment workflow

**Approach:**
- Create `landing/` directory in repo root (independent from frontend)
- Single HTML file with semantic sections (`<section id="hero">`, `<section id="deploy">`, etc.)
- Include skip-to-content link before hero for screen reader navigation
- Each section uses ARIA landmark roles where appropriate
- Single CSS file with mobile-first breakpoints defined inline:
  - `--bp-mobile: 375px` — base mobile width
  - `--bp-tablet: 768px` — grid transitions (2x2 → 1 column)
  - `--bp-desktop: 1024px` — full desktop layout
  - `--bp-wide: 1440px` — max-width container
- Copy color tokens from `frontend/src/style.css`: `--color-primary: #007aff`, `--color-bg: #f5f5f7`
- GitHub Actions workflow builds nothing (pure static) — just copies `landing/` to `gh-pages` branch
- Custom domain via `CNAME` file in `landing/`

**Decisions:**
- **D1: No build step** — Landing page is hand-authored HTML/CSS, no Vite/webpack. Simplicity favors manual maintenance for a single-page site.
- **D2: Separate directory** — `landing/` independent from `frontend/` avoids coupling app and marketing site.
- **D3: GitHub Actions with peaceiris/action-gh-pages** — Use `peaceiris/actions-gh-pages@v4` workflow; handles CNAME automatically, widely adopted pattern. Triggers on push to main branch, deploys `landing/` contents to `gh-pages` branch.

**Test scenarios:**
- [ ] `landing/index.html` exists and is valid HTML5
- [ ] `landing/style.css` exists and is valid CSS
- [ ] `.github/workflows/deploy-pages.yml` triggers on push to main
- [ ] CNAME file present for `numina.app` domain
- [ ] Deployed site accessible at GitHub Pages URL (manual verification)

---

### IU-2: Hero Section (Family-Focused)

**Files:**
- `landing/index.html` — `<section id="hero">` with headline, screenshots, CTA buttons
- `landing/style.css` — Hero layout (60/40 split), responsive breakpoints
- `landing/assets/dashboard-final-top.webp` — Dashboard hero screenshot
- `landing/assets/dashboard-final-cards.webp` — Dashboard cards screenshot
- `landing/assets/wishes-page.webp` — Children incentive screenshot

**Approach:**
- Hero contains: headline (Chinese), one dashboard screenshot (60% width), feature callout (40%)
- Hero image uses inline `width="375"` and `height="812"` attributes matching portrait aspect ratio (source images are 1125x2436 ≈ 1:2.16) to prevent CLS
- Hero image placeholder: CSS gradient `linear-gradient(135deg, #f5f5f7 0%, #e5e5ea 100%)` matching light mode background
- Hero image fallback: `onerror="this.style.background='#f5f5f7'; this.alt='Dashboard screenshot unavailable'"` for permanent load failure
- Skip-to-content link before hero: `href="#features"`, initially hidden via CSS, becomes visible on focus with outline (WCAG 2.4.7)
- Primary CTA: "部署试用" → GitHub repo quick-start section (solid button: `background: #007aff`, `color: white`, `border-radius: 8px`, hover/focus/active states)
- Secondary CTA: "了解更多" → scroll to features section (outline button: `border: 2px solid #007aff`, `color: #007aff`, matching interaction states)
- Mobile: stack vertically (screenshot first, callout below)

**Decisions:**
- **D4: Use existing screenshots** — `docs/images/current/` contains polished images; copy to `landing/assets/` and convert to WebP.
- **D5: No image cropping** — Display screenshots as-is with CSS max-width constraints; preserve authenticity.
- **D6: Anchor link for secondary CTA** — "了解更多" scrolls to `#features` section via `href="#features"`.

**Headline (Chinese):**
> 家庭资产一目了然，孩子心愿追踪更贴心

**Feature callout text:**
> 孩子心愿系统：用星星硬币激励孩子完成家务，培养财商意识

**Test scenarios:**
- [ ] Hero section renders with headline + single screenshot + callout
- [ ] Primary CTA links to GitHub repo quick-start
- [ ] Secondary CTA scrolls to features section
- [ ] Responsive: mobile stacks vertically, desktop shows 60/40 split
- [ ] Hero image renders correctly without lazy loading
- [ ] Skip link visible on keyboard focus (Tab from page top)

---

### IU-3: Deploy Section (Terminal Hero)

**Files:**
- `landing/index.html` — `<section id="deploy">` with terminal-style block
- `landing/style.css` — Terminal styling, blinking cursor animation

**Approach:**
- Terminal block displays `docker-compose up -d` with monospace font, dark background
- CSS-only blinking cursor via `@keyframes blink` animation
- Tagline: "一键启动，30秒就绪"
- Link to README quick-start section

**CSS Animation:**
```css
@keyframes blink {
  0%, 50% { opacity: 1; }
  51%, 100% { opacity: 0; }
}
.cursor {
  animation: blink 1s infinite;
}
@media (prefers-reduced-motion: reduce) {
  .cursor { animation: none; opacity: 1; }
}
```

**Decisions:**
- **D7: CSS-only animation** — No GSAP/Lottie per requirements R11. Keyframes are sufficient for cursor blink.
- **D8: 1s blink cycle** — Standard terminal cursor timing; matches user expectations.

**Test scenarios:**
- [ ] Terminal block renders with monospace font and dark background
- [ ] Cursor blinks at 1s interval
- [ ] Link to README quick-start section works
- [ ] Section visible below hero (scroll trigger)
- [ ] `prefers-reduced-motion` disables animation

---

### IU-4: Trust Badges

**Files:**
- `landing/index.html` — `<section id="trust">` with badge row
- `landing/style.css` — Badge styling, tooltip expansion

**Badges:**
1. "36+ Tests ✓" → tooltip: "自动化测试覆盖，每次提交验证" → link: GitHub Actions (https://github.com/vincentruan/numina/actions)
2. "Self-Hosted ✓" → tooltip: "数据存储在您的硬件上" → link: GitHub repo
3. "Open Source ✓" → tooltip: "代码公开，可审计" → link: GitHub repo
4. "MIT License ✓" → tooltip: "个人和商业免费使用" → link: LICENSE file (create MIT LICENSE in repo root before deployment)

**Prerequisite:**
- Create `LICENSE` file (MIT license text) in repo root — required before landing page deployment

**Approach:**
- Horizontal row of 4 badges, Apple blue `#007aff` color
- `<details>/<summary>` structure for each badge; summary shows badge label, details shows tooltip text
- Tooltip styling: `background: rgba(0,0,0,0.05)`, `padding: 8px 12px`, `border-radius: 8px`, `max-width: 280px`, `margin-top: 4px`, `font-size: 14px`
- Single-open behavior via JS:
  ```js
  document.querySelectorAll('details.trust-badge').forEach(d => {
    d.addEventListener('toggle', e => {
      if (e.target.open) {
        document.querySelectorAll('details.trust-badge').forEach(other => {
          if (other !== e.target) other.removeAttribute('open');
        });
      }
    });
  });
  ```
- Mobile: 2x2 grid (preserves horizontal scanning, badges fit comfortably)

**Decisions:**
- **D9: Tap-first interaction** — Use `<details>/<summary>` HTML5 elements for expandable tooltips; works on all devices without hover dependency.
- **D10: Badge color from design tokens** — Use `#007aff` (Apple HIG primary) matching frontend.

**Test scenarios:**
- [ ] 4 badges render horizontally on desktop
- [ ] Each badge expands to show tooltip on tap/click
- [ ] Links resolve to correct destinations (GitHub Actions, GitHub repo, LICENSE)
- [ ] Mobile: badges display as 2x2 grid
- [ ] Badge color matches `#007aff`

---

### IU-5: Comparison Grid

**Files:**
- `landing/index.html` — `<section id="comparison">` with semantic table
- `landing/style.css` — Table styling, Numina column highlight

**Columns:**
- Numina | Traditional Budget Apps | Spreadsheets

**Rows:**
- Privacy (self-hosted vs cloud vs local file)
- Family Structure (multi-user roles vs single user vs single file)
- Liability Tracking (yes vs partial vs manual)
- Children Incentives (star coins vs none vs none)
- Cost (free vs subscription vs free)

**Approach:**
- Semantic HTML table with `<thead>`, `<tbody>`, `<th>`
- `<caption class="sr-only">Numina与传统预算应用和电子表格功能对比</caption>` — visually hidden but screen reader accessible
- Numina column has left border highlight (4px, color `#007aff`) for subtle emphasis without overwhelming content
- Footer: "Last updated: 2026-04-18"
- Mobile: table scrolls horizontally (preserves row-by-row comparison comprehension)
- Scroll indicator: `-webkit-overflow-scrolling: touch` + gradient fade at right edge (`mask-image: linear-gradient(to right, black 90%, transparent 100%)`)

**Decisions:**
- **D11: Generic categories** — No specific brand names (Mint, YNAB) per requirements R18; avoids legal/reputation risk.
- **D12: Static update date** — Hard-coded in HTML; update manually when comparison changes.

**Test scenarios:**
- [ ] Table renders with 3 columns, 5 rows
- [ ] Semantic HTML structure (`<thead>`, `<tbody>`, `<th>`, `<caption>`)
- [ ] Numina column has 4px left border in `#007aff`
- [ ] "Last updated" date visible in table footer
- [ ] Mobile: table scrolls horizontally with visible scroll gradient fade
- [ ] Screen reader announces caption when navigating to table

---

### IU-6: Feature Showcase

**Files:**
- `landing/index.html` — `<section id="features">` with 4 feature cards
- `landing/style.css` — Card layout, hover/focus/active states
- `landing/assets/icons/asset-tracking.svg` — Asset tracking icon (stroke-based, 24x24)
- `landing/assets/icons/liability-management.svg` — Liability icon
- `landing/assets/icons/dashboard-visualization.svg` — Dashboard icon
- `landing/assets/icons/children-incentive.svg` — Children incentive icon

**Cards:**
1. Asset Tracking — icon + description: "追踪家庭所有实物与金融资产，实时掌握资产分布与价值变化" + screenshot thumbnail (dashboard-final-top.webp — shows net worth overview)
2. Liability Management — icon + description: "管理房贷、车贷、信用卡负债，清晰了解家庭债务状况与还款进度" + screenshot thumbnail (dashboard-final-bottom.webp — liability section visible)
3. Dashboard Visualization — icon + description: "可视化展示净资产趋势与资产分配，一目了然的家庭财务健康状态" + screenshot thumbnail (dashboard-final-cards.webp)
4. Children Incentive System — icon + description: "星星硬币激励系统，用游戏化方式培养孩子财商与家务责任感" + screenshot thumbnail (wishes-page.webp)

**Approach:**
- Grid of 4 cards, 2x2 on desktop, 1 column on mobile (transition at 768px breakpoint)
- Each card: SVG icon (new icons from D13), title, 2-3 sentence description
- Each card has minimum 44x44px touch target area on mobile (WCAG 2.5.5)
- Screenshot thumbnails use CSS fallback: `object-fit: cover` with `onerror="this.style.background='#f5f5f7'"` for graceful degradation
- Focus outline: 2px solid `#007aff`, offset 2px from card edge (WCAG-compliant contrast)
- Interaction states: hover (lift 2px + shadow `0 4px 12px rgba(0,0,0,0.15)`), focus (outline visible), active (press down 1px)
- Links to GitHub repo feature sections (not app pages)

**Decisions:**
- **D13: Create new SVG icons** — No existing icon system to reuse; create 4 simple SVG icons for landing page (asset, liability, dashboard, children). Place in `landing/assets/icons/`. Avoid emoji per style guidelines.
- **D14: Link to README** — Users haven't deployed; link to GitHub repo feature descriptions, not app routes.

**Test scenarios:**
- [ ] 4 feature cards render in grid
- [ ] Hover state: card lifts 2px with shadow
- [ ] Focus state: 2px outline visible
- [ ] Active state: card presses down 1px
- [ ] Links point to GitHub repo sections
- [ ] Mobile: single column layout

---

### IU-7: Footer

**Files:**
- `landing/index.html` — `<footer>` with links
- `landing/style.css` — Footer styling

**Links:**
- GitHub repo
- Documentation (`docs/` folder link)
- LICENSE

**Content:**
> Made by Numina Team

**Approach:**
- 3 horizontal links, centered, footer-height 48px
- Links use `#007aff` color, hover underline, focus outline
- Mobile: links stack vertically with adequate touch spacing (16px gap)

**Decisions:**
- **D18: 3 essential links** — GitHub (code source), docs (setup guide), LICENSE (legal terms) cover user needs without clutter.
- **D19: No emoji** — Footer text is clean per D13 emoji avoidance decision; consistent across landing page.

**Test scenarios:**
- [ ] Footer renders with 3 links
- [ ] "Made by Numina Team" text visible
- [ ] Links resolve to correct destinations

---

### IU-8: Image Pipeline (WebP Optimization)

**Files:**
- `landing/assets/*.webp` — Converted screenshots
- `scripts/convert-to-webp.sh` — Conversion script (optional, could be manual)

**Source images (copy to landing/assets/ and convert to WebP):**
- `docs/images/current/dashboard-final-top.png` → `dashboard-final-top.webp` (alt: "Dashboard overview showing family net worth, asset allocation pie chart, and trend line chart", hero + feature card 1)
- `docs/images/current/dashboard-final-bottom.png` → `dashboard-final-bottom.webp` (alt: "Dashboard bottom section showing liability summary and recent transactions", feature card 2)
- `docs/images/current/dashboard-final-cards.png` → `dashboard-final-cards.webp` (alt: "Dashboard cards showing top assets with values and categories", feature card 3)
- `docs/images/current/wishes-page.png` → `wishes-page.webp` (alt: "Children wishes page showing star coin progress and chore completion tracking", feature card 4)

**Approach:**
- Use `cwebp` CLI tool or online converter (Squoosh)
- Target: max 200KB per image at quality=80
- Fallback rule: If exceeds 200KB at quality=80, try quality=70. If still exceeds 250KB, accept up to 350KB max. If exceeds 350KB, resize image dimensions instead of sacrificing quality further.
- Lazy loading for below-fold images: `loading="lazy"` attribute

**Decisions:**
- **D15: Manual conversion** — One-time conversion for initial images; script for future updates if needed.
- **D16: Lazy loading** — Hero images load immediately; feature section images use `loading="lazy"`.
- **D17: No responsive images** — Single WebP per screenshot; CSS handles scaling. Simplicity over srcset complexity.

**Test scenarios:**
- [ ] All WebP images under 200KB
- [ ] Hero images load without lazy attribute
- [ ] Below-fold images have `loading="lazy"`
- [ ] Total page load < 2s on 3G (manual verification via Chrome DevTools)

---

## Dependencies and Sequencing

**Phase 1 — Foundation (IU-1, IU-8):**
1. Create `landing/` directory structure
2. Copy and convert screenshots to WebP (IU-8)
3. Write `index.html` skeleton with semantic sections
4. Write `style.css` with mobile-first base (copy design tokens from `frontend/src/style.css`)
5. Create GitHub Actions workflow
6. Create CNAME file

**Phase 2 — Content (IU-2, IU-3, IU-4, IU-5, IU-6, IU-7):**
7. Create MIT LICENSE file in repo root (prerequisite for IU-4 badge link — must complete before step 10)
8. Implement Hero section HTML/CSS with image placeholders and skip link
9. Implement Deploy section with blinking cursor + reduced-motion media query
10. Implement Trust badges with `<details>` tooltips and single-open JS behavior
11. Implement Comparison grid table with caption
12. Implement Feature showcase cards with hover/focus states
13. Implement Footer

**Phase 3 — Polish:**
14. Verify responsive breakpoints (375 mobile, 768 tablet grid transitions, 1024 desktop, 1440 wide desktop)
15. Verify all links resolve correctly (including LICENSE file existence)
16. Test performance (<2s load, CLS < 0.1)
17. Verify `prefers-reduced-motion` disables animations
18. Verify focus outline contrast meets WCAG AA (4.5:1)

---

## Risks and Mitigations

| Risk | Mitigation |
|------|------------|
| Custom domain DNS misconfiguration | Test with `numina.github.io` first; add CNAME after DNS verified |
| WebP quality loss at 200KB limit | Use quality=80; verify screenshots remain readable |
| Comparison grid becomes outdated | Hard-code "Last updated" date; manual maintenance policy |
| Trust badge tooltips unusable on mobile | Use `<details>/<summary>` for tap-first interaction |
| Page exceeds 2s load target | Audit image sizes; ensure lazy loading; inline critical CSS |

---

## Outstanding Questions (Resolved at Implementation)

None — requirements document covers all product decisions. Technical questions defer to implementation discovery.

---

## Test Strategy

**Manual verification:**
- Visual QA: screenshots match expected layout across breakpoints
- Performance: Chrome DevTools network tab, simulate 3G
- Accessibility: keyboard navigation, color contrast check

**Automated checks:**
- HTML validation (W3C validator or manual review)
- CSS validation (no syntax errors)
- GitHub Actions workflow runs without error

---

## References

- Origin document: `docs/brainstorms/2026-04-18-landing-page-requirements.md`
- Design tokens: `frontend/src/style.css`
- Screenshots: `docs/images/current/`
- CI pattern: `.github/workflows/ci.yml`