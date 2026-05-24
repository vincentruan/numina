import { describe, it, expect } from 'vitest'
import { quadraticBezier, bezierPath, bezierControl } from './bezier'

describe('quadraticBezier', () => {
  const p0 = { x: 0, y: 100 }
  const p2 = { x: 100, y: 100 }

  it('returns start point at t=0', () => {
    const ctrl = { x: 50, y: 0 }
    expect(quadraticBezier(p0, ctrl, p2, 0)).toEqual(p0)
  })

  it('returns end point at t=1', () => {
    const ctrl = { x: 50, y: 0 }
    expect(quadraticBezier(p0, ctrl, p2, 1)).toEqual(p2)
  })

  it('returns midpoint of straight-line interpolation when control is on the line', () => {
    const ctrlOnLine = { x: 50, y: 100 }
    const mid = quadraticBezier(p0, ctrlOnLine, p2, 0.5)
    expect(mid.x).toBeCloseTo(50)
    expect(mid.y).toBeCloseTo(100)
  })

  it('lifts y above start/end midpoint when control is elevated', () => {
    const ctrlAbove = { x: 50, y: 0 }
    const mid = quadraticBezier(p0, ctrlAbove, p2, 0.5)
    expect(mid.y).toBeLessThan(100)
  })
})

describe('bezierPath', () => {
  it('produces SVG quadratic path string with M and Q tokens', () => {
    const path = bezierPath({ x: 0, y: 0 }, { x: 100, y: 50 }, 80)
    expect(path).toMatch(/^M /)
    expect(path).toContain(' Q ')
  })

  it('places control point at midpoint x and lifted y above min(start.y, end.y)', () => {
    const path = bezierPath({ x: 0, y: 100 }, { x: 200, y: 200 }, 60)
    // midpoint x = 100, lifted y = 100 - 60 = 40
    expect(path).toBe('M 0 100 Q 100 40 200 200')
  })
})

describe('bezierControl', () => {
  it('returns midpoint x and y lifted by controlOffset above min(start.y, end.y)', () => {
    expect(bezierControl({ x: 0, y: 80 }, { x: 200, y: 120 }, 50)).toEqual({ x: 100, y: 30 })
  })
})
