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
  amplitude: number    // initial wave amplitude
  frequency: number    // angular frequency (waves around circle)
  speed: number        // expansion speed (px per second)
  color: string        // neon stroke color
  glowColor: string    // neon glow/shadow color
  lineWidth: number
  noiseSeed: number    // unique seed for irregularity
}

// Configuration
const MAX_RIPPLES = LOW_END ? 5 : 8
const WAVE_LIFETIME = 3200  // ms for a wave to fully expand and fade

// Neon cyberpunk palette: [strokeColor, glowColor]
const NEON_COLORS: Array<[string, string]> = [
  ['#00d4ff', 'rgba(0,212,255,0.6)'],    // cyan
  ['#b967ff', 'rgba(185,103,255,0.6)'],  // violet
  ['#ff2a6d', 'rgba(255,42,109,0.6)'],   // hot pink
  ['#05ffa1', 'rgba(5,255,161,0.6)'],    // mint green
]

const LAYER_CONFIGS = [
  { amplitude: 14, frequency: 6,  speed: 38,  lineWidth: 2.5 },
  { amplitude: 11, frequency: 8,  speed: 50,  lineWidth: 2.0 },
  { amplitude: 8,  frequency: 10, speed: 62,  lineWidth: 1.4 },
  { amplitude: 6,  frequency: 13, speed: 76,  lineWidth: 0.9 },
]

// Breathing rhythm: spawn interval pulses between fast and slow
function spawnInterval(globalTime: number): number {
  const base = LOW_END ? 550 : 360
  const pulse = Math.sin(globalTime * 0.8) * (LOW_END ? 80 : 120)
  return base + pulse
}

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
let dismissStart: number | null = null

// ── Draw ──────────────────────────────────────────────────────────────────────

function drawFrame(canvas: HTMLCanvasElement, ctx: CanvasRenderingContext2D, now: number) {
  const W = canvas.width
  const H = canvas.height
  const cx = W / 2
  const cy = H / 2

  ctx.clearRect(0, 0, W, H)

  // Update dismiss progress
  if (props.dismissing) {
    if (dismissStart === null) dismissStart = now
    dismissProgress = Math.min(1, (now - dismissStart) / 400)
  } else {
    dismissStart = null
    dismissProgress = 0
  }

  const deltaTime = (now - lastFrameTime) / 1000 // seconds
  globalTime += deltaTime

  // Spawn new ripples
  if (!props.dismissing && now - lastSpawn > spawnInterval(globalTime)) {
    const configIdx = nextRippleId % LAYER_CONFIGS.length
    const config = LAYER_CONFIGS[configIdx]
    const [color, glowColor] = NEON_COLORS[nextRippleId % NEON_COLORS.length]
    ripples.push({
      id: nextRippleId++,
      birth: now,
      baseRadius: 20 * DPR,  // start from center
      amplitude: config.amplitude * DPR,
      frequency: config.frequency,
      speed: config.speed * DPR,
      color,
      glowColor,
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

  ripples.forEach((ripple) => {
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

    const alpha = lifeAlpha * dismissAlpha * 0.9

    // Amplitude decays as ripple expands
    const expansionDecay = Math.max(0.3, 1 - lifeProgress * 0.7)
    const currentAmp = ripple.amplitude * expansionDecay * (props.dismissing ? (1 - dismissProgress) : 1)

    // Dynamic noise for irregular movement
    const noiseTime = globalTime * 1.5 + ripple.noiseSeed
    const radiusNoise = fractalNoise(noiseTime * 0.7, 3) * 8 * DPR * (1 - lifeProgress * 0.5)
    const angleNoise = fractalNoise(noiseTime * 0.5 + 100, 3) * 0.3

    // Line thins as it expands (inner=thick, outer=thin)
    const currentLineWidth = ripple.lineWidth * Math.max(0.3, 1 - lifeProgress * 0.65)

    // Build the path points once, reuse for glow + core passes
    const pts: Array<[number, number]> = []
    for (let i = 0; i <= POINTS; i++) {
      const angle = (i / POINTS) * Math.PI * 2 + angleNoise
      const wavePhase = age * 3 + ripple.noiseSeed * 0.1
      const waveNoise = fractalNoise(angle * ripple.frequency / (2 * Math.PI) + wavePhase, 2)
      const waveOffset = currentAmp * Math.sin(angle * ripple.frequency + wavePhase) * (0.5 + waveNoise * 0.5)
      const r = currentRadius + radiusNoise + waveOffset
      pts.push([cx + r * Math.cos(angle), cy + r * Math.sin(angle)])
    }

    function tracePath() {
      ctx.beginPath()
      ctx.moveTo(pts[0][0], pts[0][1])
      for (let i = 1; i < pts.length; i++) ctx.lineTo(pts[i][0], pts[i][1])
      ctx.closePath()
    }

    // Radial gradient: bright at center, dims toward canvas edge
    const grad = ctx.createRadialGradient(cx, cy, 0, cx, cy, Math.min(W, H) * 0.5)
    grad.addColorStop(0, ripple.color)
    grad.addColorStop(0.65, ripple.color)
    grad.addColorStop(1, ripple.glowColor.replace('0.6)', '0.0)'))

    // Pass 1: wide glow halo (blurred, low opacity)
    if (!LOW_END) {
      ctx.save()
      ctx.globalAlpha = alpha * 0.45
      ctx.shadowBlur = 18 * DPR
      ctx.shadowColor = ripple.glowColor
      ctx.strokeStyle = grad
      ctx.lineWidth = currentLineWidth * 2.5
      tracePath()
      ctx.stroke()
      ctx.restore()
    }

    // Pass 2: sharp neon core line
    ctx.save()
    ctx.globalAlpha = alpha
    ctx.shadowBlur = LOW_END ? 0 : 8 * DPR
    ctx.shadowColor = ripple.glowColor
    ctx.strokeStyle = grad
    ctx.lineWidth = currentLineWidth
    tracePath()
    ctx.stroke()
    ctx.restore()
  })

  // Clean up expired ripples
  ripples = ripples.filter(r => {
    const lifeProgress = (now - r.birth) / 1000 / (WAVE_LIFETIME / 1000)
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
  // Reset animation state on each mount so remounts start clean (M1)
  lastFrameTime = 0
  globalTime = 0
  ripples = []
  lastSpawn = 0
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
    dismissStart = null
    ripples = []
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
