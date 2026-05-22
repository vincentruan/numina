# Login Multi-Animal Pixel Background Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add 3 Q版 zodiac animal SVG silhouettes (horse, pig, snake) to the login page pixel background, randomly selecting one of 4 animals on each page load.

**Architecture:** Create 3 new SVG files as CSS mask silhouettes alongside the existing deer.svg. Modify `useDeerField.ts` to randomly pick one SVG at mount time. No changes to LoginPage.vue or any other file.

**Tech Stack:** SVG path data, Vue 3 composable (TypeScript), CSS mask-image

---

## File Structure

| Action | File | Responsibility |
|--------|------|---------------|
| Create | `frontend/apps/main/public/images/horse.svg` | Q版 horse silhouette for CSS mask |
| Create | `frontend/apps/main/public/images/pig.svg` | Q版 pig silhouette for CSS mask |
| Create | `frontend/apps/main/public/images/snake.svg` | Q版 snake silhouette for CSS mask |
| Modify | `frontend/apps/main/src/composables/useDeerField.ts` | Random animal selection logic |

---

### Task 1: Create Horse SVG Silhouette

**Files:**
- Create: `frontend/apps/main/public/images/horse.svg`

- [ ] **Step 1: Create the horse SVG file**

Create `frontend/apps/main/public/images/horse.svg` with a Q版 (chibi) horse silhouette. Requirements:
- ViewBox: `0 0 2064 2591` (matching deer.svg)
- Single `<path>` with `fill-rule="nonzero"`
- Q版 proportions: big round head (~40% height), compact body, short legs, mane outline, pointed ears

```xml
<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" width="2064" height="2591" viewBox="0 0 2064 2591">
  <path fill-rule="nonzero"
    d="[Q版 horse path data — big round head with pointed ears at top, flowing mane silhouette on one side, compact rounded body in the middle, four short stubby legs at the bottom. Head occupies roughly y=0 to y=1000, body y=1000 to y=1800, legs y=1800 to y=2400. Centered horizontally around x=1032.]"/>
</svg>
```

The SVG must be a recognizable horse silhouette in Q版 style when viewed at any size. The path should define:
- Two pointed ears at the top (triangular protrusions from the head circle)
- Large rounded head circle (radius ~450px centered around x=1032, y=550)
- Mane flowing down one side of the head and neck (irregular bumpy outline on the right)
- Short thick neck connecting to an oval body
- Compact oval body (horizontally wider than tall)
- Four short, stubby rectangular legs
- Small tail on one side

- [ ] **Step 2: Verify the SVG renders correctly**

Open the file in a browser to confirm the silhouette is recognizable as a cute horse:
```bash
open frontend/apps/main/public/images/horse.svg
```

- [ ] **Step 3: Commit**

```bash
git add frontend/apps/main/public/images/horse.svg
git commit -m "feat(login): add Q版 horse SVG silhouette for pixel background"
```

---

### Task 2: Create Pig SVG Silhouette

**Files:**
- Create: `frontend/apps/main/public/images/pig.svg`

- [ ] **Step 1: Create the pig SVG file**

Create `frontend/apps/main/public/images/pig.svg` with a Q版 pig silhouette. Requirements:
- ViewBox: `0 0 2064 2591` (matching deer.svg)
- Single `<path>` with `fill-rule="nonzero"`
- Q版 proportions: large circular head, big snout bump, short pointed ears, round body, curly tail, stubby legs

```xml
<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" width="2064" height="2591" viewBox="0 0 2064 2591">
  <path fill-rule="nonzero"
    d="[Q版 pig path data — very round head with two small triangular ears at top, prominent round snout bump on the face, wide round body below, four very short stubby legs, curly tail on one side. Head occupies roughly y=0 to y=1100, body y=1100 to y=1900, legs y=1900 to y=2400. Centered horizontally around x=1032.]"/>
</svg>
```

The path should define:
- Two small pointed triangular ears at the top
- Large circular head (radius ~500px, slightly wider than horse)
- Prominent round snout bump protruding from the lower face area
- Very round, wide oval body (wider proportionally than the horse)
- Four very short stubby legs (shorter than horse legs)
- Curly spiral tail on one side (distinctive pig feature visible in silhouette)

- [ ] **Step 2: Verify the SVG renders correctly**

```bash
open frontend/apps/main/public/images/pig.svg
```

- [ ] **Step 3: Commit**

```bash
git add frontend/apps/main/public/images/pig.svg
git commit -m "feat(login): add Q版 pig SVG silhouette for pixel background"
```

---

### Task 3: Create Snake SVG Silhouette

**Files:**
- Create: `frontend/apps/main/public/images/snake.svg`

- [ ] **Step 1: Create the snake SVG file**

Create `frontend/apps/main/public/images/snake.svg` with a Q版 snake silhouette. Requirements:
- ViewBox: `0 0 2064 2591` (matching deer.svg)
- Single `<path>` with `fill-rule="nonzero"`
- Head-focused design: oversized cute round head (~40% height), small trailing body in S-curves, forked tongue tip

```xml
<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" width="2064" height="2591" viewBox="0 0 2064 2591">
  <path fill-rule="nonzero"
    d="[Q版 snake path data — very large round head at top with forked tongue tip extending upward as a small Y-shape bifurcation, two small round bumps for eyes visible in silhouette, body narrows into a neck below the head, then trails down in gentle S-curves getting progressively thinner toward the tail at the bottom. Head occupies roughly y=200 to y=1200, body curves y=1200 to y=2500. Forked tongue y=0 to y=200. Centered horizontally.]"/>
</svg>
```

The path should define:
- Small forked tongue tip at the very top (Y-shaped bifurcation, ~150px tall)
- Very large circular head (radius ~500px) — the dominant feature
- Two subtle bumps on the head outline suggesting eyes
- Narrow neck transitioning from head to body
- Body in gentle S-curves, getting progressively thinner
- Tail tip at the bottom, pointed

- [ ] **Step 2: Verify the SVG renders correctly**

```bash
open frontend/apps/main/public/images/snake.svg
```

- [ ] **Step 3: Commit**

```bash
git add frontend/apps/main/public/images/snake.svg
git commit -m "feat(login): add Q版 snake SVG silhouette for pixel background"
```

---

### Task 4: Add Random Animal Selection to useDeerField

**Files:**
- Modify: `frontend/apps/main/src/composables/useDeerField.ts:501-513`

- [ ] **Step 1: Add the animal list constant**

At the top of the file (after the existing constants, around line 70), add:

```typescript
const ANIMAL_SVGS = ['deer.svg', 'horse.svg', 'pig.svg', 'snake.svg']
```

- [ ] **Step 2: Modify the start() function to use random selection**

In the `start()` function (line 501), replace the hardcoded fetch:

```typescript
// Before (lines 505-513):
fetch('/images/deer.svg')
  .then((r) => r.blob())
  .then((blob) => {
    maskBlobUrl = URL.createObjectURL(blob)
    applyMask(maskBlobUrl)
  })
  .catch(() => {
    applyMask('/images/deer.svg')
  })

// After:
const picked = ANIMAL_SVGS[Math.floor(Math.random() * ANIMAL_SVGS.length)]
fetch(`/images/${picked}`)
  .then((r) => r.blob())
  .then((blob) => {
    maskBlobUrl = URL.createObjectURL(blob)
    applyMask(maskBlobUrl)
  })
  .catch(() => {
    applyMask(`/images/${picked}`)
  })
```

- [ ] **Step 3: Run typecheck**

```bash
cd frontend/apps/main && npm run typecheck
```

Expected: passes with no errors.

- [ ] **Step 4: Commit**

```bash
git add frontend/apps/main/src/composables/useDeerField.ts
git commit -m "feat(login): randomly select animal silhouette on page load"
```

---

### Task 5: Visual Verification

**Files:** None (verification only)

- [ ] **Step 1: Start dev server and test**

```bash
cd frontend/apps/main && npm run dev
```

Open `http://localhost:5173/login` in browser. Refresh the page multiple times (at least 8-10 times) and confirm:
1. All 4 animals appear (deer, horse, pig, snake)
2. Each animal's pixel silhouette is clearly recognizable
3. The flickering animation works identically for all animals
4. The stellar particle background is unaffected
5. Switching between login steps (step 1 → step 2) keeps the same animal

- [ ] **Step 2: Check mobile viewport**

In browser DevTools, switch to mobile viewport (375×667) and confirm:
1. Animals scale properly via the CSS mask
2. No overflow or clipping issues
3. Pixel grid still fills the masked area correctly

- [ ] **Step 3: Stop dev server**

Stop the dev server (Ctrl+C).
