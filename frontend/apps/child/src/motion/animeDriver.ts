/**
 * animeDriver — single-clock timeline root for all 3D modules.
 *
 * Contract:
 * - Only the render loop calls `tickDriver(now)`. No component may auto-play.
 * - Components get child timelines via `createChildTimeline()` — scoped, revertible.
 * - Direct `import { animate } from 'animejs'` in component files is forbidden
 *   (enforced by ESLint no-restricted-imports).
 */
import { createTimeline, type Timeline, type TimelinePosition } from 'animejs'

let rootTimeline: Timeline | null = null
const childTimelines = new Set<Timeline>()

/** Get or lazily create the root timeline (autoplay disabled). */
function getRoot(): Timeline {
  if (!rootTimeline) {
    rootTimeline = createTimeline({ autoplay: false })
  }
  return rootTimeline
}

/**
 * Advance the root timeline to the given timestamp.
 * Called exclusively from the render loop — never from components.
 */
export function tickDriver(now: number): void {
  const root = getRoot()
  root.seek(now)
}

/**
 * Create a child timeline synced to the root clock.
 * The child is attached via `sync()` so it advances when the root is seeked.
 * Components call this instead of creating standalone timelines.
 * Returns the child timeline — call `revert()` on it to cancel and detach.
 */
export function createChildTimeline(): Timeline {
  const root = getRoot()
  const child = createTimeline({ autoplay: false })
  root.sync(child, 0 as TimelinePosition)
  childTimelines.add(child)
  return child
}

/**
 * Revert all child timelines and release references.
 * Called on full teardown (e.g., module unmount, WebGL context loss).
 */
export function revertAll(): void {
  for (const child of childTimelines) {
    child.revert()
  }
  childTimelines.clear()
  if (rootTimeline) {
    rootTimeline.pause()
    rootTimeline = null
  }
}

/** Read-only access to the root timeline for diagnostics. */
export function getRootTimeline(): Timeline | null {
  return rootTimeline
}
