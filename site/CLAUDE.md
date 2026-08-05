# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Site Module Purpose

The `site/` module is the **brand/marketing static site** for Numina, deployed to `numina.app` via GitHub Pages. It is NOT part of the Vue frontend application — it's a separate, pure static HTML/CSS artifact for pre-deployment discovery and brand storytelling.

**Target audiences:**
- `site/overview/index.html` — Family users (Chinese-speaking, privacy-concerned, emotionally-driven)
- `site/project/index.html` — Developers (technical evaluators, deployment complexity focused)
- `site/index.html` — General landing page (mixed audience, currently placeholder)

## Architecture

```
site/
├── index.html              # General landing (placeholder, needs redesign)
├── overview/index.html     # Brand page for families — atmospheric, minimal
├── project/index.html      # Developer docs — feature-first, deployment guide
├── style.css               # Shared stylesheet (CSS design system)
├── CNAME                   # Custom domain: numina.app
├── assets/                 # Screenshots and icons (WebP optimized)
│   ├── dashboard-final-top.webp
│   ├── dashboard-final-bottom.webp
│   ├── dashboard-final-cards.webp
│   ├── wishes-page.webp
│   └── icons/*.svg
└── robots.txt
```

**Path convention:** All subpages use `../assets/` relative paths (works for `file://` browsing and nginx).

## Design Principles — Avoiding "AI Slop" Aesthetic

The current pages suffer from generic, cookie-cutter design. Future redesigns must:

### Typography Anti-Patterns

| Never Use | Why |
|-----------|-----|
| Inter, Roboto, Arial | Overused, generic, zero character |
| Space Grotesk | Converged choice across generations |
| Fraunces | Overused "distinctive" choice — now generic |
| System fonts | Safe but forgettable |

**Instead:** Choose fonts with character. Pair distinctive display + refined body font.

### Visual Tropes Anti-Patterns

| Never Use | Why |
|-----------|-----|
| Purple gradients on white | Cliché AI aesthetic |
| Aggressive gradient backgrounds | Synthetic, not atmospheric |
| Emoji (unless brand-native) | Feels forced |
| Rounded corners + left-border accent | Cookie-cutter pattern |
| SVG-drawn imagery | Placeholder quality |
| Predictable 3-column grids | No surprise |
| Centered hero with gradient bg | Most generic landing pattern |

**Instead:** Asymmetry, overlap, diagonal flow, grid-breaking elements. Layer gradients with patterns.

### Scale Requirements

- Mobile hit targets: ≥44×44px (WCAG 2.5.5)
- Fixed-size content text: ≥24px
- Print: ≥12pt

### CSS Allies

Use modern features: `text-wrap: pretty`, CSS Grid `gap`, `aspect-ratio`, `clamp()`, `backdrop-filter`.

---

**Deep reading:** See `design-reference.md` for comprehensive patterns, animation code, background techniques, and process checklist.

**Remember**: Bold maximalism and refined minimalism both work — the key is **intentionality**. Match complexity to aesthetic vision.

## File Relationships

- `style.css` is linked by all HTML pages — changes affect all pages
- ID selectors in `style.css` (`#hero`, `#deploy`, `#features`) auto-apply to matching IDs
- Page-specific styles go in `<style>` blocks in each HTML file's `<head>`
- NEVER redeclare classes from `style.css` in page `<style>` blocks (specificity conflicts)

## Content Guidelines

### Overview Page (Family Brand)

- **Tone**: Atmospheric, minimal, brand-recognition focus
- **Language**: Chinese-first, no English leakage
- **Structure**: Hero → Philosophy pillars → Feature showcase → Children highlight → Footer
- **Philosophy pillars**: 隐私优先 / 家庭共享 / 开源透明 — use emojis or inline SVGs
- **CTAs**: Soft, non-transactional ("探索功能 →", not "立即部署")
- **Zero JavaScript** — no `<script>` tags on this page

### Project Page (Developer Docs)

- **Tone**: Feature-first, technical, deployment-focused
- **Sticky nav**: Anchor links with `scroll-margin-top: var(--nav-height)`
- **Trust badges**: `<details>` accordion with single-open behavior (inline script at body end)
- **Comparison grid**: Numina vs Traditional vs Spreadsheets — `.numina-column` left-border accent
- **Deploy section**: Dark background (`#1d1d1f`), terminal animation, step-by-step guide
- **Config table**: Environment variables with SECRET_KEY production warning

## Deployment

```bash
# Local preview (works with file:// paths)
open site/index.html
open site/overview/index.html
open site/project/index.html

# GitHub Pages deployment
# Automatically triggers on push to main when site/** changes
# Workflow: .github/workflows/deploy-pages.yml
# Publishes ./site to gh-pages branch

# nginx deployment
# Set root to site/ directory (not subdirectories)
# ../assets/ paths require root-level access
```

## Accessibility

- Skip-link: `<a href="#features" class="skip-link">跳转到主要内容</a>`
- Alt text for screenshots (meaningful description)
- Alt="" for decorative icons
- Min 44×44px touch targets on mobile
- `prefers-reduced-motion` media query disables cursor blink animation

## Cross-Links

Both pages cross-link each other:
- `overview/index.html` footer: "开发者？查看部署指南 →" → `../project/`
- `project/index.html` footer: "产品介绍 →" → `../overview/`

## What NOT to Do

- Do NOT add filler content, placeholder sections, or "data slop"
- Do NOT use Inter/Roboto/Arial/Space Grotesk fonts
- Do NOT use purple gradients or generic rounded-corner + left-border patterns
- Do NOT add JavaScript on overview page (brand should be static)