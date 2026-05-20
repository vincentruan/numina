import { onMounted, onUnmounted, type Ref } from 'vue'

// Two-layer background system:
//   bgCanvas  — DeerFlow-style glow blobs (large drifting aurora/nebula effect)
//   deerCanvas — dim lavender pixel grid masked to deer SVG silhouette

// ── Deer pixel grid constants ──────────────────────────────────────────────
const CELL_SIZE = 4
const CELL_GAP = 1
const MAX_ALPHA = 0.45
const FLICKER_RATE = 0.06

// ── Glow blob constants (DeerFlow-style) ───────────────────────────────────
// Large drifting blobs with breathing animation (aurora/nebula effect)
// Blobs combine slow drift + sinusoidal size/opacity pulse
const BLOB_COUNT_BASE = 5
const REFERENCE_AREA = 2_073_600  // 1080×1920

// Size range (large blobs for aurora feel)
const BLOB_RADIUS_MIN = 80
const BLOB_RADIUS_MAX = 150

// Drift speed (px/s) — slow ambient movement
const DRIFT_SPEED_MIN = 5
const DRIFT_SPEED_MAX = 15

// Breathing cycle: 2-4 seconds per full breath
const BREATH_SPEED_MIN = 0.25  // 4s cycle
const BREATH_SPEED_MAX = 0.5   // 2s cycle

// Breathing amplitude: size expansion and opacity boost at peak
const BREATH_SIZE_AMPLITUDE_MIN = 0.2
const BREATH_SIZE_AMPLITUDE_MAX = 0.4
const BREATH_OPACITY_AMPLITUDE_MIN = 0.3
const BREATH_OPACITY_AMPLITUDE_MAX = 0.5

// Base opacity at rest (breathing increases at peak)
const BLOB_OPACITY_MIN = 0.35
const BLOB_OPACITY_MAX = 0.55

// Wander: gradual direction changes
const WANDER_INTERVAL_MIN = 2.0
const WANDER_INTERVAL_MAX = 5.5
const WANDER_ANGLE_MAX = Math.PI * 0.65

// Color palette: cyan/teal variations (DeerFlow aesthetic)
const BLOB_COLORS = [
  [0, 220, 255],    // primary cyan
  [50, 255, 220],   // teal
  [100, 255, 255],  // light cyan
]

interface Grid {
  cols: number
  rows: number
  alphas: Float32Array
  dpr: number
}

interface GlowBlob {
  x: number
  y: number
  baseRadius: number      // 80-150px
  currentRadius: number   // breathing-modulated
  breathPhase: number     // 0..1 (cycle progress)
  breathSpeed: number     // cycles/s (0.25-0.5)
  breathSizeAmplitude: number   // 0.2-0.4
  breathOpacityAmplitude: number // 0.3-0.5
  baseOpacity: number     // 0.35-0.55
  vx: number              // drift velocity x
  vy: number              // drift velocity y
  wanderTimer: number     // countdown to next direction change
  wanderInterval: number  // 2-5.5s
  colorVariant: number    // index into BLOB_COLORS
}

function debounce<T extends (...args: unknown[]) => void>(fn: T, delay: number): T {
  let id: ReturnType<typeof setTimeout> | null = null
  return ((...args: unknown[]) => {
    if (id) clearTimeout(id)
    id = setTimeout(() => fn(...args), delay)
  }) as T
}

function rand(min: number, max: number) {
  return min + Math.random() * (max - min)
}

// ── Deer grid helpers ──────────────────────────────────────────────────────

function buildGrid(canvas: HTMLCanvasElement, w: number, h: number): Grid {
  const dpr = Math.min(window.devicePixelRatio || 1, 2)
  canvas.width = w * dpr
  canvas.height = h * dpr

  const step = CELL_SIZE + CELL_GAP
  const cols = Math.floor(w / step)
  const rows = Math.floor(h / step)
  const alphas = new Float32Array(cols * rows)
  for (let i = 0; i < alphas.length; i++) {
    alphas[i] = Math.random() * MAX_ALPHA
  }
  return { cols, rows, alphas, dpr }
}

function flickerGrid(alphas: Float32Array, dt: number) {
  const prob = FLICKER_RATE * dt
  for (let i = 0; i < alphas.length; i++) {
    if (Math.random() < prob) {
      alphas[i] = Math.random() * MAX_ALPHA
    }
  }
}

function drawGrid(ctx: CanvasRenderingContext2D, grid: Grid) {
  const { cols, rows, alphas, dpr } = grid
  const step = (CELL_SIZE + CELL_GAP) * dpr
  const size = CELL_SIZE * dpr

  ctx.clearRect(0, 0, ctx.canvas.width, ctx.canvas.height)

  for (let c = 0; c < cols; c++) {
    for (let r = 0; r < rows; r++) {
      const a = alphas[c * rows + r]
      if (a < 0.01) continue
      ctx.fillStyle = `rgba(189,187,255,${a})`
      ctx.fillRect(c * step, r * step, size, size)
    }
  }
}

function blobCount(w: number, h: number): number {
  const area = w * h
  const scale = area / REFERENCE_AREA
  const clamped = Math.max(0.5, Math.min(2.5, scale))
  return Math.max(3, Math.round(BLOB_COUNT_BASE * clamped))
}

function buildBlobs(w: number, h: number): GlowBlob[] {
  const blobs: GlowBlob[] = []
  const count = blobCount(w, h)

  for (let i = 0; i < count; i++) {
    const baseRadius = rand(BLOB_RADIUS_MIN, BLOB_RADIUS_MAX)
    const speed = rand(DRIFT_SPEED_MIN, DRIFT_SPEED_MAX)
    const angle = Math.random() * Math.PI * 2

    blobs.push({
      x: Math.random() * w,
      y: Math.random() * h,
      baseRadius,
      currentRadius: baseRadius,
      breathPhase: Math.random(), // staggered start
      breathSpeed: rand(BREATH_SPEED_MIN, BREATH_SPEED_MAX),
      breathSizeAmplitude: rand(BREATH_SIZE_AMPLITUDE_MIN, BREATH_SIZE_AMPLITUDE_MAX),
      breathOpacityAmplitude: rand(BREATH_OPACITY_AMPLITUDE_MIN, BREATH_OPACITY_AMPLITUDE_MAX),
      baseOpacity: rand(BLOB_OPACITY_MIN, BLOB_OPACITY_MAX),
      vx: Math.cos(angle) * speed,
      vy: Math.sin(angle) * speed,
      wanderTimer: Math.random() * WANDER_INTERVAL_MAX,
      wanderInterval: rand(WANDER_INTERVAL_MIN, WANDER_INTERVAL_MAX),
      colorVariant: Math.floor(Math.random() * BLOB_COLORS.length),
    })
  }
  return blobs
}

function updateBlobs(blobs: GlowBlob[], dt: number, w: number, h: number) {
  for (const b of blobs) {
    // Drift movement
    b.x += b.vx * dt
    b.y += b.vy * dt

    // Wrap edges smoothly
    const margin = b.currentRadius * 1.5
    if (b.x < -margin) b.x = w + margin
    else if (b.x > w + margin) b.x = -margin
    if (b.y < -margin) b.y = h + margin
    else if (b.y > h + margin) b.y = -margin

    // Wander: gradual direction changes
    b.wanderTimer += dt
    if (b.wanderTimer >= b.wanderInterval) {
      b.wanderTimer = 0
      b.wanderInterval = rand(WANDER_INTERVAL_MIN, WANDER_INTERVAL_MAX)
      const speed = rand(DRIFT_SPEED_MIN, DRIFT_SPEED_MAX)
      const currentAngle = Math.atan2(b.vy, b.vx)
      const newAngle = currentAngle + rand(-WANDER_ANGLE_MAX, WANDER_ANGLE_MAX)
      b.vx = Math.cos(newAngle) * speed
      b.vy = Math.sin(newAngle) * speed
    }

    // Breathing: sinusoidal pulse for radius AND opacity
    b.breathPhase = (b.breathPhase + b.breathSpeed * dt) % 1
    const breathWave = (Math.sin(b.breathPhase * Math.PI * 2) + 1) / 2

    // Radius expands during peak
    b.currentRadius = b.baseRadius * (1 + b.breathSizeAmplitude * breathWave)
  }
}

function drawBlobs(ctx: CanvasRenderingContext2D, blobs: GlowBlob[], dpr: number) {
  ctx.clearRect(0, 0, ctx.canvas.width, ctx.canvas.height)

  for (const b of blobs) {
    const x = b.x * dpr
    const y = b.y * dpr
    const r = b.currentRadius * dpr

    // Breathing wave for opacity modulation
    const breathWave = (Math.sin(b.breathPhase * Math.PI * 2) + 1) / 2
    const opacity = b.baseOpacity * (1 + b.breathOpacityAmplitude * breathWave)

    // Select color variant
    const [cr, cg, cb] = BLOB_COLORS[b.colorVariant]

    // Radial gradient: bright center → soft edge → transparent
    const gradient = ctx.createRadialGradient(x, y, 0, x, y, r)
    gradient.addColorStop(0, `rgba(${cr},${cg},${cb},${opacity.toFixed(3)})`)
    gradient.addColorStop(0.35, `rgba(${cr},${cg},${cb},${(opacity * 0.4).toFixed(3)})`)
    gradient.addColorStop(0.7, `rgba(${cr},${cg},${cb},${(opacity * 0.15).toFixed(3)})`)
    gradient.addColorStop(1, `rgba(${cr},${cg},${cb},0)`)

    ctx.beginPath()
    ctx.arc(x, y, r, 0, Math.PI * 2)
    ctx.fillStyle = gradient
    ctx.fill()
  }
}

// ── Main composable ────────────────────────────────────────────────────────

export function useDeerField(
  bgCanvasRef: Ref<HTMLCanvasElement | null>,
  deerCanvasRef: Ref<HTMLCanvasElement | null>,
) {
  let rafId: number | null = null
  let bgCtx: CanvasRenderingContext2D | null = null
  let deerCtx: CanvasRenderingContext2D | null = null
  let grid: Grid | null = null
  let blobs: GlowBlob[] = []
  let bgDpr = 1
  let vpW = 0
  let vpH = 0
  let lastTime = 0
  let paused = false
  let handleResize: (() => void) | null = null
  let handleVisibility: (() => void) | null = null
  let maskBlobUrl: string | null = null

  function resize() {
    const bg = bgCanvasRef.value
    const deer = deerCanvasRef.value
    if (!bg || !deer) return

    vpW = window.innerWidth
    vpH = window.innerHeight

    bgDpr = Math.min(window.devicePixelRatio || 1, 2)
    bg.width = vpW * bgDpr
    bg.height = vpH * bgDpr
    bg.style.width = `${vpW}px`
    bg.style.height = `${vpH}px`
    bgCtx = bg.getContext('2d')
    bgCtx?.setTransform(1, 0, 0, 1, 0, 0)

    deer.style.width = `${vpW}px`
    deer.style.height = `${vpH}px`
    grid = buildGrid(deer, vpW, vpH)
    deerCtx = deer.getContext('2d')
    deerCtx?.setTransform(1, 0, 0, 1, 0, 0)

    blobs = buildBlobs(vpW, vpH)
  }

  function loop(ts: number) {
    if (!paused && bgCtx && deerCtx && grid) {
      const dt = lastTime === 0 ? 0.016 : Math.min((ts - lastTime) / 1000, 0.1)
      lastTime = ts

      updateBlobs(blobs, dt, vpW, vpH)
      drawBlobs(bgCtx, blobs, bgDpr)

      flickerGrid(grid.alphas, dt)
      drawGrid(deerCtx, grid)
    }
    rafId = requestAnimationFrame(loop)
  }

  function applyMask(url: string) {
    const deer = deerCanvasRef.value
    if (!deer) return
    deer.style.webkitMaskImage = `url("${url}")`
    deer.style.maskImage = `url("${url}")`
  }

  function start() {
    resize()

    // Fetch SVG as blob URL so mobile browsers (iOS Safari) can use it as a CSS mask.
    // External URL references in mask-image are unreliable on mobile WebKit.
    fetch('/images/deer.svg')
      .then((r) => r.blob())
      .then((blob) => {
        maskBlobUrl = URL.createObjectURL(blob)
        applyMask(maskBlobUrl)
      })
      .catch(() => {
        // Fallback to direct path if fetch fails
        applyMask('/images/deer.svg')
      })

    handleResize = debounce(resize, 150)
    window.addEventListener('resize', handleResize)

    handleVisibility = () => {
      paused = document.hidden
      if (!paused) lastTime = 0
    }
    document.addEventListener('visibilitychange', handleVisibility)

    rafId = requestAnimationFrame(loop)
  }

  function stop() {
    if (rafId !== null) {
      cancelAnimationFrame(rafId)
      rafId = null
    }
    if (handleResize) {
      window.removeEventListener('resize', handleResize)
      handleResize = null
    }
    if (handleVisibility) {
      document.removeEventListener('visibilitychange', handleVisibility)
      handleVisibility = null
    }
    if (maskBlobUrl) {
      URL.revokeObjectURL(maskBlobUrl)
      maskBlobUrl = null
    }
  }

  onMounted(start)
  onUnmounted(stop)
}
