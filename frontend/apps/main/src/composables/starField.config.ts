/**
 * Star field animation configuration
 * Centralizes all visual and performance parameters for the cosmic background
 */

export type DeviceTier = 'low' | 'medium' | 'high'

export interface StarLayerConfig {
  count: number
  minRadius: number
  maxRadius: number
  minAlpha: number
  maxAlpha: number
  minSpeedX: number
  maxSpeedX: number
  minSpeedY: number
  maxSpeedY: number
  twinkleChance: number // 0-1, probability of twinkle
}

export interface MeteorConfig {
  enabled: boolean
  maxActive: number
  spawnChance: number // per frame, 0-1
  minSpeed: number
  maxSpeed: number
  minLength: number
  maxLength: number
  fadeRate: number
}

export interface TierConfig {
  fps: number
  farStars: StarLayerConfig
  midStars: StarLayerConfig
  nearStars: StarLayerConfig
  meteor: MeteorConfig
  dprCap: number
}

// Low tier: minimal stars, no meteors, reduced twinkle
const LOW_TIER_CONFIG: TierConfig = {
  fps: 18,
  dprCap: 1.5,
  farStars: {
    count: 25,
    minRadius: 0.5,
    maxRadius: 1,
    minAlpha: 0.3,
    maxAlpha: 0.5,
    minSpeedX: 0.02,
    maxSpeedX: 0.05,
    minSpeedY: 0.01,
    maxSpeedY: 0.02,
    twinkleChance: 0,
  },
  midStars: {
    count: 10,
    minRadius: 1,
    maxRadius: 1.5,
    minAlpha: 0.4,
    maxAlpha: 0.6,
    minSpeedX: 0.03,
    maxSpeedX: 0.08,
    minSpeedY: 0.01,
    maxSpeedY: 0.03,
    twinkleChance: 0,
  },
  nearStars: {
    count: 3,
    minRadius: 1.5,
    maxRadius: 2,
    minAlpha: 0.5,
    maxAlpha: 0.8,
    minSpeedX: 0.05,
    maxSpeedX: 0.1,
    minSpeedY: 0.02,
    maxSpeedY: 0.04,
    twinkleChance: 0.2,
  },
  meteor: {
    enabled: false,
    maxActive: 0,
    spawnChance: 0,
    minSpeed: 0,
    maxSpeed: 0,
    minLength: 0,
    maxLength: 0,
    fadeRate: 0,
  },
}

// Medium tier: moderate stars, limited meteors
const MEDIUM_TIER_CONFIG: TierConfig = {
  fps: 24,
  dprCap: 2,
  farStars: {
    count: 60,
    minRadius: 0.5,
    maxRadius: 1,
    minAlpha: 0.3,
    maxAlpha: 0.5,
    minSpeedX: 0.02,
    maxSpeedX: 0.06,
    minSpeedY: 0.01,
    maxSpeedY: 0.02,
    twinkleChance: 0.1,
  },
  midStars: {
    count: 25,
    minRadius: 1,
    maxRadius: 1.5,
    minAlpha: 0.4,
    maxAlpha: 0.7,
    minSpeedX: 0.03,
    maxSpeedX: 0.1,
    minSpeedY: 0.01,
    maxSpeedY: 0.03,
    twinkleChance: 0.3,
  },
  nearStars: {
    count: 6,
    minRadius: 1.5,
    maxRadius: 2.5,
    minAlpha: 0.6,
    maxAlpha: 0.9,
    minSpeedX: 0.05,
    maxSpeedX: 0.12,
    minSpeedY: 0.02,
    maxSpeedY: 0.05,
    twinkleChance: 0.4,
  },
  meteor: {
    enabled: true,
    maxActive: 1,
    spawnChance: 0.001,
    minSpeed: 8,
    maxSpeed: 12,
    minLength: 30,
    maxLength: 50,
    fadeRate: 0.02,
  },
}

// High tier: full stars, meteors enabled
const HIGH_TIER_CONFIG: TierConfig = {
  fps: 30,
  dprCap: 2,
  farStars: {
    count: 150,
    minRadius: 0.5,
    maxRadius: 1,
    minAlpha: 0.3,
    maxAlpha: 0.5,
    minSpeedX: 0.02,
    maxSpeedX: 0.06,
    minSpeedY: 0.01,
    maxSpeedY: 0.02,
    twinkleChance: 0.15,
  },
  midStars: {
    count: 60,
    minRadius: 1,
    maxRadius: 1.5,
    minAlpha: 0.4,
    maxAlpha: 0.7,
    minSpeedX: 0.03,
    maxSpeedX: 0.1,
    minSpeedY: 0.01,
    maxSpeedY: 0.03,
    twinkleChance: 0.35,
  },
  nearStars: {
    count: 15,
    minRadius: 1.5,
    maxRadius: 2.5,
    minAlpha: 0.6,
    maxAlpha: 0.9,
    minSpeedX: 0.05,
    maxSpeedX: 0.12,
    minSpeedY: 0.02,
    maxSpeedY: 0.05,
    twinkleChance: 0.5,
  },
  meteor: {
    enabled: true,
    maxActive: 3,
    spawnChance: 0.002,
    minSpeed: 10,
    maxSpeed: 15,
    minLength: 40,
    maxLength: 70,
    fadeRate: 0.025,
  },
}

const TIER_CONFIGS: Record<DeviceTier, TierConfig> = {
  low: LOW_TIER_CONFIG,
  medium: MEDIUM_TIER_CONFIG,
  high: HIGH_TIER_CONFIG,
}

/**
 * Get configuration for a specific device tier
 */
export function getTierConfig(tier: DeviceTier): TierConfig {
  return TIER_CONFIGS[tier]
}

/**
 * Get total star count for a tier
 */
export function getTotalStarCount(tier: DeviceTier): number {
  const config = TIER_CONFIGS[tier]
  return config.farStars.count + config.midStars.count + config.nearStars.count
}

/**
 * Base density area: standard mobile viewport (375×812)
 * Star counts in tier configs are calibrated for this area.
 */
const BASE_DENSITY_AREA = 375 * 812

/**
 * Scale a base star count proportionally to the actual viewport area.
 * Multiplier is clamped to [1, maxMultiplier] so counts never go below
 * the mobile baseline and never explode on very large monitors.
 */
export function getScaledCount(baseCount: number, viewportArea: number, maxMultiplier = 4): number {
  const multiplier = Math.min(Math.max(viewportArea / BASE_DENSITY_AREA, 1), maxMultiplier)
  return Math.round(baseCount * multiplier)
}

/**
 * Star colors - lavender palette to complement the #010120 midnight blue background
 */
export const STAR_COLORS = {
  // Primary star color — soft lavender-white
  primary: 'rgba(220, 218, 255, 1)',
  // Secondary — slightly cooler lavender
  secondary: 'rgba(189, 187, 255, 1)',
  // Bright stars — near-white with lavender tint
  bright: 'rgba(240, 239, 255, 1)',
  // Accent — deeper lavender for mid-layer variety
  accent: 'rgba(150, 140, 255, 1)',
}

/**
 * Background gradient colors (from existing LoginPage)
 */
export const GRADIENT_COLORS = {
  start: '#010120',
  end: '#000010',
  angle: 160,
}