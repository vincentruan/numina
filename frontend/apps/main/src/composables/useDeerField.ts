import { onMounted, onUnmounted, type Ref } from 'vue'

// Two-layer background system:
//   bgCanvas  — stellar pulsation particles (85% normal + 15% stars with rays)
//   deerCanvas — dim lavender pixel grid masked to deer SVG silhouette

// ── Deer pixel grid constants ──────────────────────────────────────────────
const CELL_SIZE = 4
const CELL_GAP = 1
const MAX_ALPHA = 0.45
const FLICKER_RATE = 0.06

// ── Stellar pulsation particle constants ───────────────────────────────────
// Particle system: 85% normal particles (steady) + 15% stars (dramatic pulsation)
// Stars expand slowly to peak brightness with radiating spikes, then contract
const PARTICLE_COUNT_BASE = 40
const REFERENCE_AREA = 2_073_600 // 1080×1920
const STAR_RATIO = 0.15 // 15% of particles are stars

// Normal particle size (steady, small)
const NORMAL_RADIUS_MIN = 1.2
const NORMAL_RADIUS_MAX = 2.4

// Star particle size — at rest (trough) and peak (max expansion)
const STAR_RADIUS_MIN = 1.8
const STAR_RADIUS_MAX = 3.5
// Star pulsation amplitude: peak size = base * (1 + amplitude)
const STAR_SIZE_AMPLITUDE_MIN = 1.6
const STAR_SIZE_AMPLITUDE_MAX = 2.4

// Pulsation cycle: 4-6 seconds per full breath (slow stellar feel)
const STAR_CYCLE_MIN = 4.0
const STAR_CYCLE_MAX = 6.0
// Normal particles breathe gently — slightly faster, less amplitude
const NORMAL_CYCLE_MIN = 3.0
const NORMAL_CYCLE_MAX = 5.0
const NORMAL_BREATH_AMPLITUDE = 0.35 // gentle size/opacity variation

// Opacity at rest (trough) and peak
const NORMAL_OPACITY_MIN = 0.35
const NORMAL_OPACITY_MAX = 0.65
const STAR_OPACITY_MIN = 0.45
const STAR_OPACITY_MAX = 0.85

// Star halo extent
const STAR_HALO_MULTIPLIER = 5 // halo radius = current radius * this

// Drift speed (px/s) — gentle ambient movement
const DRIFT_SPEED_MIN = 3
const DRIFT_SPEED_MAX = 10

// Wander: gradual direction changes
const WANDER_INTERVAL_MIN = 2.5
const WANDER_INTERVAL_MAX = 6.0
const WANDER_ANGLE_MAX = Math.PI * 0.5

// Color palette: cyan/teal/lavender variations
const PARTICLE_COLORS: Array<[number, number, number]> = [
  [0, 220, 255], // primary cyan
  [80, 240, 240], // teal
  [150, 220, 255], // light cyan-blue
  [189, 187, 255], // lavender (brand accent)
]

interface Grid {
  cols: number
  rows: number
  alphas: Float32Array
  dpr: number
}

interface Particle {
  x: number
  y: number
  isStar: boolean
  baseRadius: number // at trough
  currentRadius: number // updated per frame
  pulsePhase: number // 0..1 (cycle progress)
  pulseSpeed: number // cycles/s
  sizeAmplitude: number // peak = base * (1 + amplitude)
  baseOpacity: number // at trough
  peakOpacity: number // at peak
  vx: number
  vy: number
  wanderTimer: number
  wanderInterval: number
  colorVariant: number
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

// ── Particle helpers ───────────────────────────────────────────────────────

function particleCount(w: number, h: number): number {
  const area = w * h
  const scale = area / REFERENCE_AREA
  const clamped = Math.max(0.5, Math.min(2.5, scale))
  return Math.max(20, Math.round(PARTICLE_COUNT_BASE * clamped))
}

function buildParticles(w: number, h: number): Particle[] {
  const particles: Particle[] = []
  const count = particleCount(w, h)

  for (let i = 0; i < count; i++) {
    const isStar = Math.random() < STAR_RATIO
    const speed = rand(DRIFT_SPEED_MIN, DRIFT_SPEED_MAX)
    const angle = Math.random() * Math.PI * 2

    if (isStar) {
      const baseRadius = rand(STAR_RADIUS_MIN, STAR_RADIUS_MAX)
      const cycleDuration = rand(STAR_CYCLE_MIN, STAR_CYCLE_MAX)
      particles.push({
        x: Math.random() * w,
        y: Math.random() * h,
        isStar: true,
        baseRadius,
        currentRadius: baseRadius,
        pulsePhase: Math.random(),
        pulseSpeed: 1 / cycleDuration,
        sizeAmplitude: rand(STAR_SIZE_AMPLITUDE_MIN, STAR_SIZE_AMPLITUDE_MAX),
        baseOpacity: STAR_OPACITY_MIN,
        peakOpacity: STAR_OPACITY_MAX,
        vx: Math.cos(angle) * speed,
        vy: Math.sin(angle) * speed,
        wanderTimer: Math.random() * WANDER_INTERVAL_MAX,
        wanderInterval: rand(WANDER_INTERVAL_MIN, WANDER_INTERVAL_MAX),
        colorVariant: Math.floor(Math.random() * PARTICLE_COLORS.length),
      })
    } else {
      const baseRadius = rand(NORMAL_RADIUS_MIN, NORMAL_RADIUS_MAX)
      const cycleDuration = rand(NORMAL_CYCLE_MIN, NORMAL_CYCLE_MAX)
      particles.push({
        x: Math.random() * w,
        y: Math.random() * h,
        isStar: false,
        baseRadius,
        currentRadius: baseRadius,
        pulsePhase: Math.random(),
        pulseSpeed: 1 / cycleDuration,
        sizeAmplitude: NORMAL_BREATH_AMPLITUDE,
        baseOpacity: NORMAL_OPACITY_MIN,
        peakOpacity: NORMAL_OPACITY_MAX,
        vx: Math.cos(angle) * speed,
        vy: Math.sin(angle) * speed,
        wanderTimer: Math.random() * WANDER_INTERVAL_MAX,
        wanderInterval: rand(WANDER_INTERVAL_MIN, WANDER_INTERVAL_MAX),
        colorVariant: Math.floor(Math.random() * PARTICLE_COLORS.length),
      })
    }
  }
  return particles
}

function updateParticles(particles: Particle[], dt: number, w: number, h: number) {
  for (const p of particles) {
    // Drift movement
    p.x += p.vx * dt
    p.y += p.vy * dt

    // Wrap edges — use star halo extent as margin so spikes don't pop in/out
    const margin = p.isStar ? p.currentRadius * STAR_HALO_MULTIPLIER : p.currentRadius * 3
    if (p.x < -margin) p.x = w + margin
    else if (p.x > w + margin) p.x = -margin
    if (p.y < -margin) p.y = h + margin
    else if (p.y > h + margin) p.y = -margin

    // Wander: gradual direction changes
    p.wanderTimer += dt
    if (p.wanderTimer >= p.wanderInterval) {
      p.wanderTimer = 0
      p.wanderInterval = rand(WANDER_INTERVAL_MIN, WANDER_INTERVAL_MAX)
      const speed = rand(DRIFT_SPEED_MIN, DRIFT_SPEED_MAX)
      const currentAngle = Math.atan2(p.vy, p.vx)
      const newAngle = currentAngle + rand(-WANDER_ANGLE_MAX, WANDER_ANGLE_MAX)
      p.vx = Math.cos(newAngle) * speed
      p.vy = Math.sin(newAngle) * speed
    }

    // Pulsation: sinusoidal pulse for radius
    p.pulsePhase = (p.pulsePhase + p.pulseSpeed * dt) % 1
    const pulseWave = (Math.sin(p.pulsePhase * Math.PI * 2) + 1) / 2 // 0→1→0

    // Radius expands during peak
    p.currentRadius = p.baseRadius * (1 + p.sizeAmplitude * pulseWave)
  }
}

function drawParticles(ctx: CanvasRenderingContext2D, particles: Particle[], dpr: number) {
  ctx.clearRect(0, 0, ctx.canvas.width, ctx.canvas.height)

  // Pass 1: normal particles (draw first so stars render on top)
  for (const p of particles) {
    if (p.isStar) continue
    drawNormalParticle(ctx, p, dpr)
  }

  // Pass 2: star particles with halo + rays
  for (const p of particles) {
    if (!p.isStar) continue
    drawStarParticle(ctx, p, dpr)
  }
}

function drawNormalParticle(ctx: CanvasRenderingContext2D, p: Particle, dpr: number) {
  const x = p.x * dpr
  const y = p.y * dpr
  const r = p.currentRadius * dpr

  const pulseWave = (Math.sin(p.pulsePhase * Math.PI * 2) + 1) / 2
  const opacity = p.baseOpacity + (p.peakOpacity - p.baseOpacity) * pulseWave
  const [cr, cg, cb] = PARTICLE_COLORS[p.colorVariant]

  // Soft glow: small radial gradient
  const haloRadius = r * 3
  const gradient = ctx.createRadialGradient(x, y, 0, x, y, haloRadius)
  gradient.addColorStop(0, `rgba(${cr},${cg},${cb},${opacity.toFixed(3)})`)
  gradient.addColorStop(0.3, `rgba(${cr},${cg},${cb},${(opacity * 0.4).toFixed(3)})`)
  gradient.addColorStop(0.7, `rgba(${cr},${cg},${cb},${(opacity * 0.1).toFixed(3)})`)
  gradient.addColorStop(1, `rgba(${cr},${cg},${cb},0)`)

  ctx.beginPath()
  ctx.arc(x, y, haloRadius, 0, Math.PI * 2)
  ctx.fillStyle = gradient
  ctx.fill()
}

function drawStarParticle(ctx: CanvasRenderingContext2D, p: Particle, dpr: number) {
  const x = p.x * dpr
  const y = p.y * dpr
  const r = p.currentRadius * dpr

  const pulseWave = (Math.sin(p.pulsePhase * Math.PI * 2) + 1) / 2 // 0→1→0
  const opacity = p.baseOpacity + (p.peakOpacity - p.baseOpacity) * pulseWave
  const [cr, cg, cb] = PARTICLE_COLORS[p.colorVariant]

  // Wide halo — expands with pulsation, creates the "star brightening" feel
  const haloRadius = r * STAR_HALO_MULTIPLIER
  const haloGradient = ctx.createRadialGradient(x, y, 0, x, y, haloRadius)
  haloGradient.addColorStop(0, `rgba(${cr},${cg},${cb},${(opacity * 0.6).toFixed(3)})`)
  haloGradient.addColorStop(0.15, `rgba(${cr},${cg},${cb},${(opacity * 0.3).toFixed(3)})`)
  haloGradient.addColorStop(0.4, `rgba(${cr},${cg},${cb},${(opacity * 0.1).toFixed(3)})`)
  haloGradient.addColorStop(0.7, `rgba(${cr},${cg},${cb},${(opacity * 0.03).toFixed(3)})`)
  haloGradient.addColorStop(1, `rgba(${cr},${cg},${cb},0)`)
  ctx.beginPath()
  ctx.arc(x, y, haloRadius, 0, Math.PI * 2)
  ctx.fillStyle = haloGradient
  ctx.fill()

  // Bright core — white center that intensifies at peak
  const coreOpacity = Math.min(1, opacity * (0.7 + pulseWave * 0.5))
  const coreRadius = r * (1.2 + pulseWave * 0.8)
  const coreGradient = ctx.createRadialGradient(x, y, 0, x, y, coreRadius)
  coreGradient.addColorStop(0, `rgba(255,255,255,${coreOpacity.toFixed(3)})`)
  coreGradient.addColorStop(0.3, `rgba(${cr},${cg},${cb},${(coreOpacity * 0.7).toFixed(3)})`)
  coreGradient.addColorStop(0.7, `rgba(${cr},${cg},${cb},${(coreOpacity * 0.2).toFixed(3)})`)
  coreGradient.addColorStop(1, `rgba(${cr},${cg},${cb},0)`)
  ctx.beginPath()
  ctx.arc(x, y, coreRadius, 0, Math.PI * 2)
  ctx.fillStyle = coreGradient
  ctx.fill()
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
  let particles: Particle[] = []
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

    particles = buildParticles(vpW, vpH)
  }

  function loop(ts: number) {
    if (!paused && bgCtx && deerCtx && grid) {
      const dt = lastTime === 0 ? 0.016 : Math.min((ts - lastTime) / 1000, 0.1)
      lastTime = ts

      updateParticles(particles, dt, vpW, vpH)
      drawParticles(bgCtx, particles, bgDpr)

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
