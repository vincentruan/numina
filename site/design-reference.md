# Design Reference Guide

Comprehensive design guidance for the Numina site module. For quick reference, see `CLAUDE.md`.

## 1. Visual Tropes to Avoid — "AI Slop" Anti-Patterns

The current pages suffer from generic, "on distribution" outputs. Avoid these:

### Typography Anti-Patterns

| Never Use | Why |
|-----------|-----|
| Inter, Roboto, Arial | Overused, generic, zero character |
| Space Grotesk | Converged choice across generations |
| Fraunces | Overused "distinctive" choice — now generic |
| System fonts | `-apple-system, BlinkMacSystemFont...` — safe but forgettable |

**Instead:** Choose fonts that are beautiful, unique, and interesting. Pair a distinctive display font with a refined body font. For Chinese content, consider custom web fonts that feel premium.

### Visual Tropes Anti-Patterns

| Never Use | Why |
|-----------|-----|
| Purple gradients on white backgrounds | Cliché AI aesthetic |
| Aggressive gradient backgrounds | Feels synthetic, not atmospheric |
| Emoji (unless brand-native) | Most brands don't use — feels forced |
| Rounded corners with left-border accent | Cookie-cutter component pattern |
| SVG-drawn imagery | Placeholder quality — use real assets or placeholders |
| Predictable 3-column grids | Standard layout, no surprise |
| Centered hero with gradient bg | Most generic landing page pattern |

**Instead:** 
- Layer CSS gradients with geometric patterns
- Use placeholders for missing imagery (better than bad SVG attempts)
- Asymmetry, overlap, diagonal flow, grid-breaking elements
- Draw from IDE themes and cultural aesthetics for inspiration

### Content Anti-Patterns

| Never Use | Why |
|-----------|-----|
| Filler content, placeholder sections | Every element should earn its place |
| "Data slop" — unnecessary numbers/icons/stats | Not useful, clutter |
| Dummy text to fill space | Design problem, not content problem |

**Philosophy:** "One thousand no's for every yes." Less is more.

---

## 2. Scale Requirements

### Mobile (320px+ viewport)

| Element | Requirement |
|---------|-------------|
| Hit targets | ≥44×44px minimum (WCAG 2.5.5) |
| Touch spacing | 16px gap minimum |
| Text | 16px base, 14px minimum |

### Fixed-Size Content (1920×1080 slides, presentations)

| Element | Requirement |
|---------|-------------|
| Text | Never smaller than 24px; ideally much larger |
| Content density | Single focal point per slide |

### Print Documents

| Element | Requirement |
|---------|-------------|
| Text | 12pt minimum |

---

## 3. Animation Patterns

### For Static HTML Pages

**CSS-only approach — no animation libraries:**

```css
/* Orchestrated page load with staggered reveals */
.feature-card:nth-child(1) { animation-delay: 0ms; }
.feature-card:nth-child(2) { animation-delay: 100ms; }
.feature-card:nth-child(3) { animation-delay: 200ms; }
.feature-card:nth-child(4) { animation-delay: 300ms; }

@keyframes fadeInUp {
  from {
    opacity: 0;
    transform: translateY(20px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

.feature-card {
  animation: fadeInUp 0.4s ease-out forwards;
  opacity: 0; /* Start hidden, reveal via animation */
}
```

**Reduced motion support:**

```css
@media (prefers-reduced-motion: reduce) {
  .feature-card {
    animation: none;
    opacity: 1; /* Immediately visible */
  }
}
```

### High-Impact Moments

Focus on:
- **Page load orchestration** — one well-timed reveal sequence
- **Scroll-triggered effects** — surprise, not predictable
- **Hover states** — subtle, not distracting

Avoid:
- Scattered micro-interactions
- Animation on every element
- GSAP/Lottie libraries for static pages

---

## 4. Backgrounds & Atmosphere

### Layered Gradients

```css
/* Multi-layer gradient with pattern overlay */
.hero {
  background: 
    linear-gradient(135deg, #1a1a2e 0%, #16213e 50%, #0f3460 100%),
    url('pattern.svg') repeat;
  background-blend-mode: overlay;
}
```

### Geometric Patterns

```css
/* CSS-only geometric pattern */
.pattern-bg {
  background: 
    radial-gradient(circle at 20% 80%, rgba(255,255,255,0.1) 0%, transparent 50%),
    radial-gradient(circle at 80% 20%, rgba(255,255,255,0.1) 0%, transparent 50%),
    linear-gradient(180deg, #0f0f23 0%, #1a1a3e 100%);
}
```

### Contextual Effects

Match background to brand tone:
- Financial apps → depth, trust (dark blues, subtle gradients)
- Family apps → warmth, accessibility (soft gradients, organic shapes)

---

## 5. Layout Patterns

### Asymmetry

```css
/* Off-center focal point */
.hero-content {
  margin-left: 15%; /* Not centered */
  max-width: 70%;
}
```

### Overlap

```css
/* Element breaking grid boundaries */
.highlight-card {
  transform: translateY(-40px);
  z-index: 10;
}
```

### Grid-Breaking Elements

```css
/* Full-bleed section breaking container */
.highlight-section {
  width: 100vw;
  margin-left: calc(50% - 50vw);
  padding: 48px calc(50vw - 50%);
}
```

### Negative Space vs. Density

Pick one and commit:
- **Generous negative space** — luxury, premium feel
- **Controlled density** — information-rich, editorial feel

---

## 6. CSS Allies

Modern CSS features that elevate design:

| Feature | Use Case |
|---------|----------|
| `text-wrap: pretty` | Better text line breaks |
| `gap` in flexbox/grid | Consistent spacing without margins |
| `aspect-ratio` | Maintain proportions without padding hacks |
| `clamp()` | Fluid typography (e.g., `font-size: clamp(1rem, 2vw, 2rem)`) |
| `backdrop-filter: blur()` | Glassmorphism effects (use sparingly) |
| `mask-image` | Gradient fades on scrollable content |
| CSS Grid subgrid | Nested grid alignment |

---

## 7. Content Guidelines

### No Filler

Every element must earn its place. If a section feels empty:
- **Solution 1:** Remove it
- **Solution 2:** Redesign layout (not add content)
- **Solution 3:** Ask user if additional content would help

### Ask Before Adding

Never unilaterally add:
- Additional sections
- Pages
- Copy text
- Icons/imagery

The user knows their audience better than you.

### Create a System Up Front

Before building:
1. Define layout patterns (section headers, titles, images)
2. Choose 1-2 background colors for variety
3. Commit to typography scale
4. Plan intentional visual rhythm

---

## 8. Design Process Checklist

```
1. Explore context → Check files, docs, recent commits
2. Ask questions → Purpose, constraints, success criteria
3. Propose 2-3 approaches → With trade-offs
4. Present design → Sections scaled to complexity
5. User approves → Iterate if needed
6. Build → Test, verify, iterate
```

---

## 9. Color Usage

### From Brand/Design System

If design system exists:
- Use exact colors from tokens
- If too restrictive, use `oklch` to define harmonious colors matching palette

### Without Design System

1. Choose 1-2 dominant colors
2. Add sharp accents (not evenly distributed)
3. Commit to cohesive aesthetic
4. Use CSS variables for consistency

```css
:root {
  --color-primary: oklch(0.65 0.2 250); /* Dominant */
  --color-accent: oklch(0.7 0.15 30);   /* Sharp accent */
  --color-neutral: oklch(0.95 0.02 250);
}
```

---

## 10. Verification Approach

### Browser Testing

- Check page loads cleanly (no console errors)
- Verify responsive breakpoints (320px, 768px, 1024px, 1440px)
- Test keyboard navigation (Tab order, focus visibility)

### Visual Checks

- Color contrast meets WCAG AA (4.5:1 for text)
- Hit targets ≥44px on mobile
- No horizontal overflow at minimum viewport

### Screenshot Verification

For complex layouts:
- Capture at multiple widths
- Compare spacing/alignment visually
- Check for unintended overlaps

---

## 11. Tweaks System (For Interactive Prototypes)

If adding variation controls:

```javascript
// Register listener before announcing availability
window.addEventListener('message', (e) => {
  if (e.data.type === '__activate_edit_mode') showTweaksPanel();
  if (e.data.type === '__deactivate_edit_mode') hideTweaksPanel();
});

// Announce availability after listener registered
window.parent.postMessage({type: '__edit_mode_available'}, '*');

// Persist changes
window.parent.postMessage({
  type: '__edit_mode_set_keys',
  edits: { fontSize: 18, primaryColor: '#D97757' }
}, '*');
```

**Tweakable defaults:**

```javascript
const TWEAK_DEFAULTS = /*EDITMODE-BEGIN*/{
  "primaryColor": "#D97757",
  "fontSize": 16
}/*EDITMODE-END*/;
```

---

## 12. Speaker Notes (For Slide Decks)

Only add when explicitly requested:

```html
<script type="application/json" id="speaker-notes">
[
  "Slide 0: Opening hook...",
  "Slide 1: Key insight...",
  ...
]
</script>
```

Page must call `window.postMessage({slideIndexChanged: N})` on init and slide change.

---

## References

- `site/CLAUDE.md` — Architecture and conventions
- `site/good-design.txt` — Original aesthetic guidance
- `site/Claude-Design-Sys-Prompt.txt` — Comprehensive design system prompt