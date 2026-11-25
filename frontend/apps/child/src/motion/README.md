# Motion & Physics Infrastructure

Shared modules for all 3D components in the child app (Knowledge Ocean, physics challenges, etc.).

## Single Clock Rule

Only the render loop calls `tickDriver(now)`. Components receive child timelines via `createChildTimeline()` and never auto-play. This prevents multiple animation clocks from fighting each other.

```ts
// ✅ Correct — child timeline, driven by render loop
const child = createChildTimeline()
child.add('.mesh', { opacity: [0, 1], duration: 300 })
// In render loop: tickDriver(now) advances everything

// ❌ Wrong — direct import, independent clock
import { animate } from 'animejs' // forbidden in components
animate('.mesh', { opacity: [0, 1] }) // auto-plays on its own clock
```

## Physics / Animation Separation

- **Physics** (rapier) drives: rigid body positions, gravity, collisions, scale beam tilt.
- **Animation** (anime.js) drives: elastic bounces, fades, UI transitions, island bobbing.
- **Visual group** layers on top of the physics mesh — they never fight over the same property.

```
Physics body → mesh.position (every frame)
Anime timeline → mesh.scale, mesh.material.opacity (decorative)
```

## Lifecycle Protocol

All 3D modules follow the same SPA lifecycle:

| Event | Action |
|-------|--------|
| `onActivated` / `visibilitychange` → visible | Resume render loop |
| `onDeactivated` / `visibilitychange` → hidden | Pause render loop |
| `onBeforeUnmount` | Revert child timelines, dispose geometry/materials, release body refs |

Memory invariant: JS Heap and WebGL context count must not grow over 20 mount/unmount cycles.

## Modules

### `animeDriver.ts`
Single timeline root + `tickDriver(now)`. Components use `createChildTimeline()`.

### `easing.ts`
Named easing exports (`easeOutElastic`, `easeOutQuad`, etc.). Components import from here.

### `materials.ts`
Bridge from `clay.css` tokens to three.js `Color` instances. `clayColor('primary')` reads `--color-primary`.

### `rapierWorld.ts`
RAPIER.init() singleton with fixed-timestep accumulator. `getWorld()` for shared use, `createScopedWorld(id)` for isolated physics.

### `islandBody.ts`
Factory helpers: `createKinematicIsland()`, `createDynamicObject()`, `createStaticGround()`.

## Reduced Motion

All modules respect `useReducedMotion()`. When active:
- Physics simulation continues (gameplay correctness)
- Visual micro-animations (bounce, wobble, bob) are skipped — instant state transitions
- Audio still plays
