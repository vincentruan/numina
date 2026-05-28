<template>
  <canvas ref="canvasEl" class="wave-canvas" aria-hidden="true" />
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted, watch } from 'vue'

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

// ── Theme detection ─────────────────────────────────────────────────────────────

const isDark = ref(document.documentElement.dataset.theme === 'dark')
const themeObserver = new MutationObserver(() => {
  isDark.value = document.documentElement.dataset.theme === 'dark'
})

// ── Reduced-motion detection ───────────────────────────────────────────────────

const reduceQuery = window.matchMedia('(prefers-reduced-motion: reduce)')
const prefersReduced = ref(reduceQuery.matches)
const onMotionChange = (e: MediaQueryListEvent) => { prefersReduced.value = e.matches }

// ── TikTok 2-color palette ────────────────────────────────────────────────────

const PALETTE = {
  dark: {
    cyan: '#00f2fe', cyanGlow: 'rgba(0,242,254,0.55)',
    red:  '#fe0979', redGlow:  'rgba(254,9,121,0.55)',
    blend: 'screen' as GlobalCompositeOperation,
  },
  light: {
    cyan: '#00b8c8', cyanGlow: 'rgba(0,184,200,0.30)',
    red:  '#d61b6e', redGlow:  'rgba(214,27,110,0.30)',
    blend: 'multiply' as GlobalCompositeOperation,
  },
} as const

const p = computed(() => isDark.value ? PALETTE.dark : PALETTE.light)

// ── Polar curve parameters ────────────────────────────────────────────────────

interface LineParams {
  basePhase: number
  rotSpeed: number   // rad/s, negative = counter-clockwise
  n1: number         // primary radial harmonic count
  n2: number         // secondary radial harmonic count
  n3: number         // slow wobble harmonic count
  amp1: number       // primary amplitude (relative to R)
  amp2: number       // secondary amplitude
  amp3: number       // wobble amplitude
  drift1: number     // phase drift speed for harmonic 1
  drift2: number     // phase drift speed for harmonic 2
  drift3: number     // phase drift speed for harmonic 3
  baseR: number      // base radius scale (relative to R)
}

const LINE_COUNT_HIGH = 9
const LINE_COUNT_LOW  = 5
const STEPS_HIGH = 200
const STEPS_LOW  = 120
const DISMISS_DURATION = 300

function makeLineParams(index: number, total: number): LineParams {
  const basePhase = (index / total) * Math.PI * 2
  const rotDir = (index % 2 === 0) ? 1 : -1
  const rotSpeed = (0.18 + index * 0.04) * rotDir

  return {
    basePhase,
    rotSpeed,
    n1: 2 + (index % 4),
    n2: 3 + (index % 3),
    n3: 1,
    amp1: 0.22 + (index % 3) * 0.07,
    amp2: 0.12 + (index % 2) * 0.06,
    amp3: 0.08,
    drift1: 0.29 + index * 0.05,
    drift2: 0.17 + index * 0.08,
    drift3: 0.11 + index * 0.03,
    baseR:  0.55 + (index % 5) * 0.06,
  }
}

// ── Draw a single polar rotating curve ───────────────────────────────────────

function drawPolarCurve(
  ctx: CanvasRenderingContext2D,
  cx: number,
  cy: number,
  R: number,
  params: LineParams,
  t: number,
  alpha: number,
  lineWidth: number,
  palette: { color: string; glowColor: string; blend: GlobalCompositeOperation },
  skipGlow: boolean,
): void {
  const { rotSpeed, basePhase, n1, n2, n3, amp1, amp2, amp3, drift1, drift2, drift3, baseR } = params
  const rotation = t * rotSpeed + basePhase
  const STEPS = LOW_END ? STEPS_LOW : STEPS_HIGH

  const pts: Array<[number, number]> = []
  for (let i = 0; i <= STEPS; i++) {
    const theta = (i / STEPS) * Math.PI * 2
    const r = R * (
      baseR
      + amp1 * Math.sin(n1 * theta + t * drift1)
      + amp2 * Math.sin(n2 * theta - t * drift2 + 1.3)
      + amp3 * Math.cos(n3 * theta + t * drift3)
    )
    const angle = theta + rotation
    pts.push([cx + r * Math.cos(angle), cy + r * Math.sin(angle)])
  }

  ctx.save()
  ctx.globalCompositeOperation = palette.blend
  ctx.globalAlpha = alpha

  ctx.beginPath()
  const first = pts[0]!
  ctx.moveTo(first[0], first[1])
  for (let i = 1; i < pts.length; i++) ctx.lineTo(pts[i]![0], pts[i]![1])
  ctx.closePath()

  if (!skipGlow) {
    ctx.shadowBlur = lineWidth * 10
    ctx.shadowColor = palette.glowColor
    ctx.strokeStyle = palette.color
    ctx.lineWidth = lineWidth * 2.0
    ctx.stroke()
  }

  ctx.shadowBlur = 0
  ctx.strokeStyle = palette.color
  ctx.lineWidth = lineWidth * 0.8
  ctx.stroke()

  ctx.restore()
}

// ── Animation state ───────────────────────────────────────────────────────────

const lineCount = LOW_END ? LINE_COUNT_LOW : LINE_COUNT_HIGH

const state = {
  lines: [] as LineParams[],
  globalTime: 0,
  lastFrameTime: 0,
  dismissProgress: 0,
  dismissStart: null as number | null,
}

// ── Draw frame ────────────────────────────────────────────────────────────────

function drawFrame(canvas: HTMLCanvasElement, ctx: CanvasRenderingContext2D, now: number): void {
  const W = canvas.width
  const H = canvas.height
  const cx = W / 2
  const cy = H / 2
  const unit = Math.min(W, H)
  const framePalette = p.value

  const effectiveInterval = prefersReduced.value ? 100 : FRAME_INTERVAL
  if (now - state.lastFrameTime < effectiveInterval) return

  ctx.clearRect(0, 0, W, H)

  if (props.dismissing) {
    if (state.dismissStart === null) state.dismissStart = now
    state.dismissProgress = Math.min(1, (now - state.dismissStart) / DISMISS_DURATION)
  } else {
    state.dismissStart = null
    state.dismissProgress = 0
  }

  const deltaTime = state.lastFrameTime === 0 ? 0 : (now - state.lastFrameTime) / 1000
  state.globalTime += deltaTime
  state.lastFrameTime = now

  const t = state.globalTime

  const dismissScale = props.dismissing
    ? 1 - state.dismissProgress * 0.5 * (prefersReduced.value ? 0 : 1)
    : 1
  const dismissAlpha = props.dismissing
    ? Math.max(0, 1 - state.dismissProgress * 1.3)
    : 1

  const R = unit * 0.44
  const clipR = unit * 0.46
  const lineWidth = unit * 0.007

  ctx.save()
  ctx.beginPath()
  ctx.arc(cx, cy, clipR, 0, Math.PI * 2)
  ctx.clip()

  ctx.save()
  ctx.translate(cx, cy)
  ctx.scale(dismissScale, dismissScale)
  ctx.translate(-cx, -cy)

  const skipGlow = LOW_END

  for (let i = 0; i < state.lines.length; i++) {
    const params = state.lines[i]!
    const isCyan = i % 2 === 0
    const palette = {
      color:     isCyan ? framePalette.cyan     : framePalette.red,
      glowColor: isCyan ? framePalette.cyanGlow : framePalette.redGlow,
      blend:     framePalette.blend,
    }

    const breathPhase = prefersReduced.value
      ? 0
      : t * 0.8 + (i / state.lines.length) * Math.PI * 2
    const breathAlpha = prefersReduced.value
      ? 0.6
      : 0.55 + Math.sin(breathPhase) * 0.2

    const rotSpeedFactor = prefersReduced.value ? 0.15 : 1

    drawPolarCurve(
      ctx, cx, cy, R,
      { ...params, rotSpeed: params.rotSpeed * rotSpeedFactor },
      t,
      breathAlpha * dismissAlpha,
      lineWidth,
      palette,
      skipGlow,
    )
  }

  ctx.restore()
  ctx.restore()
}

// ── Resize ────────────────────────────────────────────────────────────────────

function resize(canvas: HTMLCanvasElement) {
  const parent = canvas.parentElement
  if (!parent) return
  const w = parent.clientWidth * DPR
  const h = parent.clientHeight * DPR
  if (w === 0 || h === 0) return
  canvas.width = w
  canvas.height = h
}

// ── Lifecycle ─────────────────────────────────────────────────────────────────

let ro: ResizeObserver | null = null
const rafBox = { id: 0 }

function loop(now: number) {
  rafBox.id = requestAnimationFrame(loop)
  const canvas = canvasEl.value
  if (!canvas) return
  const ctx = canvas.getContext('2d')
  if (!ctx) return
  drawFrame(canvas, ctx, now)
}

onMounted(() => {
  const canvas = canvasEl.value
  if (!canvas) return

  state.lines = Array.from({ length: lineCount }, (_, i) => makeLineParams(i, lineCount))
  state.globalTime = 0
  state.lastFrameTime = 0
  state.dismissProgress = 0
  state.dismissStart = null

  resize(canvas)
  ro = new ResizeObserver(() => resize(canvas))
  ro.observe(canvas.parentElement ?? canvas)
  rafBox.id = requestAnimationFrame(loop)
  themeObserver.observe(document.documentElement, {
    attributes: true,
    attributeFilter: ['data-theme'],
  })
  reduceQuery.addEventListener('change', onMotionChange)
})

onUnmounted(() => {
  cancelAnimationFrame(rafBox.id)
  ro?.disconnect()
  ro = null
  themeObserver.disconnect()
  reduceQuery.removeEventListener('change', onMotionChange)
})

watch(() => props.dismissing, (val) => {
  if (!val) {
    state.dismissProgress = 0
    state.dismissStart = null
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
