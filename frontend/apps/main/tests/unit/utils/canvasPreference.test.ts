import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest'

// Mock localStorage BEFORE importing the module
const localStorageMock = (() => {
  let store: Record<string, string> = {}
  return {
    getItem: vi.fn((key: string) => store[key] || null),
    setItem: vi.fn((key: string, value: string) => {
      store[key] = value
    }),
    removeItem: vi.fn((key: string) => {
      delete store[key]
    }),
    clear: vi.fn(() => {
      store = {}
    }),
  }
})()

Object.defineProperty(global, 'localStorage', {
  value: localStorageMock,
  configurable: true,
})

// Import AFTER mock is set up
import { useCanvasPreference } from '@/utils/canvasPreference'

describe('useCanvasPreference', () => {
  beforeEach(() => {
    localStorageMock.clear()
    vi.clearAllMocks()
  })

  afterEach(() => {
    // Reset state to default for next test
    const { setCollapsed } = useCanvasPreference()
    setCollapsed(false)
  })

  describe('toggleCollapse', () => {
    it('toggles from false to true', () => {
      const { isCollapsed, toggleCollapse } = useCanvasPreference()
      expect(isCollapsed.value).toBe(false)
      toggleCollapse()
      expect(isCollapsed.value).toBe(true)
    })

    it('toggles from true to false', () => {
      const { isCollapsed, toggleCollapse } = useCanvasPreference()
      toggleCollapse() // set to true
      toggleCollapse() // set back to false
      expect(isCollapsed.value).toBe(false)
    })

    it('can toggle multiple times', () => {
      const { isCollapsed, toggleCollapse } = useCanvasPreference()
      toggleCollapse()
      expect(isCollapsed.value).toBe(true)
      toggleCollapse()
      expect(isCollapsed.value).toBe(false)
      toggleCollapse()
      expect(isCollapsed.value).toBe(true)
    })
  })

  describe('setCollapsed', () => {
    it('sets collapsed to true', () => {
      const { isCollapsed, setCollapsed } = useCanvasPreference()
      setCollapsed(true)
      expect(isCollapsed.value).toBe(true)
    })

    it('sets collapsed to false', () => {
      const { isCollapsed, setCollapsed } = useCanvasPreference()
      setCollapsed(true) // set to true first
      setCollapsed(false) // then to false
      expect(isCollapsed.value).toBe(false)
    })

    it('setting same value does not change state', () => {
      const { isCollapsed, setCollapsed } = useCanvasPreference()
      setCollapsed(false)
      expect(isCollapsed.value).toBe(false)
      setCollapsed(false)
      expect(isCollapsed.value).toBe(false)
    })
  })

  describe('clearPreference', () => {
    it('removes localStorage key and resets to false', () => {
      const { isCollapsed, setCollapsed, clearPreference } = useCanvasPreference()
      setCollapsed(true)
      expect(isCollapsed.value).toBe(true)
      clearPreference()
      expect(isCollapsed.value).toBe(false)
      expect(localStorageMock.removeItem).toHaveBeenCalledWith(
        'canvas:collapse-preference',
      )
    })

    it('clearing when already false still removes key', () => {
      const { isCollapsed, clearPreference } = useCanvasPreference()
      expect(isCollapsed.value).toBe(false)
      clearPreference()
      expect(isCollapsed.value).toBe(false)
      expect(localStorageMock.removeItem).toHaveBeenCalledWith(
        'canvas:collapse-preference',
      )
    })
  })

  describe('singleton behavior', () => {
    it('shares state across multiple calls', () => {
      const instance1 = useCanvasPreference()
      const instance2 = useCanvasPreference()
      instance1.toggleCollapse()
      expect(instance2.isCollapsed.value).toBe(true)
    })

    it('toggle from one instance affects all instances', () => {
      const instance1 = useCanvasPreference()
      const instance2 = useCanvasPreference()
      instance1.toggleCollapse()
      expect(instance1.isCollapsed.value).toBe(true)
      expect(instance2.isCollapsed.value).toBe(true)
      instance2.toggleCollapse()
      expect(instance1.isCollapsed.value).toBe(false)
      expect(instance2.isCollapsed.value).toBe(false)
    })

    it('setCollapsed from one instance affects all instances', () => {
      const instance1 = useCanvasPreference()
      const instance2 = useCanvasPreference()
      instance1.setCollapsed(true)
      expect(instance2.isCollapsed.value).toBe(true)
    })
  })

  describe('return value consistency', () => {
    it('returns same ref across multiple calls', () => {
      const instance1 = useCanvasPreference()
      const instance2 = useCanvasPreference()
      expect(instance1.isCollapsed).toBe(instance2.isCollapsed)
    })
  })
})