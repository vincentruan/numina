import { onMounted, onUnmounted, type Ref } from 'vue'

// Two-layer background system:
//   bgCanvas  — firefly particles: small glowing dots that drift irregularly
//   deerCanvas — dim square pixel grid masked to deer SVG silhouette

// ── Deer pixel grid constants ──────────────────────────────────────────────
const CELL_SIZE = 4
const CELL_GAP = 1
const MAX_ALPHA = 0.45   // kept dim so login form stays readable
const FLICKER_RATE = 0.06

// ── Firefly particle constants ─────────────────────────────────────────────
const FIREFLY_COUNT_BASE = 80   // per 1000×1000 px area, scaled to viewport
const FIREFLY_MIN_R = 1.0
const FIREFLY_MAX_R = 3.5
const FIREFLY_SPEED_MIN = 8     // px/s
const FIREFLY_SPEED_MAX = 28
const FIREFLY_PULSE_SPEED_MIN = 0.4  // opacity pulse cycles/s
const FIREFLY_PULSE_SPEED_MAX = 1.2

interface Grid {
  cols: number
  rows: number
  alphas: Float32Array
  dpr: number
}

interface Firefly {
  x: number
  y: number
  r: number
  baseAlpha: number
  alpha: number
  pulsePhase: number
  pulseSpeed: number
  vx: number
  vy: number
  wanderTimer: number
  wanderInterval: number
}

function debounce<T extends (...args: unknown[]) => void>(fn: T, delay: number): T {
  let id: ReturnType<typeof setTimeout> | null = null
  return ((...args: unknown[]) => {
    if (id) clearTimeout(id)
    id = setTimeout(() => fn(...args), delay)
  }) as T
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
      // Lavender-tinted pixels for the deer silhouette
      ctx.fillStyle = `rgba(189,187,255,${a})`
      ctx.fillRect(c * step, r * step, size, size)
    }
  }
}

// ── Firefly helpers ────────────────────────────────────────────────────────

function rand(min: number, max: number) {
  return min + Math.random() * (max - min)
}

function buildFireflies(w: number, h: number): Firefly[] {
  const area = (w * h) / (1000 * 1000)
  const count = Math.round(FIREFLY_COUNT_BASE * Math.max(area, 0.3))
  const flies: Firefly[] = []
  for (let i = 0; i < count; i++) {
    const speed = rand(FIREFLY_SPEED_MIN, FIREFLY_SPEED_MAX)
    const angle = Math.random() * Math.PI * 2
    flies.push({
      x: Math.random() * w,
      y: Math.random() * h,
      r: rand(FIREFLY_MIN_R, FIREFLY_MAX_R),
      baseAlpha: rand(0.25, 0.75),
      alpha: 0,
      pulsePhase: Math.random() * Math.PI * 2,
      pulseSpeed: rand(FIREFLY_PULSE_SPEED_MIN, FIREFLY_PULSE_SPEED_MAX),
      vx: Math.cos(angle) * speed,
      vy: Math.sin(angle) * speed,
      wanderTimer: 0,
      wanderInterval: rand(1.5, 4.0),
    })
  }
  return flies
}

function updateFireflies(flies: Firefly[], dt: number, w: number, h: number) {
  for (const f of flies) {
    // Drift
    f.x += f.vx * dt
    f.y += f.vy * dt

    // Wrap around edges
    if (f.x < -10) f.x = w + 10
    else if (f.x > w + 10) f.x = -10
    if (f.y < -10) f.y = h + 10
    else if (f.y > h + 10) f.y = -10

    // Random direction change (wander)
    f.wanderTimer += dt
    if (f.wanderTimer >= f.wanderInterval) {
      f.wanderTimer = 0
      f.wanderInterval = rand(1.5, 4.0)
      const speed = rand(FIREFLY_SPEED_MIN, FIREFLY_SPEED_MAX)
      // Gradually turn rather than snap
      const currentAngle = Math.atan2(f.vy, f.vx)
      const newAngle = currentAngle + rand(-Math.PI * 0.7, Math.PI * 0.7)
      f.vx = Math.cos(newAngle) * speed
      f.vy = Math.sin(newAngle) * speed
    }

    // Pulse opacity
    f.pulsePhase += f.pulseSpeed * dt * Math.PI * 2
    const pulse = (Math.sin(f.pulsePhase) + 1) * 0.5  // 0..1
    f.alpha = f.baseAlpha * (0.3 + 0.7 * pulse)
  }
}

function drawFireflies(ctx: CanvasRenderingContext2D, flies: Firefly[], dpr: number) {
  ctx.clearRect(0, 0, ctx.canvas.width, ctx.canvas.height)

  for (const f of flies) {
    const x = f.x * dpr
    const y = f.y * dpr
    const r = f.r * dpr

    // Outer glow
    const glow = ctx.createRadialGradient(x, y, 0, x, y, r * 4)
    glow.addColorStop(0, `rgba(189,187,255,${f.alpha * 0.6})`)
    glow.addColorStop(0.4, `rgba(189,187,255,${f.alpha * 0.2})`)
    glow.addColorStop(1, `rgba(189,187,255,0)`)
    ctx.beginPath()
    ctx.arc(x, y, r * 4, 0, Math.PI * 2)
    ctx.fillStyle = glow
    ctx.fill()

    // Bright core
    ctx.beginPath()
    ctx.arc(x, y, r, 0, Math.PI * 2)
    ctx.fillStyle = `rgba(220,218,255,${Math.min(f.alpha * 1.4, 1)})`
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

    // Background canvas for fireflies
    bgDpr = Math.min(window.devicePixelRatio || 1, 2)
    bg.width = vpW * bgDpr
    bg.height = vpH * bgDpr
    bg.style.width = `${vpW}px`
    bg.style.height = `${vpH}px`
    bgCtx = bg.getContext('2d')
    bgCtx?.setTransform(1, 0, 0, 1, 0, 0)

    // Deer canvas for pixel grid
    grid = buildGrid(deer, vpW, vpH)
    deerCtx = deer.getContext('2d')
    deerCtx?.setTransform(1, 0, 0, 1, 0, 0)

    // Rebuild fireflies for new viewport size
    flies = buildFireflies(vpW, vpH)
  }

  function loop(ts: number) {
    if (!paused && bgCtx && deerCtx && grid) {
      const dt = lastTime === 0 ? 0.016 : Math.min((ts - lastTime) / 1000, 0.1)
      lastTime = ts

      // Update & draw fireflies on bg canvas
      updateFireflies(flies, dt, vpW, vpH)
      drawFireflies(bgCtx, flies, bgDpr)

      // Update & draw deer pixel grid
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
