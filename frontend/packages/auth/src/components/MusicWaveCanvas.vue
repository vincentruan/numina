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

// ── Ripple wave definition ────────────────────────────────────────────────────

interface Ripple {
  id: number
  birth: number        // creation time (ms)
  baseRadius: number   // initial radius
  maxRadius: number    // maximum radius before fade
  amplitude: number    // initial wave amplitude
  frequency: number    // angular frequency (waves around circle)
  speed: number        // expansion speed (px per second)
  color: string
  lineWidth: number
  noiseSeed: number    // unique seed for irregularity
}

// Configuration
const MAX_RIPPLES = LOW_END ? 5 : 8
const SPAWN_INTERVAL = LOW_END ? 600 : 400  // ms between new ripples
const WAVE_LIFETIME = 3000  // ms for a wave to fully expand and fade

const LAYER_CONFIGS = [
  { amplitude: 12, frequency: 6,  speed: 40,  color: '#bdbbff', lineWidth: 2.0 },
  { amplitude: 10, frequency: 8,  speed: 50,  color: '#a78bfa', lineWidth: 1.6 },
  { amplitude: 8,  frequency: 10, speed: 60,  color: '#818cf8', lineWidth: 1.3 },
  { amplitude: 6,  frequency: 12, speed: 70,  color: '#c084fc', lineWidth: 1.0 },
]

// ── Lightweight pseudo-noise ─────────────────────────────────────────────────

function hash(n: number): number {
  const x = Math.sin(n * 12.9898) * 43758.5453
  return x - Math.floor(x)
}

function smoothNoise(t: number): number {
  const i = Math.floor(t)
  const f = t - i
  const u = f * f * (3 - 2 * f)
  return hash(i) * (1 - u) + hash(i + 1) * u
}

// Multi-octave noise for more organic irregularity
function fractalNoise(t: number, octaves: number = 3): number {
  let val = 0
  let amp = 1
  let freq = 1
  for (let o = 0; o < octaves; o++) {
    val += smoothNoise(t * freq) * amp
    amp *= 0.5
    freq *= 2
  }
  return val / (2 - Math.pow(0.5, octaves)) // normalize to ~[0,1]
}

// ── Animation state ───────────────────────────────────────────────────────────

let rafId = 0
let lastFrameTime = 0
let ripples: Ripple[] = []
let nextRippleId = 0
let lastSpawn = 0
let globalTime = 0

// Dismiss state
let dismissProgress = 0
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
    dismissProgress = Math.min(1, (now - dismissStart) / 400)
  } else {
    dismissStart = 0
    dismissProgress = 0
  }

  const deltaTime = (now - lastFrameTime) / 1000 // seconds
  globalTime += deltaTime

  // Spawn new ripples
  if (!props.dismissing && now - lastSpawn > SPAWN_INTERVAL) {
    const config = LAYER_CONFIGS[nextRippleId % LAYER_CONFIGS.length]
    ripples.push({
      id: nextRippleId++,
      birth: now,
      baseRadius: 20 * DPR,  // start from center
      maxRadius: Math.min(W, H) * 0.45,
      amplitude: config.amplitude * DPR,
      frequency: config.frequency,
      speed: config.speed * DPR,
      color: config.color,
      lineWidth: config.lineWidth * DPR,
      noiseSeed: Math.random() * 1000,
    })
    lastSpawn = now

    // Remove oldest if too many
    if (ripples.length > MAX_RIPPLES) {
      ripples.shift()
    }
  }

  // Update and draw each ripple
  const POINTS = LOW_END ? 60 : 90

  ripples.forEach((ripple, index) => {
    const age = (now - ripple.birth) / 1000 // seconds
    const lifeProgress = age / (WAVE_LIFETIME / 1000)

    // Remove expired ripples
    if (lifeProgress >= 1 || (props.dismissing && dismissProgress > 0.8)) {
      return
    }

    // Calculate current radius (expands outward)
    const currentRadius = ripple.baseRadius + ripple.speed * age

    // Life-based fade: starts at 0, peaks at ~20%, fades to 0 at 100%
    let lifeAlpha: number
    if (lifeProgress < 0.15) {
      // Fade in (0 → 1)
      lifeAlpha = lifeProgress / 0.15
    } else if (lifeProgress > 0.6) {
      // Fade out (1 → 0)
      lifeAlpha = 1 - (lifeProgress - 0.6) / 0.4
    } else {
      lifeAlpha = 1
    }

    // Dismiss fade
    const dismissAlpha = props.dismissing ? Math.max(0, 1 - dismissProgress * 1.5) : 1

    const alpha = lifeAlpha * dismissAlpha * 0.85

    // Amplitude decays as ripple expands
    const expansionDecay = Math.max(0.3, 1 - lifeProgress * 0.7)
    const currentAmp = ripple.amplitude * expansionDecay * (props.dismissing ? (1 - dismissProgress) : 1)

    // Dynamic noise for irregular movement
    const noiseTime = globalTime * 1.5 + ripple.noiseSeed
    const radiusNoise = fractalNoise(noiseTime * 0.7, 3) * 8 * DPR * (1 - lifeProgress * 0.5)
    const angleNoise = fractalNoise(noiseTime * 0.5 + 100, 3) * 0.3

    ctx.beginPath()
    ctx.strokeStyle = ripple.color
    ctx.globalAlpha = alpha
    ctx.lineWidth = ripple.lineWidth * (1 - lifeProgress * 0.5) // line gets thinner

    for (let i = 0; i <= POINTS; i++) {
      const angle = (i / POINTS) * Math.PI * 2 + angleNoise

      // Wave perturbation along the circumference (creates the wavy edge)
      const wavePhase = age * 3 + ripple.noiseSeed * 0.1
      const waveNoise = fractalNoise(angle * ripple.frequency / (2 * Math.PI) + wavePhase, 2)
      const waveOffset = currentAmp * Math.sin(angle * ripple.frequency + wavePhase) * (0.5 + waveNoise * 0.5)

      // Radius varies with noise + wave
      const r = currentRadius + radiusNoise + waveOffset

      const x = cx + r * Math.cos(angle)
      const y = cy + r * Math.sin(angle)

      if (i === 0) {
        ctx.moveTo(x, y)
      } else {
        ctx.lineTo(x, y)
      }
    }

    ctx.closePath()
    ctx.stroke()
  })

  ctx.globalAlpha = 1

  // Clean up expired ripples
  ripples = ripples.filter(r => {
    const lifeProgress = (now - r.birth) / WAVE_LIFETIME
    return lifeProgress < 1 && !(props.dismissing && dismissProgress > 0.8)
  })
}

// ── RAF loop ──────────────────────────────────────────────────────────────────

function loop(now: number) {
  rafId = requestAnimationFrame(loop)

  if (now - lastFrameTime < FRAME_INTERVAL) return

  const canvas = canvasEl.value
  if (!canvas) return
  const ctx = canvas.getContext('2d')
  if (!ctx) return

  drawFrame(canvas, ctx, now)
  lastFrameTime = now
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

watch(() => props.dismissing, (val) => {
  if (!val) {
    dismissProgress = 0
    dismissStart = 0
    ripples = [] // Clear ripples on reset
    lastSpawn = 0
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
