/**
 * 3D Castle-specific types.
 * Extends the 2D castle API types with 3D scene properties.
 */
import type { CastleFloor, CastleTower, CastleWindow } from '@/api/learning'

/** 3D tower representation with scene position. */
export interface Castle3DTower {
  /** Source data from API. */
  source: CastleTower
  /** Tower center position in 3D space. */
  position: { x: number; y: number; z: number }
  /** Tower height (floors * floorHeight). */
  height: number
  /** Subject theme color (from CONTINENT_THEMES). */
  color: string
}

/** 3D floor representation. */
export interface Castle3DFloor {
  /** Source data from API. */
  source: CastleFloor
  /** Floor index (0 = bottom). */
  index: number
  /** Y position in tower. */
  y: number
  /** Brick count to render (capped at 8). */
  brickCount: number
}

/** 3D brick representation. */
export interface Castle3DBrick {
  /** Topic id if this brick represents a specific topic. */
  topicId?: string
  /** Brick position in floor grid. */
  position: { x: number; y: number; z: number }
  /** Whether this brick is newly mastered (triggers drop animation). */
  isNew: boolean
}

/** 3D window representation. */
export interface Castle3DWindow {
  /** Source data from API. */
  source: CastleWindow
  /** Window position on tower exterior. */
  position: { x: number; y: number; z: number }
  /** Tower subject this window belongs to. */
  subject: string
}

/** Full 3D castle scene data. */
export interface Castle3DScene {
  /** Towers with 3D positions. */
  towers: Castle3DTower[]
  /** Windows across all towers. */
  windows: Castle3DWindow[]
  /** Streak days for decoration. */
  streakDays: number
}

/** Camera transition target. */
export interface CameraTarget {
  /** Camera position. */
  position: { x: number; y: number; z: number }
  /** Camera look-at target. */
  target: { x: number; y: number; z: number }
}

/** Scene layer. */
export type CastleLayer = 'panorama' | 'tower'
