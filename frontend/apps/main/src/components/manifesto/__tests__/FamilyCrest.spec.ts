import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { mount } from '@vue/test-utils'
import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import FamilyCrest from '../FamilyCrest.vue'

// Mock i18n — return interpolated template for crestAria
vi.mock('vue-i18n', () => ({
  useI18n: () => ({
    t: (key: string, params?: Record<string, string | number>) => {
      if (key === 'manifesto.crestAria' && params) {
        return `Family crest: ${params.name}, ${params.signed} of ${params.total} members have signed`
      }
      if (params) {
        return Object.entries(params).reduce(
          (s, [k, v]) => s.replace(`{${k}}`, String(v)),
          key,
        )
      }
      return key
    },
  }),
}))

/**
 * happy-dom ships its own window.matchMedia that vi.stubGlobal cannot
 * override. Use Object.defineProperty to replace it reliably.
 */
function setupMatchMedia(reducedMotion = false) {
  const mock = vi.fn().mockImplementation((query: string) => ({
    matches: query === '(prefers-reduced-motion: reduce)' ? reducedMotion : false,
    media: query,
    addEventListener: vi.fn(),
    removeEventListener: vi.fn(),
  }))
  Object.defineProperty(window, 'matchMedia', {
    value: mock,
    writable: true,
    configurable: true,
  })
}

/** Read the SFC source so we can assert scoped CSS rules that happy-dom
 *  does not inject into the DOM. */
function readSfcSource(): string {
  const filePath = resolve(__dirname, '../FamilyCrest.vue')
  return readFileSync(filePath, 'utf-8')
}

function createMember(
  name: string,
  status: 'signed' | 'confirmed' | 'pending_sign' | 'pending_confirm' | 'rejected' | 'expired',
) {
  return { name, role: 'member', signingStatus: status }
}

describe('FamilyCrest', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    setupMatchMedia(false)
  })

  afterEach(() => {
    vi.restoreAllMocks()
  })

  // ── AE1: Basic SVG rendering ──────────────────────────────────────────────

  it('renders SVG with viewBox, 3 member groups, ring circle, and family char "D"', () => {
    const members = [
      createMember('Alice', 'signed'),
      createMember('Bob', 'pending_sign'),
      createMember('Carol', 'confirmed'),
    ]
    const wrapper = mount(FamilyCrest, {
      props: { members, familyName: 'Demo' },
    })

    // Root element renders
    const root = wrapper.find('.family-crest')
    expect(root.exists()).toBe(true)

    // SVG with viewBox
    const svg = root.find('svg')
    expect(svg.exists()).toBe(true)
    // SVG attributes may be case-sensitive in happy-dom; use getAttribute
    expect(svg.element.getAttribute('viewBox')).toBe('0 0 100 100')

    // Ring circle
    const ring = svg.find('circle')
    expect(ring.exists()).toBe(true)

    // 3 member groups
    const groups = svg.findAll('.family-crest__member')
    expect(groups).toHaveLength(3)

    // Family character displayed
    const center = root.find('.family-crest__center')
    expect(center.text()).toBe('D')

    wrapper.unmount()
  })

  // ── AE2: Signing status → active/muted CSS classes ────────────────────────

  it('assigns active class for signed and confirmed, muted for pending_sign and rejected', () => {
    const members = [
      createMember('A', 'signed'),
      createMember('B', 'pending_sign'),
      createMember('C', 'confirmed'),
      createMember('D', 'rejected'),
    ]
    const wrapper = mount(FamilyCrest, {
      props: { members, familyName: 'Test' },
    })

    const groups = wrapper.findAll('.family-crest__member')
    expect(groups).toHaveLength(4)

    expect(groups[0].classes()).toContain('family-crest__member--active')
    expect(groups[1].classes()).toContain('family-crest__member--muted')
    expect(groups[2].classes()).toContain('family-crest__member--active')
    expect(groups[3].classes()).toContain('family-crest__member--muted')

    wrapper.unmount()
  })

  // ── AE3: prefers-reduced-motion ───────────────────────────────────────────

  it('queries prefers-reduced-motion and defines CSS transition:none override', async () => {
    // Strategy: happy-dom's window.matchMedia cannot be reliably overridden
    // to return matches:true, so we verify the two halves separately:
    //   1) JS behavior: onMounted queries matchMedia with the correct query
    //   2) CSS behavior: scoped style defines transition:none for reduced-motion

    // 1) JS: spy on existing matchMedia to confirm the query is made
    const origMatchMedia = window.matchMedia.bind(window)
    const spy = vi.fn((q: string) => origMatchMedia(q))
    Object.defineProperty(window, 'matchMedia', { value: spy, writable: true, configurable: true })

    const members = [createMember('Alice', 'signed')]
    const wrapper = mount(FamilyCrest, {
      props: { members, familyName: 'Demo' },
    })

    expect(spy).toHaveBeenCalledWith('(prefers-reduced-motion: reduce)')

    wrapper.unmount()

    // 2) CSS: scoped <style> block declares transition:none under reduced-motion
    const sfc = readSfcSource()
    const styleBlock = sfc.match(/<style[^>]*>([\s\S]*?)<\/style>/)?.[1] ?? ''
    expect(styleBlock).toContain('prefers-reduced-motion')
    expect(styleBlock).toContain('transition: none')
  })

  // ── AE5: Single member layout ─────────────────────────────────────────────

  it('renders correctly with a single member without layout breakage', () => {
    const members = [createMember('Solo', 'signed')]
    const wrapper = mount(FamilyCrest, {
      props: { members, familyName: 'Solo' },
    })

    const groups = wrapper.findAll('.family-crest__member')
    expect(groups).toHaveLength(1)

    // Verify the single member has a valid transform position (not NaN/undefined)
    const transform = groups[0].attributes('transform')
    expect(transform).toBeTruthy()
    expect(transform).toContain('translate(')

    wrapper.unmount()
  })

  // ── KTD7: Empty family guard ──────────────────────────────────────────────

  it('renders nothing when members is empty and familyName is empty', () => {
    const wrapper = mount(FamilyCrest, {
      props: { members: [], familyName: '' },
    })

    // v-if guard prevents rendering — root element is a comment node
    expect(wrapper.find('.family-crest').exists()).toBe(false)
    expect(wrapper.html()).toContain('<!--')

    wrapper.unmount()
  })

  // ── sealChar fallback chain ───────────────────────────────────────────────

  describe('sealChar fallback chain', () => {
    it('displays first char of familyName ("D" for "Demo")', () => {
      const wrapper = mount(FamilyCrest, {
        props: {
          members: [createMember('Alice', 'signed')],
          familyName: 'Demo',
        },
      })

      expect(wrapper.find('.family-crest__center').text()).toBe('D')
      wrapper.unmount()
    })

    it('falls back to first member name when familyName is empty ("A" for "Alice")', () => {
      const wrapper = mount(FamilyCrest, {
        props: {
          members: [createMember('Alice', 'signed')],
          familyName: '',
        },
      })

      // familyName empty → falls to member name
      expect(wrapper.find('.family-crest__center').text()).toBe('A')
      wrapper.unmount()
    })

    it('falls back to "家" when both familyName and first member name are empty', () => {
      const wrapper = mount(FamilyCrest, {
        props: {
          // Member with empty name — familyName also empty but members.length > 0 passes v-if
          members: [{ name: '', role: 'member', signingStatus: 'signed' }],
          familyName: '',
        },
      })

      // familyName empty → member name empty → fallback "家"
      expect(wrapper.find('.family-crest__center').text()).toBe('家')
      wrapper.unmount()
    })
  })

  // ── ARIA accessibility ────────────────────────────────────────────────────

  it('has role="img" and aria-label containing family name and signing count', () => {
    const members = [
      createMember('Alice', 'signed'),
      createMember('Bob', 'pending_sign'),
      createMember('Carol', 'confirmed'),
    ]
    const wrapper = mount(FamilyCrest, {
      props: { members, familyName: 'Demo' },
    })

    const root = wrapper.find('.family-crest')
    expect(root.attributes('role')).toBe('img')

    const ariaLabel = root.attributes('aria-label')
    expect(ariaLabel).toBeTruthy()
    // Should contain the seal character and signing count
    expect(ariaLabel).toContain('D')
    expect(ariaLabel).toContain('2') // 2 signed (Alice + Carol)
    expect(ariaLabel).toContain('3') // 3 total

    wrapper.unmount()
  })

  // ── No data-reveal (scroll reveal conflict avoidance) ─────────────────────

  it('does NOT have data-reveal attribute on root element', () => {
    const members = [createMember('Alice', 'signed')]
    const wrapper = mount(FamilyCrest, {
      props: { members, familyName: 'Demo' },
    })

    const root = wrapper.find('.family-crest')
    expect(root.attributes('data-reveal')).toBeUndefined()

    wrapper.unmount()
  })

  // ── Prop interface (R10) ──────────────────────────────────────────────────

  it('accepts members and familyName props without error', () => {
    expect(() => {
      const wrapper = mount(FamilyCrest, {
        props: {
          members: [
            { name: 'A', role: 'owner', signingStatus: 'signed' },
            { name: 'B', role: 'member', signingStatus: 'pending_sign' },
          ],
          familyName: 'Wang',
        },
      })
      wrapper.unmount()
    }).not.toThrow()
  })

  // ── CSS transition on member elements ─────────────────────────────────────

  it('.family-crest__member scoped CSS defines transition for opacity and transform', () => {
    // happy-dom does not inject scoped CSS into the DOM,
    // so we verify the <style> block in the SFC source directly.
    const sfc = readSfcSource()
    expect(sfc).toContain('.family-crest__member')
    expect(sfc).toContain('transition')
    expect(sfc).toContain('opacity')
    expect(sfc).toContain('transform')
  })
})
