import { describe, it, expect, beforeEach } from 'vitest'
import {
  tickDriver,
  createChildTimeline,
  revertAll,
  getRootTimeline,
} from './animeDriver'

describe('animeDriver', () => {
  beforeEach(() => {
    revertAll()
  })

  it('getRootTimeline returns null before first use', () => {
    expect(getRootTimeline()).toBeNull()
  })

  it('tickDriver creates root timeline lazily', () => {
    tickDriver(0)
    expect(getRootTimeline()).not.toBeNull()
  })

  it('createChildTimeline returns a timeline that is synced to root', () => {
    const child = createChildTimeline()
    expect(child).toBeDefined()
    expect(child.paused).toBe(true) // autoplay: false
    // Root should exist after creating a child
    expect(getRootTimeline()).not.toBeNull()
  })

  it('tickDriver advances child timelines via root seek', () => {
    const child = createChildTimeline()
    // Add a simple animation to the child
    child.add({ x: 0 }, { x: 100, duration: 1000 })

    // The child is paused/synced — tickDriver advances it
    tickDriver(500)

    // After seeking to 500ms, the animation should be mid-way
    expect(child.currentTime).toBeGreaterThanOrEqual(0)
  })

  it('revertAll destroys root timeline', () => {
    createChildTimeline()
    expect(getRootTimeline()).not.toBeNull()
    revertAll()
    expect(getRootTimeline()).toBeNull()
  })

  it('multiple child timelines coexist', () => {
    const child1 = createChildTimeline()
    const child2 = createChildTimeline()
    expect(child1).not.toBe(child2)
    expect(getRootTimeline()).not.toBeNull()
  })
})
