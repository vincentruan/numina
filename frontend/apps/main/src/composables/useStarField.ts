/**
 * useStarField composable
 * Canvas 2D cosmic star background animation with performance optimization
 */

import { ref, onMounted, onUnmounted, type Ref } from 'vue'
import { getTierConfig, getScaledCount, STAR_COLORS, type StarLayerConfig } from './starField.config'
import { getTier } from '@/utils/deviceTier'

// Base frame time for animation normalization (60fps = 16.67ms)
const BASE_FRAME_TIME = 16.67

// Star data structure
interface Star {
  x: number
  y: number
  r: number
  alpha: number
  baseAlpha: number
  speedX: number
  speedY: number
  twinklePhase: number
  twinkleSpeed: number
  twinkleAmplitude: number
  layer: 'far' | 'mid' | 'near'
}

// Meteor data structure
interface Meteor {
  x: number
  y: number
  vx: number
  vy: number
  length: number
  life: number
  maxLife: number
  active: boolean
}

// Animation state
interface AnimationState {
  rafId: number | null
  lastTime: number
  isPaused: boolean
}

/**
 * Debounce helper
 */
function debounce<T extends (...args: unknown[]) => void>(fn: T, delay: number): T {
  let timeoutId: ReturnType<typeof setTimeout> | null = null
  return ((...args: unknown[]) => {
    if (timeoutId) clearTimeout(timeoutId)
    timeoutId = setTimeout(() => fn(...args), delay)
  }) as T
}

/**
 * Random value in range
 */
function random(min: number, max: number): number {
  return Math.random() * (max - min) + min
}

/**
 * Create stars for a layer
 */
function createStars(
  config: StarLayerConfig,
  layer: 'far' | 'mid' | 'near',
  canvasWidth: number,
  canvasHeight: number
): Star[] {
  const stars: Star[] = []
  for (let i = 0; i < config.count; i++) {
    const baseAlpha = random(config.minAlpha, config.maxAlpha)
    stars.push({
      x: random(0, canvasWidth),
      y: random(0, canvasHeight),
      r: random(config.minRadius, config.maxRadius),
      alpha: baseAlpha,
      baseAlpha,
      speedX: random(config.minSpeedX, config.maxSpeedX),
      speedY: random(config.minSpeedY, config.maxSpeedY),
      twinklePhase: random(0, Math.PI * 2),
      twinkleSpeed: random(0.02, 0.05),
      twinkleAmplitude: config.twinkleChance > 0 ? random(0.1, 0.3) : 0,
      layer,
    })
  }
  return stars
}

/**
 * Main composable
 */
export function useStarField(canvasRef: Ref<HTMLCanvasElement | null>) {
  const isRunning = ref(false)

  // Internal state
  let state: AnimationState = {
    rafId: null,
    lastTime: 0,
    isPaused: false,
  }

  let stars: Star[] = []
  let meteors: Meteor[] = []
  let ctx: CanvasRenderingContext2D | null = null
  let config: ReturnType<typeof getTierConfig> | null = null

  // DPR-capped dimensions
  let canvasWidth = 0
  let canvasHeight = 0
  let dpr = 1

  // Event handlers (stored for cleanup)
  let handleResize: (() => void) | null = null
  let handleVisibilityChange: (() => void) | null = null

  /**
   * Initialize canvas and animation
   */
  function init(): boolean {
    if (!canvasRef.value) return false

    const canvas = canvasRef.value
    ctx = canvas.getContext('2d')
    if (!ctx) {
      console.warn('useStarField: Could not get 2D context')
      return false
    }

    // Get device tier and config
    const tier = getTier()
    config = getTierConfig(tier)

    // Set up canvas dimensions with capped DPR
    setupDimensions()

    // Create stars
    createAllStars()

    // Create meteor pool
    createMeteorPool()

    return true
  }

  /**
   * Set up canvas dimensions with DPR capping
   */
  function setupDimensions(): void {
    if (!canvasRef.value || !config) return

    const canvas = canvasRef.value
    const rect = canvas.getBoundingClientRect()

    // Cap DPR
    dpr = Math.min(window.devicePixelRatio || 1, config.dprCap)

    // Fall back to window dimensions if getBoundingClientRect returns 0
    // (can happen when canvas has no CSS size set, or before first paint)
    canvasWidth = rect.width > 0 ? rect.width : window.innerWidth
    canvasHeight = rect.height > 0 ? rect.height : window.innerHeight

    // Set canvas internal dimensions
    canvas.width = canvasWidth * dpr
    canvas.height = canvasHeight * dpr

    // Reset transform and scale context for DPR
    // Use setTransform to prevent accumulation on resize
    ctx?.setTransform(dpr, 0, 0, dpr, 0, 0)
  }

  /**
   * Create all star layers with density scaling based on viewport area.
   * Base counts in config are calibrated for a 375×812 mobile viewport;
   * larger viewports get proportionally more stars (capped at 4× for high tier,
   * 2× for low tier to stay lightweight).
   */
  function createAllStars(): void {
    if (!config) return

    const viewportArea = canvasWidth * canvasHeight
    // Low tier uses a lower cap to avoid performance issues on weak devices
    const maxMultiplier = config.fps <= 18 ? 2 : 4

    const farCount = getScaledCount(config.farStars.count, viewportArea, maxMultiplier)
    const midCount = getScaledCount(config.midStars.count, viewportArea, maxMultiplier)
    const nearCount = getScaledCount(config.nearStars.count, viewportArea, maxMultiplier)

    stars = [
      ...createStars({ ...config.farStars, count: farCount }, 'far', canvasWidth, canvasHeight),
      ...createStars({ ...config.midStars, count: midCount }, 'mid', canvasWidth, canvasHeight),
      ...createStars({ ...config.nearStars, count: nearCount }, 'near', canvasWidth, canvasHeight),
    ]
  }

  /**
   * Create meteor pool
   */
  function createMeteorPool(): void {
    if (!config?.meteor.enabled) {
      meteors = []
      return
    }

    meteors = []
    for (let i = 0; i < config.meteor.maxActive; i++) {
      meteors.push({
        x: 0,
        y: 0,
        vx: 0,
        vy: 0,
        length: 0,
        life: 0,
        maxLife: 0,
        active: false,
      })
    }
  }

  /**
   * Spawn a meteor
   */
  function spawnMeteor(): void {
    if (!config?.meteor.enabled) return

    const inactiveMeteor = meteors.find(m => !m.active)
    if (!inactiveMeteor) return

    const meteorConfig = config.meteor
    const speed = random(meteorConfig.minSpeed, meteorConfig.maxSpeed)
    const angle = random(Math.PI * 0.15, Math.PI * 0.35) // 27-63 degrees, moving down-right

    inactiveMeteor.x = random(-canvasWidth * 0.1, canvasWidth * 0.7)
    inactiveMeteor.y = random(-50, canvasHeight * 0.3)
    inactiveMeteor.vx = Math.cos(angle) * speed
    inactiveMeteor.vy = Math.sin(angle) * speed
    inactiveMeteor.length = random(meteorConfig.minLength, meteorConfig.maxLength)
    inactiveMeteor.life = 1
    inactiveMeteor.maxLife = 1
    inactiveMeteor.active = true
  }

  /**
   * Update stars
   */
  function updateStars(deltaTime: number): void {
    const dt = deltaTime / BASE_FRAME_TIME // Normalize to ~60fps frame time

    for (const star of stars) {
      // Move star
      star.x += star.speedX * dt
      star.y += star.speedY * dt

      // Wrap around edges
      if (star.x > canvasWidth + 10) star.x = -10
      if (star.x < -10) star.x = canvasWidth + 10
      if (star.y > canvasHeight + 10) star.y = -10
      if (star.y < -10) star.y = canvasHeight + 10

      // Twinkle
      if (star.twinkleAmplitude > 0) {
        star.twinklePhase += star.twinkleSpeed * dt
        star.alpha = star.baseAlpha + Math.sin(star.twinklePhase) * star.twinkleAmplitude
        star.alpha = Math.max(0.1, Math.min(1, star.alpha))
      }
    }
  }

  /**
   * Update meteors
   */
  function updateMeteors(deltaTime: number): void {
    if (!config?.meteor.enabled) return

    const dt = deltaTime / 16.67

    // Maybe spawn new meteor
    if (Math.random() < config.meteor.spawnChance * dt) {
      spawnMeteor()
    }

    // Update active meteors
    for (const meteor of meteors) {
      if (!meteor.active) continue

      meteor.x += meteor.vx * dt
      meteor.y += meteor.vy * dt
      meteor.life -= config.meteor.fadeRate * dt

      // Deactivate if off screen or faded
      if (
        meteor.life <= 0 ||
        meteor.x > canvasWidth + 100 ||
        meteor.y > canvasHeight + 100
      ) {
        meteor.active = false
      }
    }
  }

  /**
   * Draw all elements
   */
  function draw(): void {
    if (!ctx || !canvasRef.value) return

    // Clear canvas
    ctx.clearRect(0, 0, canvasWidth, canvasHeight)

    // Draw stars (sorted by layer for proper depth)
    for (const star of stars) {
      ctx.beginPath()
      ctx.arc(star.x, star.y, star.r, 0, Math.PI * 2)

      // Color based on layer: far=white, mid=light blue or faint purple accent, near=warm white
      let color: string
      if (star.layer === 'near') {
        color = STAR_COLORS.bright
      } else if (star.layer === 'mid' && Math.random() < 0.2) {
        color = STAR_COLORS.accent
      } else {
        color = STAR_COLORS.primary
      }
      ctx.fillStyle = color.replace('1)', `${star.alpha})`)
      ctx.fill()
    }

    // Draw meteors
    for (const meteor of meteors) {
      if (!meteor.active) continue

      // Guard against zero velocity (prevents NaN)
      const speed = Math.sqrt(meteor.vx ** 2 + meteor.vy ** 2)
      if (speed === 0) continue

      const tailX = meteor.x - meteor.vx * meteor.length / speed
      const tailY = meteor.y - meteor.vy * meteor.length / speed

      ctx.beginPath()
      ctx.moveTo(tailX, tailY)
      ctx.lineTo(meteor.x, meteor.y)

      // Gradient from transparent to bright
      const gradient = ctx.createLinearGradient(tailX, tailY, meteor.x, meteor.y)
      gradient.addColorStop(0, 'rgba(255, 255, 255, 0)')
      gradient.addColorStop(1, `rgba(255, 255, 255, ${meteor.life * 0.6})`)

      ctx.strokeStyle = gradient
      ctx.lineWidth = 1.5
      ctx.stroke()
    }
  }

  /**
   * Main animation loop
   */
  function animate(timestamp: number): void {
    if (state.isPaused || !config) {
      state.rafId = requestAnimationFrame(animate)
      return
    }

    // FPS throttling
    const elapsed = timestamp - state.lastTime
    const targetInterval = 1000 / config.fps

    if (elapsed >= targetInterval) {
      state.lastTime = timestamp - (elapsed % targetInterval)

      updateStars(elapsed)
      updateMeteors(elapsed)
      draw()
    }

    state.rafId = requestAnimationFrame(animate)
  }

  /**
   * Start animation
   */
  function start(): void {
    if (isRunning.value) return

    // Set running flag early to prevent race conditions
    isRunning.value = true

    if (!init()) {
      console.warn('useStarField: Initialization failed')
      isRunning.value = false
      return
    }

    // Set up resize handler with debounce
    handleResize = debounce(() => {
      setupDimensions()
      // Recreate stars for new dimensions
      createAllStars()
    }, 150)
    window.addEventListener('resize', handleResize)

    // Set up visibility handler (guard against redundant assignments)
    handleVisibilityChange = () => {
      if (state.isPaused !== document.hidden) {
        state.isPaused = document.hidden
      }
    }
    document.addEventListener('visibilitychange', handleVisibilityChange)

    // Start animation loop
    state.lastTime = performance.now()
    state.isPaused = false
    state.rafId = requestAnimationFrame(animate)
  }

  /**
   * Stop animation and cleanup
   */
  function stop(): void {
    if (state.rafId !== null) {
      cancelAnimationFrame(state.rafId)
      state.rafId = null
    }

    if (handleResize) {
      window.removeEventListener('resize', handleResize)
      handleResize = null
    }

    if (handleVisibilityChange) {
      document.removeEventListener('visibilitychange', handleVisibilityChange)
      handleVisibilityChange = null
    }

    // Reset state
    state = {
      rafId: null,
      lastTime: 0,
      isPaused: false,
    }

    stars = []
    meteors = []
    ctx = null
    config = null

    isRunning.value = false
  }

  // Auto-lifecycle management
  onMounted(() => {
    start()
  })

  onUnmounted(() => {
    stop()
  })

  return {
    start,
    stop,
    isRunning,
  }
}