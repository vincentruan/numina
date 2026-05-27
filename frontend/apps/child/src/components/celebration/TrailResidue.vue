<template>
  <Teleport to="body">
    <svg
      ref="svgRef"
      class="trail-overlay"
      aria-hidden="true"
      :viewBox="`0 0 ${vw} ${vh}`"
      preserveAspectRatio="none"
    />
  </Teleport>
</template>

<script setup lang="ts">
import { ref, onMounted, onBeforeUnmount } from 'vue'

const MAX_TRAILS = 50
const TRAIL_LIFETIME_MS = 1500
const REMOVAL_BUFFER_MS = 100

const svgRef = ref<SVGSVGElement | null>(null)
const vw = ref(typeof window !== 'undefined' ? window.innerWidth : 0)
const vh = ref(typeof window !== 'undefined' ? window.innerHeight : 0)

interface TrailEntry {
  path: SVGPathElement
  removalHandle: ReturnType<typeof setTimeout>
}

const trails: TrailEntry[] = []

function onResize(): void {
  vw.value = window.innerWidth
  vh.value = window.innerHeight
}

function evictOldest(): void {
  const oldest = trails.shift()
  if (!oldest) return
  clearTimeout(oldest.removalHandle)
  if (oldest.path.parentNode) oldest.path.parentNode.removeChild(oldest.path)
}

function addPath(d: string): void {
  if (!svgRef.value) return
  // FIFO bound: a child completing many tasks rapidly should not accumulate
  // unbounded SVG nodes between the per-path 60s timer.
  while (trails.length >= MAX_TRAILS) evictOldest()
  const ns = 'http://www.w3.org/2000/svg'
  const path = document.createElementNS(ns, 'path')
  path.setAttribute('d', d)
  path.setAttribute('class', 'trail-segment')
  svgRef.value.appendChild(path)
  const entry: TrailEntry = {
    path,
    removalHandle: setTimeout(() => {
      const idx = trails.indexOf(entry)
      if (idx !== -1) trails.splice(idx, 1)
      if (path.parentNode) path.parentNode.removeChild(path)
    }, TRAIL_LIFETIME_MS + REMOVAL_BUFFER_MS),
  }
  trails.push(entry)
}

function clearAll(): void {
  trails.forEach((e) => clearTimeout(e.removalHandle))
  trails.length = 0
  if (svgRef.value) {
    while (svgRef.value.firstChild) {
      svgRef.value.removeChild(svgRef.value.firstChild)
    }
  }
}

onMounted(() => {
  if (typeof window !== 'undefined') {
    window.addEventListener('resize', onResize)
  }
})

onBeforeUnmount(() => {
  if (typeof window !== 'undefined') {
    window.removeEventListener('resize', onResize)
  }
  clearAll()
})

defineExpose({ addPath, clearAll })
</script>

<style scoped>
.trail-overlay {
  position: fixed;
  inset: 0;
  width: 100vw;
  height: 100vh;
  pointer-events: none;
  z-index: 998;
  overflow: visible;
}

.trail-overlay :deep(.trail-segment) {
  fill: none;
  stroke: var(--color-brand-ochre);
  stroke-width: 1.5;
  stroke-dasharray: 4 4;
  stroke-linecap: round;
  opacity: 0.4;
  animation: trail-fade 1.5s linear forwards;
}

@keyframes trail-fade {
  from {
    opacity: 0.4;
  }
  to {
    opacity: 0;
  }
}
</style>
