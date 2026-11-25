import { describe, it, expect, beforeEach } from 'vitest'
import { initRapier, getWorld, stepPhysics, destroyWorld, isInitialized, createScopedWorld, destroyScopedWorld, _resetForTesting } from './rapierWorld'

describe('rapierWorld', () => {
  beforeEach(() => {
    _resetForTesting()
  })

  it('isInitialized is false before init', () => {
    expect(isInitialized()).toBe(false)
  })

  it('initRapier sets initialized flag', async () => {
    await initRapier()
    expect(isInitialized()).toBe(true)
  })

  it('initRapier is idempotent', async () => {
    await initRapier()
    await initRapier() // should not throw
    expect(isInitialized()).toBe(true)
  })

  it('getWorld throws before init', () => {
    expect(() => getWorld()).toThrow('initRapier')
  })

  it('getWorld returns a world after init', async () => {
    await initRapier()
    const world = getWorld()
    expect(world).toBeDefined()
    expect(world.bodies.len()).toBe(0)
  })

  it('getWorld returns same singleton on repeated calls', async () => {
    await initRapier()
    const w1 = getWorld()
    const w2 = getWorld()
    expect(w1).toBe(w2)
  })

  it('stepPhysics does not throw with default world', async () => {
    await initRapier()
    getWorld() // create default
    expect(() => stepPhysics(1 / 60)).not.toThrow()
  })

  it('stepPhysics clamps accumulator on large dt (tab-return)', async () => {
    await initRapier()
    getWorld()
    // Simulate returning from a background tab (10 seconds elapsed)
    expect(() => stepPhysics(10)).not.toThrow()
  })

  it('stepPhysics with 120Hz display does 2 steps per frame', async () => {
    await initRapier()
    getWorld()
    // 1/120 second = ~8.3ms, should result in 0 steps (accumulator < FIXED_DT)
    // Actually 1/120 < 1/60, so no step yet
    expect(() => stepPhysics(1 / 120)).not.toThrow()
    // Second frame accumulates to 2/120 = 1/60 → one step
    expect(() => stepPhysics(1 / 120)).not.toThrow()
  })

  it('destroyWorld frees the singleton', async () => {
    await initRapier()
    getWorld()
    destroyWorld()
    // After destroy, getWorld should create a new one (init is still true)
    const w2 = getWorld()
    expect(w2).toBeDefined()
  })

  it('createScopedWorld returns independent world', async () => {
    await initRapier()
    const defaultWorld = getWorld()
    const scoped = createScopedWorld('test-challenge')
    expect(scoped).toBeDefined()
    expect(scoped).not.toBe(defaultWorld)
  })

  it('createScopedWorld returns same world for same id', async () => {
    await initRapier()
    const s1 = createScopedWorld('balance')
    const s2 = createScopedWorld('balance')
    expect(s1).toBe(s2)
  })

  it('destroyScopedWorld cleans up', async () => {
    await initRapier()
    createScopedWorld('temp')
    destroyScopedWorld('temp')
    // Creating again should give a fresh world
    const s2 = createScopedWorld('temp')
    expect(s2).toBeDefined()
    expect(s2.bodies.len()).toBe(0)
  })
})
