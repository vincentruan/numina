import { onMounted, onUnmounted, type Ref } from 'vue'

// Two-layer background system:
//   bgCanvas  — firefly particles with depth layers (near/far size + brightness variation)
//   deerCanvas — dim lavender pixel grid masked to deer SVG silhouette

// ── Deer pixel grid constants ──────────────────────────────────────────────
const CELL_SIZE = 4
const CELL_GAP = 1
const MAX_ALPHA = 0.45
const FLICKER_RATE = 0.06

// ── Firefly depth-layer constants ─────────────────────────────────────────
// 4 depth layers (0=far/dim/slow, 3=near/bright/fast) — inspired by Galaxy shader
const NUM_LAYERS = 4
// Particles per layer — generous count so halos overlap and fill the field
const PARTICLES_PER_LAYER = 50
// Outer glow radius per layer (CSS px): far=large diffuse blob, near=tight bright dot
const LAYER_RADIUS_MIN = [60, 35, 14, 4]
const LAYER_RADIUS_MAX = [110, 60, 24, 9]
// Core radius fraction of glow radius
const CORE_RATIO = 0.10
// Speed (px/s): near layers move faster
const LAYER_SPEED_MIN = [3, 7, 13, 20]
const LAYER_SPEED_MAX = [8, 16, 26, 40]
// Peak opacity per layer — all layers visible, far layers are soft hazes
const LAYER_BASE_ALPHA_MIN = [0.40, 0.45, 0.55, 0.70]
const LAYER_BASE_ALPHA_MAX = [0.65, 0.70, 0.80, 0.95]
// Glow center opacity multiplier per layer (far=soft center, near=bright center)
const LAYER_GLOW_CENTER = [0.28, 0.42, 0.58, 0.75]
// Twinkle speed (cycles/s): near layers twinkle faster
const LAYER_TWINKLE_MIN = [0.12, 0.22, 0.38, 0.55]
const LAYER_TWINKLE_MAX = [0.25, 0.45, 0.72, 1.10]
// Twinkle depth per layer: far layers barely flicker, near layers pulse more
const LAYER_TWINKLE_DEPTH = [0.20, 0.35, 0.50, 0.65]
// Wander interval (s)
const WANDER_MIN = 2.0
const WANDER_MAX = 5.5
const WANDER_ANGLE = Math.PI * 0.65

interface Grid {
  cols: number
  rows: number
  alphas: Float32Array
  dpr: number
}

interface Firefly {
  x: number
  y: number
  glowR: number      // outer glow radius (CSS px)
  coreR: number      // bright core radius
  baseAlpha: number  // peak opacity
  alpha: number      // current opacity
  twinklePhase: number
  twinkleSpeed: number
  twinkleDepth: number  // per-particle twinkle intensity
  vx: number
  vy: number
  wanderTimer: number
  wanderInterval: number
  layer: number      // 0=far … NUM_LAYERS-1=near
  glowCenter: number // center opacity multiplier for this layer
  rTint: number      // slight color variation
  bTint: number
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

// Triangle wave: oscillates 0→1→0 smoothly (no discontinuity at peak/trough)
function triWave(phase: number): number {
  const p = ((phase % 1) + 1) % 1  // 0..1
  return p < 0.5 ? p * 2 : (1 - p) * 2
}

// ── Deer grid helpers ──────────────────────────────────────────────────────

function buildGrid(canvas: HTMLCanvasElement, w: number, h: number): Grid {
  const dpr = Math.min(window.devicePixelRatio || 1, 2)
  canvas.width = w * dpr
  canvas.height = h * dpr
  canvas.style.width = `${w}px`
  canvas.style.height = `${h}px`

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

// ── Firefly helpers ────────────────────────────────────────────────────────

function buildFireflies(w: number, h: number): Firefly[] {
  // Scale count with viewport area but keep a generous minimum
  const area = (w * h) / (1_000_000)
  const countPerLayer = Math.round(PARTICLES_PER_LAYER * Math.max(area * 2.5, 1.0))
  const flies: Firefly[] = []

  for (let layer = 0; layer < NUM_LAYERS; layer++) {
    for (let i = 0; i < countPerLayer; i++) {
      const glowR = rand(LAYER_RADIUS_MIN[layer], LAYER_RADIUS_MAX[layer])
      const speed = rand(LAYER_SPEED_MIN[layer], LAYER_SPEED_MAX[layer])
      const angle = Math.random() * Math.PI * 2
      flies.push({
        x: Math.random() * w,
        y: Math.random() * h,
        glowR,
        coreR: glowR * CORE_RATIO,
        baseAlpha: rand(LAYER_BASE_ALPHA_MIN[layer], LAYER_BASE_ALPHA_MAX[layer]),
        alpha: 0,
        twinklePhase: Math.random(),
        twinkleSpeed: rand(LAYER_TWINKLE_MIN[layer], LAYER_TWINKLE_MAX[layer]),
        twinkleDepth: LAYER_TWINKLE_DEPTH[layer],
        vx: Math.cos(angle) * speed,
        vy: Math.sin(angle) * speed,
        wanderTimer: Math.random() * WANDER_MAX,
        wanderInterval: rand(WANDER_MIN, WANDER_MAX),
        layer,
        glowCenter: LAYER_GLOW_CENTER[layer],
        rTint: Math.random() * 0.20,
        bTint: Math.random() * 0.15,
      })
    }
  }
  return flies
}

function updateFireflies(flies: Firefly[], dt: number, w: number, h: number) {
  for (const f of flies) {
    f.x += f.vx * dt
    f.y += f.vy * dt

    // Wrap edges
    if (f.x < -f.glowR * 2) f.x = w + f.glowR * 2
    else if (f.x > w + f.glowR * 2) f.x = -f.glowR * 2
    if (f.y < -f.glowR * 2) f.y = h + f.glowR * 2
    else if (f.y > h + f.glowR * 2) f.y = -f.glowR * 2

    // Wander: gradual direction change
    f.wanderTimer += dt
    if (f.wanderTimer >= f.wanderInterval) {
      f.wanderTimer = 0
      f.wanderInterval = rand(WANDER_MIN, WANDER_MAX)
      const speed = rand(LAYER_SPEED_MIN[f.layer], LAYER_SPEED_MAX[f.layer])
      const currentAngle = Math.atan2(f.vy, f.vx)
      const newAngle = currentAngle + rand(-WANDER_ANGLE, WANDER_ANGLE)
      f.vx = Math.cos(newAngle) * speed
      f.vy = Math.sin(newAngle) * speed
    }

    // Triangle-wave twinkle — per-layer depth controls modulation range
    f.twinklePhase = (f.twinklePhase + f.twinkleSpeed * dt) % 1
    const twinkle = triWave(f.twinklePhase)
    // modulation: 1.0 ± (twinkleDepth * 0.5), so far layers barely flicker
    const modulation = 1.0 + (twinkle - 0.5) * f.twinkleDepth
    f.alpha = Math.min(f.baseAlpha * modulation, 1.0)
  }
}

function drawFireflies(ctx: CanvasRenderingContext2D, flies: Firefly[], dpr: number) {
  ctx.clearRect(0, 0, ctx.canvas.width, ctx.canvas.height)

  // Draw back-to-front (far layers first) for correct depth compositing
  for (let layer = 0; layer < NUM_LAYERS; layer++) {
    for (const f of flies) {
      if (f.layer !== layer) continue

      const x = f.x * dpr
      const y = f.y * dpr
      const gr = f.glowR * dpr
      const cr = f.coreR * dpr
      const a = f.alpha

      // Color: lavender base with per-particle tint
      const r = Math.round(189 + f.rTint * 40)
      const g = Math.round(187 + Math.min(f.rTint, f.bTint) * 20)
      const b = 255

      // Use globalAlpha to scale the entire particle — far layers are genuinely dim
      ctx.globalAlpha = a

      // Outer glow — radial gradient with inverse-distance falloff
      // Far layers: wide soft halo; near layers: tight bright halo
      const gc = f.glowCenter
      const glow = ctx.createRadialGradient(x, y, 0, x, y, gr)
      glow.addColorStop(0,    `rgba(${r},${g},${b},${gc.toFixed(3)})`)
      glow.addColorStop(0.3,  `rgba(${r},${g},${b},${(gc * 0.45).toFixed(3)})`)
      glow.addColorStop(0.65, `rgba(${r},${g},${b},${(gc * 0.12).toFixed(3)})`)
      glow.addColorStop(1,    `rgba(${r},${g},${b},0)`)
      ctx.beginPath()
      ctx.arc(x, y, gr, 0, Math.PI * 2)
      ctx.fillStyle = glow
      ctx.fill()

      // Bright core — near layers get a more prominent solid dot
      const coreAlpha = 0.5 + f.layer * 0.15
      ctx.beginPath()
      ctx.arc(x, y, cr, 0, Math.PI * 2)
      ctx.fillStyle = `rgba(${Math.min(r + 30, 255)},${Math.min(g + 28, 255)},255,${coreAlpha.toFixed(3)})`
      ctx.fill()

      ctx.globalAlpha = 1
    }
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
  let flies: Firefly[] = []
  let bgDpr = 1
  let vpW = 0
  let vpH = 0
  let lastTime = 0
  let paused = false
  let handleResize: (() => void) | null = null
  let handleVisibility: (() => void) | null = null

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

    grid = buildGrid(deer, vpW, vpH)
    deerCtx = deer.getContext('2d')
    deerCtx?.setTransform(1, 0, 0, 1, 0, 0)

    flies = buildFireflies(vpW, vpH)
  }

  function loop(ts: number) {
    if (!paused && bgCtx && deerCtx && grid) {
      const dt = lastTime === 0 ? 0.016 : Math.min((ts - lastTime) / 1000, 0.1)
      lastTime = ts

      updateFireflies(flies, dt, vpW, vpH)
      drawFireflies(bgCtx, flies, bgDpr)

      flickerGrid(grid.alphas, dt)
      drawGrid(deerCtx, grid)
    }
    rafId = requestAnimationFrame(loop)
  }

  function start() {
    resize()

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
  }

  onMounted(start)
  onUnmounted(stop)
}
