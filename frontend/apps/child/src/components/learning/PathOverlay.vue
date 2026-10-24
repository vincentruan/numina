<template>
  <svg
    v-if="visibleSegments.length > 0"
    class="path-overlay"
    aria-hidden="true"
  >
    <defs>
      <linearGradient :id="gradientId" x1="0%" y1="0%" x2="100%" y2="0%">
        <stop offset="0%" stop-color="var(--color-path-trail-start)" />
        <stop offset="100%" stop-color="var(--color-path-trail-end)" />
      </linearGradient>
    </defs>
    <path
      :d="trailPath"
      class="path-overlay__trail"
      :class="{ 'path-overlay__trail--static': isReducedMotion }"
    />
    <template v-if="!isReducedMotion">
      <circle
        v-for="dot in pulseDots"
        :key="dot.i"
        :cx="dot.x"
        :cy="dot.y"
        :r="dot.r"
        class="path-overlay__dot"
        :style="{ animationDelay: dot.delay }"
      />
    </template>
  </svg>
</template>

<script setup lang="ts">
defineOptions({ name: 'PathOverlay' })

import { ref, computed, watch, onMounted, onBeforeUnmount, getCurrentInstance, nextTick } from 'vue'
import { useReducedMotion } from '@/composables/useReducedMotion'
import type { ProgressWithTopic } from '@/api/learning'

const isReducedMotion = useReducedMotion()

const props = defineProps<{
  pathTopicIds: string[]
  allItems: ProgressWithTopic[]
  expandedDomains: Set<string>
}>()

// Fixed gradient ID — component is a singleton on the page
const gradientId = 'path-overlay-gradient'

interface MeasuredPoint {
  topicId: string
  x: number
  y: number
}

interface PulseDot {
  i: number
  x: number
  y: number
  r: number
  delay: string
}

const measuredPoints = ref<MeasuredPoint[]>([])
const containerRect = ref<DOMRect | null>(null)
let containerEl: Element | null = null
let resizeObserver: ResizeObserver | null = null
let resizeTimer: ReturnType<typeof setTimeout> | null = null

// Get the domain for a topic ID
function getTopicDomain(topicId: string): string | null {
  const item = props.allItems.find((i) => i.topic.id === topicId)
  return item?.topic.domain ?? null
}

// Check if a topic is in an expanded domain
function isTopicVisible(topicId: string): boolean {
  const domain = getTopicDomain(topicId)
  if (!domain) return false
  return props.expandedDomains.has(domain)
}

// Compute visible path segments (pairs of consecutive visible topics)
const visibleSegments = computed(() => {
  const visible = props.pathTopicIds.filter((id) => isTopicVisible(id))
  const segments: Array<{ from: string; to: string }> = []
  for (let i = 0; i < visible.length - 1; i++) {
    segments.push({ from: visible[i], to: visible[i + 1] })
  }
  return segments
})

// Measure topic node positions relative to the container element
function measurePositions() {
  if (!containerEl) return

  containerRect.value = containerEl.getBoundingClientRect()
  const points: MeasuredPoint[] = []

  for (const topicId of props.pathTopicIds) {
    if (!isTopicVisible(topicId)) continue
    const el = document.querySelector(`[data-topic-id="${topicId}"]`)
    if (!el) continue

    const rect = el.getBoundingClientRect()
    const cRect = containerRect.value
    points.push({
      topicId,
      x: rect.left - cRect.left + rect.width / 2,
      y: rect.top - cRect.top + rect.height / 2,
    })
  }

  measuredPoints.value = points
}

// Generate SVG path using cubic bezier curves
const trailPath = computed(() => {
  const pts = measuredPoints.value
  if (pts.length < 2) return ''

  let d = `M ${pts[0].x} ${pts[0].y}`
  for (let i = 1; i < pts.length; i++) {
    const prev = pts[i - 1]
    const curr = pts[i]
    // Horizontal offset for control points creates smooth S-curves
    const dx = (curr.x - prev.x) * 0.4
    const cp1x = prev.x + dx
    const cp1y = prev.y
    const cp2x = curr.x - dx
    const cp2y = curr.y
    d += ` C ${cp1x} ${cp1y}, ${cp2x} ${cp2y}, ${curr.x} ${curr.y}`
  }
  return d
})

// Generate pulse dots at midpoint intervals along the path
const pulseDots = computed<PulseDot[]>(() => {
  const pts = measuredPoints.value
  if (pts.length < 2) return []

  const dots: PulseDot[] = []
  let dotIndex = 0

  for (let i = 0; i < pts.length - 1; i++) {
    const prev = pts[i]
    const curr = pts[i + 1]
    // Place 2 dots per segment at 33% and 66% intervals
    for (const t of [0.33, 0.66]) {
      dots.push({
        i: dotIndex++,
        x: prev.x + (curr.x - prev.x) * t,
        y: prev.y + (curr.y - prev.y) * t,
        r: 3,
        delay: `${dotIndex * 0.3}s`,
      })
    }
  }
  return dots
})

// Re-measure on data changes. Watch expandedDomains as array since Vue 3
// Sets lack deep reactivity — the computed returns a new Set reference on
// each toggle, so the outer watcher fires on reference change.
watch(
  () => [props.pathTopicIds, Array.from(props.expandedDomains)],
  async () => {
    await nextTick()
    // Wait for CSS height transitions on DomainSection to complete (~300ms)
    // before measuring; nextTick only covers Vue's DOM patch, not transitions.
    setTimeout(() => measurePositions(), 350)
  },
)

// ResizeObserver for responsive re-measurement
onMounted(() => {
  // Use parent element as positioning container (PathOverlay is rendered
  // inside .cluster-map div), avoiding fragile global querySelector.
  containerEl = (getCurrentInstance()?.proxy?.$el as Element)?.parentElement ?? null
  if (containerEl) {
    resizeObserver = new ResizeObserver(() => {
      // Debounce to avoid visual jitter during rotation/resize
      if (resizeTimer) clearTimeout(resizeTimer)
      resizeTimer = setTimeout(() => {
        measurePositions()
      }, 100)
    })
    resizeObserver.observe(containerEl)
  }
  // Initial measurement
  nextTick(() => measurePositions())
})

onBeforeUnmount(() => {
  resizeObserver?.disconnect()
  if (resizeTimer) clearTimeout(resizeTimer)
})
</script>

<style scoped>
.path-overlay {
  position: absolute;
  inset: 0;
  pointer-events: none;
  overflow: visible;
  z-index: 1;
}

.path-overlay__trail {
  fill: none;
  stroke: url(#path-overlay-gradient);
  stroke-width: 4;
  stroke-linecap: round;
  stroke-dasharray: 80 120;
  animation: path-flow 2.5s linear infinite;
}

.path-overlay__trail--static {
  animation: none;
  stroke-dasharray: none;
  opacity: 0.7;
}

.path-overlay__dot {
  fill: var(--color-path-dot);
  will-change: transform, opacity;
  transform-box: fill-box;
  transform-origin: center;
  animation: dot-pulse 1.8s ease-in-out infinite;
}

@keyframes path-flow {
  to {
    stroke-dashoffset: -200;
  }
}

/* Use transform: scale() instead of animating the SVG r attribute —
 * scale + opacity are composite-only properties and avoid per-frame
 * repaints. scale(1.67) on r=3 gives the same 3->5 visual range. */
@keyframes dot-pulse {
  0%, 100% {
    transform: scale(1);
    opacity: 0.4;
  }
  50% {
    transform: scale(1.67);
    opacity: 0.9;
  }
}

@media (prefers-reduced-motion: reduce) {
  .path-overlay__trail {
    animation: none;
    stroke-dasharray: none;
  }
  .path-overlay__dot {
    animation: none;
    opacity: 0.6;
  }
}
</style>
