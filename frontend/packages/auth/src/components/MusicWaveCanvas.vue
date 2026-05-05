<template>
  <canvas ref="canvasEl" class="wave-canvas" aria-hidden="true" />
</template>

<script setup lang="ts">
import { ref, onMounted, onUnmounted, watch } from 'vue'

const props = defineProps<{ dismissing: boolean }>()

const canvasEl = ref<HTMLCanvasElement | null>(null)

// ── Device capability detection ───────────────────────────────────────────────

function isLowEnd(): boolean {
  const nav = navigator as Navigator & { hardwareConcurrency?: number; deviceMemory?: number }
  const cores = nav.hardwareConcurrency ?? 4
  const mem = nav.deviceMemory ?? 4
  return cores <= 2 || mem <= 2
}

const LOW_END = isLowEnd()
const DPR = Math.min(window.devicePixelRatio || 1, 2)
const TARGET_FPS = LOW_END ? 30 : 60
const FRAME_INTERVAL = 1000 / TARGET_FPS

// ── Wave layer definitions ────────────────────────────────────────────────────

interface WaveLayer {
  amplitude: number      // base amplitude in px
  frequency: number      // angular frequency (radians per unit arc)
  phase: number          // initial phase offset
  speed: number          // phase advance per frame
  color: string
  lineWidth: number
  noiseScale: number     // how much pseudo-noise perturbs the amplitude
  noiseSpeed: number     // how fast the noise evolves
}

const LAYERS: WaveLayer[] = LOW_END
  ? [
      { amplitude: 18, frequency: 5.5, phase: 0,    speed: 0.028, color: '#bdbbff', lineWidth: 1.5, noiseScale: 0.35, noiseSpeed: 0.018 },
      { amplitude: 12, frequency: 8,   phase: 1.2,  speed: 0.022, color: '#a78bfa', lineWidth: 1.2, noiseScale: 0.5,  noiseSpeed: 0.024 },
      { amplitude: 8,  frequency: 11,  phase: 2.5,  speed: 0.035, color: '#818cf8', lineWidth: 1.0, noiseScale: 0.6,  noiseSpeed: 0.030 },
    ]
  : [
      { amplitude: 22, frequency: 5,   phase: 0,    speed: 0.025, color: '#bdbbff', lineWidth: 1.8, noiseScale: 0.30, noiseSpeed: 0.015 },
      { amplitude: 16, frequency: 7.5, phase: 1.1,  speed: 0.020, color: '#a78bfa', lineWidth: 1.5, noiseScale: 0.45, noiseSpeed: 0.022 },
      { amplitude: 11, frequency: 10,  phase: 2.3,  speed: 0.032, color: '#818cf8', lineWidth: 1.2, noiseScale: 0.55, noiseSpeed: 0.028 },
      { amplitude: 7,  frequency: 14,  phase: 3.7,  speed: 0.040, color: '#c084fc', lineWidth: 1.0, noiseScale: 0.65, noiseSpeed: 0.035 },
    ]

// ── Lightweight pseudo-noise (value noise, no deps) ───────────────────────────

function hash(n: number): number {
  // Simple integer hash → [0,1)
  const x = Math.sin(n) * 43758.5453123
  return x - Math.floor(x)
}

function smoothNoise(t: number): number {
  const i = Math.floor(t)
  const f = t - i
  const u = f * f * (3 - 2 * f) // smoothstep
  return hash(i) * (1 - u) + hash(i + 1) * u
}

// ── Animation state ───────────────────────────────────────────────────────────

let rafId = 0
let lastFrameTime = 0
let time = 0

// Per-layer noise offsets (evolve independently)
const noiseOffsets = LAYERS.map((_, i) => i * 17.3)

// Dismiss state: expand radius + fade
let dismissProgress = 0   // 0 → 1 over ~500ms
let dismissStart = 0

// ── Draw ──────────────────────────────────────────────────────────────────────

function drawFrame(canvas: HTMLCanvasElement, ctx: CanvasRenderingContext2D, now: number) {
  const W = canvas.width
  const H = canvas.height
  const cx = W / 2
  const cy = H / 2

  ctx.clearRect(0, 0, W, H)

  // Update dismiss progress
  if (props.dismissing) {
    if (dismissStart === 0) dismissStart = now
    dismissProgress = Math.min(1, (now - dismissStart) / 500)
  } else {
    dismissStart = 0
    dismissProgress = 0
  }

  const baseRadius = Math.min(W, H) * 0.28
  const POINTS = LOW_END ? 80 : 120

  LAYERS.forEach((layer, li) => {
    // Evolve noise offset
    noiseOffsets[li] += layer.noiseSpeed

    // Dynamic amplitude: base * (1 + noise perturbation) * dismiss decay
    const noiseVal = smoothNoise(noiseOffsets[li])  // [0,1]
    const noiseMod = 1 + (noiseVal - 0.5) * 2 * layer.noiseScale
    const dismissDecay = props.dismissing ? Math.max(0, 1 - dismissProgress * 1.4) : 1
    const amp = layer.amplitude * noiseMod * dismissDecay * DPR

    // Radius expands outward during dismiss
    const radiusBoost = props.dismissing ? dismissProgress * baseRadius * 0.6 : 0
    const r = (baseRadius + li * 18 * DPR) + radiusBoost * DPR

    // Opacity fades during dismiss
    const alpha = props.dismissing
      ? Math.max(0, 1 - dismissProgress * 1.2)
      : 0.75 + noiseVal * 0.25

    ctx.beginPath()
    ctx.strokeStyle = layer.color
    ctx.globalAlpha = alpha
    ctx.lineWidth = layer.lineWidth * DPR

    for (let i = 0; i <= POINTS; i++) {
      const angle = (i / POINTS) * Math.PI * 2
      // sin wave along the arc + phase + time
      const waveOffset = amp * Math.sin(angle * layer.frequency + layer.phase + time * layer.speed * 60)
      const pr = r + waveOffset
      const x = cx + pr * Math.cos(angle)
      const y = cy + pr * Math.sin(angle)
      if (i === 0) ctx.moveTo(x, y)
      else ctx.lineTo(x, y)
    }

    ctx.closePath()
    ctx.stroke()
    ctx.globalAlpha = 1
  })
}

// ── RAF loop ──────────────────────────────────────────────────────────────────

function loop(now: number) {
  rafId = requestAnimationFrame(loop)

  if (now - lastFrameTime < FRAME_INTERVAL) return
  lastFrameTime = now
  time += 1 / TARGET_FPS

  const canvas = canvasEl.value
  if (!canvas) return
  const ctx = canvas.getContext('2d')
  if (!ctx) return

  drawFrame(canvas, ctx, now)
}

// ── Resize ────────────────────────────────────────────────────────────────────

function resize() {
  const canvas = canvasEl.value
  if (!canvas) return
  const parent = canvas.parentElement
  if (!parent) return
  canvas.width = parent.clientWidth * DPR
  canvas.height = parent.clientHeight * DPR
}

// ── Lifecycle ─────────────────────────────────────────────────────────────────

let ro: ResizeObserver | null = null

onMounted(() => {
  resize()
  ro = new ResizeObserver(resize)
  if (canvasEl.value?.parentElement) ro.observe(canvasEl.value.parentElement)
  rafId = requestAnimationFrame(loop)
})

onUnmounted(() => {
  cancelAnimationFrame(rafId)
  ro?.disconnect()
})

// Stop RAF when dismiss animation completes (dismissProgress reaches 1)
watch(() => props.dismissing, (val) => {
  if (!val) {
    dismissProgress = 0
    dismissStart = 0
  }
})
</script>

<style scoped>
.wave-canvas {
  position: absolute;
  inset: 0;
  width: 100%;
  height: 100%;
  pointer-events: none;
}
</style>
