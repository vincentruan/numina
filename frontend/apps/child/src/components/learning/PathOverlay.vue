<template>
  <svg
    v-if="visibleSegments.length > 0"
    class="path-overlay"
    role="img"
    :aria-label="t('learning.recommendPath.pathA11yLabel')"
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

import { ref, computed, watch, onMounted, onBeforeUnmount, nextTick } from 'vue'
import { useI18n } from 'vue-i18n'
import { useReducedMotion } from '@/composables/useReducedMotion'
import type { ProgressWithTopic } from '@/api/learning'

const { t } = useI18n()
const isReducedMotion = useReducedMotion()

const props = defineProps<{
  pathTopicIds: string[]
  allItems: ProgressWithTopic[]
  expandedDomains: Set<string>
}>()

// Unique gradient ID to avoid SVG collisions when multiple instances exist
const gradientId = 'path-gradient-' + Math.random().toString(36).slice(2, 8)

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

// Measure topic node positions relative to the .cluster-map container
function measurePositions() {
  const container = document.querySelector('.cluster-map')
  if (!container) return

  containerRect.value = container.getBoundingClientRect()
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

// Re-measure on data changes
watch(
  () => [props.pathTopicIds, props.expandedDomains],
  async () => {
    await nextTick()
    measurePositions()
  },
  { deep: true },
)

// ResizeObserver for responsive re-measurement
onMounted(() => {
  const container = document.querySelector('.cluster-map')
  if (container) {
    resizeObserver = new ResizeObserver(() => {
      // Debounce to avoid visual jitter during rotation/resize
      if (resizeTimer) clearTimeout(resizeTimer)
      resizeTimer = setTimeout(() => {
        measurePositions()
      }, 100)
    })
    resizeObserver.observe(container)
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
  stroke: url(#path-gradient);
  stroke-width: 4;
  stroke-linecap: round;
  stroke-dasharray: 80 120;
  animation: path-flow 2.5s linear infinite;
  will-change: transform;
}

.path-overlay__trail--static {
  animation: none;
  stroke-dasharray: none;
  opacity: 0.7;
}

.path-overlay__dot {
  fill: var(--color-path-dot);
  animation: dot-pulse 1.8s ease-in-out infinite;
}

@keyframes path-flow {
  to {
    stroke-dashoffset: -200;
  }
}

@keyframes dot-pulse {
  0%, 100% {
    r: 3;
    opacity: 0.4;
  }
  50% {
    r: 5;
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
