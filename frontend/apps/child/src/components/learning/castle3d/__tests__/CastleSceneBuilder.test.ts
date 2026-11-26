/**
 * CastleSceneBuilder tests.
 */
import { describe, it, expect } from 'vitest'
import type { CastleIndex, CastleTower, CastleFloor } from '@/api/learning'
import {
  buildCastleScene,
  buildTower,
  buildFloor,
  buildBrick,
  calcBrickCount,
  getTowerCenter,
} from '../CastleSceneBuilder'

const mockFloor: CastleFloor = {
  domain: 'fractions',
  mastered_count: 4,
  learning_count: 2,
  review_due_count: 1,
  total_count: 10,
}

const mockTower: CastleTower = {
  subject: 'math',
  mastered_count: 4,
  learning_count: 2,
  review_due_count: 1,
  total_count: 10,
  floors: [mockFloor],
}

const mockCastle: CastleIndex = {
  towers: [mockTower],
  windows: [],
  streak_days: 5,
}

describe('CastleSceneBuilder', () => {
  describe('calcBrickCount', () => {
    it('returns 0 for empty floor', () => {
      const empty: CastleFloor = { ...mockFloor, total_count: 0, mastered_count: 0, learning_count: 0 }
      expect(calcBrickCount(empty)).toBe(0)
    })

    it('returns at least 1 for any progress', () => {
      const partial: CastleFloor = { ...mockFloor, mastered_count: 1, learning_count: 0, total_count: 100 }
      expect(calcBrickCount(partial)).toBeGreaterThanOrEqual(1)
    })

    it('caps at MAX_BRICKS_PER_FLOOR (8)', () => {
      const full: CastleFloor = { ...mockFloor, mastered_count: 100, learning_count: 0, total_count: 100 }
      expect(calcBrickCount(full)).toBeLessThanOrEqual(8)
    })

    it('scales with mastery ratio', () => {
      const half: CastleFloor = { ...mockFloor, mastered_count: 5, learning_count: 0, total_count: 10 }
      const full: CastleFloor = { ...mockFloor, mastered_count: 10, learning_count: 0, total_count: 10 }
      expect(calcBrickCount(half)).toBeLessThan(calcBrickCount(full))
    })
  })

  describe('buildBrick', () => {
    it('creates brick at specified position', () => {
      const brick = buildBrick(1, 2, 3)
      expect(brick.position.x).toBe(1)
      expect(brick.position.z).toBe(2)
      expect(brick.userData.type).toBe('brick')
    })
  })

  describe('buildFloor', () => {
    it('creates floor with correct brick count', () => {
      const floor = buildFloor(mockFloor, 0)
      const brickCount = calcBrickCount(mockFloor)
      expect(floor.children.length).toBe(brickCount)
    })

    it('stores floor data in userData', () => {
      const floor = buildFloor(mockFloor, 2)
      expect(floor.userData.floorIndex).toBe(2)
    })
  })

  describe('buildTower', () => {
    it('creates tower with floors', () => {
      const tower = buildTower(mockTower, 0)
      // Tower mesh + floor groups
      expect(tower.children.length).toBeGreaterThan(0)
    })

    it('positions tower at x offset', () => {
      const tower = buildTower(mockTower, 5)
      expect(tower.position.x).toBe(5)
    })

    it('never hands a CSS variable to the material', () => {
      // CONTINENT_THEMES colors are `var(--color-brand-*)`. three.js cannot
      // parse those and silently renders black, so the builder must resolve
      // them first. A raw `var(...)` in the material color means a black tower.
      const tower = buildTower(mockTower, 0)
      const body = tower.children.find(
        (c) => (c.userData as { type?: string }).type === 'tower',
      ) as { material?: { color?: { getHexString: () => string } } }

      expect(body).toBeTruthy()
      const hex = body.material?.color?.getHexString()
      expect(hex).toMatch(/^[0-9a-f]{6}$/)
      expect(hex).not.toBe('000000')
    })
  })

  describe('buildCastleScene', () => {
    it('creates one tower per subject', () => {
      const scene = buildCastleScene(mockCastle)
      expect(scene.towers.size).toBe(1)
      expect(scene.towers.has('math')).toBe(true)
    })

    it('root group contains all towers', () => {
      const scene = buildCastleScene(mockCastle)
      expect(scene.root.children.length).toBe(1)
    })

    it('multiple towers create multiple groups', () => {
      const multi: CastleIndex = {
        towers: [
          { ...mockTower, subject: 'math' },
          { ...mockTower, subject: 'science' },
        ],
        windows: [],
        streak_days: 0,
      }
      const scene = buildCastleScene(multi)
      expect(scene.towers.size).toBe(2)
    })
  })

  describe('getTowerCenter', () => {
    it('returns tower center position', () => {
      const tower = buildTower(mockTower, 3)
      const center = getTowerCenter(tower)
      expect(center.x).toBe(3)
    })
  })
})
