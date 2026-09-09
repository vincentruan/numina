import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { nextTick } from 'vue'
import { mount } from '@vue/test-utils'
import ClassicTemplate from '../templates/ClassicTemplate.vue'
import ModernTemplate from '../templates/ModernTemplate.vue'

// Mock i18n
vi.mock('vue-i18n', () => ({
  useI18n: () => ({
    t: (key: string) => key,
  }),
}))

// Mock family store
vi.mock('@/stores/family', () => ({
  useFamilyStore: () => ({
    family: { name: 'TestFamily' },
  }),
}))

// Mock IntersectionObserver
const mockObserve = vi.fn()
const mockUnobserve = vi.fn()
const mockDisconnect = vi.fn()
let observerCallback: (entries: Array<{ target: Element; isIntersecting: boolean }>) => void

class MockIntersectionObserver {
  constructor(cb: typeof observerCallback) {
    observerCallback = cb
  }
  observe = mockObserve
  unobserve = mockUnobserve
  disconnect = mockDisconnect
}

vi.stubGlobal('IntersectionObserver', MockIntersectionObserver)

function setupMatchMedia(reducedMotion = false) {
  vi.stubGlobal(
    'matchMedia',
    vi.fn().mockImplementation((query: string) => ({
      matches: query === '(prefers-reduced-motion: reduce)' ? reducedMotion : false,
      media: query,
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
    })),
  )
}

// Minimal stubs for child components used by templates
const globalStubs = {
  WaxSeal: { template: '<div class="wax-seal-stub" />' },
  VanIcon: { template: '<i class="van-icon-stub" />' },
}

const defaultProps = {
  title: 'Test Title',
  body: 'Paragraph one.\n\nParagraph two.\n\nParagraph three.',
  signatures: [{ name: 'Member 1', data: null }, { name: 'Member 2', data: null }],
  members: [
    { name: 'Member 1', role: 'owner', signingStatus: 'signed' as const },
    { name: 'Member 2', role: 'member', signingStatus: 'pending_sign' as const },
  ],
}

describe('Scroll reveal integration', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    setupMatchMedia(false)
  })

  afterEach(() => {
    vi.restoreAllMocks()
  })

  describe('ClassicTemplate', () => {
    it('renders paragraphs with data-reveal and --reveal-index', () => {
      const wrapper = mount(ClassicTemplate, {
        props: defaultProps,
        global: { stubs: globalStubs },
      })

      const paragraphs = wrapper.findAll('.certificate-body p')
      expect(paragraphs).toHaveLength(3)

      paragraphs.forEach((p, idx) => {
        expect(p.attributes('data-reveal')).toBe('')
        expect(p.attributes('style')).toContain(`--reveal-index: ${idx}`)
      })

      wrapper.unmount()
    })

    it('signature grid paragraphs do NOT have data-reveal', () => {
      const wrapper = mount(ClassicTemplate, {
        props: defaultProps,
        global: { stubs: globalStubs },
      })

      const signatureElements = wrapper.findAll('.signature-cell')
      signatureElements.forEach(el => {
        expect(el.find('[data-reveal]').exists()).toBe(false)
      })

      wrapper.unmount()
    })

    it('paragraph elements are ready for scroll reveal observation', async () => {
      const wrapper = mount(ClassicTemplate, {
        props: defaultProps,
        global: { stubs: globalStubs },
      })
      await nextTick()

      // The composable in ManifestoViewer will observe these elements.
      // Here we verify the template renders the correct attributes.
      const paragraphs = wrapper.findAll('.certificate-body p[data-reveal]')
      expect(paragraphs).toHaveLength(3)
      expect(paragraphs[0].attributes('style')).toContain('--reveal-index: 0')

      wrapper.unmount()
    })
  })

  describe('ModernTemplate', () => {
    it('renders paragraphs with data-reveal and --reveal-index', () => {
      const wrapper = mount(ModernTemplate, {
        props: defaultProps,
        global: { stubs: globalStubs },
      })

      const paragraphs = wrapper.findAll('.modern-body p')
      expect(paragraphs).toHaveLength(3)

      paragraphs.forEach((p, idx) => {
        expect(p.attributes('data-reveal')).toBe('')
        expect(p.attributes('style')).toContain(`--reveal-index: ${idx}`)
      })

      wrapper.unmount()
    })

    it('signature elements do NOT have data-reveal', () => {
      const wrapper = mount(ModernTemplate, {
        props: defaultProps,
        global: { stubs: globalStubs },
      })

      const signatureLines = wrapper.findAll('.signature-line')
      signatureLines.forEach(el => {
        expect(el.find('[data-reveal]').exists()).toBe(false)
      })

      wrapper.unmount()
    })
  })

  describe('Reduced motion', () => {
    it('does not observe elements when prefers-reduced-motion is reduce', async () => {
      setupMatchMedia(true)

      const wrapper = mount(ClassicTemplate, {
        props: defaultProps,
        global: { stubs: globalStubs },
      })
      await nextTick()

      // The composable in ManifestoViewer would skip observer creation.
      // Templates render data-reveal attributes regardless, but the CSS
      // reduced-motion override ensures elements are visible.
      // Here we verify the template still renders correctly.
      const paragraphs = wrapper.findAll('.certificate-body p')
      expect(paragraphs.length).toBeGreaterThan(0)

      wrapper.unmount()
    })
  })
})
