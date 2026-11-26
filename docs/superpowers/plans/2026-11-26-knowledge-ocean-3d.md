# KnowledgeOcean3D (T5–T10) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Deliver the T5–T10 core of a 3D knowledge ocean at `/learning/ocean-3d`: shared 3D scene framework, floating subject islands, shader sea, mastery fog, Sprite labels, and level camera animations, with the existing 3D castle migrated onto the shared framework without public-API changes.

**Architecture:** A new `scene3d/` layer owns renderer/loop/lifecycle and orbit-camera mechanics. `ocean3d/` builds the L0 subject-island and L1 domain-region scenes on that layer, while the existing castle delegates its camera and theme-color resolution to it. The Vue page owns L0/L1/topic-level state and reuses `TopicConstellation.vue` for the existing 2D topic layer; no persistence, HUD animation, or 2D fallback rendering is added in this scope.

**Tech Stack:** Vue 3 + TypeScript + Vite 8, three.js 0.187 (`three` / `@types/three` already installed), animejs 4.5 via `@/motion/animeDriver`, vitest 4 + happy-dom + `@vue/test-utils`, existing clay.css tokens, pnpm child-app scripts.

**Spec:** `docs/superpowers/specs/2026-11-26-knowledge-ocean-3d-design.md`

## Global Constraints

- Single clock: **only the render loop calls `tickDriver(now)`**; every camera/island animation is a `createChildTimeline()` child. No direct `animejs` imports (ESLint blocks them in components).
- No new dependencies: `three`, `@dimforge/rapier3d-compat`, `animejs` already exist; keep existing Vite `manualChunks` (`three-runtime`, `rapier-runtime`, `motion-runtime`) unchanged.
- Lazy loading: dynamically `import('three')` (and any anime-dependent module) only after WebGL detection succeeds; no static three.js imports in the page or component that would pull three into the main bundle.
- Three-way lifecycle: `onDeactivated` + `visibilitychange` pause; `onActivated` resumes; `onBeforeUnmount` disposes renderer/scenes/timelines/observers/listeners. `webglcontextlost` stops the loop and emits `fallback` (no 2D fallback rendered here).
- Visual: use clay.css tokens (`--ocean-sea-color`, `--ocean-land-color`, `--ocean-fog-color`, `--ocean-label-color`, `--color-brand-*`), no new fonts, rounder shapes/softer shadows than the mockup.
- Layout: L0 islands non-overlapping with ~15% margin; L1 regions separated by water lanes; labels above islands, never hidden by fog/water, `sizeAttenuation: false`.
- Fog mapping for this feature: `opacity = 1 - sqrt(clamp(masteryRatio, 0, 1))` — **do not reuse** `fogOpacityForRatio()` (2D thresholds differ).
- Reduced motion: sea/island animation static and camera level changes instantaneous when `useReducedMotion()` is true.
- No URN/3D physics bodies in T5–T10: island bobbing is shader/anime-only; do not call rapier APIs or initialize the physics world.
- State is page-local Vue refs only; no cross-route persistence. Changing `/learning` and `KnowledgeOcean.vue` data/interaction is out of scope.
- All commands below run from `frontend/apps/child` unless prefixed with repo root paths (`pnpm -C apps/child …` from `frontend/` is equivalent).

## Review Focus

1. **WebGL unavailable** — no three import, `fallback` emitted, component shows a non-blank message (`KnowledgeOcean3D.fallback`); test: Task 5 WebGL test.
2. **WebGL context lost after mount** — loop stops and `fallback` fires without an exception; test: Task 5 WebGL test.
3. **Tab hidden / KeepAlive deactivated** — rAF and `tickDriver` stop, then resume once on activation/visibility; no double loop; test: Task 1 lifecycle handle test + Task 5 component lifecycle test.
4. **30-second unmount + repeated mount/unmount** — renderer disposed, ResizeObserver/listeners removed, child timelines reverted (20-cycle suite gets 30 rAF ticks per cycle); test: Task 1 leak test.
5. **L1 domain click must stay in the 2D topic layer with back navigation** — page-level state only, back button returns to L1, pinch returns to L0; test: Task 6 page navigation test.
6. **Labels under low-mastery fog / behind other labels** — labels render above fog/water and nearer labels sort over farther ones; test: Task 4 label tests.
7. **Castle public API freeze** — `CameraController`, `createPanoramaCamera`, `createTowerCamera`, `frameCastle`, `animateTo()` promise semantics and existing castle test assertions unchanged; tests: Task 2 + Task 7.

---

## File Structure

```text
frontend/apps/child/src/
├── components/learning/
│   ├── scene3d/                            # NEW shared framework
│   │   ├── useSceneLifecycle.ts            # renderer/scene/camera/loop/resize/pause/teardown
│   │   ├── OrbitCameraController.ts        # orbit + pinch + animateTo (castle-compatible)
│   │   ├── resolveThemeColor.ts            # CSS var → literal color
│   │   └── __tests__/
│   │       ├── useSceneLifecycle.test.ts
│   │       └── OrbitCameraController.test.ts
│   ├── ocean3d/                            # NEW T5–T10 scene modules
│   │   ├── KnowledgeOcean3D.vue            # WebGL gate, canvas, events, lifecycle wiring
│   │   ├── OceanSceneBuilder.ts            # T6 islands + T8 fog/mastery rings + dispose
│   │   ├── OceanWater.ts                   # T7 shader water
│   │   ├── OceanLabels.ts                  # T9 Sprite labels + depth sort
│   │   ├── OceanCameraController.ts        # T10 dive/ascend/reset
│   │   ├── oceanGeometry.ts                # pure layout + fog math (no three import)
│   │   └── __tests__/
│   │       ├── oceanGeometry.test.ts
│   │       ├── OceanSceneBuilder.test.ts
│   │       ├── OceanWater.test.ts
│   │       ├── OceanLabels.test.ts
│   │       ├── OceanCameraController.test.ts
│   │       └── KnowledgeOcean3D.test.ts
│   ├── castle3d/                           # MODIFIED, public API unchanged
│   │   ├── CameraController.ts             # delegates to scene3d/OrbitCameraController
│   │   ├── CastleSceneBuilder.ts           # uses scene3d/resolveThemeColor
│   │   └── __tests__/ (existing tests unchanged)
│   └── KnowledgeOcean.vue                  # UNCHANGED — only its exported types are imported
├── pages/learning/
│   ├── LearningOcean3DPage.vue             # NEW /learning/ocean-3d page
│   └── __tests__/LearningOcean3DPage.test.ts
├── router/index.ts                         # MODIFIED: ocean-3d route
└── i18n/locales/{zh-CN,en-US}.ts           # MODIFIED: learning.ocean3d.*
```

Shared type location: `scene3d/OrbitCameraController.ts` exports `OrbitState`, `CameraController` (class), and `createChildTimeline`-based `animateTo`. The castle file re-exports/delegates those names. `oceanGeometry.ts` exports `OceanIslandNode`, `OceanDomainNode`, `layoutOceanNodes()`, `fogOpacityForMastery()`, `OCEAN_HALF_SPAN = 10`, and `ISLAND_MARGIN_RATIO = 0.15`.

---

## Task 1: Shared scene lifecycle handle (T5 core)

**Files:**
- Create: `frontend/apps/child/src/components/learning/scene3d/useSceneLifecycle.ts`
- Create: `frontend/apps/child/src/components/learning/scene3d/__tests__/useSceneLifecycle.test.ts`

**Interfaces:**
- Consumes: `tickDriver(now)` from `@/motion/animeDriver`; `Scene`, `PerspectiveCamera`, `WebGLRenderer` from `three` (injected into `mount`, not statically imported by this file).
- Produces:
  ```ts
  export interface SceneLifecycleDeps {
    THREE: typeof import('three')
    scene: Scene
    camera: PerspectiveCamera
    renderer: WebGLRenderer
    onFrame?: (now: number) => void
    onContextLost?: (event: Event) => void
  }
  export interface SceneLifecycleHandle {
    mount(canvas: HTMLCanvasElement, container: HTMLElement, deps: SceneLifecycleDeps): void
    pause(): void
    resume(): void
    destroy(): void
    setDocumentVisibilityPaused(paused: boolean): void
    isPaused(): boolean
    getFrameCount(): number
  }
  export function useSceneLifecycle(): SceneLifecycleHandle
  ```

- [ ] **Step 1: Write failing lifecycle tests**

```ts
// tests to add to __tests__/useSceneLifecycle.test.ts
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { useSceneLifecycle } from '../useSceneLifecycle'

function deps(overrides: Partial<Parameters<ReturnType<typeof useSceneLifecycle>['mount']>[2]> = {}) {
  return {
    THREE: { /* minimal three namespace: Scene, PerspectiveCamera, WebGLRenderer */ },
    scene: { clear: vi.fn() } as never,
    camera: { aspect: 1, updateProjectionMatrix: vi.fn() } as never,
    renderer: { setSize: vi.fn(), setPixelRatio: vi.fn(), render: vi.fn(), dispose: vi.fn(), forceContextLoss: vi.fn() } as never,
    onFrame: vi.fn(),
    ...overrides,
  }
}

describe('useSceneLifecycle', () => {
  beforeEach(() => { vi.useFakeTimers(); vi.spyOn(globalThis, 'requestAnimationFrame').mockImplementation((cb) => setTimeout(() => cb(performance.now()), 16) as unknown as number); vi.spyOn(globalThis, 'cancelAnimationFrame').mockImplementation((id) => clearTimeout(id)) })
  afterEach(() => { vi.restoreAllMocks(); vi.useRealTimers() })

  it('mount resizes renderer/camera, starts one rAF loop, and advances per frame', async () => { /* expect setSize called with container dims; await one frame; expect onFrame + renderer.render once */ })
  it('pause cancels the loop and resume starts exactly one loop', async () => { /* frame count does not increase while paused; after resume only one callback per frame */ })
  it('resize observer updates renderer/camera and is disconnected on destroy', async () => { /* change mock container dims, trigger observer callback */ })
  it('context lost handler stops the loop and calls onContextLost once', async () => { /* dispatch fake event through canvas listener registry */ })
  it('setDocumentVisibilityPaused composes with pause/resume: hidden stays paused after visible', async () => { /* pause from visibility then resume() — expect no frames until visibility unpaused */ })
  it('20 mount/destroy cycles leave no rAF, listeners, or observer', () => { /* expect observer.disconnect called 20 times; cancelAnimationFrame after destroy; getFrameCount() === 0 */ })
})
```

- [ ] **Step 2: Run lifecycle tests to verify failure**

Run: `pnpm -C apps/child exec vitest run src/components/learning/scene3d/__tests__/useSceneLifecycle.test.ts`
Expected: FAIL — module `useSceneLifecycle` not found.

- [ ] **Step 3: Implement `useSceneLifecycle()` in `scene3d/useSceneLifecycle.ts`**

One `rAF` callback per mounted handle. `mount()` creates `ResizeObserver` on `container`, sets renderer size to `container.clientWidth/Height` with `Math.min(devicePixelRatio, 2)`, sets camera aspect and calls `updateProjectionMatrix()`, installs `canvas.addEventListener('webglcontextlost', handler)` with `preventDefault()`, then starts the loop. The loop calls `deps.onFrame?.(now)` (if supplied) then `tickDriver(now)` exactly once then `renderer.render(scene, camera)` and schedules the next frame unless paused/destroyed. `pause()` cancels rAF and sets a manual-pause flag; `resume()` clears it. `setDocumentVisibilityPaused(true)` cancels rAF and sets a separate hidden flag; `false` clears it. The loop runs only when **both** flags are clear and the handle is mounted/undestroyed, so an explicit `resume()` cannot restart a loop while the document is hidden. `destroy()` also unhooks the observer/listener and nulls all refs. Do not import `three` statically — use injected `deps.THREE` for anything constructed.

- [ ] **Step 4: Run lifecycle tests to verify pass**

Run: `pnpm -C apps/child exec vitest run src/components/learning/scene3d/__tests__/useSceneLifecycle.test.ts`
Expected: PASS — all five tests green.

- [ ] **Step 5: Commit**

```bash
git add frontend/apps/child/src/components/learning/scene3d/useSceneLifecycle.ts frontend/apps/child/src/components/learning/scene3d/__tests__/useSceneLifecycle.test.ts
git commit -m "feat(child): add shared 3D scene lifecycle handle"
```

---

## Task 2: Shared orbit camera controller (castle-compatible)

**Files:**
- Create: `frontend/apps/child/src/components/learning/scene3d/OrbitCameraController.ts`
- Create: `frontend/apps/child/src/components/learning/scene3d/__tests__/OrbitCameraController.test.ts`

**Interfaces:**
- Consumes: `PerspectiveCamera`, `Vector3` from `three`; `createChildTimeline` from `@/motion/animeDriver`; `type Timeline` from `animejs` (type-only import allowed).
- Produces (same signatures as today's castle controller):
  ```ts
  export interface OrbitState { radius: number; theta: number; phi: number; target: Vector3 }
  export class CameraController {
    constructor(camera: PerspectiveCamera, initialState?: OrbitState)
    enable(domElement: HTMLElement): void
    disable(): void
    dispose(domElement?: HTMLElement): void
    animateTo(target: Vector3, position: Vector3, duration?: number): Promise<void>
    transitionToPanorama(): Promise<void>
    transitionToTower(towerCenter: Vector3, towerHeight: number): Promise<void>
    getPosition(): Vector3
    getTarget(): Vector3
  }
  export const DEFAULT_PANORAMA: OrbitState
  export const DEFAULT_TOWER: OrbitState
  export function createPanoramaCamera(camera: PerspectiveCamera): CameraController
  export function createTowerCamera(camera: PerspectiveCamera): CameraController
  export function frameCastle(camera: PerspectiveCamera, bounds: { center: Vector3; size: Vector3 }): CameraController
  ```
  Additionally: `setPinchZoom(enabled: boolean)` / `getRadius()` for the ocean controller; `getStateSnapshot(): { radius; theta; phi; target: Vector3 }` for tests.

- [ ] **Step 1: Write failing orbit tests**

```ts
it('animateTo resolves a Promise and writes spherical state', async () => { const c = new CameraController(new PerspectiveCamera(60,1,.1,100)); const p = c.animateTo(new Vector3(0,0,0), new Vector3(0,0,10), 40); expect(p).toBeInstanceOf(Promise); await p; expect(c.getRadius()).toBeCloseTo(10) })
it('pinch zoom changes radius without changing theta/phi', () => { /* enable with pinching: true; dispatch two-touch move on a stub HTMLElement; expect getRadius decrease and theta unchanged */ })
it('dispose removes listeners and reverts transition timeline', () => { /* enable then dispose(el); expect afterward touchmove does not affect camera; getRootTimeline()?.children?.length unchanged */ })
it('reduced motion: instant positioning still updates camera', () => { /* construct with { instant: true } option; animateTo resolves and getPosition matches target+offset immediately */ })
```

- [ ] **Step 2: Run orbit tests to verify failure**

Run: `pnpm -C apps/child exec vitest run src/components/learning/scene3d/__tests__/OrbitCameraController.test.ts`
Expected: FAIL — module not found.

- [ ] **Step 3: Implement `OrbitCameraController.ts`**

Move the current castle implementation verbatim in behavior: `DEFAULT_PANORAMA` radius 20 / theta 0 / phi π/3 / target (0,2,0); `DEFAULT_TOWER` radius 8 / phi π/2.5 / target (0,3,0); phi clamped `[0.1, π−0.1]`; `FRAME_MARGIN = 1.35`; `frameCastle` fits width & height then clamps radius ≥ 12; `animateTo()` uses `createChildTimeline()` and resolves after `duration + 50ms`. Add an optional constructor options object `{ instant?: boolean; pinchZoom?: boolean }`: with `instant`, `animateTo()` writes state and resolves immediately (reduced-motion path). With `pinchZoom`, track two-touch distance changes and scale `state.radius` by `previousDistance / currentDistance`, clamped to `[2, 80]`, leaving theta/phi untouched. Preserve existing pointer/touch rotate handlers and `enable()/disable()/dispose()` semantics, including the private `rotate(dx, dy)` name that castle tests reach through a cast.

- [ ] **Step 4: Run orbit + existing castle camera tests**

Run: `pnpm -C apps/child exec vitest run src/components/learning/scene3d/__tests__/OrbitCameraController.test.ts src/components/learning/castle3d/__tests__/CameraController.test.ts`
Expected: PASS — new tests green and existing castle assertions unchanged.

- [ ] **Step 5: Commit**

```bash
git add frontend/apps/child/src/components/learning/scene3d/OrbitCameraController.ts frontend/apps/child/src/components/learning/scene3d/__tests__/OrbitCameraController.test.ts
git commit -m "feat(child): extract shared orbit camera controller"
```

---

## Task 3: Shared theme-color resolver + castle delegation

**Files:**
- Create: `frontend/apps/child/src/components/learning/scene3d/resolveThemeColor.ts`
- Modify: `frontend/apps/child/src/components/learning/castle3d/CastlePanorama.vue` (delegate lifecycle to `scene3d`)
- Modify: `frontend/apps/child/src/components/learning/castle3d/CameraController.ts` (replace body with delegating re-export)
- Modify: `frontend/apps/child/src/components/learning/castle3d/CastleSceneBuilder.ts` (swap private resolver for import)
- Test: existing `castle3d/__tests__/CameraController.test.ts`, `CastleSceneBuilder.test.ts`, `integration.test.ts` must pass unchanged; new `scene3d/__tests__/resolveThemeColor.test.ts`.

**Interfaces:**
- Consumes: `CONTINENT_THEMES` from `@/data/continentThemes`.
- Produces: `export function resolveThemeColor(subject: string): string` — literal hex/`rgb()` passes through; `var(--x, fallback)` resolves from `getComputedStyle(document.documentElement)`, falling back to fallback then `#808080`.
  `CameraController.ts` must keep exporting all four names and class behavior from Task 2.

- [ ] **Step 1: Write failing resolver tests**

```ts
it('resolves var(--color-brand-ochre) from document styles', () => { /* stub getComputedStyle returning #e8b94a; expect resolveThemeColor('mathematics') === '#e8b94a' */ })
it('uses the inline fallback when the CSS var is empty', () => { /* expect resolveThemeColor('science') === '#e6f7f5' */ })
it('returns #808080 for an unknown subject', () => { expect(resolveThemeColor('unknown')).toBe('#808080') })
```

- [ ] **Step 2: Run resolver test to verify failure**

Run: `pnpm -C apps/child exec vitest run src/components/learning/scene3d/__tests__/resolveThemeColor.test.ts`
Expected: FAIL — module not found.

- [ ] **Step 3: Implement resolver and castle delegation**

Create `resolveThemeColor.ts` with the exact regex/fallback behavior currently in `CastleSceneBuilder.ts:32-50`. In `CastleSceneBuilder.ts`, delete the private function and import `resolveThemeColor` from `../scene3d/resolveThemeColor`. In `castle3d/CameraController.ts`, delete the implementation and re-export `CameraController`, `DEFAULT_PANORAMA`, `DEFAULT_TOWER`, `createPanoramaCamera`, `createTowerCamera`, `frameCastle`, and `type OrbitState` from `../scene3d/OrbitCameraController` (no behavior change).

Then replace CastlePanorama's inline renderer/loop/resize/activated/deactivated/context-lost code with `useSceneLifecycle()`: in `mount()` call `handle.mount(canvas, container, { THREE, scene, camera, renderer, onFrame, onContextLost })`; `onFrame(now)` keeps the castle's existing `handlePick()` and `updateLabels()` and `renderer.render()` behavior — remove its `tickDriver(now)` call because the lifecycle handle owns the single clock; `onContextLost` keeps `console.error` and emits nothing (the castle parent handles degradation through its existing 2D route). Replace the castle's `window.addEventListener('resize')` + `resize()` with the lifecycle's ResizeObserver; replace `onDeactivated`/`onActivated` with `handle.pause()`/`handle.resume()`; add a `visibilitychange` listener calling `handle.setDocumentVisibilityPaused(document.hidden)`; `teardown()` calls `handle.destroy()` before disposing scene/brick-drop resources. Keep `towerLabels`, `defineExpose({ focusTower, resetCamera })`, and emitted events unchanged. If any existing castle test assertion breaks, fix the migration — do not edit the tests.

- [ ] **Step 4: Run full castle3d + resolver test set**

Run: `pnpm -C apps/child exec vitest run src/components/learning/castle3d src/components/learning/scene3d/__tests__/resolveThemeColor.test.ts`
Expected: PASS — all existing castle tests and new resolver tests green.

- [ ] **Step 5: Commit**

```bash
git add frontend/apps/child/src/components/learning/scene3d/resolveThemeColor.ts frontend/apps/child/src/components/learning/scene3d/__tests__/resolveThemeColor.test.ts frontend/apps/child/src/components/learning/castle3d/CameraController.ts frontend/apps/child/src/components/learning/castle3d/CastleSceneBuilder.ts frontend/apps/child/src/components/learning/castle3d/CastlePanorama.vue
git commit -m "refactor(child): share theme colors and orbit camera with castle"
```

---

## Task 4: Ocean geometry math + island/fog scene builder (T6 + T8)

**Files:**
- Create: `frontend/apps/child/src/components/learning/ocean3d/oceanGeometry.ts`
- Create: `frontend/apps/child/src/components/learning/ocean3d/OceanSceneBuilder.ts`
- Create: `frontend/apps/child/src/components/learning/ocean3d/__tests__/oceanGeometry.test.ts`
- Create: `frontend/apps/child/src/components/learning/ocean3d/__tests__/OceanSceneBuilder.test.ts`

**Interfaces:**
- Consumes: `layoutIslands()` from `@/utils/islandLayout`, `CONTINENT_THEMES` + `resolveThemeColor` from `scene3d`, `OceanSubject` / `OceanDomain` types from `@/components/learning/KnowledgeOcean.vue` (type-only).
- Produces:
  ```ts
  export interface OceanIslandNode { id: string; displayName: string; icon: string; terrain: string; x: number; z: number; worldRadius: number; masteryRatio: number }
  export interface OceanDomainNode { id: string; subject: string; displayName: string; x: number; z: number; worldRadius: number; masteryRatio: number }
  export function layoutOceanNodes(subjects: OceanSubject[]): OceanIslandNode[]
  export function layoutOceanDomains(domains: OceanDomain[]): OceanDomainNode[]
  export function fogOpacityForMastery(ratio: number): number
  export interface OceanScene {
    root: Group
    islands: OceanIslandNode[]
    pickTargets: Object3D[]
    dispose(): void
  }
  export function buildOceanScene(nodes: OceanIslandNode[], options?: { reducedMotion?: boolean; domainMode?: boolean }): OceanScene
  export function disposeOceanScene(scene: OceanScene): void
  ```
  `domainMode: true` builds rounded box-like region tiles (separated by water lanes) with fog rings, but the same `pickTargets` / `dispose` contract.

- [ ] **Step 1: Write failing geometry and builder tests**

```ts
describe('layoutOceanNodes', () => {
  it('maps normalized layout to world X/Z with 15% margin and no overlap', () => {
    const subjects = Array.from({ length: 8 }, (_, i) => ({ id: `s${i}`, terrain: 'math', displayName: `S${i}`, icon: '📐', topicCount: i + 1, masteryRatio: 0 }))
    const nodes = layoutOceanNodes(subjects)
    expect(nodes).toHaveLength(8)
    for (const n of nodes) { expect(Math.abs(n.x)).toBeLessThanOrEqual(OCEAN_HALF_SPAN * (1 - ISLAND_MARGIN_RATIO)); expect(Math.abs(n.z)).toBeLessThanOrEqual(OCEAN_HALF_SPAN * (1 - ISLAND_MARGIN_RATIO)) }
    for (let i = 0; i < nodes.length; i++) for (let j = i + 1; j < nodes.length; j++) { const d = Math.hypot(nodes[i].x - nodes[j].x, nodes[i].z - nodes[j].z); expect(d).toBeGreaterThan(nodes[i].worldRadius + nodes[j].worldRadius) }
  })
  it('is deterministic for the same subject set regardless of input order', () => { expect(layoutOceanNodes(a)).toEqual(layoutOceanNodes([...a].reverse())) })
})
describe('fogOpacityForMastery (spec T8)', () => {
  it.each([[0,1],[0.25,0.5],[0.5,1-Math.SQRT1_2],[1,0]])('maps %s to %s', (ratio, expected) => expect(fogOpacityForMastery(ratio)).toBeCloseTo(expected))
  it('clamps out-of-range ratios', () => { expect(fogOpacityForMastery(-1)).toBe(1); expect(fogOpacityForMastery(2)).toBe(0) })
})
describe('buildOceanScene', () => {
  it('builds one pick target and ring per island with correct fog opacity', () => { const nodes = layoutOceanNodes([{ id:'math', ... masteryRatio: 0.25 }]); const scene = buildOceanScene(nodes); expect(scene.pickTargets).toHaveLength(1); expect(scene.root.children.length).toBeGreaterThanOrEqual(nodes.length) })
  it('dispose clears geometry/material references', () => { /* spy dispose on meshes, call disposeOceanScene(scene), expect root.children.length === 0 */ })
  it('domainMode builds region tiles with water lanes between them', () => { const scene = buildOceanScene(domainNodes, { domainMode: true }); expect(scene.pickTargets).toHaveLength(domainNodes.length) })
})
```

- [ ] **Step 2: Run tests to verify failure**

Run: `pnpm -C apps/child exec vitest run src/components/learning/ocean3d/__tests__/oceanGeometry.test.ts src/components/learning/ocean3d/__tests__/OceanSceneBuilder.test.ts`
Expected: FAIL — modules not found.

- [ ] **Step 3: Implement geometry math and scene builder**

`oceanGeometry.ts`: call `layoutIslands()` with `{ id, terrain, topicCount }`, map `x → (x − 0.5) * 2 * OCEAN_HALF_SPAN * (1 − ISLAND_MARGIN_RATIO)` and `y → z` with the same formula; `worldRadius = radius * 2 * OCEAN_HALF_SPAN` (radius is normalized to width 1 in `layoutIslands`). Apply the same mapping to domains via `layoutIslands` on `{ id, terrain: 'region', topicCount }`. `fogOpacityForMastery(r) = 1 − Math.sqrt(Math.max(0, Math.min(1, r)))`. Keep this file free of `three` imports so pure logic tests are fast.

`OceanSceneBuilder.ts`: for L0, build each floating island from a low-poly `CylinderGeometry` top + tapered lower cone/`SphereGeometry` cap, `MeshStandardMaterial` with `resolveThemeColor(subject)`, placed at `(x, 0, z)` with `castShadow/receiveShadow` on the top mesh. For L1 (`domainMode: true`), build rounded box-like region tiles at `(x, 0, z)`, sized to leave a visible water lane between neighbors. Set `userData = { islandId: node.id }` on every L0 pick target and `userData = { domainId: node.id, subject: node.subject }` on every L1 tile. Add a `RingGeometry` mastery ring around each node whose arc/luminance reflects `masteryRatio`; add a semi-transparent fog mesh above it with `depthWrite: false`, `opacity = fogOpacityForMastery(ratio)`. When `reducedMotion` is true, skip the bob timeline; otherwise create one `createChildTimeline()` with looping `y` keyframes on all island groups (single child; do **not** call `tickDriver` here). `disposeOceanScene()` traverses `root`, disposes unique geometries/materials/textures, reverts the bob timeline, and clears the group.

- [ ] **Step 4: Run tests to verify pass**

Run: `pnpm -C apps/child exec vitest run src/components/learning/ocean3d/__tests__/oceanGeometry.test.ts src/components/learning/ocean3d/__tests__/OceanSceneBuilder.test.ts`
Expected: PASS — layout deterministic/non-overlapping, fog mapping exact, disposal verified.

- [ ] **Step 5: Commit**

```bash
git add frontend/apps/child/src/components/learning/ocean3d/oceanGeometry.ts frontend/apps/child/src/components/learning/ocean3d/OceanSceneBuilder.ts frontend/apps/child/src/components/learning/ocean3d/__tests__/oceanGeometry.test.ts frontend/apps/child/src/components/learning/ocean3d/__tests__/OceanSceneBuilder.test.ts
git commit -m "feat(child): build 3D ocean islands with mastery fog"
```

---

## Task 5: Shader sea (T7)

**Files:**
- Create: `frontend/apps/child/src/components/learning/ocean3d/OceanWater.ts`
- Create: `frontend/apps/child/src/components/learning/ocean3d/__tests__/OceanWater.test.ts`

**Interfaces:**
- Consumes: `PlaneGeometry`, `ShaderMaterial`, `Mesh`, `Color` from `three`; `clayColor('ocean-sea')` from `@/motion/materials`.
- Produces:
  ```ts
  export interface OceanWater { mesh: Mesh; update(elapsedSeconds: number): void; setReducedMotion(reduced: boolean): void; dispose(): void }
  export function createOceanWater(THREE: typeof import('three'), options?: { reducedMotion?: boolean; seaColor?: string }): OceanWater
  ```

- [ ] **Step 1: Write failing water tests**

```ts
it('writes uTime from update and never auto-plays a tween', () => { const water = createOceanWater(THREE, { seaColor:'#cfe8f5' }); water.update(1.5); expect((water.mesh.material as ShaderMaterial).uniforms.uTime.value).toBe(1.5); expect((water.mesh.material as ShaderMaterial).uniforms.uSeaColor.value.getHexString()).toBe(new Color('#cfe8f5').getHexString()); expect(getRootTimeline()).toBeNull() })
it('reduced motion freezes the wave uniform', () => { const water = createOceanWater(THREE, { reducedMotion:true }); water.update(9); expect(water.mesh.material.uniforms.uTime.value).toBe(0) })
it('dispose frees geometry and material', () => { /* spies on dispose; expect both called exactly once */ })
```

- [ ] **Step 2: Run water tests to verify failure**

Run: `pnpm -C apps/child exec vitest run src/components/learning/ocean3d/__tests__/OceanWater.test.ts`
Expected: FAIL — module not found.

- [ ] **Step 3: Implement `createOceanWater()`**

Large `PlaneGeometry(2 * OCEAN_HALF_SPAN, 2 * OCEAN_HALF_SPAN, 32, 32)` rotated to X/Z at `y = −0.6`. `ShaderMaterial` with uniforms `uTime`, `uSeaColor` (from `clayColor('ocean-sea')`, overridable by option), `uHighlight`; vertex shader adds two low-amplitude `sin/cos` wave terms driven by `uTime` and `position.xz`; fragment shader mixes the sea color with a subtle specular highlight. `update(seconds)` writes `uTime.value = seconds` unless reduced motion, where it stays `0`. No anime timeline and no `tickDriver` here — the component calls `update()` from `onFrame`. `dispose()` releases geometry and material.

- [ ] **Step 4: Run water tests to verify pass**

Run: `pnpm -C apps/child exec vitest run src/components/learning/ocean3d/__tests__/OceanWater.test.ts`
Expected: PASS — uTime/reduced-motion/dispose assertions green.

- [ ] **Step 5: Commit**

```bash
git add frontend/apps/child/src/components/learning/ocean3d/OceanWater.ts frontend/apps/child/src/components/learning/ocean3d/__tests__/OceanWater.test.ts
git commit -m "feat(child): add shader ocean water surface"
```

---

## Task 6: Sprite labels with depth sorting (T9)

**Files:**
- Create: `frontend/apps/child/src/components/learning/ocean3d/OceanLabels.ts`
- Create: `frontend/apps/child/src/components/learning/ocean3d/__tests__/OceanLabels.test.ts`

**Interfaces:**
- Consumes: `CanvasTexture`, `Sprite`, `SpriteMaterial`, `Vector3`, `PerspectiveCamera` from `three`; `--ocean-label-color` via `getComputedStyle`.
- Produces:
  ```ts
  export interface OceanLabel { id: string; sprite: Sprite; setVisible(visible: boolean): void }
  export interface OceanLabelSet {
    sprites: Sprite[]
    update(camera: PerspectiveCamera): void
    dispose(): void
  }
  export function createOceanLabels(
    THREE: typeof import('three'),
    nodes: Array<{ id: string; displayName: string; icon: string; x: number; z: number; worldRadius: number }>,
    options?: { reducedMotion?: boolean },
  ): OceanLabelSet
  export function sortLabelsByCameraDistance(labels: OceanLabel[], camera: PerspectiveCamera): OceanLabel[]
  ```

- [ ] **Step 1: Write failing label tests**

```ts
it('creates one label per node, above island and non-attenuating', () => { const set = createOceanLabels(THREE, [node]); expect(set.sprites).toHaveLength(1); expect((set.sprites[0].material as SpriteMaterial).sizeAttenuation).toBe(false); expect(set.sprites[0].position.y).toBeGreaterThan(0) })
it('depth-sorts near labels over far labels', () => { const camera = new PerspectiveCamera(); camera.position.set(0,10,0); const sorted = sortLabelsByCameraDistance([far, near], camera); expect(sorted.map(l => l.id)).toEqual(['near','far']) })
it('sets renderOrder above fog and water', () => { expect(set.sprites[0].renderOrder).toBeGreaterThan(10) })
it('dispose releases canvas textures and materials', () => { /* spy texture.dispose and material.dispose */ })
```

- [ ] **Step 2: Run label tests to verify failure**

Run: `pnpm -C apps/child exec vitest run src/components/learning/ocean3d/__tests__/OceanLabels.test.ts`
Expected: FAIL — module not found.

- [ ] **Step 3: Implement `OceanLabels.ts`**

For each node draw a rounded-rect canvas with `icon + displayName` using the app's inherited font (`system-ui, sans-serif` is already the clay.css default; do not load a font), wrap it in `CanvasTexture`, and create a `SpriteMaterial({ map, sizeAttenuation: false, transparent: true, depthTest: false, depthWrite: false })`. Place each sprite at `(x, worldRadius * 2 + 1.2, z)` — above the island and above the fog mesh. `renderOrder = 20` so fog/water never covers labels. `update(camera)` sorts sprites by camera distance (nearest last so it draws on top) and assigns ascending `renderOrder` starting at 20. Cache textures by `icon + displayName` string when multiple nodes share a name; `dispose()` releases each unique texture/material once.

- [ ] **Step 4: Run label tests to verify pass**

Run: `pnpm -C apps/child exec vitest run src/components/learning/ocean3d/__tests__/OceanLabels.test.ts`
Expected: PASS — sizeAttenuation, sorting, renderOrder, disposal all green.

- [ ] **Step 5: Commit**

```bash
git add frontend/apps/child/src/components/learning/ocean3d/OceanLabels.ts frontend/apps/child/src/components/learning/ocean3d/__tests__/OceanLabels.test.ts
git commit -m "feat(child): add depth-sorted 3D ocean labels"
```

---

## Task 7: Level camera controller (T10) and component wiring

**Files:**
- Create: `frontend/apps/child/src/components/learning/ocean3d/OceanCameraController.ts`
- Create: `frontend/apps/child/src/components/learning/ocean3d/KnowledgeOcean3D.vue`
- Create: `frontend/apps/child/src/components/learning/ocean3d/__tests__/OceanCameraController.test.ts`
- Create: `frontend/apps/child/src/components/learning/ocean3d/__tests__/KnowledgeOcean3D.test.ts`

**Interfaces:**
- Consumes: `useSceneLifecycle()` (Task 1), `CameraController` / `OrbitCameraController` (Task 2), `buildOceanScene()` (Task 4), `createOceanWater()` (Task 5), `createOceanLabels()` (Task 6), `isWebGLAvailable()` from `@/composables/useWebGLAvailable`, `useReducedMotion()`.
- Produces:
  ```ts
  export interface OceanCameraController {
    diveTo(node: { x: number; z: number; worldRadius: number }): Promise<void>
    ascend(): Promise<void>
    reset(): Promise<void>
    dispose(): void
  }
  export function createOceanCameraController(camera: PerspectiveCamera, options?: { instant?: boolean }): OceanCameraController & { getStateSnapshot(): { radius: number; theta: number; phi: number; target: Vector3 } }
  ```
  Component props/emits:
  ```ts
  props: { subjects: OceanSubject[]; domains: OceanDomain[]; selectedSubject: string; selectedDomain: string; selectedTopicLevel: boolean }
  emits: {
    previewSubject: [subject: string]
    selectSubject: [subject: string]
    previewDomain: [payload: { subject: string; domain: string }]
    selectDomain: [payload: { subject: string; domain: string }]
    zoomOut: []
    fallback: []
    interacted: []
    oceanNavigation: [OceanNodeRef | null]
  }
  ```

`OceanNodeRef` is `{ id: string; subject?: string; x: number; z: number; worldRadius: number }`. `OceanCameraController` methods accept `OceanNodeRef` via structural typing. `KnowledgeOcean3D.vue` also emits `oceanNavigation` whenever a subject/domain is entered so the page can drive 2D state from one source of truth.

- [ ] **Step 1: Write failing camera and component tests**

```ts
// OceanCameraController.test.ts
it('diveTo creates an animeDriver child timeline and moves the camera', async () => { const c = createOceanCameraController(new PerspectiveCamera(55,1,.1,200)); await c.diveTo({x:2,z:3,worldRadius:1}); expect(c.getStateSnapshot().target.x).toBeCloseTo(2) })
it('ascend returns to L0 world center', async () => { /* expect target≈(0,0,0) and radius≈22 */ })
it('instant mode moves immediately', () => { const c = createOceanCameraController(camera,{instant:true}); void c.diveTo(node); expect(c.getStateSnapshot().target.x).toBeCloseTo(node.x) })
it('20 dive/ascend cycles leave no child timelines', () => { for (let i=0;i<20;i++) await c.diveTo(node).then(()=>c.ascend()); c.dispose(); expect(getRootTimeline()).toBeNull() })

// KnowledgeOcean3D.test.ts — mock three via vi.mock('three') and stub WebGL detection
it('does not import three and emits fallback when WebGL unavailable', async () => { /* stub isWebGLAvailable false; mount component; expect wrapper.text() to contain fallback i18n text and emitted fallback; expect three mock not constructed */ })
it('emits selectSubject on canvas dblclick when raycaster hits an island', async () => { /* set container width/height, stub raycaster intersectObjects with userData.islandId; dispatch dblclick; expect emitted('selectSubject')[0][0] === 'math' */ })
it('emits zoomOut on pinch-out gesture', async () => { /* dispatch touchstart/touchmove/touchend with two touches increasing distance; expect emitted('zoomOut') */ })
it('stops the loop and emits fallback on webglcontextlost', async () => { /* dispatch event; expect emitted fallback and rAF canceled */ })
it('pause/resume works across deactivate/activate and visibilitychange', async () => { /* find component via wrapper.findComponent; call onDeactivated hook / dispatch document visibilitychange; expect render count frozen then resumed */ })
```

- [ ] **Step 2: Run tests to verify failure**

Run: `pnpm -C apps/child exec vitest run src/components/learning/ocean3d/__tests__/OceanCameraController.test.ts src/components/learning/ocean3d/__tests__/KnowledgeOcean3D.test.ts`
Expected: FAIL — modules not found.

- [ ] **Step 3: Implement `OceanCameraController.ts`**

L0 state: radius 22, theta 0, phi π/3, target (0, 0, 0). `diveTo(node)` animates (child timeline via `CameraController.animateTo`) to target `(node.x, 0, node.z)` with radius `max(node.worldRadius * 3, 6)` and lower phi (closer to horizon); `ascend()` and `reset()` both animate back to L0. `instant: true` uses the shared controller's instant mode. `dispose()` reverts the active timeline and calls `CameraController.dispose()`.

- [ ] **Step 4: Implement `KnowledgeOcean3D.vue`**

`<script setup lang="ts">` with `defineOptions({ name: 'KnowledgeOcean3D' })`. On mount: if `!isWebGLAvailable()`, emit `fallback` and render only a friendly message (`t('learning.ocean3d.fallback')`) — never `import('three')` in this branch. Otherwise dynamically `import('three')` and `import('./OceanCameraController')`, create scene/camera/renderer (`PerspectiveCamera(55, aspect, 0.1, 200)`, alpha true, pixel ratio ≤ 2), add ambient + directional light, call `buildOceanScene(layoutOceanNodes(props.subjects), { reducedMotion })`, `createOceanWater(THREE, { reducedMotion })`, `createOceanLabels(THREE, nodes, { reducedMotion })`, and `createOceanCameraController(camera, { instant: reducedMotion.value })`. `useSceneLifecycle().mount(...)`; `onFrame(now)` calls `water.update(now / 1000)` and `labels.update(camera)` and processes pending pointer events — the lifecycle handle owns `tickDriver(now)` and `renderer.render(scene, camera)`, so the component must not call either. Add `document.addEventListener('visibilitychange', …)` calling `handle.setDocumentVisibilityPaused(document.hidden)`, removed on unmount; on `onActivated` call `handle.resume()`, on `onDeactivated` call `handle.pause()`, on `onBeforeUnmount` call `handle.destroy()` plus water/labels/scene/camera disposal.

Picking: on `dblclick` (L0) set NDC from canvas rect, use `THREE.Raycaster` against `scene.pickTargets` and emit `selectSubject(id)` from `userData.islandId` / `selectDomain(payload)` from `userData.domainId + userData.subject` based on the current level; on single `pointerup` emit `previewSubject` / `previewDomain` and `interacted`. Call `oceanCameraController.diveTo(node)` on double-click and `ascend()` on `zoomOut`. On two-touch pinch-out (distance increase > 15%) emit `zoomOut`; pinch-in on a picked island emits `selectSubject`. Keep two independent level refs: `sceneLevel: 'subject' | 'domain'` driven by `props.selectedSubject` + `props.selectedDomain` (selecting a domain sets `selectedDomain` but not `selectedTopicLevel`), and `viewMode: 'ocean' | 'topic'` driven by `props.selectedTopicLevel`. When `viewMode === 'topic'`, skip water/label updates and do not pick (the parent overlays the 2D constellation); when it switches back, re-add the ocean scene group. Rebuild ocean/domain scene groups when `props.subjects` / `props.domains` change; expose `resetCamera()` / `diveTo()` for the page. Add `touch-action: none` on the canvas so gestures don't scroll the page.

- [ ] **Step 5: Run tests to verify pass**

Run: `pnpm -C apps/child exec vitest run src/components/learning/ocean3d/__tests__/OceanCameraController.test.ts src/components/learning/ocean3d/__tests__/KnowledgeOcean3D.test.ts`
Expected: PASS — camera entry points, WebGL gate, picking, pinch, lifecycle tests green.

- [ ] **Step 6: Commit**

```bash
git add frontend/apps/child/src/components/learning/ocean3d/OceanCameraController.ts frontend/apps/child/src/components/learning/ocean3d/KnowledgeOcean3D.vue frontend/apps/child/src/components/learning/ocean3d/__tests__/OceanCameraController.test.ts frontend/apps/child/src/components/learning/ocean3d/__tests__/KnowledgeOcean3D.test.ts
git commit -m "feat(child): wire 3D ocean component with level camera"
```

---

## Task 8: Route, page state, localized topic layer

**Files:**
- Create: `frontend/apps/child/src/pages/learning/LearningOcean3DPage.vue`
- Create: `frontend/apps/child/src/pages/learning/__tests__/LearningOcean3DPage.test.ts`
- Modify: `frontend/apps/child/src/router/index.ts` (route after `learning/castle-3d`)
- Modify: `frontend/apps/child/src/i18n/locales/zh-CN.ts` and `en-US.ts` (add `learning.ocean3d.*`)

**Interfaces:**
- Consumes: `getMyLearningMapIndex()` + `getTopicIndex()` from `@/api/learning`; `getContinentTheme`, `domainLabel`, `useLocalizedTopic`; `KnowledgeOcean3D` (Task 7); `TopicConstellation.vue` (`topics: ConstellationTopic[]`, `edges: ConstellationEdge[]`, `viewWidth`, `viewHeight`; emits `selectTopic`).
- Produces: page-local refs `subjects`, `domains`, `topics`, `edges`, `selectedSubject`, `selectedDomain`, `level: 'ocean' | 'topic'`; no exported store or router params for level.

- [ ] **Step 1: Write failing page/route tests**

```ts
vi.mock('@/api/learning', () => ({ getMyLearningMapIndex: vi.fn(), getTopicIndex: vi.fn() }))
vi.mock('@/components/learning/ocean3d/KnowledgeOcean3D.vue', () => ({ default: { template: '<div data-test="ocean3d" @select-subject="$emit(\'selectSubject\', $event)" @select-domain="$emit(\'selectDomain\', $event)" @zoom-out="$emit(\'zoomOut\')" />', emits: ['selectSubject','selectDomain','zoomOut','fallback'] } }))

it('computes subjects/domains from two index calls with the same mastery口径 as LearningMapPage', async () => { /* progress rows mastered count / topic index totals; expect 1 subject island and 1 domain region */ })
it('domain click switches to 2D TopicConstellation without navigating; back returns to 3D L1', async () => { /* emit selectDomain; expect TopicConstellation visible and router.push not called; click back; expect ocean3d visible again with selectedSubject still set */ })
it('zoomOut from L1 clears selectedSubject and selectedDomain', async () => { /* expect ocean3d props selectedSubject === '' */ })
it('state is page-local: remounting starts at L0 with empty selection', async () => { /* navigate away and remount; expect selectedSubject === '' and no persisted refs */ })
it('shows loading, error, and empty states', async () => { /* reject API then retry; resolve empty arrays; assert data-test markers */ })
it('route /learning/ocean-3d is named KnowledgeOcean3D', () => { /* import router routes and assert path/name */ })
```

- [ ] **Step 2: Run page tests to verify failure**

Run: `pnpm -C apps/child exec vitest run src/pages/learning/__tests__/LearningOcean3DPage.test.ts`
Expected: FAIL — page module not found / route missing.

- [ ] **Step 3: Implement page data and states**

Mirror `LearningMapPage.vue:307-420`: build `subjects` from all `getTopicIndex()` rows (mastery = progress rows with `mastery_level === 'mastered'` divided by that subject's topic-index total; display name via `t('learning.subject.<id>', id)`; icon/terrain via `getContinentTheme`); build `domains` for the selected subject only, keyed `${subject}:${domain || '__other__'}` with `domainLabel()`; build `topics` for the selected domain with `useLocalizedTopic()`; derive `edges` only when topic detail is available — this page intentionally does one light load, so pass `[]` edges and let `TopicConstellation` show isolated nodes (no `getTopicsBatch`, no `getSubjectDependencies`). Loading uses `RoleShimmer`; error shows `t('learning.ocean3d.error')` with a retry button; empty shows `t('learning.ocean3d.empty')`.

- [ ] **Step 4: Implement navigation and route/i18n**

On `selectSubject(id)`: set `selectedSubject`, clear `selectedTopicLevel`, and call `ocean3d.diveTo()` with the matching node. Preview events no-op (HUD feedback is T14, out of scope). On `selectDomain(payload)`: set `selectedDomain` and `selectedTopicLevel = true` while keeping `selectedSubject` — this reveals the 2D constellation overlay without clearing 3D L1 state. Back sets `selectedTopicLevel = false` (L1). `zoomOut` clears both `selectedSubject` and `selectedDomain` plus `selectedTopicLevel` and calls `KnowledgeOcean3D.resetCamera()`. On `oceanNavigation(node)` (component-initiated pinch/dive) apply the same state transitions through one shared handler so the two levels cannot diverge. Topic selection routes to existing `/learning/topic/:id` (the 2D topic page) — do not invent a new route. Add route `{ path: 'learning/ocean-3d', name: 'KnowledgeOcean3D', component: () => import('@/pages/learning/LearningOcean3DPage.vue'), meta: { hasSkeleton: true } }` immediately after `castle-3d`. Add zh/en keys under `learning.ocean3d`: `title`, `subtitle`, `back`, `backToOcean`, `retry`, `error`, `empty`, `fallback`, `hint`, `topics` (`{count}`). Reuse `learning.ocean.*` strings where identical (do not duplicate `topics` if the same placeholder works).

- [ ] **Step 5: Run page tests to verify pass**

Run: `pnpm -C apps/child exec vitest run src/pages/learning/__tests__/LearningOcean3DPage.test.ts`
Expected: PASS — data derivation, 2D topic layer transition, back/zoomOut, loading/error/empty, route assertions green.

- [ ] **Step 6: Commit**

```bash
git add frontend/apps/child/src/pages/learning/LearningOcean3DPage.vue frontend/apps/child/src/pages/learning/__tests__/LearningOcean3DPage.test.ts frontend/apps/child/src/router/index.ts frontend/apps/child/src/i18n/locales/zh-CN.ts frontend/apps/child/src/i18n/locales/en-US.ts
git commit -m "feat(child): add /learning/ocean-3d route and page"
```

---

## Task 9: Full verification and leak regression

**Files:**
- No new files; run the complete child-app verification suite and inspect for forbidden patterns.

**Interfaces:**
- Consumes: all modules from Tasks 1–8.

- [ ] **Step 1: Run full child test suite**

Run: `pnpm -C apps/child test:run`
Expected: PASS — including all pre-existing castle3d tests and new ocean3d/scene3d/page tests.

- [ ] **Step 2: Run typecheck and lint**

Run: `pnpm -C apps/child typecheck && pnpm -C apps/child lint`
Expected: PASS — no TS errors, no ESLint errors (especially no direct `animejs` imports).

- [ ] **Step 3: Verify no forbidden patterns in changed files**

Run from repo root:
```bash
git diff --name-only | xargs grep -nE 'import \{ *animate *\} from .animejs.|@ts-ignore|@ts-expect-error|test\.skip|it\.only|describe\.only|TODO' || true
```
Expected: no matches in new code. Confirm `git status --short` shows only intended files (spec file from before this plan is untouched).

- [ ] **Step 4: Run an additional 20-cycle ocean lifecycle regression**

Run: `pnpm -C apps/child exec vitest run src/components/learning/ocean3d/__tests__ src/components/learning/scene3d/__tests__ src/components/learning/castle3d/__tests__`
Expected: PASS — the 20 mount/destroy and 20 dive/ascend cycle tests complete without leaked timelines/rAF.

- [ ] **Step 5: Commit verification fixes (only if Step 1–4 found issues)**

```bash
git add <files-fixed>
git commit -m "fix(child): address ocean3d verification findings"
```

---

## Delivery notes (not in scope, do not implement here)

- No real-device FPS/memory numbers may be claimed — no browser/device measurement was requested or performed in this plan.
- Deferred to later tasks: T14 HUD motion, T15 island-lighting loop, T16 error feedback, T18 accessibility DOM list, T19 2D fallback rendering, T20–T23 screenshot/memory regression, T0.2/T0.5 device measurements, and full three-level 3D topic constellation.
