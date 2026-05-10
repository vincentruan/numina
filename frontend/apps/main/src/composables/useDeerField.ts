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
// Base particles per layer at 1080×1920 reference area (~2M px²).
// Actual count scales linearly with viewport area so mobile/desktop feel equally dense.
const PARTICLES_PER_LAYER_BASE = [30, 25, 12, 6]
const REFERENCE_AREA = 2_073_600  // 1080×1920
// Outer glow radius per layer (CSS px)
// Layer 0: large diffuse far halos; Layer 3: large bright near orbs with spikes
const LAYER_RADIUS_MIN = [55, 30, 22, 35]
const LAYER_RADIUS_MAX = [100, 55, 40, 70]
// Core radius fraction of glow radius
const CORE_RATIO = 0.12
// Speed (px/s): near layers move faster
const LAYER_SPEED_MIN = [3, 7, 13, 18]
const LAYER_SPEED_MAX = [8, 16, 26, 35]
// Peak opacity per layer
const LAYER_BASE_ALPHA_MIN = [0.35, 0.42, 0.55, 0.72]
const LAYER_BASE_ALPHA_MAX = [0.60, 0.68, 0.80, 0.98]
// Glow center opacity multiplier per layer
const LAYER_GLOW_CENTER = [0.25, 0.40, 0.60, 0.80]
// Twinkle speed (cycles/s)
const LAYER_TWINKLE_MIN = [0.10, 0.20, 0.40, 0.60]
const LAYER_TWINKLE_MAX = [0.22, 0.42, 0.75, 1.20]
// Twinkle depth per layer
const LAYER_TWINKLE_DEPTH = [0.18, 0.32, 0.52, 0.70]
// Wander interval (s)
const WANDER_MIN = 2.0
const WANDER_MAX = 5.5
const WANDER_ANGLE = Math.PI * 0.65
// Lifecycle duration (s) — near layers cycle faster
const LIFECYCLE_DURATION_MIN = [6.0, 4.5, 3.0, 2.5]
const LIFECYCLE_DURATION_MAX = [12.0, 8.0, 5.5, 4.5]
// Star spike: layers 2 and 3 (near/mid-near) get diffraction spikes
const SPIKE_LAYERS = [false, false, true, true]
// Spike arm half-length (CSS px) — scales with the larger near-layer glow radii
const SPIKE_LENGTH_PX = [0, 0, 35, 60]
// Spike arm width (CSS px)
const SPIKE_WIDTH = [0, 0, 1.5, 2.0]

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
  baseAlpha: number  // peak opacity at lifecycle peak
  alpha: number      // current opacity (lifecycle × twinkle)
  twinklePhase: number
  twinkleSpeed: number
  twinkleDepth: number
  vx: number
  vy: number
  wanderTimer: number
  wanderInterval: number
  layer: number
  glowCenter: number
  rTint: number
  bTint: number
  // Lifecycle: 0→1 over lifecycleDuration, then respawn
  lifecyclePhase: number  // 0..1
  lifecycleDuration: number  // seconds for one full birth→death cycle
  spikeAngle: number  // rotation of the 4-arm star spike (radians)
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

function layerCount(layer: number, w: number, h: number): number {
  const area = w * h
  const scale = area / REFERENCE_AREA
  // Clamp scale: mobile gets at least 50%, large monitors get at most 250%
  const clamped = Math.max(0.5, Math.min(2.5, scale))
  return Math.max(4, Math.round(PARTICLES_PER_LAYER_BASE[layer] * clamped))
}

function buildFireflies(w: number, h: number): Firefly[] {
  const flies: Firefly[] = []

  for (let layer = 0; layer < NUM_LAYERS; layer++) {
    const count = layerCount(layer, w, h)
    for (let i = 0; i < count; i++) {
      const glowR = rand(LAYER_RADIUS_MIN[layer], LAYER_RADIUS_MAX[layer])
      const speed = rand(LAYER_SPEED_MIN[layer], LAYER_SPEED_MAX[layer])
      const angle = Math.random() * Math.PI * 2
      // Stagger lifecycle phases so particles don't all peak simultaneously
      const lifecyclePhase = Math.random()
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
        lifecyclePhase,
        lifecycleDuration: rand(LIFECYCLE_DURATION_MIN[layer], LIFECYCLE_DURATION_MAX[layer]),
        spikeAngle: Math.random() * Math.PI * 0.25, // slight random rotation of spike arms
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

    // Lifecycle: advance phase 0→1, then respawn with new duration
    f.lifecyclePhase += dt / f.lifecycleDuration
    if (f.lifecyclePhase >= 1.0) {
      f.lifecyclePhase = 0
      f.lifecycleDuration = rand(LIFECYCLE_DURATION_MIN[f.layer], LIFECYCLE_DURATION_MAX[f.layer])
    }

    // Lifecycle envelope: fade in (0→0.3), peak (0.3→0.75), fade out (0.75→1.0)
    // Mirrors deerflow's `depth * smoothstep(1.0, 0.9, depth)` pattern
    const p = f.lifecyclePhase
    let lifecycle: number
    if (p < 0.3) {
      lifecycle = p / 0.3  // 0→1 fade in
    } else if (p < 0.75) {
      lifecycle = 1.0       // peak
    } else {
      lifecycle = (1.0 - p) / 0.25  // 1→0 fade out
    }

    // Triangle-wave twinkle — modulates on top of lifecycle envelope
    f.twinklePhase = (f.twinklePhase + f.twinkleSpeed * dt) % 1
    const twinkle = triWave(f.twinklePhase)
    const modulation = 1.0 + (twinkle - 0.5) * f.twinkleDepth

    f.alpha = Math.min(f.baseAlpha * lifecycle * modulation, 1.0)
  }
}

function drawSpikes(
  ctx: CanvasRenderingContext2D,
  x: number, y: number,
  glowR: number, coreR: number,
  r: number, g: number,
  alpha: number, layer: number,
  spikeAngle: number,
  dpr: number,
) {
  // armLen in physical pixels (already DPR-scaled input coords)
  const armLen = SPIKE_LENGTH_PX[layer] * dpr
  const halfW = SPIKE_WIDTH[layer] * dpr
  // 4 arms at 0°, 45°, 90°, 135° plus the particle's random rotation offset
  const angles = [0, Math.PI * 0.5, Math.PI * 0.25, Math.PI * 0.75]

  ctx.save()
  // Spike opacity: boost relative to particle alpha so spikes are visible even at mid-lifecycle
  ctx.globalAlpha = Math.min(alpha * 1.4, 1.0)
  ctx.translate(x, y)
  ctx.rotate(spikeAngle)

  for (const baseAngle of angles) {
    ctx.save()
    ctx.rotate(baseAngle)
    const grad = ctx.createLinearGradient(0, 0, armLen, 0)
    grad.addColorStop(0,    `rgba(${Math.min(r + 60, 255)},${Math.min(g + 55, 255)},255,1.0)`)
    grad.addColorStop(0.12, `rgba(${Math.min(r + 40, 255)},${Math.min(g + 35, 255)},255,0.7)`)
    grad.addColorStop(0.4,  `rgba(${r},${g},255,0.25)`)
    grad.addColorStop(1,    `rgba(${r},${g},255,0)`)

    ctx.beginPath()
    ctx.moveTo(-coreR * 0.5, 0)
    ctx.bezierCurveTo(
      armLen * 0.1, -halfW,
      armLen * 0.4, -halfW * 0.4,
      armLen, 0,
    )
    ctx.bezierCurveTo(
      armLen * 0.4, halfW * 0.4,
      armLen * 0.1, halfW,
      -coreR * 0.5, 0,
    )
    ctx.fillStyle = grad
    ctx.fill()

    // Mirror arm in opposite direction
    ctx.save()
    ctx.rotate(Math.PI)
    ctx.beginPath()
    ctx.moveTo(-coreR * 0.5, 0)
    ctx.bezierCurveTo(
      armLen * 0.1, -halfW,
      armLen * 0.4, -halfW * 0.4,
      armLen, 0,
    )
    ctx.bezierCurveTo(
      armLen * 0.4, halfW * 0.4,
      armLen * 0.1, halfW,
      -coreR * 0.5, 0,
    )
    ctx.fillStyle = grad
    ctx.fill()
    ctx.restore()

    ctx.restore()
  }

  ctx.restore()
}

function drawFireflies(ctx: CanvasRenderingContext2D, flies: Firefly[], dpr: number) {
  ctx.clearRect(0, 0, ctx.canvas.width, ctx.canvas.height)

  // Draw back-to-front (far layers first) for correct depth compositing
  for (let layer = 0; layer < NUM_LAYERS; layer++) {
    for (const f of flies) {
      if (f.layer !== layer) continue
      if (f.alpha < 0.005) continue

      const x = f.x * dpr
      const y = f.y * dpr
      const gr = f.glowR * dpr
      const cr = f.coreR * dpr
      const a = f.alpha

      // Color: lavender base with per-particle tint
      const r = Math.round(189 + f.rTint * 40)
      const g = Math.round(187 + Math.min(f.rTint, f.bTint) * 20)

      // Use globalAlpha to scale the entire particle — far layers are genuinely dim
      ctx.globalAlpha = a

      // Outer glow — radial gradient with inverse-distance falloff
      const gc = f.glowCenter
      const glow = ctx.createRadialGradient(x, y, 0, x, y, gr)
      glow.addColorStop(0,    `rgba(${r},${g},255,${gc.toFixed(3)})`)
      glow.addColorStop(0.3,  `rgba(${r},${g},255,${(gc * 0.45).toFixed(3)})`)
      glow.addColorStop(0.65, `rgba(${r},${g},255,${(gc * 0.12).toFixed(3)})`)
      glow.addColorStop(1,    `rgba(${r},${g},255,0)`)
      ctx.beginPath()
      ctx.arc(x, y, gr, 0, Math.PI * 2)
      ctx.fillStyle = glow
      ctx.fill()

      // Bright core
      const coreAlpha = 0.5 + f.layer * 0.15
      ctx.beginPath()
      ctx.arc(x, y, cr, 0, Math.PI * 2)
      ctx.fillStyle = `rgba(${Math.min(r + 30, 255)},${Math.min(g + 28, 255)},255,${coreAlpha.toFixed(3)})`
      ctx.fill()

      ctx.globalAlpha = 1

      // Star spikes for near layers — drawn after resetting globalAlpha so they
      // use their own alpha internally (avoids double-multiplying lifecycle fade)
      if (SPIKE_LAYERS[layer]) {
        drawSpikes(ctx, x, y, gr, cr, r, g, a, layer, f.spikeAngle, dpr)
      }
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
