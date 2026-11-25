import { describe, it, expect } from 'vitest'
import { resolveChallengeBackend, isPhysics3D, CHALLENGE_CLASSIFICATION, loadChallengeComponent } from './router'

describe('challenge router', () => {
  it('classifies balance as physics-3d', () => {
    expect(resolveChallengeBackend('balance')).toBe('physics-3d')
  })

  it('classifies distribute as physics-3d', () => {
    expect(resolveChallengeBackend('distribute')).toBe('physics-3d')
  })

  it('classifies puzzle as physics-3d', () => {
    expect(resolveChallengeBackend('puzzle')).toBe('physics-3d')
  })

  it('classifies classify as enhanced-2d', () => {
    expect(resolveChallengeBackend('classify')).toBe('enhanced-2d')
  })

  it('classifies order as enhanced-2d', () => {
    expect(resolveChallengeBackend('order')).toBe('enhanced-2d')
  })

  it('classifies connect as enhanced-2d', () => {
    expect(resolveChallengeBackend('connect')).toBe('enhanced-2d')
  })

  it('classifies estimate as native-2d', () => {
    expect(resolveChallengeBackend('estimate')).toBe('native-2d')
  })

  it('classifies pattern as native-2d', () => {
    expect(resolveChallengeBackend('pattern')).toBe('native-2d')
  })

  it('classifies spot-the-mistake as native-2d', () => {
    expect(resolveChallengeBackend('spot-the-mistake')).toBe('native-2d')
  })

  it('classifies draw-grid as native-2d', () => {
    expect(resolveChallengeBackend('draw-grid')).toBe('native-2d')
  })

  it('all 10 challenge types are classified', () => {
    const types = Object.keys(CHALLENGE_CLASSIFICATION)
    expect(types).toHaveLength(10)
  })

  it('isPhysics3D returns true only for physics types', () => {
    expect(isPhysics3D('balance')).toBe(true)
    expect(isPhysics3D('classify')).toBe(false)
    expect(isPhysics3D('estimate')).toBe(false)
  })

  it('loadChallengeComponent returns 2D component for native-2d types', async () => {
    const component = await loadChallengeComponent('estimate')
    expect(component).not.toBeNull()
  })

  it('loadChallengeComponent returns 2D component for enhanced-2d types', async () => {
    const component = await loadChallengeComponent('classify')
    expect(component).not.toBeNull()
  })
})
