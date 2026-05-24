<template>
  <Teleport to="body">
    <div
      v-if="active"
      class="fly-overlay"
      aria-hidden="true"
      :data-particle-type="particleType"
    >
      <span
        v-for="i in particleCount"
        :key="i"
        :ref="(el) => setParticleRef(i - 1, el as HTMLElement | null)"
        class="particle"
        :class="cssFilter ? 'with-filter' : null"
      >
        <slot name="particle" :index="i - 1">
          <span v-if="particleType === 'star'" class="glyph">⭐</span>
          <span v-else-if="particleType === 'coin'" class="glyph">🪙</span>
          <span v-else-if="particleType === 'sparkle'" class="glyph">✨</span>
          <span v-else class="glyph">🔥</span>
        </slot>
      </span>
    </div>
  </Teleport>
</template>

<script setup lang="ts">
import { onUnmounted, watch, nextTick } from 'vue'
import { quadraticBezier, bezierControl, type Point } from '@/utils/bezier'

type Resolvable = Point | HTMLElement | string | null | undefined

const props = withDefaults(
  defineProps<{
    active: boolean
    origin: Resolvable | Resolvable[]
    target: Resolvable
    particleCount?: number
    particleType?: 'star' | 'coin' | 'sparkle' | 'flame'
    duration?: number
    staggerMs?: number
    controlPointOffset?: number
    rotationDeg?: number
    scaleCurve?: [number, number, number]
    cssFilter?: string
  }>(),
  {
    particleCount: 8,
    particleType: 'star',
    duration: 800,
    staggerMs: 120,
    controlPointOffset: 200,
    rotationDeg: 720,
    scaleCurve: () => [0.5, 1.2, 0.8],
    cssFilter: undefined,
  },
)

const emit = defineEmits<{
  landingPerParticle: [index: number]
  allLanded: []
}>()

const particleEls: Array<HTMLElement | null> = []
function setParticleRef(idx: number, el: HTMLElement | null): void {
  particleEls[idx] = el
}

function resolveToPoint(input: Resolvable): Point | null {
  if (input == null) return null
  if (typeof input === 'string') {
    const el = document.querySelector(input) as HTMLElement | null
    if (!el) return null
    const r = el.getBoundingClientRect()
    return { x: r.left + r.width / 2, y: r.top + r.height / 2 }
  }
  if (input instanceof HTMLElement) {
    const r = input.getBoundingClientRect()
    return { x: r.left + r.width / 2, y: r.top + r.height / 2 }
  }
  return input
}

let rafId: number | null = null
let landedFlags: boolean[] = []
let launchAt = 0

function scaleAt(t: number): number {
  const [s, p, e] = props.scaleCurve
  if (t < 0.6) return s + ((p - s) * t) / 0.6
  return p + ((e - p) * (t - 0.6)) / 0.4
}

function startAnimation(): void {
  cancelRaf()
  landedFlags = new Array(props.particleCount).fill(false)

  const targetPt = resolveToPoint(props.target)
  if (!targetPt) {
    emit('allLanded')
    return
  }

  const origins: Array<Point | null> = []
  if (Array.isArray(props.origin)) {
    for (let i = 0; i < props.particleCount; i++) {
      const src = props.origin[i % props.origin.length]
      origins.push(resolveToPoint(src))
    }
  } else {
    const single = resolveToPoint(props.origin)
    for (let i = 0; i < props.particleCount; i++) origins.push(single)
  }

  launchAt = performance.now()

  const tick = (now: number) => {
    let allDone = true
    for (let i = 0; i < props.particleCount; i++) {
      const el = particleEls[i]
      const origin = origins[i]
      if (!el) continue
      if (!origin) {
        if (!landedFlags[i]) {
          landedFlags[i] = true
          emit('landingPerParticle', i)
        }
        continue
      }
      const elapsed = now - launchAt - i * props.staggerMs
      if (elapsed < 0) {
        el.style.opacity = '0'
        allDone = false
        continue
      }
      const rawT = elapsed / props.duration
      const t = Math.max(0, Math.min(1, rawT))
      const eased = 1 - Math.pow(1 - t, 3)
      const ctrl = bezierControl(origin, targetPt, props.controlPointOffset)
      const pt = quadraticBezier(origin, ctrl, targetPt, eased)
      const scale = scaleAt(eased)
      const rotate = props.rotationDeg * eased
      el.style.opacity = '1'
      el.style.transform = `translate3d(${pt.x}px, ${pt.y}px, 0) translate(-50%, -50%) rotate(${rotate}deg) scale(${scale})`
      if (props.cssFilter) el.style.filter = props.cssFilter
      if (t >= 1 && !landedFlags[i]) {
        landedFlags[i] = true
        emit('landingPerParticle', i)
        el.style.opacity = '0'
      }
      if (t < 1) allDone = false
    }
    if (allDone) {
      rafId = null
      emit('allLanded')
      return
    }
    rafId = requestAnimationFrame(tick)
  }
  rafId = requestAnimationFrame(tick)
}

function cancelRaf(): void {
  if (rafId !== null) {
    cancelAnimationFrame(rafId)
    rafId = null
  }
}

watch(
  () => props.active,
  async (v) => {
    if (v) {
      await nextTick()
      startAnimation()
    } else {
      cancelRaf()
    }
  },
  { immediate: false },
)

onUnmounted(cancelRaf)
</script>

<style scoped>
.fly-overlay {
  position: fixed;
  inset: 0;
  pointer-events: none;
  z-index: 999;
  overflow: visible;
}
.particle {
  position: absolute;
  left: 0;
  top: 0;
  opacity: 0;
  will-change: transform, opacity;
  pointer-events: none;
  font-size: 28px;
  line-height: 1;
}
.particle.with-filter {
  filter: drop-shadow(0 0 6px var(--color-brand-ochre));
}
.particle .glyph {
  display: inline-block;
}
[data-particle-type='sparkle'] .particle {
  font-size: 18px;
}
[data-particle-type='flame'] .particle {
  font-size: 22px;
}
</style>
