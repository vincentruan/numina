<template>
  <div class="knowledge-ocean-wrap">
    <!--
      Three zoom levels (R4): subject (islands in the sea), domain (regions of
      one subject), topic (constellation of one domain). All levels are always
      computed; zoom changes which is legible, never what exists.
    -->
    <svg
      ref="svgRef"
      class="knowledge-ocean"
      :viewBox="`0 0 ${VIEW_W} ${VIEW_H}`"
      role="application"
      :aria-label="t('learning.ocean.a11yLabel')"
      @touchstart.passive="onTouchStart"
      @touchmove="onTouchMove"
      @touchend="onTouchEnd"
    >
      <!-- Sea (R7 — legible at every mastery ratio) -->
      <rect class="ocean-sea" x="0" y="0" :width="VIEW_W" :height="VIEW_H" />

      <!-- Decorative waves -->
      <path
        v-for="(wave, i) in waves"
        :key="`wave-${i}`"
        class="ocean-wave"
        :d="wave.d"
      />

      <!-- ── Subject level: islands (R2, R3, R5, R7) ── -->
      <template v-if="level === 'subject'">
        <g
          v-for="island in islands"
          :key="island.id"
          class="ocean-island"
          :class="[
            `ocean-island--${island.terrain}`,
            { 'ocean-island--active': island.id === props.selectedSubject },
          ]"
          :transform="`translate(${island.x * VIEW_W}, ${island.y * VIEW_H})`"
          :data-island-id="island.id"
          :tabindex="0"
          role="button"
          :aria-label="island.displayName"
          @click="onIslandTap(island)"
          @keydown.enter="onIslandTap(island)"
        >
          <!-- Landmass silhouette (R7 — rendered under fog, always visible) -->
          <path
            class="ocean-island__land"
            :d="island.silhouette"
          />
          <!-- Fog veil (R5 — opacity from subject mastery; R6 — never blocks
               interaction: pointer-events none) -->
          <path
            class="ocean-island__fog"
            :d="island.silhouette"
            :style="{ opacity: island.fogOpacity }"
          />
          <!-- Label above fog (R7) -->
          <text
            class="ocean-island__label"
            y="-8"
            text-anchor="middle"
          >{{ island.icon }} {{ island.displayName }}</text>
        </g>
      </template>

      <!-- ── Domain level: regions (R4) ── -->
      <template v-else-if="level === 'domain'">
        <g
          v-for="region in regions"
          :key="region.id"
          class="ocean-region"
          :class="[
            `ocean-region--${region.terrain}`,
            { 'ocean-region--active': region.id === props.selectedDomain },
          ]"
          :transform="`translate(${region.x * VIEW_W}, ${region.y * VIEW_H})`"
          :tabindex="0"
          role="button"
          :aria-label="region.displayName"
          @click="onRegionTap(region)"
          @keydown.enter="onRegionTap(region)"
        >
          <rect
            class="ocean-region__land"
            x="-40"
            y="-24"
            width="80"
            height="48"
            rx="14"
          />
          <rect
            class="ocean-region__fog"
            x="-40"
            y="-24"
            width="80"
            height="48"
            rx="14"
            :style="{ opacity: region.fogOpacity }"
          />
          <text class="ocean-region__label" text-anchor="middle">
            {{ region.displayName }}
          </text>
          <text class="ocean-region__count" y="12" text-anchor="middle">
            {{ t('learning.ocean.topics', { count: region.topicCount }) }}
          </text>
        </g>
      </template>

      <!-- ── Topic level: constellation (R9, R10) ── -->
      <template v-else>
        <TopicConstellation
          :topics="domainTopics"
          :edges="domainEdges"
          :view-width="VIEW_W"
          :view-height="VIEW_H"
          @select-topic="onTopicTap"
        />
      </template>
    </svg>

    <!-- Back navigation -->
    <button
      v-if="level !== 'subject'"
      class="ocean-back"
      type="button"
      @click="onZoomOut"
    >
      {{ level === 'topic'
        ? t('learning.ocean.backToSubject', { subject: subjectDisplayName })
        : t('learning.ocean.backToOcean') }}
    </button>

    <!-- Zoom hint (F1) -->
    <p v-if="level === 'subject'" class="ocean-hint">
      {{ t('learning.ocean.zoomHint') }}
    </p>
  </div>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { layoutIslands } from '@/utils/islandLayout'
import { fogOpacityForRatio } from '@/utils/continentFog'
import TopicConstellation from './TopicConstellation.vue'

export interface OceanSubject {
  id: string
  terrain: string
  displayName: string
  icon: string
  topicCount: number
  masteryRatio: number
}

export interface OceanDomain {
  id: string
  subject: string
  domain: string
  displayName: string
  topicCount: number
  masteryRatio: number
}

export interface OceanTopic {
  id: string
  subject: string
  domain: string
  displayName: string
  masteryLevel: string
}

export interface OceanDependencyEdge {
  topic_id: string
  prerequisite_id: string
  strength: string | null
}

const props = defineProps<{
  subjects: OceanSubject[]
  domains: OceanDomain[]
  topics: OceanTopic[]
  edges: OceanDependencyEdge[]
  selectedSubject: string
  selectedDomain: string
}>()

const emit = defineEmits<{
  /** Single tap on an island — the page shows a preview (R6). */
  previewSubject: [subject: string]
  /** Double-tap or pinch-in — descend into this subject (R8). */
  selectSubject: [subject: string]
  /** Single tap on a region — preview (R6). */
  previewDomain: [payload: { subject: string; domain: string }]
  /** Double-tap — descend into this domain (R8). */
  selectDomain: [payload: { subject: string; domain: string }]
  /** Topic node tapped — enter practice (F2). */
  selectTopic: [payload: { id: string }]
  /** Pinch-out — return one zoom level up (R8). */
  zoomOut: []
  /** A zoom gesture moved to this level (R12). Levels: 0 subject, 1 domain, 2 topic. */
  zoomed: [level: number]
  /** Any pan/tap interaction (R12). */
  interacted: []
}>()

const { t } = useI18n()

// Canvas coordinate space — fixed viewBox; the SVG scales to container.
const VIEW_W = 360
const VIEW_H = 480

// ── Zoom level derivation (R4) ──

type Level = 'subject' | 'domain' | 'topic'
const level = computed<Level>(() => {
  if (props.selectedSubject && props.selectedDomain) return 'topic'
  if (props.selectedSubject) return 'domain'
  return 'subject'
})

const subjectDisplayName = computed(() => {
  const s = props.subjects.find((x) => x.id === props.selectedSubject)
  return s?.displayName ?? props.selectedSubject
})

// ── Subject level: islands (R3 — organic layout from relationships) ──

export interface RenderedIsland {
  id: string
  terrain: string
  displayName: string
  icon: string
  x: number
  y: number
  fogOpacity: number
  silhouette: string
}

/** Organic blob silhouette around (0,0), deterministic per island. */
function islandSilhouette(seed: string, radiusPx: number): string {
  // Cheap deterministic angle from the id.
  let hash = 0
  for (let i = 0; i < seed.length; i++) {
    hash = (hash * 31 + seed.charCodeAt(i)) | 0
  }
  const rng = (n: number) => {
    const x = Math.sin(hash + n * 127.1) * 43758.5453
    return x - Math.floor(x)
  }
  const points: Array<[number, number]> = []
  const bumps = 8
  for (let i = 0; i < bumps; i++) {
    const angle = (i / bumps) * Math.PI * 2
    const r = radiusPx * (0.75 + rng(i) * 0.5)
    points.push([Math.cos(angle) * r, Math.sin(angle) * r * 0.8])
  }
  // Closed smooth path through the points (Catmull-Rom → bezier).
  let d = `M ${points[0][0].toFixed(1)} ${points[0][1].toFixed(1)}`
  for (let i = 0; i < bumps; i++) {
    const p0 = points[i]
    const p1 = points[(i + 1) % bumps]
    const mx = (p0[0] + p1[0]) / 2
    const my = (p0[1] + p1[1]) / 2
    d += ` Q ${p0[0].toFixed(1)} ${p0[1].toFixed(1)} ${mx.toFixed(1)} ${my.toFixed(1)}`
  }
  return d + ' Z'
}

const islands = computed<RenderedIsland[]>(() => {
  const layout = layoutIslands(
    props.subjects.map((s) => ({ id: s.id, terrain: s.terrain, topicCount: s.topicCount })),
  )
  const posById = new Map(layout.positions.map((p) => [p.id, p]))
  return props.subjects.map((s) => {
    const pos = posById.get(s.id) ?? { x: 0.5, y: 0.5, radius: 0.04 }
    // radius is in normalized units; convert to px in the viewBox space.
    const radiusPx = pos.radius * VIEW_W
    return {
      id: s.id,
      terrain: s.terrain,
      displayName: s.displayName,
      icon: s.icon,
      x: pos.x,
      y: pos.y,
      fogOpacity: fogOpacityForRatio(s.masteryRatio),
      silhouette: islandSilhouette(s.id, radiusPx * 2.2),
    }
  })
})

// ── Domain level: regions ──

export interface RenderedRegion {
  id: string
  subject: string
  domain: string
  terrain: string
  displayName: string
  topicCount: number
  x: number
  y: number
  fogOpacity: number
}

const regions = computed<RenderedRegion[]>(() => {
  const subjectDomains = props.domains.filter((d) => d.subject === props.selectedSubject)
  const layout = layoutIslands(
    subjectDomains.map((d) => ({ id: d.id, terrain: 'region', topicCount: d.topicCount })),
  )
  const posById = new Map(layout.positions.map((p) => [p.id, p]))
  return subjectDomains.map((d) => {
    const pos = posById.get(d.id) ?? { x: 0.5, y: 0.5 }
    return {
      id: d.id,
      subject: d.subject,
      domain: d.domain,
      terrain: props.subjects.find((s) => s.id === d.subject)?.terrain ?? 'default',
      displayName: d.displayName,
      topicCount: d.topicCount,
      x: pos.x,
      y: pos.y,
      fogOpacity: fogOpacityForRatio(d.masteryRatio),
    }
  })
})

// ── Topic level: constellation inputs (R9, R10) ──

const domainTopics = computed(() =>
  props.topics.filter(
    (tp) => tp.subject === props.selectedSubject && tp.domain === props.selectedDomain,
  ),
)

const domainEdges = computed(() => {
  const topicIds = new Set(domainTopics.value.map((tp) => tp.id))
  return props.edges.filter(
    (e) => topicIds.has(e.topic_id) && topicIds.has(e.prerequisite_id),
  )
})

// ── Decorative waves (F1 — a sea, not a canvas) ──

const waves = computed(() => {
  const paths: Array<{ d: string }> = []
  for (let i = 0; i < 5; i++) {
    const y = 60 + i * 100 + ((i * 37) % 23)
    const x = (i * 53) % 120
    paths.push({
      d: `M ${x} ${y} q 12 -6 24 0 t 24 0 t 24 0 t 24 0 t 24 0 t 24 0 t 24 0 t 24 0`,
    })
  }
  return paths
})

// ── Tap handling ──

// Double-tap window (R8): two taps on the same target within this interval.
const DOUBLE_TAP_MS = 300

interface TapState {
  target: string
  time: number
}

let lastTap: TapState | null = null

function isDoubleTap(target: string): boolean {
  const now = Date.now()
  const double = lastTap !== null
    && lastTap.target === target
    && now - lastTap.time < DOUBLE_TAP_MS
  lastTap = double ? null : { target, time: now }
  return double
}

function onIslandTap(island: RenderedIsland) {
  // A pinch-in on this island just ended — the browser's synthetic click
  // would otherwise open a redundant preview. Consume the suppression.
  if (suppressedTapIslandId === island.id) {
    suppressedTapIslandId = null
    return
  }
  emit('interacted')
  if (isDoubleTap(`island:${island.id}`)) {
    emit('selectSubject', island.id)
    emit('zoomed', 1)
  } else {
    // First tap — preview (R6: preview rather than refusal, even when fogged).
    emit('previewSubject', island.id)
  }
}

function onRegionTap(region: RenderedRegion) {
  emit('interacted')
  if (isDoubleTap(`region:${region.id}`)) {
    emit('selectDomain', { subject: props.selectedSubject, domain: region.domain })
    emit('zoomed', 2)
  } else {
    emit('previewDomain', { subject: props.selectedSubject, domain: region.domain })
  }
}

function onTopicTap(payload: { id: string }) {
  emit('interacted')
  emit('selectTopic', payload)
}

function onZoomOut() {
  emit('zoomOut')
  emit('zoomed', level.value === 'topic' ? 1 : 0)
}

// ── Pinch handling (R8) ──
// Two-finger pinch-in (fingers move closer) on the subject level descends
// into the island under the pinch center. Pinch-out (fingers spread) zooms
// up one level. Tap-vs-pinch on islands is disambiguated by the touch
// sequence: a single-finger tap bubbles to click; a completed pinch with a
// target island suppresses the pending tap.

const svgRef = ref<SVGSVGElement | null>(null)

interface PinchState {
  startDist: number
  centerX: number
  centerY: number
  islandId: string | null
  target: EventTarget | null
}

let pinch: PinchState | null = null
let pinchConsumed = false
// A pinch-in on an island must not then fire a click-triggered preview on the
// same island. We stash the island id here at touchend and consume it on the
// next click.
let suppressedTapIslandId: string | null = null

function touchDistance(touches: TouchList): number {
  const dx = touches[0].clientX - touches[1].clientX
  const dy = touches[0].clientY - touches[1].clientY
  return Math.sqrt(dx * dx + dy * dy)
}

function islandAtPoint(
  x: number,
  y: number,
  fallback: EventTarget | null,
): RenderedIsland | null {
  // Prefer elementFromPoint at the pinch center (correct on real devices when
  // the two fingers straddle an island). Fall back to the touchstart target
  // when elementFromPoint is unavailable or returns nothing (jsdom/happy-dom).
  let el: Element | null = null
  if (typeof document !== 'undefined' && typeof document.elementFromPoint === 'function') {
    el = document.elementFromPoint(x, y)
  }
  if (!el && fallback instanceof Element) el = fallback
  if (!el) return null
  const g = el.closest('.ocean-island')
  if (!g) return null
  const id = g.getAttribute('data-island-id')
  return islands.value.find((i) => i.id === id) ?? null
}

function onTouchStart(e: TouchEvent) {
  if (e.touches.length !== 2) return
  const dist = touchDistance(e.touches)
  pinch = {
    startDist: dist,
    centerX: (e.touches[0].clientX + e.touches[1].clientX) / 2,
    centerY: (e.touches[0].clientY + e.touches[1].clientY) / 2,
    islandId: null,
    target: e.target,
  }
  pinchConsumed = false
}

function onTouchMove(e: TouchEvent) {
  if (e.touches.length === 2) {
    // Block the browser's native pinch-zoom during an in-app pinch gesture.
    e.preventDefault()
  }
  if (!pinch || e.touches.length !== 2) return
  const dist = touchDistance(e.touches)
  const ratio = dist / pinch.startDist
  if (pinchConsumed) return
  if (ratio < 0.6) {
    // Pinch-in — descend.
    pinchConsumed = true
    if (level.value === 'subject') {
      const island = islandAtPoint(pinch.centerX, pinch.centerY, pinch.target)
      if (island) {
        pinch.islandId = island.id
        emit('selectSubject', island.id)
        emit('zoomed', 1)
        emit('interacted')
      }
    }
    // At domain/topic level, pinch-in has no further level to descend via
    // pinch — the child double-taps a region instead.
  } else if (ratio > 1.4) {
    // Pinch-out — ascend one level (R8).
    pinchConsumed = true
    if (level.value !== 'subject') {
      emit('zoomOut')
      emit('zoomed', level.value === 'topic' ? 1 : 0)
      emit('interacted')
    }
  }
}

function onTouchEnd(_e: TouchEvent) {
  if (pinch?.islandId) suppressedTapIslandId = pinch.islandId
  pinch = null
}
</script>

<style scoped>
.knowledge-ocean-wrap {
  position: relative;
  width: 100%;
}

.knowledge-ocean {
  display: block;
  width: 100%;
  height: auto;
  touch-action: pan-y; /* we own pinch; browser must not zoom the page */
  user-select: none;
  -webkit-user-select: none;
}

/* ── Sea ── */

.ocean-sea {
  fill: var(--ocean-sea-color, #cfe8f5);
}

.ocean-wave {
  fill: none;
  stroke: var(--ocean-wave-color, rgba(255, 255, 255, 0.55));
  stroke-width: 2;
  stroke-linecap: round;
}

/* ── Islands (subject level) ── */

.ocean-island {
  cursor: pointer;
  outline: none;
}

.ocean-island__land {
  fill: var(--ocean-land-color, #e8d9a8);
  stroke: var(--ocean-land-border, #c9b37e);
  stroke-width: 1.5;
}

.ocean-island--math .ocean-island__land { fill: #f2dfa7; }
.ocean-island--science .ocean-island__land { fill: #bfe3cf; }
.ocean-island--language .ocean-island__land { fill: #f5cfc5; }
.ocean-island--social .ocean-island__land { fill: #e8d0b3; }
.ocean-island--arts .ocean-island__land { fill: #e3d1f0; }

/* Fog veil — opacity bound inline from mastery (R5); pointer-events none so
   it never blocks taps (R6). */
.ocean-island__fog {
  fill: var(--ocean-fog-color, #b8c4d0);
  pointer-events: none;
  transition: opacity 0.4s ease;
}

@media (prefers-reduced-motion: reduce) {
  .ocean-island__fog {
    transition: none;
  }
}

/* Label rendered above the fog layer in DOM order (R7). */
.ocean-island__label {
  font-family: Inter, sans-serif;
  font-size: 13px;
  font-weight: 600;
  fill: var(--ocean-label-color, #16324a);
  paint-order: stroke;
  stroke: rgba(255, 255, 255, 0.85);
  stroke-width: 3px;
  pointer-events: none;
}

.ocean-island--active .ocean-island__land {
  stroke: var(--color-primary, #0a0a0a);
  stroke-width: 2.5;
}

.ocean-island:focus-visible .ocean-island__land {
  stroke: var(--color-primary, #0a0a0a);
  stroke-width: 2.5;
}

/* ── Regions (domain level) ── */

.ocean-region {
  cursor: pointer;
  outline: none;
}

.ocean-region__land {
  fill: #f2e7c9;
  stroke: #c9b37e;
  stroke-width: 1.5;
}

.ocean-region--science .ocean-region__land { fill: #bfe3cf; }
.ocean-region--language .ocean-region__land { fill: #f5cfc5; }
.ocean-region--social .ocean-region__land { fill: #e8d0b3; }
.ocean-region--arts .ocean-region__land { fill: #e3d1f0; }
.ocean-region--math .ocean-region__land { fill: #f2dfa7; }

.ocean-region__fog {
  fill: var(--ocean-fog-color, #b8c4d0);
  pointer-events: none;
  transition: opacity 0.4s ease;
}

.ocean-region__label {
  font-family: Inter, sans-serif;
  font-size: 12px;
  font-weight: 600;
  fill: var(--ocean-label-color, #16324a);
  pointer-events: none;
}

.ocean-region__count {
  font-family: Inter, sans-serif;
  font-size: 10px;
  fill: var(--ocean-label-muted, #4a6a80);
  pointer-events: none;
}

.ocean-region--active .ocean-region__land,
.ocean-region:focus-visible .ocean-region__land {
  stroke: var(--color-primary, #0a0a0a);
  stroke-width: 2.5;
}

/* ── Chrome ── */

.ocean-back {
  position: absolute;
  top: 8px;
  left: 8px;
  padding: 6px 12px;
  min-height: 32px;
  border: none;
  border-radius: 16px;
  background: var(--color-surface-card, #ffffff);
  color: var(--color-ink, #0a0a0a);
  font-family: Inter, sans-serif;
  font-size: 13px;
  font-weight: 500;
  box-shadow: 0 1px 4px rgba(0, 0, 0, 0.15);
  cursor: pointer;
}

.ocean-hint {
  margin: 6px 0 0;
  text-align: center;
  font-family: Inter, sans-serif;
  font-size: 12px;
  color: var(--color-muted, #6a6a6a);
}

/* ── Dark mode ── */

[data-theme='dark'] .ocean-sea {
  fill: #10222e;
}

[data-theme='dark'] .ocean-wave {
  stroke: rgba(255, 255, 255, 0.12);
}

[data-theme='dark'] .ocean-island__land {
  fill: #2c3e33;
  stroke: #46604e;
}

[data-theme='dark'] .ocean-island__label {
  fill: #f0ece0;
  stroke: rgba(10, 26, 26, 0.85);
}

[data-theme='dark'] .ocean-region__land {
  fill: #2c3e33;
  stroke: #46604e;
}

[data-theme='dark'] .ocean-region__label {
  fill: #f0ece0;
}

[data-theme='dark'] .ocean-region__count {
  fill: #a8b8c0;
}
</style>
