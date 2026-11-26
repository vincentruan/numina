# 3D Knowledge Castle (Orbit Camera) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Transform the 2D CSS Knowledge Castle into a 3D orbit-camera experience where children can rotate/zoom the castle, enter towers, and interact with windows — reusing Phase 1 infrastructure.

**Architecture:** Three-layer scene graph (L0 Panorama → L1 Tower → L2 Floor) with orbit camera from Phase 1. Each layer is a separate Vue component that mounts its own three.js scene fragment. Camera transitions are anime.js timelines. Physics (brick drop) uses rapier.

**Tech Stack:** Vue 3 + three.js 0.187 + rapier3d-compat 0.21 + animejs 4.5 + clay.css

**Spec:** `docs/plans/2026-11-24-2217-feat-3d-game-learning-system-plan.md` §Phase 3 (brainstorm-approved design)

## Global Constraints

- `<script setup lang="ts">` only — no Options API
- `any` / `@ts-ignore` / `@ts-expect-error` forbidden
- i18n required — every user-facing string via `t('key')`
- Snowflake IDs as `string` — never `number`
- Vant 4 auto-imported — no additional UI libraries
- Single-clock rule: only render loop calls `tickDriver(now)`
- Physics/animation separation: rapier drives bodies, anime drives visuals
- Lifecycle: pause on `onDeactivated`, full teardown on `onBeforeUnmount`
- Graceful degradation: WebGL unavailable → fallback to 2D `KnowledgeCastle.vue`
- Min touch target: 56×56px for all tappable 3D elements (raycaster expanded radius)
- prefers-reduced-motion: physics runs, visual animations skipped

## Review Focus

1. **Orbit camera on mobile** — touch rotate/zoom must not conflict with page scroll (need touch-action: none on canvas)
2. **WebGL context loss** — `webglcontextlost` must trigger fallback, not crash
3. **Memory leak over 20 mount/unmount cycles** — verified via browser DevTools
4. **Large tower count** — 8+ towers must not drop below 55 FPS (mid-range Android)
5. **Camera transition smoothness** — panorama → tower zoom must not disorient (easing curve critical)

---

## File Structure

```
frontend/apps/child/src/
├── components/learning/castle3d/
│   ├── CastlePanorama.vue        # L0: Full castle orbit view
│   ├── TowerInterior.vue         # L1: Single tower interior
│   ├── FloorView.vue             # L2: Domain floor with bricks
│   ├── CastleWindow3D.vue        # Interactive window (raycaster target)
│   ├── CameraController.ts       # Orbit camera + transitions
│   ├── CastleSceneBuilder.ts     # Scene graph construction from data
│   └── index.ts                  # Public exports
├── pages/learning/
│   ├── LearningCastle3DPage.vue  # Route page: /learning/castle-3d
│   └── __tests__/
│       └── LearningCastle3DPage.test.ts
├── composables/
│   └── useCastle3D.ts            # Bridge: data → scene props
└── types/
    └── castle3d.ts               # 3D-specific types
```

**Modified files:**
- `frontend/apps/child/src/router/index.ts` — Add `/learning/castle-3d` route
- `frontend/apps/child/src/i18n/locales/zh-CN.ts` — Castle 3D strings

---

## Task 1: Route + Page Skeleton + 2D Fallback

**Goal:** New route `/learning/castle-3d` with WebGL detection and fallback.

**Files:**
- Create: `frontend/apps/child/src/pages/learning/LearningCastle3DPage.vue`
- Create: `frontend/apps/child/src/pages/learning/__tests__/LearningCastle3DPage.test.ts`
- Modify: `frontend/apps/child/src/router/index.ts`
- Modify: `frontend/apps/child/src/i18n/locales/zh-CN.ts`

**Interfaces:**
- Produces: Route `/learning/castle-3d` that renders `LearningCastle3DPage`
- Produces: `useWebGLAvailable()` composable export (or reuse from spike)

- [ ] **Step 1: Add route**

In `router/index.ts`, add:
```typescript
{
  path: '/learning/castle-3d',
  name: 'LearningCastle3D',
  component: () => import('@/pages/learning/LearningCastle3DPage.vue'),
}
```

- [ ] **Step 2: Create page skeleton**

`LearningCastle3DPage.vue`:
- Template: `<div ref="container" />` + fallback slot
- Script: `onMounted` checks WebGL, loads `CastlePanorama` if available, else renders existing `KnowledgeCastle`
- Props: `castle: CastleIndex | null`, `state: 'loading' | 'error' | 'content'`
- Emits: `retry`, `windowSelect`

- [ ] **Step 3: Add i18n strings**

In `zh-CN.ts`, add under `learning.castle3d`:
- `title`: '3D 知识城堡'
- `subtitle`: '环绕查看你的城堡'
- `fallback`: '你的设备不支持 3D，切换到普通视图'
- `loading`: '加载中...'

- [ ] **Step 4: Write tests**

Test: page renders fallback when WebGL unavailable (mock `isWebGLAvailable`)
Test: page renders 3D container when WebGL available
Test: route resolves `/learning/castle-3d`

- [ ] **Step 5: Verify**

Run: `pnpm vitest run src/pages/learning/__tests__/LearningCastle3DPage.test.ts`
Expected: PASS

---

## Task 2: Orbit Camera Controller

**Goal:** Reusable orbit camera with touch/mouse support, matching Phase 1 ocean camera.

**Files:**
- Create: `frontend/apps/child/src/components/learning/castle3d/CameraController.ts`

**Interfaces:**
- Consumes: `WebGLRenderer`, `PerspectiveCamera`, `HTMLCanvasElement`
- Produces: `OrbitCameraController` class with `enable()`, `disable()`, `dispose()`, `target: Vector3`, `position: Vector3`
- Produces: `animateTo(target: Vector3, position: Vector3, duration: number)` — anime.js timeline transition

**Approach:** Use three.js `OrbitControls` (from `three/examples/jsm/controls/OrbitControls.js`) with touch-action: none on canvas. Transitions use anime.js child timeline on camera.position and camera.lookAt.

- [ ] **Step 1: Write failing test for camera creation**

```typescript
describe('CameraController', () => {
  it('creates orbit camera with default position', () => {
    const { camera, controller } = createTestCamera()
    expect(controller).toBeDefined()
    expect(camera.position.z).toBeGreaterThan(0) // Behind castle
  })
})
```

- [ ] **Step 2: Implement `CameraController`**

Export:
```typescript
export class CameraController {
  constructor(camera: PerspectiveCamera, domElement: HTMLElement)
  enable(): void
  disable(): void
  dispose(): void
  animateTo(target: Vector3, position: Vector3, duration: number): Promise<void>
}
```

- [ ] **Step 3: Write failing test for animation**

Test: `animateTo` moves camera smoothly over duration
Test: `disable` stops touch input
Test: `dispose` releases event listeners

- [ ] **Step 4: Verify**

Run: `pnpm vitest run src/components/learning/castle3d/CameraController.test.ts`

---

## Task 3: Castle Scene Builder (Data → 3D)

**Goal:** Convert `CastleIndex` data into three.js scene objects.

**Files:**
- Create: `frontend/apps/child/src/components/learning/castle3d/CastleSceneBuilder.ts`

**Interfaces:**
- Consumes: `CastleIndex` from `@/api/learning`
- Produces: `Group` (root scene group) with tower children
- Produces: `getTowerBySubject(subject: string): Group | null`
- Produces: `getWindows(): Mesh[]` — raycaster targets

**Visual mapping:**
- Tower: `CylinderGeometry` (radius 1.5, height = floors * 2), material = `CONTINENT_THEMES[subject].color`
- Floor: `RingGeometry` (annular disc) at y = floorIndex * 2
- Brick: `BoxGeometry(0.3, 0.2, 0.3)` arranged in grid on floor
- Window: `SphereGeometry(0.2, 16, 16)` emissive material, positioned on tower exterior

- [ ] **Step 1: Write failing test for tower creation**

```typescript
describe('CastleSceneBuilder', () => {
  it('creates one tower per subject', () => {
    const castle: CastleIndex = {
      towers: [
        { subject: 'math', floors: [...], ... },
        { subject: 'science', floors: [...], ... },
      ],
      windows: [],
      streak_days: 5,
    }
    const root = buildCastleScene(castle)
    expect(root.children.length).toBe(2) // 2 towers
  })
})
```

- [ ] **Step 2: Implement `buildCastleScene`**

```typescript
export function buildCastleScene(castle: CastleIndex): Group
export function buildTower(tower: CastleTower): Group
export function buildFloor(floor: CastleFloor, index: number): Group
export function buildBricks(floor: CastleFloor, floorGroup: Group): void
export function buildWindows(windows: CastleWindow[], towerGroup: Group): Mesh[]
```

- [ ] **Step 3: Write tests for floor and brick layout**

Test: floor at correct y position
Test: brick count = `min(brickCount(floor), 8)`
Test: window emissive material for visibility

- [ ] **Step 4: Verify**

Run: `pnpm vitest run src/components/learning/castle3d/CastleSceneBuilder.test.ts`

---

## Task 4: Panorama View (L0)

**Goal:** Full castle orbit view with tower layout and click-to-enter.

**Files:**
- Create: `frontend/apps/child/src/components/learning/castle3d/CastlePanorama.vue`

**Interfaces:**
- Consumes: `castle: CastleIndex | null`, `CameraController` from Task 2, `buildCastleScene` from Task 3
- Produces: Mounted 3D scene with orbit controls
- Emits: `towerSelect(subject: string)`, `windowSelect(window: CastleWindow)`

**Approach:**
- `onMounted`: init renderer, camera, controls, build scene
- Render loop: `tickDriver(now)` + `requestAnimationFrame`
- Raycaster: on tap/click, check intersection with tower meshes → emit `towerSelect`
- Windows: separate raycaster check → emit `windowSelect`

- [ ] **Step 1: Write failing test for panorama mount**

Test: mounts with WebGL renderer
Test: creates orbit camera at default distance
Test: raycaster detects tower tap

- [ ] **Step 2: Implement `CastlePanorama.vue`**

Template: `<canvas ref="canvas" />`
Script: `onMounted` → `initRapier()` → `buildCastleScene()` → `CameraController.enable()` → render loop
Emit on tower tap: `emit('towerSelect', subject)`

- [ ] **Step 3: Verify**

Run: dev server, navigate to `/learning/castle-3d`
Expected: Castle renders, orbit camera works, towers clickable

---

## Task 5: Tower Interior (L1)

**Goal:** Zoom into single tower, show floors and bricks with orbit camera.

**Files:**
- Create: `frontend/apps/child/src/components/learning/castle3d/TowerInterior.vue`

**Interfaces:**
- Consumes: `tower: CastleTower`, `CameraController.animateTo()`
- Produces: Tower interior view with floor labels
- Emits: `back()`, `windowSelect(window: CastleWindow)`

**Approach:**
- Camera animates from panorama position to tower center (close-up)
- Tower mesh highlighted (emissive boost)
- Other towers dimmed (opacity reduction)
- Floor labels as `Sprite` with text texture (or HTML overlay)

- [ ] **Step 1: Write failing test for camera transition**

Test: `animateTo` moves camera to tower center
Test: other towers dim to 30% opacity

- [ ] **Step 2: Implement `TowerInterior.vue`**

Props: `tower: CastleTower`, `castle: CastleIndex`
`onMounted`: animate camera to tower position
`onBack`: animate camera back to panorama

- [ ] **Step 3: Verify**

Run: dev server, tap tower in panorama
Expected: Camera zooms to tower, floor details visible

---

## Task 6: Brick Drop Physics Animation

**Goal:** New bricks animate with rapier physics on first render.

**Files:**
- Create: `frontend/apps/child/src/components/learning/castle3d/BrickDropAnimation.ts`

**Interfaces:**
- Consumes: `rapierWorld`, `createDynamicObject` from Phase 1
- Produces: `animateBrickDrop(brickMesh: Mesh, targetPosition: Vector3)` — returns `Promise<void>`

**Approach:**
- Brick starts above floor (y = floorY + 3)
- Rapier dynamic body with gravity
- On collision with floor plane, body becomes kinematic
- Anime.js elastic bounce on settle

- [ ] **Step 1: Write failing test for brick drop**

Test: brick starts above target
Test: rapier body falls under gravity
Test: anime bounce on settle

- [ ] **Step 2: Implement `BrickDropAnimation`**

```typescript
export function animateBrickDrop(
  brickMesh: Mesh,
  targetPosition: Vector3,
  world: World,
): Promise<void>
```

- [ ] **Step 3: Integrate with scene builder**

In `buildBricks`, if `isNewBrick`, call `animateBrickDrop` instead of static placement.

- [ ] **Step 4: Verify**

Run: dev server with `?new=<topicId>`, check brick falls and bounces

---

## Task 7: Camera Transitions + Back Button

**Goal:** Smooth panorama ↔ tower transitions with anime.js.

**Files:**
- Modify: `frontend/apps/child/src/components/learning/castle3d/CameraController.ts` (add transition queue)

**Interfaces:**
- Consumes: anime.js `createChildTimeline`
- Produces: `transitionToTower(subject)`, `transitionToPanorama()`

- [ ] **Step 1: Write failing test for transition**

Test: `transitionToTower` animates camera over 800ms
Test: `transitionToPanorama` returns to default position
Test: transitions are queued (no overlap)

- [ ] **Step 2: Implement transition queue**

Use anime.js timeline with easing `easeInOutCubic` (from `easing.ts`).

- [ ] **Step 3: Wire up in Panorama**

On `towerSelect` → `transitionToTower(subject)`
On `back` emit → `transitionToPanorama()`

- [ ] **Step 4: Verify**

Run: dev server, tap tower → zoom in, tap back → zoom out

---

## Task 8: Windows + Exercise Navigation

**Goal:** Castle windows navigate to practice/review.

**Files:**
- Create: `frontend/apps/child/src/components/learning/castle3D/CastleWindow3D.vue`

**Interfaces:**
- Consumes: `window: CastleWindow`
- Emits: `select(window: CastleWindow)`

**Approach:**
- Window = emissive sphere on tower exterior
- Raycaster hit → pulse animation → emit `select`
- Parent routes to `/learning/practice/${topic_id}?mode=${mode}`

- [ ] **Step 1: Write failing test for window interaction**

Test: window mesh is raycaster target
Test: tap emits `select` with correct window data

- [ ] **Step 2: Implement window rendering**

In `buildWindows`, create emissive sphere at tower exterior position.

- [ ] **Step 3: Wire up navigation**

In `LearningCastle3DPage`, on `windowSelect` → `router.push(...)`

- [ ] **Step 4: Verify**

Run: dev server, tap window → navigate to practice

---

## Task 9: Integration + Memory Stability

**Goal:** Full integration test, memory leak check, performance validation.

**Files:**
- Create: `frontend/apps/child/tests/integration/castle3d.test.ts`

**Test scenarios:**
- Mount/unmount 20 times, verify no WebGL context leak
- Orbit camera on mobile (touch-action: none)
- prefers-reduced-motion: brick drop skipped, physics runs
- 8+ towers at 55+ FPS

- [ ] **Step 1: Write integration tests**

```typescript
describe('Castle3D Integration', () => {
  it('mount/unmount 20 cycles without leak', async () => { ... })
  it('orbit camera touch does not scroll page', async () => { ... })
  it('prefers-reduced-motion skips brick animation', async () => { ... })
})
```

- [ ] **Step 2: Run full test suite**

Run: `pnpm vitest run`
Expected: All pass

- [ ] **Step 3: Browser validation**

Run: dev server, navigate to `/learning/castle-3d`
Check: orbit camera, tower zoom, brick drop, window navigation

---

## Task 10: Documentation

**Goal:** README for castle3d module.

**Files:**
- Create: `frontend/apps/child/src/components/learning/castle3d/README.md`

**Content:**
- Scene graph structure (L0 → L1 → L2)
- Camera transition contract
- Lifecycle protocol
- 2D fallback path

- [ ] **Step 1: Write README**

- [ ] **Step 2: Update root plan doc**

Mark Phase 3 as complete in `docs/plans/2026-11-24-2217-feat-3d-game-learning-system-plan.md`

---

## Execution Order

```
Task 1 (Route) ──────────────────────────────────────┐
Task 2 (Camera) ─────────────────────────────────────┤
Task 3 (Builder) ────────────────────────────────────┤ Task 4 (Panorama)
                                                     │─────────────────────┐
Task 5 (Tower Interior) ─────────────────────────────┤                     │
Task 6 (Brick Physics) ──────────────────────────────┤ Task 7 (Transitions)│
                                                     │─────────────────────┤
Task 8 (Windows) ────────────────────────────────────┤                     │
                                                     │─────────────────────┤
                                                     │ Task 9 (Integration)│
                                                     │─────────────────────┤
                                                     │ Task 10 (Docs)      │
                                                     └─────────────────────┘
```

Tasks 1-3 are independent and can run in parallel.
Tasks 4-8 depend on Tasks 1-3.
Tasks 9-10 depend on all above.

---

## Definition of Done

- [ ] All tests pass (unit + integration)
- [ ] Type-check: 0 errors
- [ ] Lint: 0 errors
- [ ] Browser: orbit camera, tower zoom, brick drop, window navigation all work
- [ ] Memory: 20 mount/unmount cycles, no leak
- [ ] Performance: 55+ FPS with 8 towers (simulated 6x CPU throttle)
- [ ] Fallback: 2D castle renders when WebGL unavailable
- [ ] Accessibility: reduced-motion respected, aria-labels on windows
