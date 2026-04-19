---
title: "feat: Rename landing/ to site/ + Two-Page Site (Brand + Developer)"
type: feat
status: completed
date: 2026-04-19
origin: docs/brainstorms/2026-04-19-two-page-landing-requirements.md
---

# feat: Rename landing/ to site/ + Two-Page Site (Brand + Developer)

## Overview

**Architecture change:** Rename `landing/` → `site/` to clarify that this is the brand/marketing static site, not just a "landing page." This decouples the brand site from functional modules (`frontend/`, `backend/`).

**New pages:** Add two purpose-built static pages alongside the existing `site/index.html`:

- `site/product/index.html` — brand/marketing page for families; minimalist, atmospheric, brand-recognition focus
- `site/dev/index.html` — developer evaluation page; feature-first, then deployment guide

Both pages are pure static HTML/CSS, reuse the existing `site/style.css` and `site/assets/`, and are deployable by copying the `site/` directory to any nginx root. The existing `site/index.html` is untouched.

## Problem Frame

**Architecture:** The `landing/` directory name implies a single landing page, but it's actually the entire brand/marketing static site published to `numina.app`. Renaming to `site/` clarifies its role and aligns with the naming convention of other top-level modules (`backend/`, `frontend/`, `tests/`).

**Content:** The existing single landing page mixes family-focused marketing with developer deployment info, creating a tone conflict. A family member browsing for product understanding encounters docker commands; a developer evaluating the project has to scroll past emotional copy to find the tech stack. Splitting into two audience-specific pages resolves this.

(see origin: `docs/brainstorms/2026-04-19-two-page-landing-requirements.md`)

## Requirements Trace

- R-brand-1. Brand page communicates product philosophy without feeling transactional
- R-brand-2. Hero: headline + subheadline + single screenshot + soft dual CTA
- R-brand-3. Philosophy section: 3 pillars (privacy, family, open source)
- R-brand-4. Feature showcase: 4 decorative cards with screenshot thumbnails
- R-brand-5. Children incentive highlight: full-width atmospheric section
- R-brand-6. Footer with cross-link to `/dev/`
- R-dev-1. Developer page leads with full feature list for evaluation
- R-dev-2. Trust badges (36+ Tests, Self-Hosted, Open Source, MIT) with tap-to-expand
- R-dev-3. Tech stack section
- R-dev-4. Comparison grid (Numina vs 传统预算应用 vs 电子表格)
- R-dev-5. Quick deploy section with terminal block and step-by-step guide
- R-dev-6. Configuration reference table (env vars)
- R-dev-7. Database options section
- R-dev-8. Sticky nav with anchor links and `scroll-margin-top` on targets
- R-shared-1. Pure static HTML/CSS, no build tools
- R-shared-2. Asset paths use `../assets/` (works for `file://` and nginx)
- R-shared-3. Both pages mobile-responsive (320px+)
- R-shared-4. Both pages open from `file://` without broken assets

## Scope Boundaries

- No modification to `site/index.html` content (only moved, not edited)
- No i18n / English version
- No interactive demo or live metrics
- No animation libraries (Lottie, GSAP)
- No user testimonials
- No search or navigation beyond anchor links

### Deferred to Separate Tasks

- README cross-links to `/product/` and `/dev/`: separate PR updating README.md

## Context & Research

### Relevant Code and Patterns

- `site/style.css` — complete design system: CSS custom properties, typography, breakpoints, all component classes. **Both new pages link `../style.css` directly** — no CSS duplication needed.
- `site/index.html` — reference for: `<html lang="zh-CN">` head pattern, skip-link, `onerror` fallback on `<img>`, `.btn`/`.btn-primary`/`.btn-secondary` CTAs, `.terminal-block`/`.cursor` dark section, `.trust-badge` `<details>` accordion, `.comparison-table`/`.numina-column`, `.feature-grid`/`.feature-card`, footer structure, inline `<script>` single-open accordion behavior
- `site/assets/` — all images and icons already exist; no new assets needed

### CSS Design System (from `site/style.css`)

| Token | Value |
|---|---|
| `--color-primary` | `#007aff` |
| `--color-bg` | `#f5f5f7` |
| `--color-text` | `#1d1d1f` |
| `--color-text-secondary` | `#6e6e73` |
| Font stack | `-apple-system, BlinkMacSystemFont, 'PingFang SC', ...` |
| Mobile base padding | `16px` |
| Tablet padding | `32px` |
| Desktop padding | `48px–64px` |
| Border radius | `8px` (buttons), `12px` (cards) |

### Deploy Infrastructure

- `.github/workflows/deploy-pages.yml` — currently triggers on `landing/**` and publishes `./landing`; **must be updated** to trigger on `site/**` and publish `./site`
- CNAME: `numina.app` (moves from `landing/CNAME` to `site/CNAME`, content unchanged)
- No other workflow changes needed

### Institutional Learnings

- No prior `docs/solutions/` entries for static HTML/CSS — greenfield territory

## Key Technical Decisions

- **Reuse `../style.css` with care**: Both new pages link `../style.css`. All existing classes are available. However, `style.css` uses **ID selectors** (`#deploy`, `#features`, `#trust`, `#comparison`, `#hero`) that apply automatically to any element with those IDs — they are not opt-in. The implementer must either reuse those IDs intentionally (accepting the inherited styles) or use different IDs on the new pages to avoid unintended style inheritance. The developer page's deploy section should use `id="deploy"` deliberately to inherit the dark background from `style.css`. Other section IDs should be chosen to match or avoid existing ID rules as appropriate.
- **Page-specific `<style>` blocks**: New layout classes (`.philosophy-grid`, `.highlight-section`, `.stack-grid`, sticky nav) go in a `<style>` block in `<head>`. Do not re-declare classes that already exist in `style.css` (e.g., `.feature-card:hover` is already defined in `style.css` — do not add a duplicate rule in the page `<style>` block, as specificity conflicts will cause unpredictable results). Check `style.css` before adding any override.
- **Asset path `../assets/`**: Relative one-level-up path works for both `file://` browsing and nginx without path rewriting. Verified against the directory structure. Deployment assumption: nginx root must be set to `site/`, not a subdirectory — `../assets/` will 404 if only `site/product/` or `site/dev/` is deployed in isolation.
- **Brand page: zero JS**: No `<details>` elements on brand page, so no accordion script needed.
- **Developer page: inline `<script>` at body end**: Verbatim copy of the single-open accordion behavior from `index.html` — ~10 lines, no external dependency.
- **`scroll-margin-top` on anchor targets**: Developer page has sticky nav; all `<section>` anchor targets need `scroll-margin-top` equal to the rendered sticky header height. At 320px viewport the nav links may wrap to two lines, making the nav taller than 60px — measure the actual rendered height at 320px and set `scroll-margin-top` accordingly. Use a CSS custom property (e.g., `--nav-height: 60px`) so it can be adjusted in one place.
- **No new assets**: All 4 screenshots and 4 icons already exist in `landing/assets/icons/` and `landing/assets/*.webp`.

## Open Questions

### Resolved During Planning

- **Shared CSS or not?** Resolved: link `../style.css` from both pages. The stylesheet already exists and all needed classes are defined. No duplication.
- **Asset paths for subpages?** Resolved: `../assets/` (relative). Verified against directory structure.
- **GitHub Actions workflow changes?** Resolved: update `deploy-pages.yml` — change `paths: landing/**` → `site/**` and `publish_dir: ./landing` → `./site`. One file, two lines.
- **Directory rename approach?** Resolved: `git mv landing site` — preserves git history, updates all files atomically.
- **AI features on dev page?** Resolved: removed. Not yet implemented in codebase.

### Deferred to Implementation

- Exact sticky nav height (needed for `scroll-margin-top` value) — measure after implementing the nav
- Whether any additional page-specific CSS overrides are needed beyond what `style.css` provides — discover during implementation

## Output Structure

```
site/                           # RENAMED from landing/
├── index.html              # existing (moved, content untouched)
├── style.css               # existing (moved, untouched, linked by new pages)
├── CNAME                   # existing (moved, content untouched: numina.app)
├── assets/                 # existing (moved, untouched, referenced via ../assets/)
│   ├── favicon.svg
│   ├── dashboard-final-top.webp
│   ├── dashboard-final-bottom.webp
│   ├── dashboard-final-cards.webp
│   ├── wishes-page.webp
│   └── icons/
│       ├── asset-tracking.svg
│       ├── children-incentive.svg
│       ├── dashboard-visualization.svg
│       └── liability-management.svg
├── product/
│   └── index.html          # NEW: brand/marketing page
└── dev/
    └── index.html          # NEW: developer evaluation page
```

## Implementation Units

- [ ] **Unit 1: Brand page — `landing/product/index.html`**

**Goal:** Create the family-focused brand/marketing page with atmospheric tone, no transactional elements.

**Requirements:** R-brand-1 through R-brand-6, R-shared-1 through R-shared-4

**Dependencies:** None (uses existing assets and stylesheet)

**Files:**
- Create: `landing/product/index.html`

**Approach:**
- `<head>`: `lang="zh-CN"`, title "Numina - 家庭资产，一目了然", description meta, `../style.css`, `../assets/favicon.svg`
- Skip-link: `<a href="#features" class="skip-link">跳转到主要内容</a>`
- **Section 1 — Hero**: Full-width, headline + subheadline + single `<img src="../assets/dashboard-final-top.webp">` (hero-image class, `onerror` fallback) + two CTAs using `.btn-primary` ("探索功能 →" href="#features") and `.btn-secondary` ("了解部署" href="../dev/")
- **Section 2 — Philosophy**: 3-column grid (icon emoji or inline SVG + short phrase + one sentence each): 隐私优先 / 家庭共享 / 开源透明. Use a new `.philosophy-grid` layout (3 equal columns, gap 24px, stacks to 1-col on mobile) — add as a `<style>` block in `<head>` since this layout doesn't exist in `style.css`
- **Section 3 — Feature Showcase** (`id="features"`): `.feature-grid` with 4 `.feature-card` articles. Cards are decorative — no `tabindex`, no `href` on the card itself. Each card: `.card-icon` img + `<h3>` + `.card-description` + `.card-thumbnail` img (lazy). Below each card: `<a href="https://github.com/vincentruan/numina#readme">了解更多 →</a>` text link. Desktop hover: CSS `transform: translateY(-2px)` + box-shadow on `.feature-card:hover` — add to page `<style>` block
- **Section 4 — Children Highlight**: Full-width section with dark background (`background: #1d1d1f`, `color: #f5f5f7`, `padding: 48px 16px`, `text-align: center`). Image `<img src="../assets/wishes-page.webp">` centered above copy text, `max-width: 280px`, `border-radius: 12px`. Copy: `<h2>` "孩子心愿系统" + `<p>` "用星星硬币激励家务，培养财商意识". No CTA. Add `.highlight-section` to page `<style>` block with these properties.
- **Section 5 — Footer**: `.footer-nav` links (GitHub, `../dev/`, LICENSE) + `.footer-text` "Made by Numina Team" + cross-link paragraph "开发者？查看部署指南 →" linking `../dev/`
- Zero JS — no `<script>` tags

**Patterns to follow:**
- `landing/index.html` — head structure, skip-link, img onerror pattern, btn classes, footer structure
- `landing/style.css` — all existing classes; page-specific layout additions go in a `<style>` block in `<head>`

**Test scenarios:**
- Happy path: Open `landing/product/index.html` via `file://` in browser — all 4 feature card screenshots load, hero screenshot loads, wishes screenshot loads, no broken image icons
- Happy path: "探索功能 →" CTA scrolls to `#features` section without page reload
- Happy path: "了解部署" CTA navigates to `../dev/index.html` (same tab)
- Happy path: Footer "查看部署指南 →" link navigates to `../dev/index.html`
- Edge case: Resize to 320px width — all sections stack to single column, no horizontal overflow, text remains readable
- Edge case: Resize to 768px — philosophy pillars display as 3 columns
- Edge case: Tab through page with keyboard — skip-link appears on first Tab, focus order is logical, no keyboard traps
- Edge case: All `<img>` tags have meaningful `alt` text (hero and feature cards) or empty `alt=""` (decorative icons)

**Verification:**
- Open via `file://` — zero broken images, zero console errors
- Validate HTML structure: hero → philosophy → features → highlight → footer order
- Mobile 320px: no horizontal scroll, all content visible
- Desktop: feature cards show hover lift on mouse-over
- "了解部署" link reaches `../dev/index.html` correctly

---

- [ ] **Unit 2: Developer page — `landing/dev/index.html`**

**Goal:** Create the developer evaluation page with sticky nav, full feature list, tech stack, comparison grid, deploy guide, and config reference.

**Requirements:** R-dev-1 through R-dev-8, R-shared-1 through R-shared-4

**Dependencies:** Unit 1 (cross-links reference `../product/`)

**Files:**
- Create: `landing/dev/index.html`

**Approach:**
- `<head>`: `lang="zh-CN"`, title "Numina - 开发者文档", description meta, `../style.css`, `../assets/favicon.svg`. Add page-specific `<style>` block for: sticky nav, `scroll-margin-top` on section targets, tech stack grid, config table, step list
- **Sticky Nav** (`<header>`): `position: sticky; top: 0; z-index: 100; background: white; border-bottom: 1px solid #e5e5e7`. Contains: logo text "Numina" + nav links (anchor hrefs: `#features`, `#stack`, `#deploy`, `#config`) + cross-link `<a href="../product/">产品介绍 →</a>`. All `<section>` targets get `scroll-margin-top: 60px` (adjust to actual nav height)
- **Section 1 — Feature Overview** (`id="features"`): `<h2>` + feature list organized by 5 categories (资产管理, 负债管理, 数据可视化, 家庭协作, 孩子系统). Each category: `<h3>` + `<ul>` of feature bullets. Below feature list: `.trust-badges` div with 4 `.trust-badge` `<details>` elements (36+ Tests, Self-Hosted, Open Source, MIT License) — verbatim structure from `index.html`
- **Section 2 — Tech Stack** (`id="stack"`): `<h2>` + 3-column grid (Backend / Frontend / Infrastructure). Each column: heading + `<ul>`. Use `.philosophy-grid`-style layout or a new `.stack-grid` in the `<style>` block
- **Section 3 — Comparison Grid**: `<h2>` + `.comparison-table` with `.numina-column` — verbatim structure from `index.html`. 5 rows: 隐私保护 / 家庭结构 / 负债追踪 / 孩子激励 / 成本. `<tfoot>` "Last updated: 2026-04-19"
- **Section 4 — Quick Deploy** (`id="deploy"`): Dark section (reuse `#deploy` styles from `style.css` if applicable, or add dark bg in `<style>`). `.terminal-block` with `.terminal-command` "docker-compose up -d" + `.cursor` span. Tagline "一键启动". Numbered step list: 1. clone repo 2. configure `.env` (SECRET_KEY) 3. `docker-compose up -d` 4. access `http://localhost:8080`. Link to GitHub README quick-start
- **Section 5 — Config Reference** (`id="config"`): `<h2>` + `<table>` with columns: 变量名 / 默认值 / 说明. Rows: `SECRET_KEY` (none, **生产必填**) / `DATABASE_URL` (sqlite:///./data/numina.db) / `CORS_ORIGINS` (["*"]) / `PORT` (8080). Note: "⚠️ 生产环境必须设置 SECRET_KEY"
- **Section 6 — Database Options**: `<h2>` + 3 subsections (SQLite / MySQL / PostgreSQL) each with connection string format in `<code>` block
- **Footer**: `.footer-nav` links (GitHub repo, Issues, LICENSE, CI dashboard) + `.footer-text` "Last updated: 2026-04-19" + cross-link "产品介绍 →" linking `../product/`
- **Inline `<script>` at body end**: Verbatim single-open accordion from `index.html`

**Patterns to follow:**
- `landing/index.html` — trust badge `<details>` pattern + single-open script, comparison table structure, terminal block, footer
- `landing/style.css` — `.trust-badge`, `.comparison-table`, `.numina-column`, `.terminal-block`, `.cursor`, `.btn`

**Test scenarios:**
- Happy path: Open `landing/dev/index.html` via `file://` — page loads, sticky nav visible, all 6 sections present
- Happy path: Click each anchor nav link — page scrolls to correct section, section heading not hidden behind sticky nav (scroll-margin-top working)
- Happy path: Click a trust badge `<details>` — expands to show description + link; clicking a second badge closes the first (single-open behavior)
- Happy path: All 4 trust badge links point to correct external URLs (GitHub Actions, GitHub repo, LICENSE)
- Happy path: Config table renders with all 4 env vars, SECRET_KEY row has production warning
- Happy path: "产品介绍 →" footer link navigates to `../product/index.html`
- Edge case: Resize to 320px — sticky nav wraps gracefully or scrolls horizontally without breaking layout; comparison table scrolls horizontally; no content overflow
- Edge case: Open via `file://` — `../assets/favicon.svg` loads (no broken favicon)
- Edge case: Tab through sticky nav — all anchor links and cross-link are keyboard-reachable
- Integration: Anchor links from sticky nav + `scroll-margin-top` — verify section headings are fully visible (not clipped) after anchor navigation at multiple viewport widths

**Verification:**
- Open via `file://` — zero broken images, zero console errors
- All 4 sticky nav anchors scroll to correct sections with heading fully visible
- Trust badge accordion: open one, open another — first closes automatically
- Config table: all 4 rows present, SECRET_KEY warning visible
- Mobile 320px: comparison table scrolls horizontally, nav doesn't break layout
- Cross-links to `../product/` work correctly

## System-Wide Impact

- **Interaction graph:** No callbacks, middleware, or backend involved — pure static files. GitHub Actions deploy workflow triggers automatically on push to `main` when `landing/**` changes; new files in `landing/product/` and `landing/dev/` are included automatically.
- **Error propagation:** N/A — static pages have no runtime error paths.
- **State lifecycle risks:** None.
- **API surface parity:** N/A.
- **Integration coverage:** The two pages cross-link each other (`../product/` ↔ `../dev/`). Both must exist before cross-links are live; Unit 2 depends on Unit 1 being present for the cross-link to resolve.
- **Unchanged invariants:** `landing/index.html`, `landing/style.css`, `landing/assets/`, `landing/CNAME` — all untouched. GitHub Pages deployment workflow unchanged.

## Risks & Dependencies

| Risk | Mitigation |
|------|------------|
| Page-specific `<style>` block overrides a class already in `style.css` (e.g. `.feature-card:hover`) | Check `style.css` before adding any rule to the page `<style>` block; never re-declare an existing class |
| `#deploy`, `#features`, `#trust` ID selectors in `style.css` auto-apply to matching IDs on new pages | Reuse IDs intentionally (dev page `id="deploy"` inherits dark bg deliberately) or use different IDs to avoid unintended inheritance |
| Sticky nav height at 320px exceeds `scroll-margin-top` estimate | Use `--nav-height` CSS custom property; measure rendered height at 320px and update the value |
| `../assets/` path breaks if nginx root is set to `landing/product/` or `landing/dev/` instead of `landing/` | Document: nginx root must be `landing/`; note in both pages' footers |
| Cross-links between pages break if only one page is deployed | Both pages must be deployed together; they are a unit |
| New pages are unreachable until README cross-links PR merges | README PR is a hard entry-point dependency — ship it immediately after this PR merges |

## Sources & References

- **Origin document:** [docs/brainstorms/2026-04-19-two-page-landing-requirements.md](docs/brainstorms/2026-04-19-two-page-landing-requirements.md)
- Related code: `landing/index.html`, `landing/style.css`
- Deploy workflow: `.github/workflows/deploy-pages.yml`
