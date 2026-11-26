# 3D Knowledge Castle

Orbit-camera 3D castle. A child orbits the castle, taps a tower to enter it, and
taps a window to jump into practice.

## Scene graph

Three layers, each a separate component:

```
LearningCastle3DPage        route /learning/castle-3d
├── CastlePanorama          L0 — whole castle, orbit camera, tap-to-enter
└── TowerInterior           L1 — one tower: floors, bricks, windows (2D overlay)
```

`CastlePanorama` owns the WebGL renderer and is kept mounted (`v-show`) while a
tower is open, so returning from a tower does not rebuild the scene. `TowerInterior`
is a DOM overlay — it reuses the same brick-count rule as the 3D scene, so the two
views can never disagree.

## Modules

| File | Responsibility |
|------|----------------|
| `CameraController.ts` | Orbit controls (mouse + touch) and anime.js camera transitions |
| `CastleSceneBuilder.ts` | `CastleIndex` → three.js `Group`s; owns the brick-count rule |
| `BrickDropAnimation.ts` | Rapier-driven brick drop for the newly mastered topic |
| `CastlePanorama.vue` | Renderer, render loop, raycaster picking |
| `TowerInterior.vue` | Accessible floor/window list for one tower |

## Contracts

**Single clock.** Only the render loop calls `tickDriver(now)`. Camera transitions
use `createChildTimeline()` and never auto-play.

**Physics / animation separation.** Rapier drives the falling brick's position;
anime.js drives the settle bounce and scale. They never write the same property
in the same frame.

**Brick count.** `calcBrickCount()` is the single source of truth: 0 when a floor
has no progress, at least 1 for any progress, capped at 8. The 2D overlay and the
3D scene both call it.

**One brick animates.** `?new=<topicId>` drops exactly one brick — the last brick
on the floor matching `newSubject`/`newDomain`. Everything else is static. The
query param is stripped after first read so a later visit animates nothing.

**No residual bodies.** `animateBrickDrop` creates two bodies (brick + temporary
landing plane) and frees both on settle *or* abort. Pass an `AbortSignal` and abort
it in `onBeforeUnmount` — otherwise a drop in flight outlives the world it points at.

**Degradation.** `LearningCastle3DPage` checks `isWebGLAvailable()` before importing
three.js at all. No WebGL → the existing 2D `KnowledgeCastle.vue` renders unchanged.
`webglcontextlost` stops the render loop instead of crashing.

**Reduced motion.** Physics still runs (the brick does fall), but the settle bounce
is skipped and the brick is placed at its target instantly.

## Lifecycle

| Event | Action |
|-------|--------|
| `onMounted` | `initRapier()` → build scene → enable camera → start loop |
| `onActivated` | Resume loop |
| `onDeactivated` | Pause loop |
| `onBeforeUnmount` | Abort in-flight drop → dispose controller → dispose geometries/materials → dispose renderer + force context loss |

## Touch handling

The canvas sets `touch-action: none` so orbit drags do not scroll the page. Desktop
gets mouse drag. Both paths funnel into `CameraController.rotate()`.

## Testing

Unit tests cover the builder, camera, drop animation, and overlay. The integration
test covers 20 mount/unmount cycles (no leaked bodies or timelines), an 8-tower
castle, zero-progress towers, and WebGL detection.

```bash
pnpm vitest run src/components/learning/castle3d/
```
