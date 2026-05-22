# Login Page Multi-Animal Pixel Background

## Summary

Add three Q版 (chibi-style) zodiac animal SVG silhouettes — horse (马), pig (猪), snake (蛇) — to the login page background. Each page load randomly selects one of the four animals (including the existing deer) and displays it using the same pixel-grid-with-CSS-mask technique.

## Context

The login page (`LoginPage.vue`) uses a two-layer canvas animation:
- **Background canvas**: stellar particle field with drifting, breathing stars
- **Deer canvas**: a uniform lavender pixel grid (`4px` cells, `1px` gap, `rgba(189,187,255,α)`) masked to a deer SVG silhouette via CSS `mask-image`

The pixel grid flickers organically — each cell has a per-frame probability of getting a new random alpha. The effect is a shimmering, constellation-like animal shape.

Currently only one animal exists: `public/images/deer.svg` (2064×2591 viewBox, single `<path>`).

## Requirements

### New SVG Silhouettes

Three new SVG files, each:
- Placed in `frontend/apps/main/public/images/`
- Similar viewBox dimensions (~2000×2500) for consistent mask scaling
- Single `<path>` element with `fill-rule="nonzero"` (matching `deer.svg` pattern)
- Q版 (chibi/cartoon) proportions appropriate to each animal

#### Horse (`horse.svg`)
- Round, chubby Q版 proportions — big head (~40% height), compact body
- Recognizable features in silhouette: mane outline, pointed ears, short legs
- Standing pose, filling most of the vertical space

#### Pig (`pig.svg`)
- Naturally round shape — large circular head, big snout area
- Short pointed ears, round body, short stubby legs
- Curly tail visible in silhouette
- Standing pose

#### Snake (`snake.svg`)
- Head-focused design — oversized cute round head (~40% of total height)
- Small body trailing below in gentle S-curves
- Forked tongue tip visible as a small bifurcation at the top
- Overall shape fills vertical space through the combination of big head + trailing body

### Random Selection

- On each page load (component mount), randomly pick one of 4 animals: `deer`, `horse`, `pig`, `snake`
- Pure `Math.random()` — no persistence, no session storage, no rotation logic
- Each visit gets a fresh random pick

### Code Changes

#### `useDeerField.ts`

In the `start()` function, replace the hardcoded SVG path:

```typescript
// Before
fetch('/images/deer.svg')

// After
const ANIMAL_SVGS = ['deer.svg', 'horse.svg', 'pig.svg', 'snake.svg']
const picked = ANIMAL_SVGS[Math.floor(Math.random() * ANIMAL_SVGS.length)]
fetch(`/images/${picked}`)
```

No other changes to the composable. The pixel grid parameters (`CELL_SIZE`, `CELL_GAP`, `MAX_ALPHA`, `FLICKER_RATE`, lavender color) remain identical.

#### `LoginPage.vue`

No changes.

### What Does NOT Change

- Pixel grid rendering: same `CELL_SIZE=4`, `CELL_GAP=1`, color `rgba(189,187,255,α)`
- Flicker behavior: same `FLICKER_RATE=0.06`
- Stellar particle background: completely untouched
- Login page structure/layout: untouched
- Both login steps (username/password → PIN): same background throughout
- Canvas stacking and z-index: unchanged

## File Inventory

| Action | File |
|--------|------|
| Create | `frontend/apps/main/public/images/horse.svg` |
| Create | `frontend/apps/main/public/images/pig.svg` |
| Create | `frontend/apps/main/public/images/snake.svg` |
| Modify | `frontend/apps/main/src/composables/useDeerField.ts` (~5 lines) |

## Verification

1. `npm run typecheck` passes in `frontend/apps/main/`
2. Start dev server, visit login page, refresh multiple times — confirm all 4 animals appear
3. Each animal's pixel silhouette is clearly recognizable and renders at appropriate scale
4. Flickering animation works identically across all animals
5. Stellar particle background is unaffected
6. Both login steps display the same animal (no re-roll on step change)

## Acceptance Criteria

- [ ] 4 animals total (deer + 3 new) randomly displayed on login page load
- [ ] Each animal is recognizable through its pixel-filled silhouette
- [ ] Q版 style: round, cute proportions for horse/pig/snake
- [ ] Pixel grid and flickering identical to current deer behavior
- [ ] No changes to LoginPage.vue
- [ ] TypeScript compiles without errors
