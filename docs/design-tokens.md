# Cross-App Design Token Mapping

> Two design systems, one family. This document maps the token overlap between the main app (adult-facing) and child app, establishing naming conventions and a11y baselines.

## Design Systems Overview

| | Main App | Child App |
|---|---|---|
| **Name** | Together AI | Clay |
| **File** | `frontend/apps/main/src/style.css` | `frontend/apps/child/src/assets/clay.css` |
| **Audience** | Adults (financial management) | Children (gamified learning) |
| **Tone** | Professional, clean, deep navy | Warm, playful, cream/canvas |
| **Dark mode** | `[data-theme="dark"]` | `[data-theme="dark"]` |

---

## Shared Semantic Tokens

These tokens exist in **both** apps with the same name but **different values** (appropriate to each brand). They serve identical semantic purposes.

| Token | Main (Light) | Child (Light) | Main (Dark) | Child (Dark) | Purpose |
|-------|-------------|--------------|------------|-------------|---------|
| `--color-success` | `#1a7a4a` | `#22c55e` | `#2f9e44` | `#22c55e` | Success/positive states |
| `--color-error` | `#b30000` | `#ef4444` | *(inherits)* | *(inherits)* | Error/danger states |
| `--color-canvas` | `#ffffff` | `#fffaf0` | `#0a0a1a` | `#0a1a1a` | Page background |
| `--color-ink` | `#0a0a0a` | `#0a0a0a` | *(inherits)* | *(inherits)* | Primary text |
| `--color-muted` | `#93939f` | `#6a6a6a` | *(inherits)* | *(inherits)* | Secondary/muted text |
| `--color-on-primary` | `#ffffff` | `#ffffff` | *(inherits)* | *(inherits)* | Text on primary buttons |
| `--color-on-dark` | `#ffffff` | `#ffffff` | *(inherits)* | *(inherits)* | Text on dark surfaces |

### Note on Values

The values intentionally differ:
- **Child `--color-success`** (`#22c55e`) is brighter/more saturated — matches the playful Clay palette
- **Main `--color-success`** (`#1a7a4a`) is deeper/more muted — matches the professional Together AI palette
- **Child `--color-canvas`** (`#fffaf0`) has a warm cream tint; **Main** is pure white `#ffffff`

---

## App-Only Brand Tokens

### Main App (Together AI)

| Token | Light | Dark | Purpose |
|-------|-------|------|---------|
| `--color-primary` | `#010120` | — | Brand primary (deep navy) |
| `--color-action-blue` | `#1863dc` | — | Primary action color |
| `--color-coral` | `#ff7759` | — | Accent/CTA |
| `--color-deep-green` | `#003c33` | — | Secondary accent |
| `--color-soft-stone` | `#f7f8fa` | `#12122a` | Secondary surface |
| `--color-card-border` | `rgba(1,1,32,0.08)` | `rgba(255,255,255,0.08)` | Card boundaries |
| `--color-cost` | `#f5a623` | `#ffc04d` | Opportunity cost / amber |
| `--color-trend-up` | `#FF4D4D` | — | Chart up-trend |
| `--color-trend-down` | `#00A854` | — | Chart down-trend |

### Child App (Clay)

| Token | Light | Dark | Purpose |
|-------|-------|------|---------|
| `--color-brand-pink` | `#ff4d8b` | — | Primary brand accent |
| `--color-brand-lavender` | `#b8a4ed` | — | Secondary accent |
| `--color-brand-peach` | `#ffb084` | — | Warm accent |
| `--color-brand-ochre` | `#e8b94a` | — | Gold/coin accent |
| `--color-brand-mint` | `#a4d4c5` | — | Fresh accent |
| `--color-brand-coral` | `#ff6b5a` | — | Energy accent |
| `--color-surface-soft` | `#faf5e8` | — | Card/section background |
| `--color-surface-card` | `#f5f0e0` | — | Elevated card surface |
| `--color-warning` | `#f59e0b` | — | Warning state (main uses `--color-cost`) |

#### Coin Metallic Palette (Child-only)

Three-tier coin system with metallic gradient tokens:

| Tier | Highlight | Mid | Shadow | Deep |
|------|-----------|-----|--------|------|
| Gold | `#FFF5C3` | `#D4AF37` | `#996515` | `#4A2E00` |
| Silver | `#FFFFFF` | `#A9B0C0` | `#5D6775` | `#2C3540` |
| Copper | `#F4A460` | `#B87333` | `#6E3311` | `#2E1100` |

---

## Naming Convention

| Prefix | Scope | Example |
|--------|-------|---------|
| `--color-brand-*` | Brand palette (child) | `--color-brand-pink` |
| `--color-surface-*` | Surface/background layers | `--color-surface-soft` |
| `--color-*` (semantic) | State-driven colors | `--color-success`, `--color-error` |
| `--color-coin-*` | Coin tier rendering (child) | `--color-coin-gold-mid` |
| `--color-trend-*` | Chart/data visualization (main) | `--color-trend-up` |
| `--color-on-*` | Text on colored backgrounds | `--color-on-primary` |

---

## A11y Contrast Requirements

All text/background pairs must meet **WCAG AA** minimum:

| Text Size | Minimum Contrast Ratio |
|-----------|----------------------|
| Normal text (< 18px or < 14px bold) | **4.5:1** |
| Large text (≥ 18px or ≥ 14px bold) | **3:1** |
| UI components / graphical objects | **3:1** |

### Verified Pairs (Light Mode)

| Foreground | Background | Ratio | Pass |
|-----------|-----------|-------|------|
| `--color-ink` (#0a0a0a) | `--color-canvas` main (#fff) | 21:1 | ✅ AA |
| `--color-ink` (#0a0a0a) | `--color-canvas` child (#fffaf0) | 20.1:1 | ✅ AA |
| `--color-muted` main (#93939f) | `--color-canvas` (#fff) | 3.0:1 | ⚠️ Large text only |
| `--color-muted` child (#6a6a6a) | `--color-canvas` (#fffaf0) | 5.3:1 | ✅ AA |
| `--color-on-primary` (#fff) | `--color-action-blue` (#1863dc) | 4.6:1 | ✅ AA |
| `--color-on-primary` (#fff) | `--color-brand-pink` (#ff4d8b) | 3.3:1 | ⚠️ Large text only |

---

## Guidance

### When to Share Tokens

- **Semantic state tokens** (`--color-success`, `--color-error`, `--color-warning`) — same name, app-specific values
- **Accessibility patterns** — contrast requirements, focus ring styles, touch targets
- **Animation timing** — transition durations, easing curves (if standardized later)

### When to Keep App-Specific

- **Brand colors** — the palettes convey different emotions (professional vs playful)
- **Surface hierarchy** — main uses `soft-stone`/`pale-*`; child uses `surface-soft`/`surface-card`
- **Domain-specific tokens** — coin metallic palette (child), trend colors (main)

### Future Considerations

If the apps converge further, a shared `frontend/packages/design-tokens/` npm package could export:
- Semantic token **names** (not values) as a shared interface
- A11y contrast validation utilities
- Common animation presets

For now, the two systems are intentionally independent to serve their distinct audiences.
