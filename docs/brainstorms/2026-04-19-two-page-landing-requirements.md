---
date: 2026-04-19
topic: two-page-landing
---

# Two-Page Landing Site Requirements

## Problem Frame

The existing `landing/index.html` mixes family-focused marketing with developer deployment info into a single page. This creates a tension: the emotional, atmospheric tone needed to build brand affinity conflicts with the dense technical content developers need to evaluate and deploy the project.

**Solution:** Split into two purpose-built static pages with distinct audiences, tones, and information hierarchies.

## Pages Overview

| Page | Path | Audience | Primary Goal |
|------|------|----------|--------------|
| Brand page | `/product/index.html` | Families considering asset tracking | Brand recognition and affinity — let the product philosophy land before asking for action |
| Developer page | `/dev/index.html` | Technical evaluators / deployers | Feature evaluation first, then deployment — "is this worth deploying?" before "how do I deploy?" |

Both pages: pure static HTML/CSS, no build tools, no JS frameworks, deployable directly as nginx static resources.

## Brand Page (`/product/`)

### Page Metadata

- `<title>`: Numina - 家庭资产，一目了然
- `<meta name="description">`: 隐私优先的家庭资产管理系统，自托管、开源、免费
- `<link rel="icon">`: `../assets/favicon.svg`

### Tone and Visual Direction

- Minimalist, atmospheric, generous whitespace
- Unhurried — no aggressive CTAs, no urgency language
- Communicates product philosophy: privacy-first, family-centered, calm financial clarity
- CTA is soft: "了解如何部署" or "探索功能" — not "立即部署"
- Typography-led sections, screenshots used sparingly as emotional anchors

### Content Structure (top to bottom)

1. **Hero** — Full-width, headline-first
   - Headline: communicates the product's core promise (family financial clarity, privacy, calm)
   - Subheadline: one sentence on the philosophy (self-hosted, your data, your family)
   - Single hero screenshot: `assets/dashboard-final-top.webp` — large, centered, no clutter
   - Soft CTA: "探索功能 →" scrolls to features; secondary "了解部署" links to `../dev/` (same tab — user is leaving the brand experience intentionally)

2. **Philosophy Section** — 3 pillars in a row (icon + short phrase + one sentence)
   - 隐私优先：数据存在你的硬件上，不上传任何云端
   - 家庭共享：多角色协作，父母与孩子各有专属视图
   - 开源透明：代码公开，MIT 许可，永久免费

3. **Feature Showcase** — 4 cards (reuse existing structure from `index.html`)
   - 资产追踪 / 负债管理 / 数据可视化 / 孩子激励系统
   - Each: icon + title + 2-sentence description + screenshot thumbnail
   - Cards are decorative (not tappable links) — no `tabindex`, no `href`
   - Desktop hover: lift 2px + shadow; mobile: no interaction state
   - "了解更多 →" text link below each card points to GitHub README section

4. **Children Incentive Highlight** — Full-width emotional section
   - Screenshot: `assets/wishes-page.webp`
   - Copy: 孩子心愿系统 — 用星星硬币激励家务，培养财商意识
   - No CTA — purely atmospheric

5. **Footer**
   - Links: GitHub, `/dev/` (开发者文档), LICENSE
   - "Made by Numina Team"
   - Cross-link to developer page: "开发者？查看部署指南 →"

### What's NOT on the brand page

- No terminal/docker commands
- No comparison table
- No trust badges (too transactional for this tone)
- No "30秒就绪" urgency language

---

## Developer Page (`/dev/`)

### Page Metadata

- `<title>`: Numina - 开发者文档
- `<meta name="description">`: Numina 功能特性、技术架构与部署指南
- `<link rel="icon">`: `../assets/favicon.svg`

### Tone and Visual Direction

- Technical, structured, scannable
- Dense but organized — developers want information density
- Code blocks, tables, anchor navigation
- Trust signals are appropriate here (tests, CI, license)

### Content Structure (top to bottom)

1. **Header / Nav** — Sticky, minimal
   - Logo + page title "开发者文档"
   - Anchor links: 功能特性 | 技术架构 | 快速部署 | 配置参考
   - Cross-link: "产品介绍 →" links to `/product/`

2. **Feature Overview** — Evaluation-first
   - Full feature list organized by category:
     - 资产管理：实物 + 金融资产，分类标签，价值追踪
     - 负债管理：房贷/车贷/信用卡，还款进度
     - 数据可视化：净资产趋势，资产分配饼图，ECharts
     - 家庭协作：多用户角色（管理员/成员/孩子），邀请码
     - 孩子系统：星星硬币，家务模板，心愿兑换
   - Trust badges here: "36+ Tests ✓", "Self-Hosted ✓", "Open Source ✓", "MIT License ✓"
     - Tap-to-expand detail (reuse `<details>` pattern from `index.html`)

3. **Tech Stack Section**
   - Backend: FastAPI + SQLAlchemy + SQLite/MySQL/PostgreSQL + JWT
   - Frontend: Vue 3 + TypeScript + Vite + Vant 4 + ECharts
   - Infrastructure: Docker Compose + Nginx
   - Simple two-column layout or icon grid

4. **Comparison Grid** — (moved from brand page, belongs here)
   - Numina vs 传统预算应用 vs 电子表格
   - Rows: 隐私保护 / 家庭结构 / 负债追踪 / 孩子激励 / 成本
   - Numina column highlighted
   - Semantic HTML (`<thead>`, `<tbody>`, `<th>`)

5. **Quick Deploy Section**
   - Terminal block: `docker-compose up -d` with blinking cursor (CSS-only)
   - Tagline: "一键启动" (no time claim — avoids unverifiable promise)
   - Step-by-step: clone → configure `.env` → `docker-compose up -d` → access `:8080`
   - Link to full README quick-start

6. **Configuration Reference** — Table format
   - Key env vars: `SECRET_KEY`, `DATABASE_URL`, `CORS_ORIGINS`, `PORT`
   - Each: variable name + default + description
   - Note: "生产环境必须设置 SECRET_KEY"

7. **Database Options** — Brief section
   - SQLite (default, zero config)
   - MySQL / PostgreSQL (Docker profiles)
   - Connection string formats

8. **Footer**
   - Links: GitHub repo, Issues, LICENSE, CI dashboard
   - "Last updated: 2026-04-19"
   - Cross-link: "产品介绍 →" links to `/product/`

---

## Shared Constraints

- **Pure static HTML/CSS** — no npm, no build step, no JS frameworks
- **Minimal JS** — `<details>` single-open behavior (inline `<script>`, ~10 lines) on developer page only; brand page has zero JS
- **Asset paths** — use `../assets/` (relative, one level up) for all images and icons; this works for both `file://` browsing and nginx deployment without path rewriting
- **CSS-only animations** — blinking cursor via `@keyframes` only
- **Mobile-responsive** — both pages work on mobile (320px+)
- **Performance** — images lazy-loaded below fold, WebP already in place
- **No shared CSS file** — each page is self-contained (easier nginx deployment; shared styles must be duplicated — acknowledged tradeoff)
- **Sticky nav anchor offset** — developer page anchor targets must use `scroll-margin-top` to account for sticky header height

## Existing Landing Page

`landing/index.html` is **retained as-is** — it serves as the GitHub Pages root (`/`). The two new pages are additions, not replacements. Cross-links connect all three.

**Discoverability:** The root `index.html` currently has no links to `/product/` or `/dev/`. Since modifying it is out of scope, discoverability relies on:
- Direct links from GitHub README (e.g., "产品介绍" → `/product/`, "部署文档" → `/dev/`)
- Cross-links between the two new pages themselves
- This is an acknowledged limitation — the root page is not the entry point for the new pages

## URL Structure

```
landing/
├── index.html          # existing GitHub Pages root (retained)
├── style.css           # existing (retained)
├── assets/             # existing (retained, shared by all pages)
├── product/
│   └── index.html      # brand page (new)
└── dev/
    └── index.html      # developer page (new)
```

## Success Criteria

- Brand page: a non-technical family member reads it and understands what Numina does and why it's different — without feeling sold to
- Developer page: a developer can evaluate all features, understand the tech stack, and deploy from scratch using only this page
- Both pages: open in browser directly from filesystem (`file://`) without broken assets
- Both pages: deployable by copying the `landing/` directory to nginx `root`

## Scope Boundaries

- **Not included:** i18n / English version
- **Not included:** Interactive demo or live metrics
- **Not included:** Animation libraries (Lottie, GSAP)
- **Not included:** User testimonials
- **Not included:** Search or navigation beyond anchor links
- **Not included:** Modifying `landing/index.html` (retained as-is)

## Key Decisions

- **Brand page has no comparison table or trust badges** — too transactional, breaks the atmospheric tone
- **Developer page has comparison table and trust badges** — appropriate for technical evaluation context
- **No shared CSS** — self-contained pages are simpler to deploy and maintain independently
- **Existing assets reused** — no new design work needed
- **`/product/` and `/dev/` paths** — neither overrides the root, both are additive
